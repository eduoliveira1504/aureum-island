"""Letras via LRCLIB, com cache local.

- Uma busca por faixa (quando a faixa muda), nunca por posição.
- /api/get com artista, título, álbum e duração; se não achar, /api/search.
- Encontrada: cache sem expirar, limite de ~20 MB (sai a menos usada).
- Não encontrada: cache por 7 dias. Erro de rede não é guardado.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta
from importlib import metadata
from typing import Any, Protocol

from PySide6.QtCore import QObject, QUrl, QUrlQuery, Signal

from aureum_island.pages.lyrics_model import Lyrics, cache_key, parse_lrc
from aureum_island.services.storage.db import from_db, to_db, utc_now

log = logging.getLogger(__name__)

API = "https://lrclib.net/api"
HOMEPAGE = "https://github.com/eduoliveira1504/aureum-island"
MAX_CACHE_BYTES = 20 * 1024 * 1024
NOT_FOUND_TTL = timedelta(days=7)
DURATION_TOLERANCE_S = 3
TIMEOUT_MS = 10_000


def user_agent() -> str:
    try:
        version = metadata.version("aureum-island")
    except metadata.PackageNotFoundError:
        version = "0.0.0"
    return f"AureumIsland/{version} ({HOMEPAGE})"


# --- interpretação das respostas ---------------------------------------------


def from_record(record: Any) -> tuple[Lyrics, str]:
    """Registro do LRCLIB -> (Lyrics, conteúdo para o cache)."""
    if not isinstance(record, dict):
        return Lyrics("not_found"), ""
    if record.get("instrumental"):
        return Lyrics("instrumental"), ""
    synced = record.get("syncedLyrics") or ""
    if synced.strip():
        lines = parse_lrc(synced)
        if lines:
            return Lyrics.synced(lines), synced
    plain = record.get("plainLyrics") or ""
    if plain.strip():
        return Lyrics("plain", plain=plain.strip()), plain.strip()
    return Lyrics("not_found"), ""


def pick_best(results: Any, duration_s: float | None) -> dict | None:
    """Do /api/search: duração compatível; prefere letra sincronizada."""
    if not isinstance(results, list):
        return None
    candidates = [r for r in results if isinstance(r, dict)]
    if duration_s:
        candidates = [
            r
            for r in candidates
            if r.get("duration") is None
            or abs(float(r["duration"]) - duration_s) <= DURATION_TOLERANCE_S
        ]

    def rank(r: dict) -> int:
        if r.get("syncedLyrics"):
            return 0
        if r.get("plainLyrics"):
            return 1
        return 2 if r.get("instrumental") else 3

    candidates.sort(key=rank)
    return candidates[0] if candidates and rank(candidates[0]) < 3 else None


def to_lyrics(status: str, content: str) -> Lyrics:
    if status == "synced":
        return Lyrics.synced(parse_lrc(content))
    if status == "plain":
        return Lyrics("plain", plain=content)
    return Lyrics(status)


# --- cache -------------------------------------------------------------------


class LyricsCache:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        now: Callable[[], datetime] = utc_now,
        max_bytes: int = MAX_CACHE_BYTES,
    ) -> None:
        self._conn = conn
        self._now = now
        self.max_bytes = max_bytes

    def get(self, key: str) -> Lyrics | None:
        row = self._conn.execute(
            "SELECT status, content, fetched_at FROM lyrics_cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        now = self._now()
        if row["status"] == "not_found" and from_db(row["fetched_at"]) < now - NOT_FOUND_TTL:
            with self._conn:
                self._conn.execute("DELETE FROM lyrics_cache WHERE key = ?", (key,))
            return None
        with self._conn:
            self._conn.execute(
                "UPDATE lyrics_cache SET last_used_at = ? WHERE key = ?", (to_db(now), key)
            )
        return to_lyrics(row["status"], row["content"])

    def put(self, key: str, lyrics: Lyrics, content: str) -> None:
        stamp = to_db(self._now())
        size = len(content.encode("utf-8"))
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO lyrics_cache"
                " (key, status, content, size, fetched_at, last_used_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (key, lyrics.status, content, size, stamp, stamp),
            )
        self.evict()

    def total_bytes(self) -> int:
        return self._conn.execute("SELECT COALESCE(SUM(size), 0) FROM lyrics_cache").fetchone()[0]

    def evict(self) -> None:
        """Acima do limite, remove as letras menos usadas."""
        total = self.total_bytes()
        if total <= self.max_bytes:
            return
        rows = self._conn.execute(
            "SELECT key, size FROM lyrics_cache ORDER BY last_used_at, fetched_at"
        ).fetchall()
        doomed = []
        for row in rows:
            if total <= self.max_bytes:
                break
            doomed.append((row["key"],))
            total -= row["size"]
        with self._conn:
            self._conn.executemany("DELETE FROM lyrics_cache WHERE key = ?", doomed)
        log.info("letras: %d removidas do cache (limite de tamanho)", len(doomed))


# --- rede --------------------------------------------------------------------


class HttpGet(Protocol):
    def get(
        self,
        url: str,
        params: dict[str, str],
        callback: Callable[[int | None, Any], None],
    ) -> None:
        """callback(status HTTP ou None em erro de rede, JSON ou None)."""


class QtHttp:
    """GET assíncrono no loop do Qt (QNetworkAccessManager), sem lib nova."""

    def __init__(self, parent: QObject) -> None:
        from PySide6.QtNetwork import QNetworkAccessManager

        self._nam = QNetworkAccessManager(parent)
        self._nam.setTransferTimeout(TIMEOUT_MS)
        self._agent = user_agent().encode()

    def get(self, url, params, callback) -> None:
        from PySide6.QtNetwork import QNetworkReply, QNetworkRequest

        qurl = QUrl(url)
        query = QUrlQuery()
        for name, value in params.items():
            query.addQueryItem(name, value)
        qurl.setQuery(query)
        request = QNetworkRequest(qurl)
        request.setRawHeader(b"User-Agent", self._agent)
        reply = self._nam.get(request)

        def done() -> None:
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            body = None
            if status is not None:
                try:
                    body = json.loads(bytes(reply.readAll()).decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    body = None
            elif reply.error() != QNetworkReply.NetworkError.NoError:
                log.info("letras: erro de rede (%s)", reply.errorString())
            reply.deleteLater()
            callback(status, body)

        reply.finished.connect(done)


# --- serviço -----------------------------------------------------------------


class LyricsService(QObject):
    ready = Signal(str, object)  # chave da faixa, Lyrics

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        enabled: Callable[[], bool] = lambda: True,
        http: HttpGet | None = None,
        now: Callable[[], datetime] = utc_now,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.cache = LyricsCache(conn, now=now)
        self._enabled = enabled
        self._http = http or QtHttp(self)
        self._inflight: set[str] = set()
        self.requests = 0  # contagem de chamadas ao LRCLIB (debug/testes)

    def request(self, artist: str, title: str, album: str, duration_s: float | None) -> str:
        """Pede a letra da faixa. A resposta chega por `ready`."""
        key = cache_key(artist, title, album)
        if not self._enabled():
            self.ready.emit(key, Lyrics("disabled"))
            return key
        if not title.strip():
            self.ready.emit(key, Lyrics("not_found"))
            return key
        cached = self.cache.get(key)
        if cached is not None:
            self.ready.emit(key, cached)
            return key
        if key in self._inflight:
            return key
        self._inflight.add(key)
        track = (artist, title, album, duration_s)
        if artist.strip() and album.strip() and duration_s:
            params = {
                "artist_name": artist,
                "track_name": title,
                "album_name": album,
                "duration": str(round(duration_s)),
            }
            self._call("/get", params, lambda s, b: self._on_get(key, track, s, b))
        else:
            self._search(key, track)
        return key

    def _call(self, path: str, params: dict[str, str], callback) -> None:
        self.requests += 1
        self._http.get(API + path, params, callback)

    def _on_get(self, key: str, track, status: int | None, body: Any) -> None:
        if status == 200:
            lyrics, content = from_record(body)
            if lyrics.status != "not_found":
                self._store(key, lyrics, content)
                return
        if status in (200, 404):
            self._search(key, track)
            return
        self._unavailable(key, status)

    def _search(self, key: str, track) -> None:
        artist, title, _album, duration_s = track
        params = {"track_name": title}
        if artist.strip():
            params["artist_name"] = artist
        self._call("/search", params, lambda s, b: self._on_search(key, duration_s, s, b))

    def _on_search(self, key: str, duration_s, status: int | None, body: Any) -> None:
        if status != 200:
            self._unavailable(key, status)
            return
        lyrics, content = from_record(pick_best(body, duration_s))
        self._store(key, lyrics, content)

    def _store(self, key: str, lyrics: Lyrics, content: str) -> None:
        self._inflight.discard(key)
        self.cache.put(key, lyrics, content)
        self.ready.emit(key, lyrics)

    def _unavailable(self, key: str, status: int | None) -> None:
        """Erro de rede (offline) ou do servidor (ex.: 503): não vai para o cache; a
        próxima tentativa é quando a faixa tocar de novo (nunca por posição)."""
        self._inflight.discard(key)
        log.info("letras: LRCLIB indisponível (status %s)", status)
        self.ready.emit(key, Lyrics("offline" if status is None else "unavailable"))
