"""Motor de avisos.

Provedores registráveis informam os próximos horários (`Due`). O motor arma um único
QTimer singleShot para o próximo `fire_at` de todos eles (no máximo 6 h à frente) e
rearma por evento: dado mudou, horário do Windows mudou, volta da suspensão, início.
`reminders_fired` garante que nada dispara duas vezes. Ver docs/decisions/0004.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from aureum_island.services.storage.db import to_db, utc_now

log = logging.getLogger(__name__)

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
MAX_ARM = timedelta(hours=6)
MISSED_WINDOW = timedelta(hours=12)


@dataclass(frozen=True)
class Due:
    item_type: str
    item_id: int
    fire_at: datetime  # UTC
    payload: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)
    # False: se passou da hora (app fechado, PC dormindo), é descartado sem virar
    # "aviso perdido" (ex.: água).
    stale_ok: bool = field(default=True, compare=False, hash=False)

    @property
    def key(self) -> tuple[str, int, str]:
        return self.item_type, self.item_id, to_db(self.fire_at)


class ReminderProvider(Protocol):
    """Também precisa de um signal `changed` (sem argumentos)."""

    def upcoming(self, after: datetime) -> list[Due]:
        """Avisos com fire_at > after."""


class ReminderEngine(QObject):
    fired = Signal(object)  # list[Due] na hora certa (cada um vira um aviso)
    missed = Signal(object)  # list[Due] perdidos nas últimas 12 h (início/suspensão/horário)

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        now: Callable[[], datetime] = utc_now,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self._now = now
        self._providers: list[ReminderProvider] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self.check)
        self.next_fire_at: datetime | None = None

    # --- API ----------------------------------------------------------------

    def register(self, provider: ReminderProvider) -> None:
        self._providers.append(provider)
        provider.changed.connect(self.rearm)

    def start(self) -> None:
        """Início do app: o que venceu com o app fechado vira "perdido"."""
        self.catch_up()

    def catch_up(self) -> None:
        """Início, volta da suspensão, horário do Windows alterado."""
        self._process(catch_up=True)
        self.rearm()

    def check(self) -> None:
        """Timer venceu: dispara o que chegou na hora."""
        self._process(catch_up=False)
        self.rearm()

    def rearm(self) -> None:
        pending = self._pending()
        if not pending:
            self._timer.stop()
            self.next_fire_at = None
            return
        self.next_fire_at = pending[0].fire_at
        delay = min(max(self.next_fire_at - self._now(), timedelta(0)), MAX_ARM)
        self._timer.start(int(delay.total_seconds() * 1000))

    @property
    def armed_ms(self) -> int | None:
        return self._timer.interval() if self._timer.isActive() else None

    # --- interno ------------------------------------------------------------

    def _pending(self) -> list[Due]:
        dues = [d for p in self._providers for d in p.upcoming(EPOCH) if not self._was_fired(d)]
        return sorted(dues, key=lambda d: d.fire_at)

    def _process(self, *, catch_up: bool) -> None:
        now = self._now()
        due = [d for d in self._pending() if d.fire_at <= now]
        if not due:
            return
        cutoff = now - MISSED_WINDOW
        old = [d for d in due if d.fire_at < cutoff or (catch_up and not d.stale_ok)]
        recent = [d for d in due if d not in old]
        # Mais antigos que 12 h: marcados sem mostrar (fired_at NULL).
        self._record(old, None)
        self._record(recent, now)
        if old:
            log.info("avisos: %d antigos ou vencidos descartados", len(old))
        if recent:
            log.info("avisos: %d %s", len(recent), "perdidos" if catch_up else "na hora")
            (self.missed if catch_up else self.fired).emit(recent)

    def _was_fired(self, due: Due) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM reminders_fired WHERE item_type = ? AND item_id = ? AND fire_at = ?",
            due.key,
        ).fetchone()
        return row is not None

    def _record(self, dues: list[Due], fired_at: datetime | None) -> None:
        if not dues:
            return
        stamp = to_db(fired_at) if fired_at is not None else None
        with self._conn:
            self._conn.executemany(
                "INSERT OR IGNORE INTO reminders_fired (item_type, item_id, fire_at, fired_at)"
                " VALUES (?, ?, ?, ?)",
                [(*d.key, stamp) for d in dues],
            )
