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
    accent: str = DEFAULT_ACCENT
    notch_bg: str = DEFAULT_NOTCH_BG

    def with_changes(self, **changes: Any) -> Settings:
        return replace(self, **changes)


_VALIDATORS: dict[str, Callable[[Any], bool]] = {
    "mode": lambda v: v in MODES,
    "last_page": lambda v: v in PAGES,
    "hide_on_fullscreen": lambda v: isinstance(v, bool),
    "hotkey": lambda v: isinstance(v, str) and bool(v.strip()),
    "hotkey_active": lambda v: v is None or (isinstance(v, str) and bool(v.strip())),
    "hotkey_status": lambda v: v in HOTKEY_STATUSES,
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
    return Settings(**values)


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
