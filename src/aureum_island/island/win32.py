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


# --- Janela com barra própria (Configurações) ------------------------------------
#
# A janela é FramelessWindowHint para o Qt (sem margens de moldura), mas ganha de volta os
# estilos nativos WS_CAPTION/WS_THICKFRAME: o Windows continua dando sombra, cantos
# arredondados (Win11), encaixe nas laterais e Win+setas. WM_NCCALCSIZE devolve a janela
# inteira como área do app (some a barra do Windows) e WM_NCHITTEST devolve as bordas de
# redimensionar. Arrastar fica com QWindow.startSystemMove na barra própria.

_GWL_STYLE = -16
_WS_CAPTION = 0x00C00000
_WS_THICKFRAME = 0x00040000
_WS_SYSMENU = 0x00080000
_WS_MINIMIZEBOX = 0x00020000
_WS_MAXIMIZEBOX = 0x00010000
_SWP_NOZORDER = 0x0004
_SWP_FRAMECHANGED = 0x0020
_WM_NCCALCSIZE = 0x0083
_WM_NCHITTEST = 0x0084
_SM_CXSIZEFRAME, _SM_CYSIZEFRAME, _SM_CXPADDEDBORDER = 32, 33, 92
_HT = {
    (True, False, False, False): 10,  # HTLEFT
    (False, True, False, False): 11,  # HTRIGHT
    (False, False, True, False): 12,  # HTTOP
    (True, False, True, False): 13,  # HTTOPLEFT
    (False, True, True, False): 14,  # HTTOPRIGHT
    (False, False, False, True): 15,  # HTBOTTOM
    (True, False, False, True): 16,  # HTBOTTOMLEFT
    (False, True, False, True): 17,  # HTBOTTOMRIGHT
}

if _IS_WINDOWS:

    class _Margins(ctypes.Structure):
        _fields_ = [(n, ctypes.c_int) for n in ("left", "right", "top", "bottom")]

    class _NcCalcSizeParams(ctypes.Structure):
        _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]

    _user32.IsZoomed.argtypes = [wintypes.HWND]
    _user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    _user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    _user32.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, wintypes.UINT]


def enable_custom_frame(widget: QWidget) -> None:
    """Estilos nativos de volta numa janela FramelessWindowHint (ver o comentário acima)."""
    if not native():
        return
    hwnd = _hwnd(widget)
    style = _user32.GetWindowLongPtrW(hwnd, _GWL_STYLE)
    wanted = _WS_CAPTION | _WS_THICKFRAME | _WS_SYSMENU | _WS_MINIMIZEBOX | _WS_MAXIMIZEBOX
    _user32.SetWindowLongPtrW(hwnd, _GWL_STYLE, style | wanted)
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        margins = _Margins(0, 0, 0, 1)  # 1 px de "vidro" basta para o DWM desenhar a sombra
        dwmapi.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(margins))
    except OSError:
        pass
    flags = _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOZORDER | _SWP_NOACTIVATE | _SWP_FRAMECHANGED
    _user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, flags)


def custom_frame_event(message: object, border: int) -> tuple[bool, int] | None:
    """Para o nativeEvent da janela. `border`: largura (lógica) da faixa de redimensionar.
    Devolve (tratado, resultado) ou None para o Qt seguir com a mensagem."""
    msg = wintypes.MSG.from_address(int(message))
    if msg.message == _WM_NCCALCSIZE and msg.wParam:
        if _user32.IsZoomed(msg.hWnd):
            # Maximizada, a janela passa da tela pela espessura da moldura: recolhe.
            dpi = _user32.GetDpiForWindow(msg.hWnd)
            frame_x = _user32.GetSystemMetricsForDpi(_SM_CXSIZEFRAME, dpi)
            frame_y = _user32.GetSystemMetricsForDpi(_SM_CYSIZEFRAME, dpi)
            pad = _user32.GetSystemMetricsForDpi(_SM_CXPADDEDBORDER, dpi)
            rect = _NcCalcSizeParams.from_address(msg.lParam).rgrc[0]
            rect.left += frame_x + pad
            rect.right -= frame_x + pad
            rect.top += frame_y + pad
            rect.bottom -= frame_y + pad
        return True, 0
    if msg.message == _WM_NCHITTEST and not _user32.IsZoomed(msg.hWnd):
        x = ctypes.c_short(msg.lParam & 0xFFFF).value
        y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
        rect = wintypes.RECT()
        _user32.GetWindowRect(msg.hWnd, ctypes.byref(rect))
        b = round(border * _user32.GetDpiForWindow(msg.hWnd) / 96)
        edges = (x < rect.left + b, x >= rect.right - b, y < rect.top + b, y >= rect.bottom - b)
        code = _HT.get(edges)
        if code is not None:
            return True, code
    return None
