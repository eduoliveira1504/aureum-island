"""Letras sem UI: parser LRC, linha atual e chave de cache."""

from __future__ import annotations

import bisect
import re
import unicodedata
from dataclasses import dataclass, field

_TIME = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
_OFFSET = re.compile(r"^\[offset:\s*([+-]?\d+)\s*\]\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class LyricLine:
    time_s: float
    text: str


@dataclass(frozen=True)
class Lyrics:
    """status: synced | plain | instrumental | not_found | offline (sem rede) |
    unavailable (erro do servidor) | disabled."""

    status: str
    lines: tuple[LyricLine, ...] = ()
    plain: str = ""
    times: tuple[float, ...] = field(default=(), compare=False, repr=False)

    @classmethod
    def synced(cls, lines: list[LyricLine]) -> Lyrics:
        return cls("synced", tuple(lines), times=tuple(line.time_s for line in lines))


def parse_lrc(text: str) -> list[LyricLine]:
    """Linhas `[mm:ss.xx]texto`, vários tempos por linha e `[offset:+/-ms]`."""
    offset_s = 0.0
    lines: list[LyricLine] = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        offset = _OFFSET.match(raw)
        if offset:
            # No LRC, offset positivo adianta a letra.
            offset_s = -int(offset.group(1)) / 1000
            continue
        stamps = []
        pos = 0
        while match := _TIME.match(raw, pos):
            minutes, seconds, frac = match.groups()
            value = int(minutes) * 60 + int(seconds)
            if frac:
                value += int(frac) / (10 ** len(frac))
            stamps.append(value)
            pos = match.end()
        if not stamps:
            continue  # tags como [ar:], [ti:]
        text_part = raw[pos:].strip()
        lines.extend(LyricLine(t, text_part) for t in stamps)
    lines = [LyricLine(max(0.0, line.time_s + offset_s), line.text) for line in lines]
    lines.sort(key=lambda line: line.time_s)
    return lines


def current_index(lyrics: Lyrics, position_s: float) -> int:
    """Índice da linha cantada agora (-1 antes da primeira)."""
    return bisect.bisect_right(lyrics.times, position_s) - 1


def next_change_s(lyrics: Lyrics, position_s: float) -> float | None:
    """Segundos até a próxima linha (para armar o timer), ou None se acabou."""
    i = bisect.bisect_right(lyrics.times, position_s)
    if i >= len(lyrics.times):
        return None
    return lyrics.times[i] - position_s


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return " ".join(text.split())


def cache_key(artist: str, title: str, album: str) -> str:
    """Identidade da faixa. Sem a duração: alguns players só a informam depois."""
    return f"{_norm(artist)}|{_norm(title)}|{_norm(album)}"
