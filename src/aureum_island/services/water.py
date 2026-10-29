"""Serviço da água: registros no SQLite, totais e provedor de lembretes."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta, tzinfo

from PySide6.QtCore import QObject, Signal

from aureum_island.pages.water_model import WaterConfig, reminder_slots
from aureum_island.services.reminders import Due
from aureum_island.services.storage.db import from_db, to_db, utc_now

ITEM_TYPE = "water"
ITEM_ID = 0  # o fire_at diferencia cada lembrete


class WaterService(QObject):
    changed = Signal()

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        config: Callable[[], WaterConfig],
        now: Callable[[], datetime] = utc_now,
        tz: tzinfo | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._conn = conn
        self.config = config
        self._now = now
        self._tz = tz  # None = fuso do sistema

    def now_local(self) -> datetime:
        return self._now().astimezone(self._tz)

    # --- dados --------------------------------------------------------------

    def add(self, ml: int) -> int:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO water_log (ml, at) VALUES (?, ?)", (int(ml), to_db(self._now()))
            )
        self.changed.emit()
        return cur.lastrowid

    def undo(self, entry_id: int) -> bool:
        with self._conn:
            cur = self._conn.execute("DELETE FROM water_log WHERE id = ?", (entry_id,))
        if cur.rowcount:
            self.changed.emit()
        return cur.rowcount > 0

    def entries_today(self) -> list[tuple[datetime, int]]:
        now = self.now_local()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        rows = self._conn.execute(
            "SELECT at, ml FROM water_log WHERE at >= ? AND at < ? ORDER BY at",
            (to_db(start), to_db(end)),
        )
        return [(from_db(r["at"]), r["ml"]) for r in rows]

    def total_today(self) -> int:
        return sum(ml for _, ml in self.entries_today())

    def last_drink(self) -> datetime | None:
        row = self._conn.execute("SELECT MAX(at) FROM water_log").fetchone()
        return from_db(row[0]) if row and row[0] else None

    # --- provedor de avisos -------------------------------------------------

    def upcoming(self, after: datetime) -> list[Due]:
        cfg = self.config()
        now_local = self.now_local()
        last = self.last_drink()
        last_local = last.astimezone(now_local.tzinfo) if last else None
        total = self.total_today()
        past, upcoming = reminder_slots(cfg, now_local, last_local, total)
        payload = {"total_ml": total, "goal_ml": cfg.goal_ml, "cup_ml": cfg.cup_ml}
        dues = []
        for slot in (past, upcoming):
            if slot is not None and slot > after:
                # Lembrete de água vencido com o app fechado não vira "aviso perdido".
                dues.append(Due(ITEM_TYPE, ITEM_ID, slot, payload, stale_ok=False))
        return dues
