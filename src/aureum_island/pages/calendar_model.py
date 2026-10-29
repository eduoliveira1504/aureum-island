"""Regras da página Calendário, sem UI: grade do mês e agenda do dia."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from aureum_island.services.events import Event
from aureum_island.services.storage.tasks import Task

MONTHS = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)  # fmt: skip
WEEKDAY_INITIALS = ("S", "T", "Q", "Q", "S", "S", "D")  # segunda..domingo
WEEKDAYS_SHORT = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


def first_weekday(week_start: str) -> int:
    """0 = segunda (Python), 6 = domingo."""
    return 6 if week_start == "sunday" else 0


def month_grid(year: int, month: int, week_start: str) -> list[date]:
    """6 semanas (42 dias) começando no dia da semana configurado."""
    first = date(year, month, 1)
    start = first - timedelta(days=(first.weekday() - first_weekday(week_start)) % 7)
    return [start + timedelta(days=i) for i in range(42)]


def weekday_labels(week_start: str) -> list[str]:
    offset = first_weekday(week_start)
    return [WEEKDAY_INITIALS[(offset + i) % 7] for i in range(7)]


def add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(day.day, last))


def event_days(event: Event, tz) -> list[date]:
    """Dias em que o evento aparece. Dia inteiro: de início ao fim (exclusivo), pela
    data "flutuante"; com horário: o dia local do início."""
    if event.all_day:
        first = event.start_at.date()
        last = (event.end_at.date() - timedelta(days=1)) if event.end_at else first
        span = max(0, (last - first).days)
        return [first + timedelta(days=i) for i in range(span + 1)]
    return [event.start_at.astimezone(tz).date()]


def busy_days(tasks: Iterable[Task], events: Iterable[Event], tz) -> set[date]:
    days = {t.due_at.astimezone(tz).date() for t in tasks if t.due_at is not None}
    for event in events:
        days.update(event_days(event, tz))
    return days


@dataclass(frozen=True)
class AgendaItem:
    kind: str  # task | event
    ref_id: int
    title: str
    start: datetime | None  # local; None = dia inteiro
    tag: str  # "Tarefa", "Evento" ou o nome da agenda ICS
    color: str | None  # cor da agenda ICS
    done: bool = False
    editable: bool = False  # evento local
    location: str = ""

    @property
    def all_day(self) -> bool:
        return self.start is None


def agenda_for_day(
    day: date,
    tasks: Iterable[Task],
    events: Iterable[Event],
    sources: Mapping[int, tuple[str, str]],
    tz,
) -> list[AgendaItem]:
    """Tarefas e eventos do dia, dia inteiro primeiro, depois por horário."""
    items: list[AgendaItem] = []
    for task in tasks:
        if task.due_at is None:
            continue
        local = task.due_at.astimezone(tz)
        if local.date() == day:
            items.append(AgendaItem("task", task.id, task.title, local, "Tarefa", None, task.done))
    for event in events:
        if day not in event_days(event, tz):
            continue
        name, color = (
            sources.get(event.source_id, ("Evento", None))
            if not event.local
            else (
                "Evento",
                None,
            )
        )
        start = None if event.all_day else event.start_at.astimezone(tz)
        items.append(
            AgendaItem(
                "event", event.id, event.title, start, name, color,
                editable=event.local, location=event.location,
            )
        )  # fmt: skip
    return sorted(items, key=lambda i: (not i.all_day, i.start.timestamp() if i.start else 0))


def day_title(day: date, today: date) -> str:
    """'Hoje · qui, 29 out' ou 'sex, 30 out'."""
    label = f"{WEEKDAYS_SHORT[day.weekday()]}, {day.day} {MONTHS[day.month - 1][:3]}"
    if day == today:
        return f"Hoje · {label}"
    if day == today + timedelta(days=1):
        return f"Amanhã · {label}"
    return label
