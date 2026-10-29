"""Serviço de tarefas: operações para a UI, signal `changed` e provedor de avisos."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, Signal

from aureum_island.services.reminders import Due
from aureum_island.services.storage.db import utc_now
from aureum_island.services.storage.tasks import Task, TaskRepo

ITEM_TYPE = "task"
SNOOZE = timedelta(minutes=10)


def fire_at_for(task: Task, global_offset_min: int) -> datetime | None:
    """Adiado: `snoozed_until`. Senão, `due_at` menos a antecedência (do item ou global)."""
    if task.snoozed_until is not None:
        return task.snoozed_until
    if task.due_at is None:
        return None
    offset = task.remind_offset_min if task.remind_offset_min is not None else global_offset_min
    return task.due_at - timedelta(minutes=offset)


class TaskService(QObject):
    changed = Signal()

    def __init__(
        self,
        repo: TaskRepo,
        *,
        global_offset: Callable[[], int],
        now: Callable[[], datetime] = utc_now,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = repo
        self._global_offset = global_offset
        self._now = now

    # --- provedor de avisos -------------------------------------------------

    def upcoming(self, after: datetime) -> list[Due]:
        offset = self._global_offset()
        result = []
        for task in self._repo.pending_with_due():
            fire_at = fire_at_for(task, offset)
            if fire_at is not None and fire_at > after:
                payload = {"title": task.title, "due_at": task.due_at}
                result.append(Due(ITEM_TYPE, task.id, fire_at, payload))
        return result

    # --- leitura ------------------------------------------------------------

    def list_tasks(self) -> list[Task]:
        return self._repo.list_tasks()

    def get(self, task_id: int) -> Task | None:
        return self._repo.get(task_id)

    # --- escrita (todas emitem `changed`) -----------------------------------

    def add(self, title: str, due_at: datetime | None = None) -> Task:
        return self._emit(self._repo.add(title, due_at))

    def rename(self, task_id: int, title: str) -> Task | None:
        return self._emit(self._repo.rename(task_id, title))

    def set_due(self, task_id: int, due_at: datetime | None) -> Task | None:
        return self._emit(self._repo.set_due(task_id, due_at))

    def set_remind_offset(self, task_id: int, minutes: int | None) -> Task | None:
        return self._emit(self._repo.set_remind_offset(task_id, minutes))

    def set_done(self, task_id: int, done: bool = True) -> Task | None:
        return self._emit(self._repo.set_done(task_id, done))

    def snooze(self, task_id: int) -> Task | None:
        """Adia o aviso ("+10 min"): novo fire_at = agora + 10 min."""
        return self._emit(self._repo.snooze(task_id, self._now() + SNOOZE))

    def delete(self, task_id: int) -> Task | None:
        """Exclui e devolve a tarefa, para o "Desfazer"."""
        task = self._repo.get(task_id)
        if task is not None and self._repo.delete(task_id):
            self.changed.emit()
        return task

    def restore(self, task: Task) -> Task:
        return self._emit(self._repo.restore(task))

    def _emit(self, value):
        self.changed.emit()
        return value
