"""Repositório de tarefas (CRUD básico)."""

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
    remind_offset_min: int | None
    done_at: datetime | None
    created_at: datetime

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
    )


class TaskRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(
        self,
        title: str,
        due_at: datetime | None = None,
        remind_offset_min: int | None = None,
    ) -> Task:
        title = title.strip()
        if not title:
            raise ValueError("tarefa sem título")
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO tasks (title, due_at, remind_offset_min, created_at)"
                " VALUES (?, ?, ?, ?)",
                (title, to_db(due_at) if due_at else None, remind_offset_min, to_db(utc_now())),
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

    def set_done(self, task_id: int, done: bool = True) -> Task | None:
        with self._conn:
            self._conn.execute(
                "UPDATE tasks SET done_at = ? WHERE id = ?",
                (to_db(utc_now()) if done else None, task_id),
            )
        return self.get(task_id)

    def rename(self, task_id: int, title: str) -> Task | None:
        title = title.strip()
        if not title:
            raise ValueError("tarefa sem título")
        with self._conn:
            self._conn.execute("UPDATE tasks SET title = ? WHERE id = ?", (title, task_id))
        return self.get(task_id)

    def delete(self, task_id: int) -> bool:
        with self._conn:
            cur = self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cur.rowcount > 0
