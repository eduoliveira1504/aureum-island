"""settings.json: configurações com defaults, schema versionado e escrita atômica."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

from aureum_island.theme.color import is_hex_color
from aureum_island.theme.tokens import DEFAULT_ACCENT, DEFAULT_NOTCH_BG, NOTCH_BACKGROUNDS

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2

MODES = ("normal", "minimal")
PAGES = ("music", "focus", "water", "tasks", "calendar")
REMINDER_OFFSETS = (0, 5, 10, 15, 30, 60)
WATER_INTERVALS = (30, 45, 60, 90, 120)
WATER_CUP_OPTIONS = (150, 200, 250, 300, 350, 500)  # sugestões; aceita 50 a 1000
WATER_CUP_RANGE = (50, 1000)
HOTKEY_STATUSES = ("inactive", "registered", "fallback", "failed", "unsupported")

# Atalho padrão até o schema 1. Em teclado ABNT2, Ctrl+Alt equivale a AltGr; ver 0003.
_OLD_DEFAULT_HOTKEY = "Ctrl+Alt+Space"


@dataclass(frozen=True)
class Settings:
    mode: str = "normal"
    last_page: str = "music"
    hide_on_fullscreen: bool = True
    hotkey: str = "Ctrl+Alt+I"
    # Preenchidos pelo app ao registrar: qual atalho funcionou e o status (para o Bloco 6).
    hotkey_active: str | None = None
    hotkey_status: str = "inactive"
    # Avisos
    reminder_offset_min: int = 10
    sound_enabled: bool = True
    sound_volume: float = 0.6
    native_notifications: bool = False
    # Foco (minutos) e estado salvo do ciclo atual (pages/focus_model.py)
    focus_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 15
    long_break_every: int = 4
    focus_state: dict | None = None
    # Água
    water_goal_ml: int = 2000
    water_cup_ml: int = 250
    water_reminders: bool = True
    water_interval_min: int = 60
    water_start: str = "08:00"
    water_end: str = "22:00"
    # Música: letras via LRCLIB (única chamada externa do app)
    lyrics_enabled: bool = True
    # Calendário (a opção na UI entra no Bloco 6)
    week_start: str = "sunday"
    accent: str = DEFAULT_ACCENT
    notch_bg: str = DEFAULT_NOTCH_BG

    def with_changes(self, **changes: Any) -> Settings:
        return replace(self, **changes)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_number(v: Any) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def _is_hhmm(v: Any) -> bool:
    if not isinstance(v, str) or len(v) != 5 or v[2] != ":":
        return False
    hh, mm = v[:2], v[3:]
    return hh.isdigit() and mm.isdigit() and int(hh) < 24 and int(mm) < 60


def _is_minutes(v: Any) -> bool:
    return _is_int(v) and 1 <= v <= 240


_VALIDATORS: dict[str, Callable[[Any], bool]] = {
    "mode": lambda v: v in MODES,
    "last_page": lambda v: v in PAGES,
    "hide_on_fullscreen": lambda v: isinstance(v, bool),
    "hotkey": lambda v: isinstance(v, str) and bool(v.strip()),
    "hotkey_active": lambda v: v is None or (isinstance(v, str) and bool(v.strip())),
    "hotkey_status": lambda v: v in HOTKEY_STATUSES,
    "reminder_offset_min": lambda v: v in REMINDER_OFFSETS and not isinstance(v, bool),
    "sound_enabled": lambda v: isinstance(v, bool),
    "sound_volume": lambda v: _is_number(v) and 0.0 <= v <= 1.0,
    "native_notifications": lambda v: isinstance(v, bool),
    "focus_minutes": lambda v: _is_minutes(v),
    "short_break_minutes": lambda v: _is_minutes(v),
    "long_break_minutes": lambda v: _is_minutes(v),
    "long_break_every": lambda v: _is_int(v) and 1 <= v <= 12,
    "focus_state": lambda v: v is None or isinstance(v, dict),
    "water_goal_ml": lambda v: _is_int(v) and 250 <= v <= 10_000,
    "water_cup_ml": lambda v: _is_int(v) and WATER_CUP_RANGE[0] <= v <= WATER_CUP_RANGE[1],
    "water_reminders": lambda v: isinstance(v, bool),
    "water_interval_min": lambda v: v in WATER_INTERVALS and not isinstance(v, bool),
    "water_start": lambda v: _is_hhmm(v),
    "water_end": lambda v: _is_hhmm(v),
    "lyrics_enabled": lambda v: isinstance(v, bool),
    "week_start": lambda v: v in ("sunday", "monday"),
    "accent": is_hex_color,
    "notch_bg": lambda v: v in NOTCH_BACKGROUNDS,
}


def from_dict(raw: Any) -> Settings:
    """Monta Settings a partir de dados lidos. Chave desconhecida é ignorada;
    valor inválido volta ao default."""
    if not isinstance(raw, dict):
        return Settings()
    raw = _migrate(raw)
    values: dict[str, Any] = {}
    for f in fields(Settings):
        if f.name not in raw:
            continue
        value = raw[f.name]
        if _VALIDATORS[f.name](value):
            values[f.name] = value
        else:
            log.warning("settings: valor inválido em %r, usando o padrão", f.name)
    result = Settings(**values)
    if result.water_start >= result.water_end:
        log.warning("settings: janela da água inválida, usando o padrão")
        result = replace(result, water_start=Settings.water_start, water_end=Settings.water_end)
    return result


def _migrate(raw: dict[str, Any]) -> dict[str, Any]:
    version = raw.get("schema_version", 1)
    if isinstance(version, int) and version < 2 and raw.get("hotkey") == _OLD_DEFAULT_HOTKEY:
        # O padrão antigo nunca foi escolha do usuário (não há tela de config ainda).
        raw = {k: v for k, v in raw.items() if k != "hotkey"}
    return raw


def to_dict(settings: Settings) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, **asdict(settings)}


def load(path: Path) -> Settings:
    """Lê o settings.json. Se não existe, devolve os defaults. Se está corrompido,
    move para settings.json.corrupt e devolve os defaults."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Settings()
    except OSError:
        log.exception("settings: não foi possível ler %s", path)
        return Settings()
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        log.warning("settings: JSON corrompido, voltando aos padrões")
        try:
            os.replace(path, path.with_name(path.name + ".corrupt"))
        except OSError:
            log.exception("settings: não foi possível guardar a cópia corrompida")
        return Settings()
    return from_dict(raw)


def save(settings: Settings, path: Path) -> None:
    """Grava de forma atômica: arquivo temporário na mesma pasta + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(to_dict(settings), ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
