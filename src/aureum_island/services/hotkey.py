"""Atalho global via RegisterHotKey.

RegisterHotKey não é hook de teclado: o Windows só avisa quando a combinação
registrada é pressionada; o app não lê nenhuma outra tecla.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

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


# Nome de cada tecla ao gravar um atalho novo (VK -> nome salvo no settings.json).
_VK_NAMES = {
    vk: name.upper() if len(name) == 1 else name.capitalize() for name, vk in _KEYS.items()
}
_VK_NAMES.update({0x20: "Space", 0x0D: "Enter", 0x09: "Tab"})
_MOD_ORDER = ((MOD_CONTROL, "Ctrl"), (MOD_SHIFT, "Shift"), (MOD_ALT, "Alt"), (MOD_WIN, "Win"))


def format_hotkey(modifiers: int, vk: int) -> str | None:
    """(modificadores, VK) -> 'Ctrl+Alt+I'. None se a tecla não é aceita."""
    name = _VK_NAMES.get(vk)
    if name is None:
        return None
    mods = [label for flag, label in _MOD_ORDER if modifiers & flag]
    return "+".join([*mods, name])


def display(text: str) -> str:
    """Texto do atalho para a tela ('Ctrl+Alt+Space' -> 'Ctrl+Alt+Espaço')."""
    parts = text.split("+")
    if parts and parts[-1].strip().lower() in ("space", "espaço"):
        parts[-1] = "Espaço"
    return "+".join(parts)


def altgr_conflict(hotkey: Hotkey) -> bool:
    """Ctrl+Alt+<tecla> é AltGr+<tecla> no ABNT2: bloquearia um caractere em todo app."""
    both = MOD_CONTROL | MOD_ALT
    reserved = {_KEYS[k] for k in ALTGR_RESERVED}
    return hotkey.modifiers & both == both and hotkey.vk in reserved


def validate(text: str) -> str | None:
    """Motivo para recusar um atalho escolhido pelo usuário, ou None se pode tentar."""
    try:
        hotkey = parse_hotkey(text)
    except ValueError:
        return "Combinação não reconhecida."
    if not hotkey.modifiers & (MOD_CONTROL | MOD_ALT | MOD_WIN):
        return "Use Ctrl, Alt ou Win na combinação."
    if altgr_conflict(hotkey):
        key = text.split("+")[-1].strip().upper()
        return (
            f"Bloqueado pela regra do AltGr: no teclado ABNT2, {display(text)} é o mesmo que "
            f"AltGr+{key} e bloquearia esse caractere em todos os apps."
        )
    return None


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


def _same(a: str, b: str) -> bool:
    try:
        return parse_hotkey(a) == parse_hotkey(b)
    except ValueError:
        return False


class HotkeyStatus(Enum):
    INACTIVE = "inactive"
    REGISTERED = "registered"
    FALLBACK = "fallback"  # o escolhido falhou; um dos FALLBACK_HOTKEYS funcionou
    FAILED = "failed"  # combinação já em uso ou inválida; a tela de config mostra o aviso
    UNSUPPORTED = "unsupported"


class HotkeyBackend(Protocol):
    def register(self, hotkey: Hotkey) -> bool: ...
    def unregister(self) -> None: ...


class Win32Backend:
    """RegisterHotKey / UnregisterHotKey na thread da UI (WM_HOTKEY vem para ela)."""

    def register(self, hotkey: Hotkey) -> bool:
        if _user32.RegisterHotKey(None, HOTKEY_ID, hotkey.modifiers | MOD_NOREPEAT, hotkey.vk):
            return True
        log.info("RegisterHotKey falhou (erro %d)", ctypes.get_last_error())
        return False

    def unregister(self) -> None:
        _user32.UnregisterHotKey(None, HOTKEY_ID)


class GlobalHotkey(QObject):
    activated = Signal()
    status_changed = Signal()

    def __init__(
        self,
        events: SystemEvents,
        parent: QObject | None = None,
        *,
        backend: HotkeyBackend | None = None,
    ) -> None:
        super().__init__(parent)
        if backend is None and sys.platform == "win32":
            backend = Win32Backend()
        self._backend = backend
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
        """Registra `text`. Só o atalho padrão tenta FALLBACK_HOTKEYS se falhar; um
        atalho escolhido pelo usuário fica como falhou. "" = sem atalho.
        Falha não quebra o app: fica em `status`/`error`."""
        self.unregister()
        self._text = text
        if not text:
            return self._set(HotkeyStatus.INACTIVE, None)
        if self._backend is None:
            return self._set(HotkeyStatus.UNSUPPORTED, None)
        errors: list[str] = []
        tries = candidates(text) if _same(text, DEFAULT_HOTKEY) else [text]
        for candidate in tries:
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

    def change(self, text: str) -> str | None:
        """Troca pelo atalho escolhido na tela de Configurações.

        Se for recusado (regra do AltGr) ou não registrar (em uso por outro app),
        mantém o anterior e devolve o motivo. "" = sem atalho.
        """
        if text:
            reason = validate(text)
            if reason is not None:
                return reason
        previous = self._text
        self.register(text)
        if not text or self._status in (HotkeyStatus.REGISTERED, HotkeyStatus.FALLBACK):
            return None
        if self._status is HotkeyStatus.UNSUPPORTED:
            return None
        if previous is not None:
            self.register(previous)
        return f"{display(text)} está em uso por outro app."

    def suspend(self) -> None:
        """Solta o atalho sem esquecer qual era (para gravar um novo)."""
        if self._active is not None:
            self._backend.unregister()
            self._active = None

    def resume(self) -> None:
        if self._active is None and self._text is not None:
            self.register(self._text)

    def _try_register(self, text: str) -> str | None:
        try:
            hotkey = parse_hotkey(text)
        except ValueError as exc:
            return str(exc)
        if not self._backend.register(hotkey):
            return f"não foi possível registrar {text} (talvez já esteja em uso)"
        return None

    def unregister(self) -> None:
        if self._active is not None:
            self._backend.unregister()
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
