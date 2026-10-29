"""Regras da água, sem UI: horários dos lembretes, totais do dia e por hora."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class WaterConfig:
    goal_ml: int = 2000
    cup_ml: int = 250
    reminders: bool = True
    interval_min: int = 60
    start: time = time(8, 0)
    end: time = time(22, 0)

    @property
    def interval(self) -> timedelta:
        return timedelta(minutes=self.interval_min)


def parse_time(text: str) -> time:
    hh, mm = text.split(":")
    return time(int(hh), int(mm))


def _at(day: date, t: time, tz) -> datetime:
    return datetime.combine(day, t, tzinfo=tz)


def reminder_slots(
    cfg: WaterConfig,
    now_local: datetime,
    last_drink_local: datetime | None,
    total_today_ml: int,
) -> tuple[datetime | None, datetime | None]:
    """(último horário de lembrete que já passou hoje, próximo horário).

    Lembretes a cada intervalo desde o último registro (ou desde o início da janela, se
    não bebeu hoje), só dentro da janela e só enquanto a meta não foi batida. Ignorar um
    aviso não cala os seguintes: o próximo vem um intervalo depois.
    """
    if not cfg.reminders:
        return None, None
    tz = now_local.tzinfo
    today = now_local.date()
    start, end = _at(today, cfg.start, tz), _at(today, cfg.end, tz)
    tomorrow_first = _at(today + timedelta(days=1), cfg.start, tz) + cfg.interval

    if total_today_ml >= cfg.goal_ml:
        return None, tomorrow_first

    base = start
    if last_drink_local is not None and last_drink_local.date() == today:
        base = max(base, last_drink_local)
    first = base + cfg.interval
    if first > end:
        return None, tomorrow_first

    past = None
    if now_local >= first:
        steps = int((now_local - first) / cfg.interval)
        past = first + steps * cfg.interval
        if past > end:
            past = first + int((end - first) / cfg.interval) * cfg.interval
        upcoming = past + cfg.interval
    else:
        upcoming = first
    if upcoming > end:
        upcoming = tomorrow_first
    return past, upcoming


def hourly_totals(
    entries: Iterable[tuple[datetime, int]], day: date, cfg: WaterConfig, tz
) -> list[tuple[int, int]]:
    """[(hora, ml)] para as horas da janela (início até a hora do fim, inclusive se tiver
    minutos)."""
    last_hour = cfg.end.hour if cfg.end.minute else cfg.end.hour - 1
    hours = list(range(cfg.start.hour, max(cfg.start.hour, last_hour) + 1))
    totals = dict.fromkeys(hours, 0)
    for at, ml in entries:
        local = at.astimezone(tz)
        if local.date() == day and local.hour in totals:
            totals[local.hour] += ml
    return list(totals.items())


def segments_filled(total_ml: int, goal_ml: int, segments: int) -> int:
    """Cada segmento vale 1/N da meta, independente do copo."""
    if goal_ml <= 0:
        return segments
    return min(segments, int(total_ml * segments / goal_ml))
