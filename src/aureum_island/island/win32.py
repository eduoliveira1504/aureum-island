"""Ajustes nativos das janelas do notch (só Windows; no-op nas outras plataformas)."""

from __future__ import annotations

import sys

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    _user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    _user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    _user32.SetWindowPos.restype = wintypes.BOOL

_GWL_EXSTYLE = -20
_WS_EX_NOACTIVATE = 0x08000000
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOACTIVATE = 0x0010


def native() -> bool:
    return _IS_WINDOWS and QGuiApplication.platformName() == "windows"


def _hwnd(widget: QWidget) -> int:
    return int(widget.winId())


def set_no_activate(widget: QWidget, enabled: bool) -> None:
    """WS_EX_NOACTIVATE: clicar no notch aberto por hover não tira o foco do app do usuário.
    Desligado quando o notch é aberto por atalho/clique e precisa de foco."""
    if not native():
        return
    hwnd = _hwnd(widget)
    style = _user32.GetWindowLongPtrW(hwnd, _GWL_EXSTYLE)
    new = style | _WS_EX_NOACTIVATE if enabled else style & ~_WS_EX_NOACTIVATE
    if new != style:
        _user32.SetWindowLongPtrW(hwnd, _GWL_EXSTYLE, new)


def place_below(lower: QWidget, upper: QWidget) -> None:
    """Coloca `lower` logo abaixo de `upper` no z-order (as duas ficam sempre no topo)."""
    if not native():
        upper.raise_()
        return
    _user32.SetWindowPos(
        _hwnd(lower), _hwnd(upper), 0, 0, 0, 0, _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE
    )


_DWMWA_USE_IMMERSIVE_DARK_MODE = 20


def set_dark_title_bar(widget: QWidget, dark: bool) -> None:
    """Barra de título escura ou clara (Windows 10 20H1+ e 11), seguindo o tema da janela."""
    if not native():
        return
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
    except OSError:
        return
    value = ctypes.c_int(1 if dark else 0)
    dwmapi.DwmSetWindowAttribute(
        wintypes.HWND(_hwnd(widget)),
        _DWMWA_USE_IMMERSIVE_DARK_MODE,
        ctypes.byref(value),
        ctypes.sizeof(value),
    )
