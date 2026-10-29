"""Mídia tocando no Windows (SMTC, pacotes winrt-*).

A API do winrt é assíncrona e os eventos chegam em threads do Windows. O serviço roda
numa thread própria com um loop asyncio; o estado volta para a thread da UI por um
signal (conexão enfileirada). Tudo por evento: troca de sessão, propriedades (faixa,
capa), playback e linha do tempo. Fora do Windows, o serviço base é um no-op.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Track:
    title: str
    artist: str = ""
    album: str = ""
    duration_s: float | None = None
    source: str = ""  # app de origem (AUMID)

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.title, self.artist, self.album


@dataclass(frozen=True)
class Playback:
    playing: bool = False
    position_s: float = 0.0
    updated_at: datetime | None = None  # UTC, quando a posição foi informada
    duration_s: float | None = None
    can_previous: bool = False
    can_next: bool = False
    can_toggle: bool = False
    can_seek: bool = False

    def position_at(self, now: datetime) -> float:
        """Posição agora: a informada + o tempo corrido, se estiver tocando."""
        position = self.position_s
        if self.playing and self.updated_at is not None:
            position += max(0.0, (now - self.updated_at).total_seconds())
        if self.duration_s:
            position = min(position, self.duration_s)
        return max(0.0, position)


class MediaService(QObject):
    """Interface + no-op. A versão do Windows é `_WinMediaService`."""

    track_changed = Signal(object)  # Track | None
    playback_changed = Signal(object)  # Playback
    cover_changed = Signal(object)  # bytes | None (PNG/JPEG da capa)
    _incoming = Signal(str, object)  # da thread de trabalho para a da UI

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.track: Track | None = None
        self.playback = Playback()
        self.cover: bytes | None = None
        self._incoming.connect(self._apply, Qt.ConnectionType.QueuedConnection)

    # --- comandos (no-op na base) -------------------------------------------

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def play_pause(self) -> None:
        pass

    def next(self) -> None:
        pass

    def previous(self) -> None:
        pass

    def seek(self, seconds: float) -> None:
        pass

    # --- estado (sempre aplicado na thread da UI) ---------------------------

    def _apply(self, kind: str, value: object) -> None:
        if kind == "track":
            if value != self.track:
                self.track = value
                self.track_changed.emit(value)
        elif kind == "playback":
            if value != self.playback:
                self.playback = value
                self.playback_changed.emit(value)
        elif kind == "cover" and value != self.cover:
            self.cover = value
            self.cover_changed.emit(value)


def create_media_service(parent: QObject | None = None) -> MediaService:
    if sys.platform == "win32" and QGuiApplication.platformName() == "windows":
        return _WinMediaService(parent)
    return MediaService(parent)


if sys.platform == "win32":
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager as SessionManager,
    )
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
    )
    from winrt.windows.storage.streams import Buffer, InputStreamOptions

    _TICKS_PER_SECOND = 10_000_000

    class _WinMediaService(MediaService):
        def __init__(self, parent: QObject | None = None) -> None:
            super().__init__(parent)
            self._loop: asyncio.AbstractEventLoop | None = None
            self._thread: threading.Thread | None = None
            self._manager = None
            self._session = None
            self._tokens: list[tuple[str, object]] = []
            self._manager_token = None
            self._duration: float | None = None

        # --- ciclo de vida ---------------------------------------------------

        def start(self) -> None:
            if self._thread is not None:
                return
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._run, name="aureum-media", daemon=True)
            self._thread.start()

        def stop(self) -> None:
            if self._loop is None:
                return
            future = asyncio.run_coroutine_threadsafe(self._teardown(), self._loop)
            try:
                future.result(timeout=2)
            except Exception:  # noqa: BLE001 - saindo do app, só loga
                log.exception("mídia: erro ao encerrar")
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=2)
            self._loop = self._thread = None

        def _run(self) -> None:
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._setup())
            self._loop.run_forever()

        async def _setup(self) -> None:
            try:
                self._manager = await SessionManager.request_async()
            except OSError:
                log.exception("mídia: SMTC indisponível")
                return
            self._manager_token = self._manager.add_current_session_changed(
                lambda *_: self._post(self._bind_current)
            )
            await self._bind_current()

        async def _teardown(self) -> None:
            self._unbind()
            if self._manager is not None and self._manager_token is not None:
                self._manager.remove_current_session_changed(self._manager_token)

        def _post(self, coro_fn) -> None:
            """Chamado nas threads de evento do Windows: agenda no loop da mídia."""
            loop = self._loop
            if loop is not None and loop.is_running():
                loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self._safe(coro_fn)))

        async def _safe(self, coro_fn) -> None:
            try:
                await coro_fn()
            except OSError:
                log.info("mídia: sessão mudou durante a leitura", exc_info=True)

        # --- sessão ----------------------------------------------------------

        def _unbind(self) -> None:
            session = self._session
            for name, token in self._tokens:
                if session is not None:
                    getattr(session, f"remove_{name}")(token)
            self._tokens = []
            self._session = None

        async def _bind_current(self) -> None:
            self._unbind()
            session = self._manager.get_current_session() if self._manager else None
            self._session = session
            if session is None:
                self._incoming.emit("track", None)
                self._incoming.emit("playback", Playback())
                self._incoming.emit("cover", None)
                return
            handlers = {
                "media_properties_changed": self._read_properties,
                "playback_info_changed": self._read_playback,
                "timeline_properties_changed": self._read_playback,
            }
            for name, coro_fn in handlers.items():
                token = getattr(session, f"add_{name}")(lambda *_args, fn=coro_fn: self._post(fn))
                self._tokens.append((name, token))
            await self._read_properties()
            await self._read_playback()

        async def _read_properties(self) -> None:
            session = self._session
            if session is None:
                return
            props = await session.try_get_media_properties_async()
            timeline = session.get_timeline_properties()
            self._duration = _seconds(timeline.end_time - timeline.start_time) or None
            track = Track(
                title=props.title or "",
                artist=props.artist or props.album_artist or "",
                album=props.album_title or "",
                duration_s=self._duration,
                source=session.source_app_user_model_id or "",
            )
            self._incoming.emit("track", track if track.title else None)
            cover = await _read_thumbnail(props.thumbnail)
            self._incoming.emit("cover", cover)

        async def _read_playback(self) -> None:
            session = self._session
            if session is None:
                return
            info = session.get_playback_info()
            controls = info.controls
            timeline = session.get_timeline_properties()
            updated = timeline.last_updated_time
            if updated is not None and updated.tzinfo is None:
                updated = updated.replace(tzinfo=UTC)
            duration = _seconds(timeline.end_time - timeline.start_time) or None
            playback = Playback(
                playing=info.playback_status == PlaybackStatus.PLAYING,
                position_s=_seconds(timeline.position - timeline.start_time),
                updated_at=updated,
                duration_s=duration,
                can_previous=bool(controls.is_previous_enabled),
                can_next=bool(controls.is_next_enabled),
                can_toggle=bool(controls.is_play_pause_toggle_enabled),
                can_seek=bool(controls.is_playback_position_enabled) and bool(duration),
            )
            if updated is None or updated.year < 2000:
                # Alguns apps não informam a hora da posição: usa a de agora.
                playback = replace(playback, updated_at=datetime.now(UTC))
            self._incoming.emit("playback", playback)

        # --- comandos --------------------------------------------------------

        def _command(self, name: str, *args) -> None:
            async def run() -> None:
                if self._session is not None:
                    await getattr(self._session, name)(*args)

            if self._loop is not None:
                asyncio.run_coroutine_threadsafe(self._safe(run), self._loop)

        def play_pause(self) -> None:
            self._command("try_toggle_play_pause_async")

        def next(self) -> None:
            self._command("try_skip_next_async")

        def previous(self) -> None:
            self._command("try_skip_previous_async")

        def seek(self, seconds: float) -> None:
            async def run() -> None:
                session = self._session
                if session is None:
                    return
                start = session.get_timeline_properties().start_time
                ticks = int((_seconds(start) + max(0.0, seconds)) * _TICKS_PER_SECOND)
                await session.try_change_playback_position_async(ticks)

            if self._loop is not None:
                asyncio.run_coroutine_threadsafe(self._safe(run), self._loop)

    def _seconds(value) -> float:
        if isinstance(value, timedelta):
            return value.total_seconds()
        return float(value or 0) / _TICKS_PER_SECOND

    async def _read_thumbnail(reference) -> bytes | None:
        if reference is None:
            return None
        try:
            stream = await reference.open_read_async()
            size = int(stream.size)
            if size <= 0:
                return None
            buffer = await stream.read_async(Buffer(size), size, InputStreamOptions.READ_AHEAD)
            return bytes(buffer)
        except OSError:
            log.info("mídia: capa indisponível", exc_info=True)
            return None
