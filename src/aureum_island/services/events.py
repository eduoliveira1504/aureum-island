"""Eventos (locais e ICS): repositório, serviço para a UI e provedor de avisos."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, Signal

from aureum_island.services.ics import ParsedEvent
from aureum_island.services.reminders import MISSED_WINDOW, Due
from aureum_island.services.storage.db import from_db, to_db, utc_now

ITEM_TYPE = "event"


@dataclass(frozen=True)
class Event:
    id: int
    source: str  # local | ics
    source_id: int | None
    uid: str
    title: str
    start_at: datetime  # UTC (dia inteiro: meia-noite UTC da data)
    end_at: datetime | None
    all_day: bool
    location: str
    remind_offset_min: int | None

    @property
    def local(self) -> bool:
        return self.source == "local"


def _from_row(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"],
        source=row["source"],
        source_id=row["source_id"],
        uid=row["uid"],
        title=row["title"],
        start_at=from_db(row["start_at"]),
        end_at=from_db(row["end_at"]),
        all_day=bool(row["all_day"]),
        location=row["location"] or "",
        remind_offset_min=row["remind_offset_min"],
    )


def fire_at_for(event: Event, global_offset_min: int) -> datetime | None:
    """Início menos a antecedência. Dia inteiro não tem aviso."""
    if event.all_day:
        return None
    offset = event.remind_offset_min
    if offset is None:
        offset = global_offset_min
    return event.start_at - timedelta(minutes=offset)


class EventRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, event_id: int) -> Event | None:
        row = self._conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return _from_row(row) if row else None

    def between(self, start: datetime, end: datetime) -> list[Event]:
        """Eventos que começam em [start, end) (UTC)."""
        rows = self._conn.execute(
            "SELECT * FROM events WHERE start_at >= ? AND start_at < ? ORDER BY start_at",
            (to_db(start), to_db(end)),
        )
        return [_from_row(r) for r in rows]

    def timed_from(self, start: datetime) -> list[Event]:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE all_day = 0 AND start_at >= ? ORDER BY start_at",
            (to_db(start),),
        )
        return [_from_row(r) for r in rows]

    # --- locais -------------------------------------------------------------

    def add_local(self, title: str, start: datetime, end: datetime | None) -> Event:
        title = title.strip()
        if not title:
            raise ValueError("evento sem título")
        uid = f"local-{to_db(utc_now())}-{title[:20]}"
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO events (source, source_id, uid, title, start_at, end_at, all_day)"
                " VALUES ('local', NULL, ?, ?, ?, ?, 0)",
                (uid, title, to_db(start), to_db(end) if end else None),
            )
        return self.get(cur.lastrowid)

    def update_local(self, event_id: int, **fields: object) -> Event | None:
        allowed = {"title", "start_at", "end_at", "remind_offset_min"}
        values = {}
        for name, value in fields.items():
            if name not in allowed:
                raise ValueError(name)
            values[name] = to_db(value) if isinstance(value, datetime) else value
        assignments = ", ".join(f"{n} = ?" for n in values)
        with self._conn:
            self._conn.execute(
                f"UPDATE events SET {assignments} WHERE id = ? AND source = 'local'",
                (*values.values(), event_id),
            )
        return self.get(event_id)

    def suppress_reminder(self, event_id: int, fire_at: datetime) -> None:
        """Marca o aviso como já tratado, sem mostrar (fired_at NULL)."""
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO reminders_fired (item_type, item_id, fire_at, fired_at)"
                " VALUES (?, ?, ?, NULL)",
                (ITEM_TYPE, event_id, to_db(fire_at)),
            )

    def delete_local(self, event_id: int) -> bool:
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM events WHERE id = ? AND source = 'local'", (event_id,)
            )
        return cur.rowcount > 0

    # --- ICS ----------------------------------------------------------------

    def replace_source(self, source_id: int, parsed: Iterable[ParsedEvent]) -> list[int]:
        """Troca os eventos da fonte numa transação só.

        Mesma ocorrência (uid + início) mantém o id: um aviso já disparado não volta
        se só o título mudou. O que sumiu da agenda é removido. Devolve os ids novos.
        """
        new_ids: list[int] = []
        with self._conn:
            existing = {
                (row["uid"], row["start_at"]): row["id"]
                for row in self._conn.execute(
                    "SELECT id, uid, start_at FROM events WHERE source = 'ics' AND source_id = ?",
                    (source_id,),
                )
            }
            keep: set[int] = set()
            for ev in parsed:
                key = (ev.uid, to_db(ev.start))
                values = (
                    ev.title,
                    to_db(ev.end) if ev.end else None,
                    int(ev.all_day),
                    ev.location,
                )
                if key in existing:
                    event_id = existing[key]
                    self._conn.execute(
                        "UPDATE events SET title = ?, end_at = ?, all_day = ?, location = ?"
                        " WHERE id = ?",
                        (*values, event_id),
                    )
                else:
                    cur = self._conn.execute(
                        "INSERT INTO events (source, source_id, uid, start_at, title, end_at,"
                        " all_day, location) VALUES ('ics', ?, ?, ?, ?, ?, ?, ?)",
                        (source_id, ev.uid, key[1], *values),
                    )
                    event_id = cur.lastrowid
                    new_ids.append(event_id)
                keep.add(event_id)
            stale = [(i,) for i in existing.values() if i not in keep]
            self._conn.executemany("DELETE FROM events WHERE id = ?", stale)
        return new_ids


class EventService(QObject):
    """Para a UI (eventos locais) e provedor de avisos (local + ICS)."""

    changed = Signal()

    def __init__(
        self,
        repo: EventRepo,
        *,
        global_offset: Callable[[], int],
        now: Callable[[], datetime] = utc_now,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.repo = repo
        self._global_offset = global_offset
        self._now = now

    def upcoming(self, after: datetime) -> list[Due]:
        # Só o que ainda importa: o motor descarta o que passou de 12 h.
        horizon = self._now() - MISSED_WINDOW - timedelta(hours=2)
        offset = self._global_offset()
        dues = []
        for event in self.repo.timed_from(horizon):
            fire_at = fire_at_for(event, offset)
            if fire_at is not None and fire_at > after:
                dues.append(Due(ITEM_TYPE, event.id, fire_at, {"title": event.title}))
        return dues

    def get(self, event_id: int) -> Event | None:
        return self.repo.get(event_id)

    def between(self, start: datetime, end: datetime) -> list[Event]:
        return self.repo.between(start, end)

    def add_local(self, title: str, start: datetime, end: datetime | None = None) -> Event:
        event = self.repo.add_local(title, start, end)
        if event.start_at <= self._now():
            # Evento que já começou: registrar não deve gerar "Evento chegando".
            fire_at = fire_at_for(event, self._global_offset())
            if fire_at is not None:
                self.repo.suppress_reminder(event.id, fire_at)
        self.changed.emit()
        return event

    def update_local(self, event_id: int, **fields: object) -> Event | None:
        event = self.repo.update_local(event_id, **fields)
        self.changed.emit()
        return event

    def delete_local(self, event_id: int) -> bool:
        deleted = self.repo.delete_local(event_id)
        if deleted:
            self.changed.emit()
        return deleted
