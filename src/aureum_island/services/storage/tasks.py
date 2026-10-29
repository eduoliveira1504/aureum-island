"""Repositório de tarefas (SQLite)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from aureum_island.services.storage.db import from_db, to_db, utc_now


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    due_at: datetime | None
    remind_offset_min: int | None  # None = usa a antecedência global
    done_at: datetime | None
    created_at: datetime
    snoozed_until: datetime | None = None

    @property
    def done(self) -> bool:
        return self.done_at is not None


def _from_row(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        due_at=from_db(row["due_at"]),
        remind_offset_min=row["remind_offset_min"],
        done_at=from_db(row["done_at"]),
        created_at=from_db(row["created_at"]),
        snoozed_until=from_db(row["snoozed_until"]),
    )


def _opt(dt: datetime | None) -> str | None:
    return to_db(dt) if dt is not None else None


def _clean_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise ValueError("tarefa sem título")
    return title


class TaskRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(
        self,
        title: str,
        due_at: datetime | None = None,
        remind_offset_min: int | None = None,
    ) -> Task:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO tasks (title, due_at, remind_offset_min, created_at)"
                " VALUES (?, ?, ?, ?)",
                (_clean_title(title), _opt(due_at), remind_offset_min, to_db(utc_now())),
            )
        return self.get(cur.lastrowid)

    def get(self, task_id: int) -> Task | None:
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _from_row(row) if row else None

    def list_tasks(self, include_done: bool = True) -> list[Task]:
        sql = "SELECT * FROM tasks"
        if not include_done:
            sql += " WHERE done_at IS NULL"
        sql += " ORDER BY due_at IS NULL, due_at, created_at"
        return [_from_row(r) for r in self._conn.execute(sql)]

    def pending_with_due(self) -> list[Task]:
        """Tarefas não concluídas com horário (as que geram aviso)."""
        rows = self._conn.execute(
            "SELECT * FROM tasks WHERE done_at IS NULL AND due_at IS NOT NULL ORDER BY due_at"
        )
        return [_from_row(r) for r in rows]

    def set_done(self, task_id: int, done: bool = True) -> Task | None:
        return self._update(task_id, done_at=to_db(utc_now()) if done else None)

    def rename(self, task_id: int, title: str) -> Task | None:
        return self._update(task_id, title=_clean_title(title))

    def set_due(self, task_id: int, due_at: datetime | None) -> Task | None:
        """Novo horário; limpa o adiamento."""
        return self._update(task_id, due_at=_opt(due_at), snoozed_until=None)

    def set_remind_offset(self, task_id: int, minutes: int | None) -> Task | None:
        return self._update(task_id, remind_offset_min=minutes)

    def snooze(self, task_id: int, until: datetime) -> Task | None:
        return self._update(task_id, snoozed_until=to_db(until))

    def delete(self, task_id: int) -> bool:
        with self._conn:
            cur = self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cur.rowcount > 0

    def restore(self, task: Task) -> Task:
        """Reinsere uma tarefa excluída, com o mesmo id (desfazer)."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO tasks (id, title, due_at, remind_offset_min, done_at, created_at,"
                " snoozed_until) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    task.id,
                    task.title,
                    _opt(task.due_at),
                    task.remind_offset_min,
                    _opt(task.done_at),
                    to_db(task.created_at),
                    _opt(task.snoozed_until),
                ),
            )
        return self.get(task.id)

    def _update(self, task_id: int, **columns: object) -> Task | None:
        assignments = ", ".join(f"{name} = ?" for name in columns)
        with self._conn:
            self._conn.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ?", (*columns.values(), task_id)
            )
        return self.get(task_id)
