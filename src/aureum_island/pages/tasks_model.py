"""Regras da página Tarefas, sem UI: horário digitado, filtro da lista, próxima tarefa."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime, time, timedelta

from aureum_island.services.storage.tasks import Task

_HHMM = re.compile(r"^\s*([01]?\d|2[0-3])[:h]([0-5]\d)\s*$")


def parse_hhmm(text: str) -> time | None:
    """'14:30', '9:05' ou '14h30'. Vazio -> None. Inválido -> ValueError."""
    if not text.strip():
        return None
    match = _HHMM.match(text)
    if not match:
        raise ValueError(f"horário inválido: {text!r}")
    return time(int(match.group(1)), int(match.group(2)))


def resolve_due(at: time, now_local: datetime) -> tuple[datetime, bool]:
    """Horário de hoje; se já passou, amanhã. Devolve (due_at em UTC, é amanhã)."""
    candidate = now_local.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    tomorrow = candidate <= now_local
    if tomorrow:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC), tomorrow


def _local_date(dt: datetime, now_local: datetime):
    return dt.astimezone(now_local.tzinfo).date()


def is_visible(task: Task, now_local: datetime) -> bool:
    """Hoje + amanhã + sem horário + atrasadas não concluídas. Concluídas de dias
    anteriores somem (continuam no banco)."""
    today = now_local.date()
    if task.done_at is not None and _local_date(task.done_at, now_local) < today:
        return False
    if task.due_at is None:
        return True
    day = _local_date(task.due_at, now_local)
    if day < today:
        return not task.done
    return day <= today + timedelta(days=1)


def visible_tasks(tasks: Iterable[Task], now_local: datetime) -> list[Task]:
    shown = [t for t in tasks if is_visible(t, now_local)]
    dated = sorted((t for t in shown if t.due_at is not None), key=lambda t: t.due_at)
    undated = sorted((t for t in shown if t.due_at is None), key=lambda t: t.created_at)
    return dated + undated


def is_overdue(task: Task, now: datetime) -> bool:
    return not task.done and task.due_at is not None and task.due_at < now


def next_pending(tasks: Iterable[Task], now: datetime) -> Task | None:
    """Próxima tarefa pendente com horário (a do pill em accent)."""
    upcoming = [t for t in tasks if not t.done and t.due_at is not None and t.due_at >= now]
    return min(upcoming, key=lambda t: t.due_at, default=None)


def time_label(task: Task, now_local: datetime) -> str:
    """'14:30' ou 'amanhã 08:00' ('ontem'/data para atrasadas de outros dias)."""
    if task.due_at is None:
        return ""
    local = task.due_at.astimezone(now_local.tzinfo)
    hhmm = f"{local.hour:02d}:{local.minute:02d}"
    delta = (local.date() - now_local.date()).days
    if delta == 0:
        return hhmm
    if delta == 1:
        return f"amanhã {hhmm}"
    if delta == -1:
        return f"ontem {hhmm}"
    return f"{local.day:02d}/{local.month:02d} {hhmm}"
