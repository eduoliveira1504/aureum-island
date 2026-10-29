"""Atalho global via RegisterHotKey.

RegisterHotKey não é hook de teclado: o Windows só avisa quando a combinação
registrada é pressionada; o app não lê nenhuma outra tecla.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QObject, Signal

from aureum_island.services.system_events import SystemEvents

log = logging.getLogger(__name__)

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

_MODIFIERS = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "meta": MOD_WIN,
}

_KEYS = {
    "space": 0x20,
    "espaço": 0x20,
    "enter": 0x0D,
    "tab": 0x09,
    "home": 0x24,
    "end": 0x23,
    "insert": 0x2D,
    "pause": 0x13,
    "`": 0xC0,
    "'": 0xDE,
    ";": 0xBA,
    ",": 0xBC,
    ".": 0xBE,
    "/": 0xBF,
    "-": 0xBD,
    "=": 0xBB,
}
_KEYS.update({chr(c).lower(): c for c in range(ord("A"), ord("Z") + 1)})
_KEYS.update({str(d): 0x30 + d for d in range(10)})
_KEYS.update({"[": 0xDB, "]": 0xDD})
_KEYS.update({f"f{n}": 0x6F + n for n in range(1, 25)})

HOTKEY_ID = 0xA1E1

# Em teclado ABNT2, Ctrl+Alt equivale a AltGr: Ctrl+Alt+<tecla> bloquearia em todos os
# apps o caractere que o AltGr gera com essa tecla. Nunca usar estas teclas num padrão.
ALTGR_RESERVED = frozenset(
    {"q", "w", "e", "c", "1", "2", "3", "4", "5", "6", "=", "[", "]", "/", ";"}
)

DEFAULT_HOTKEY = "Ctrl+Alt+I"
# Tentativas, em ordem, quando o atalho escolhido não registra.
FALLBACK_HOTKEYS = ("Ctrl+Alt+I", "Ctrl+Alt+K", "Ctrl+Shift+Alt+I")


@dataclass(frozen=True)
class Hotkey:
    modifiers: int
    vk: int


def parse_hotkey(text: str) -> Hotkey:
    """'Ctrl+Alt+Space' -> Hotkey. Exige ao menos um modificador e uma tecla."""
    parts = [p.strip().lower() for p in text.split("+")]
    if len(parts) < 2 or any(not p for p in parts):
        raise ValueError(f"atalho inválido: {text!r}")
    *mods, key = parts
    modifiers = 0
    for mod in mods:
        if mod not in _MODIFIERS:
            raise ValueError(f"modificador desconhecido: {mod!r}")
        modifiers |= _MODIFIERS[mod]
    if key not in _KEYS:
        raise ValueError(f"tecla desconhecida: {key!r}")
    return Hotkey(modifiers, _KEYS[key])


def candidates(text: str) -> list[str]:
    """O atalho pedido e depois os fallbacks, sem repetir combinações equivalentes."""
    result: list[str] = []
    seen: set[Hotkey] = set()
    for candidate in (text, *FALLBACK_HOTKEYS):
        try:
            key = parse_hotkey(candidate)
        except ValueError:
            key = None
        if key is not None and key in seen:
            continue
        if key is not None:
            seen.add(key)
        result.append(candidate)
    return result


class HotkeyStatus(Enum):
    INACTIVE = "inactive"
    REGISTERED = "registered"
    FALLBACK = "fallback"  # o escolhido falhou; um dos FALLBACK_HOTKEYS funcionou
    FAILED = "failed"  # combinação já em uso ou inválida; a tela de config mostra o aviso
    UNSUPPORTED = "unsupported"


class GlobalHotkey(QObject):
    activated = Signal()
    status_changed = Signal()

    def __init__(self, events: SystemEvents, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._status = HotkeyStatus.INACTIVE
        self._error: str | None = None
        self._text: str | None = None
        self._active: str | None = None
        events.hotkey.connect(self._on_hotkey)

    @property
    def status(self) -> HotkeyStatus:
        return self._status

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def text(self) -> str | None:
        """Atalho pedido."""
        return self._text

    @property
    def active(self) -> str | None:
        """Atalho que de fato está registrado (pode ser um fallback)."""
        return self._active

    def register(self, text: str) -> bool:
        """Registra `text`; se falhar, tenta FALLBACK_HOTKEYS em ordem.
        Falha não quebra o app: fica em `status`/`error`."""
        self.unregister()
        self._text = text
        if sys.platform != "win32":
            return self._set(HotkeyStatus.UNSUPPORTED, None)
        errors: list[str] = []
        for candidate in candidates(text):
            error = self._try_register(candidate)
            if error is None:
                self._active = candidate
                if candidate == text:
                    log.info("atalho global registrado: %s", candidate)
                    return self._set(HotkeyStatus.REGISTERED, None)
                log.warning("atalho global: %s; usando %s", errors[0], candidate)
                return self._set(HotkeyStatus.FALLBACK, errors[0])
            errors.append(error)
        log.warning("atalho global: nenhum atalho registrado (%s)", "; ".join(errors))
        return self._set(HotkeyStatus.FAILED, errors[0])

    def _try_register(self, text: str) -> str | None:
        try:
            hotkey = parse_hotkey(text)
        except ValueError as exc:
            return str(exc)
        if not _user32.RegisterHotKey(None, HOTKEY_ID, hotkey.modifiers | MOD_NOREPEAT, hotkey.vk):
            code = ctypes.get_last_error()
            return f"não foi possível registrar {text} (erro {code}; talvez já esteja em uso)"
        return None

    def unregister(self) -> None:
        if self._active is not None:
            _user32.UnregisterHotKey(None, HOTKEY_ID)
            self._active = None
            self._set(HotkeyStatus.INACTIVE, None)

    def _set(self, status: HotkeyStatus, error: str | None) -> bool:
        self._status, self._error = status, error
        self.status_changed.emit()
        return self._active is not None

    def _on_hotkey(self, hotkey_id: int) -> None:
        if hotkey_id == HOTKEY_ID and self._active is not None:
            self.activated.emit()


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    _user32.RegisterHotKey.restype = wintypes.BOOL
    _user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.UnregisterHotKey.restype = wintypes.BOOL
