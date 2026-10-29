"""Leitura de ICS e validação de links, sem rede e sem Qt.

O link ICS secreto dá acesso à agenda inteira: nada aqui loga ou devolve a URL em
mensagens de erro.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import urlsplit

import icalendar
import recurring_ical_events

WINDOW_BACK = timedelta(days=30)
WINDOW_AHEAD = timedelta(days=90)


class InvalidLink(ValueError):
    """Mensagem para o usuário; nunca contém o link."""


def normalize_url(text: str) -> str:
    """Aceita https:// e webcal:// (vira https://). Recusa http:// e o resto."""
    url = text.strip()
    scheme = url.split(":", 1)[0].lower() if ":" in url else ""
    if scheme == "webcal":
        url = "https" + url[len("webcal") :]
    elif scheme == "http":
        raise InvalidLink("Links http:// não são aceitos. Use https:// ou webcal://.")
    elif scheme != "https":
        raise InvalidLink("Cole um link que comece com https:// ou webcal://.")
    parts = urlsplit(url)
    if not parts.hostname:
        raise InvalidLink("Link inválido.")
    return url


def domain(url: str) -> str:
    """Só o domínio, para mostrar na lista (nunca a URL inteira)."""
    return urlsplit(url).hostname or ""


@dataclass(frozen=True)
class ParsedEvent:
    uid: str
    title: str
    start: datetime  # UTC; para dia inteiro, meia-noite UTC da data (data "flutuante")
    end: datetime | None
    all_day: bool
    location: str


def _as_utc(value: date | datetime) -> tuple[datetime, bool]:
    """(UTC, é dia inteiro). Data pura = dia inteiro; datetime sem fuso = horário local."""
    if not isinstance(value, datetime):
        return datetime.combine(value, time(0), tzinfo=UTC), True
    if value.tzinfo is None:
        value = value.astimezone()  # "floating time": horário local do PC
    return value.astimezone(UTC), False


def parse_ics(data: bytes, now: datetime) -> list[ParsedEvent]:
    """Eventos (recorrentes já expandidos, com EXDATE e RECURRENCE-ID) entre 30 dias
    atrás e 90 à frente. Levanta ValueError se o ICS for inválido."""
    calendar = icalendar.Calendar.from_ical(data)
    start, end = now - WINDOW_BACK, now + WINDOW_AHEAD
    seen: set[tuple[str, datetime]] = set()
    events: list[ParsedEvent] = []
    for component in recurring_ical_events.of(calendar).between(start, end):
        dtstart = component.get("DTSTART")
        if dtstart is None:
            continue
        begin, all_day = _as_utc(dtstart.dt)
        finish = None
        if component.get("DTEND") is not None:
            finish = _as_utc(component.get("DTEND").dt)[0]
        elif component.get("DURATION") is not None:
            finish = begin + component.get("DURATION").dt
        elif all_day:
            finish = begin + timedelta(days=1)
        uid = str(component.get("UID") or f"sem-uid-{begin.isoformat()}")
        if (uid, begin) in seen:
            continue
        seen.add((uid, begin))
        events.append(
            ParsedEvent(
                uid=uid,
                title=str(component.get("SUMMARY") or "(sem título)").strip(),
                start=begin,
                end=finish,
                all_day=all_day,
                location=str(component.get("LOCATION") or "").strip(),
            )
        )
    return events
