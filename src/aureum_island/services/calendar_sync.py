"""Agendas ICS: cadastro (link no cofre do Windows), download e sincronização.

- Sincroniza ao iniciar, a cada 30 min (singleShot rearmado), na volta da suspensão
  e no botão "Atualizar".
- ETag / If-Modified-Since quando o servidor manda; em 304 não reprocessa.
- Timeout de 15 s. Em erro (rede, HTTP, ICS inválido), mantém os eventos antigos.
- O link nunca vai para log, banco, JSON ou mensagem de erro.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from PySide6.QtCore import QObject, QTimer, QUrl, Signal

from aureum_island.services import ics
from aureum_island.services.events import EventRepo, fire_at_for
from aureum_island.services.storage import secrets
from aureum_island.services.storage.db import from_db, to_db, utc_now

log = logging.getLogger(__name__)

SYNC_EVERY = timedelta(minutes=30)
TIMEOUT_MS = 15_000
MAX_BYTES = 20 * 1024 * 1024
# A janela de expansão anda com o tempo: com 304 por mais de um dia, baixa de novo.
REPARSE_AFTER = timedelta(hours=24)


@dataclass(frozen=True)
class Source:
    id: int
    name: str
    color: str
    last_sync_at: datetime | None  # último sucesso (200 ou 304)
    last_attempt_at: datetime | None
    last_status: str | None  # ok | failed | None (nunca)


@dataclass(frozen=True)
class FetchResult:
    status: int | None  # None = erro de rede/timeout
    body: bytes = b""
    etag: str | None = None
    last_modified: str | None = None


class IcsFetcher(Protocol):
    def fetch(
        self,
        url: str,
        etag: str | None,
        last_modified: str | None,
        callback: Callable[[FetchResult], None],
    ) -> None: ...


class QtIcsFetcher:
    """GET com timeout e limite de tamanho, no loop do Qt."""

    def __init__(self, parent: QObject) -> None:
        from PySide6.QtNetwork import QNetworkAccessManager

        from aureum_island.services.lyrics import user_agent

        self._nam = QNetworkAccessManager(parent)
        self._nam.setTransferTimeout(TIMEOUT_MS)
        self._agent = user_agent().encode()

    def fetch(self, url, etag, last_modified, callback) -> None:
        from PySide6.QtNetwork import QNetworkReply, QNetworkRequest

        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", self._agent)
        if etag:
            request.setRawHeader(b"If-None-Match", etag.encode())
        if last_modified:
            request.setRawHeader(b"If-Modified-Since", last_modified.encode())
        reply = self._nam.get(request)
        too_big = {"value": False}

        def progress(received: int, _total: int) -> None:
            if received > MAX_BYTES:
                too_big["value"] = True
                reply.abort()

        def done() -> None:
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if too_big["value"]:
                log.info("agenda: arquivo maior que o limite")
                status = None
            elif (
                reply.error()
                not in (
                    QNetworkReply.NetworkError.NoError,
                    QNetworkReply.NetworkError.ContentNotFoundError,
                )
                and status is None
            ):
                # errorString() pode conter a URL: loga só o código.
                log.info("agenda: erro de rede (%s)", reply.error().name)
            body = bytes(reply.readAll()) if status == 200 else b""
            header = reply.rawHeader
            result = FetchResult(
                status=status,
                body=body,
                etag=bytes(header(b"ETag")).decode("latin-1") or None,
                last_modified=bytes(header(b"Last-Modified")).decode("latin-1") or None,
            )
            reply.deleteLater()
            callback(result)

        reply.downloadProgress.connect(progress)
        reply.finished.connect(done)


class CalendarSync(QObject):
    sources_changed = Signal()  # lista ou status das agendas mudou
    events_changed = Signal()  # eventos ICS mudaram (página e avisos)

    def __init__(
        self,
        conn: sqlite3.Connection,
        repo: EventRepo,
        *,
        global_offset: Callable[[], int],
        fetcher: IcsFetcher | None = None,
        now: Callable[[], datetime] = utc_now,
        get_url: Callable[[int], str | None] = secrets.get_ics_url,
        set_url: Callable[[int, str], None] = secrets.set_ics_url,
        delete_url: Callable[[int], None] = secrets.delete_ics_url,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._repo = repo
        self._global_offset = global_offset
        self._fetcher = fetcher or QtIcsFetcher(self)
        self._now = now
        self._get_url, self._set_url, self._delete_url = get_url, set_url, delete_url
        self.syncing: set[int] = set()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.sync_all)

    # --- agendas ------------------------------------------------------------

    def sources(self) -> list[Source]:
        rows = self._conn.execute(
            "SELECT id, name, color, last_sync_at, last_attempt_at, last_status"
            " FROM ics_sources ORDER BY id"
        )
        return [
            Source(
                r["id"],
                r["name"],
                r["color"],
                from_db(r["last_sync_at"]),
                from_db(r["last_attempt_at"]),
                r["last_status"],
            )
            for r in rows
        ]

    def domain_of(self, source_id: int) -> str:
        try:
            url = self._get_url(source_id)
        except secrets.SecretStoreError:
            return ""
        return ics.domain(url) if url else ""

    def add_source(self, name: str, color: str, link: str) -> int:
        """Valida o link (InvalidLink), grava no cofre e sincroniza. Devolve o id."""
        url = ics.normalize_url(link)
        name = name.strip() or ics.domain(url)
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO ics_sources (name, color) VALUES (?, ?)", (name, color)
            )
        source_id = cur.lastrowid
        try:
            self._set_url(source_id, url)
        except secrets.SecretStoreError:
            with self._conn:
                self._conn.execute("DELETE FROM ics_sources WHERE id = ?", (source_id,))
            raise
        log.info("agenda %d adicionada (%s)", source_id, ics.domain(url))
        self.sources_changed.emit()
        self.sync(source_id)
        return source_id

    def remove_source(self, source_id: int) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM ics_sources WHERE id = ?", (source_id,))
        try:
            self._delete_url(source_id)
        except secrets.SecretStoreError:
            log.warning("agenda %d: não foi possível apagar o link do cofre", source_id)
        self.syncing.discard(source_id)
        self.sources_changed.emit()
        self.events_changed.emit()

    # --- sincronização ------------------------------------------------------

    def start(self) -> None:
        self.sync_all()

    def sync_all(self) -> None:
        sources = self.sources()
        for source in sources:
            self.sync(source.id)
        if sources:
            self._timer.start(int(SYNC_EVERY.total_seconds() * 1000))
        else:
            self._timer.stop()

    @property
    def next_sync_ms(self) -> int | None:
        return self._timer.remainingTime() if self._timer.isActive() else None

    def sync(self, source_id: int) -> None:
        if source_id in self.syncing:
            return
        row = self._conn.execute(
            "SELECT etag, last_modified, parsed_at FROM ics_sources WHERE id = ?", (source_id,)
        ).fetchone()
        if row is None:
            return
        try:
            url = self._get_url(source_id)
        except secrets.SecretStoreError:
            url = None
        if not url:
            log.warning("agenda %d: link não encontrado no cofre", source_id)
            self._finish(source_id, ok=False)
            return
        etag, modified = row["etag"], row["last_modified"]
        parsed_at = from_db(row["parsed_at"])
        if parsed_at is None or parsed_at < self._now() - REPARSE_AFTER:
            etag = modified = None
        self.syncing.add(source_id)
        self.sources_changed.emit()
        self._fetcher.fetch(url, etag, modified, lambda r: self._on_fetched(source_id, r))

    def _on_fetched(self, source_id: int, result: FetchResult) -> None:
        if source_id not in self.syncing:
            return  # agenda removida durante o download
        if result.status == 304:
            self._finish(source_id, ok=True)
            return
        if result.status != 200:
            log.info("agenda %d: falhou (status %s); eventos mantidos", source_id, result.status)
            self._finish(source_id, ok=False)
            return
        now = self._now()
        try:
            parsed = ics.parse_ics(result.body, now)
        except (ValueError, KeyError, TypeError):
            log.info("agenda %d: ICS inválido; eventos mantidos", source_id)
            self._finish(source_id, ok=False)
            return
        new_ids = self._repo.replace_source(source_id, parsed)
        self._suppress_past(new_ids, now)
        with self._conn:
            self._conn.execute(
                "UPDATE ics_sources SET etag = ?, last_modified = ?, parsed_at = ? WHERE id = ?",
                (result.etag, result.last_modified, to_db(now), source_id),
            )
        log.info("agenda %d: %d eventos", source_id, len(parsed))
        self._finish(source_id, ok=True)
        self.events_changed.emit()

    def _suppress_past(self, event_ids: list[int], now: datetime) -> None:
        """Evento que chega já com o aviso no passado (ex.: agenda recém-adicionada) não
        vira "aviso perdido": fica marcado como disparado, sem mostrar."""
        offset = self._global_offset()
        rows = []
        for event_id in event_ids:
            event = self._repo.get(event_id)
            fire_at = fire_at_for(event, offset) if event else None
            if fire_at is not None and fire_at <= now:
                rows.append(("event", event_id, to_db(fire_at)))
        if rows:
            with self._conn:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO reminders_fired (item_type, item_id, fire_at,"
                    " fired_at) VALUES (?, ?, ?, NULL)",
                    rows,
                )

    def _finish(self, source_id: int, *, ok: bool) -> None:
        self.syncing.discard(source_id)
        stamp = to_db(self._now())
        with self._conn:
            if ok:
                self._conn.execute(
                    "UPDATE ics_sources SET last_sync_at = ?, last_attempt_at = ?,"
                    " last_status = 'ok' WHERE id = ?",
                    (stamp, stamp, source_id),
                )
            else:
                self._conn.execute(
                    "UPDATE ics_sources SET last_attempt_at = ?, last_status = 'failed'"
                    " WHERE id = ?",
                    (stamp, source_id),
                )
        self.sources_changed.emit()


def status_text(source: Source, syncing: bool) -> str:
    """'Última atualização: 14:05' / '... · falhou' / 'Atualizando…'."""
    if syncing:
        return "Atualizando…"
    if source.last_sync_at is None:
        when = "nunca"
    else:
        local = source.last_sync_at.astimezone()
        today = datetime.now().astimezone().date()
        when = f"{local.hour:02d}:{local.minute:02d}"
        if local.date() != today:
            when = f"{local.day:02d}/{local.month:02d} {when}"
    text = f"Última atualização: {when}"
    if source.last_status == "failed":
        text += " · falhou"
    return text
