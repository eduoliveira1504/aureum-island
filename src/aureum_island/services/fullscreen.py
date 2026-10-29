"""Detecta app em tela cheia no monitor do notch, por evento (sem polling).

- EVENT_SYSTEM_FOREGROUND: troca da janela em primeiro plano.
- EVENT_OBJECT_LOCATIONCHANGE, restrito ao processo dessa janela (recriado a cada troca):
  pega o app que já está na frente e entra em tela cheia (F11, vídeo).
Os callbacks só filtram e reiniciam um singleShot; a comparação de retângulos roda
depois, agrupada. Fora do Windows (e nos testes) vira no-op.
"""

from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication

log = logging.getLogger(__name__)

DEBOUNCE_MS = 150

# Janelas do shell que cobrem o monitor mas não são "tela cheia".
_SHELL_CLASSES = frozenset({"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"})


class FullscreenWatcher(QObject):
    """Interface comum. Esta classe base é o no-op."""

    fullscreen_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None, *, debug: bool = False) -> None:
        super().__init__(parent)
        self.debug = debug
        self.checks = 0
        self._fullscreen = False

    @property
    def fullscreen(self) -> bool:
        return self._fullscreen

    def start(self) -> None:
        pass

    def stop(self) -> None:
        self._set(False)

    def _set(self, value: bool) -> None:
        if value != self._fullscreen:
            self._fullscreen = value
            self.fullscreen_changed.emit(value)


def create_fullscreen_watcher(
    parent: QObject | None = None, *, debug: bool = False
) -> FullscreenWatcher:
    if sys.platform == "win32" and QGuiApplication.platformName() == "windows":
        return _WinFullscreenWatcher(parent, debug=debug)
    return FullscreenWatcher(parent, debug=debug)


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    EVENT_SYSTEM_FOREGROUND = 0x0003
    EVENT_OBJECT_LOCATIONCHANGE = 0x800B
    WINEVENT_OUTOFCONTEXT = 0x0000
    WINEVENT_SKIPOWNPROCESS = 0x0002
    OBJID_WINDOW = 0
    CHILDID_SELF = 0
    MONITOR_DEFAULTTONULL = 0
    MONITORINFOF_PRIMARY = 0x1
    GWL_STYLE = -16
    WS_CAPTION = 0x00C00000

    WINEVENTPROC = ctypes.WINFUNCTYPE(
        None,
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.HWND,
        wintypes.LONG,
        wintypes.LONG,
        wintypes.DWORD,
        wintypes.DWORD,
    )

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.SetWinEventHook.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HMODULE,
        WINEVENTPROC,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    _user32.SetWinEventHook.restype = wintypes.HANDLE
    _user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
    _user32.UnhookWinEvent.restype = wintypes.BOOL
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    _user32.GetWindowRect.restype = wintypes.BOOL
    _user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    _user32.MonitorFromWindow.restype = wintypes.HMONITOR
    _user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
    _user32.GetMonitorInfoW.restype = wintypes.BOOL
    _user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetClassNameW.restype = ctypes.c_int
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.IsWindowVisible.restype = wintypes.BOOL
    _user32.IsIconic.argtypes = [wintypes.HWND]
    _user32.IsIconic.restype = wintypes.BOOL
    _user32.IsZoomed.argtypes = [wintypes.HWND]
    _user32.IsZoomed.restype = wintypes.BOOL
    _user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t

    def _window_pid(hwnd: int) -> int:
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def _class_name(hwnd: int) -> str:
        buf = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, buf, 256)
        return buf.value

    class _WinFullscreenWatcher(FullscreenWatcher):
        def __init__(self, parent: QObject | None = None, *, debug: bool = False) -> None:
            super().__init__(parent, debug=debug)
            self._own_pid = os.getpid()
            self._foreground = 0
            self._fg_hook = None
            self._loc_hook = None
            # Referências vivas: o ctypes não pode coletar os callbacks.
            self._fg_proc = WINEVENTPROC(self._on_foreground)
            self._loc_proc = WINEVENTPROC(self._on_location)
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.setInterval(DEBOUNCE_MS)
            self._timer.timeout.connect(self._check)

        def start(self) -> None:
            if self._fg_hook:
                return
            self._fg_hook = _user32.SetWinEventHook(
                EVENT_SYSTEM_FOREGROUND,
                EVENT_SYSTEM_FOREGROUND,
                None,
                self._fg_proc,
                0,
                0,
                WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
            )
            if not self._fg_hook:
                log.warning("tela cheia: SetWinEventHook falhou (%d)", ctypes.get_last_error())
                return
            self._follow(_user32.GetForegroundWindow() or 0)

        def stop(self) -> None:
            self._timer.stop()
            self._unhook_location()
            if self._fg_hook:
                _user32.UnhookWinEvent(self._fg_hook)
                self._fg_hook = None
            super().stop()

        # --- callbacks (só filtram e agendam) -------------------------------

        def _on_foreground(self, _hook, _event, hwnd, _id_object, _id_child, _thread, _time):
            self._follow(hwnd or 0)

        def _on_location(self, _hook, _event, hwnd, id_object, id_child, _thread, _time):
            if id_object != OBJID_WINDOW or id_child != CHILDID_SELF or hwnd != self._foreground:
                return
            self._timer.start()

        # --- interno ---------------------------------------------------------

        def _follow(self, hwnd: int) -> None:
            """Nova janela em primeiro plano: refaz o hook de posição no processo dela."""
            self._foreground = hwnd
            self._unhook_location()
            pid = _window_pid(hwnd) if hwnd else 0
            if pid and pid != self._own_pid:
                self._loc_hook = _user32.SetWinEventHook(
                    EVENT_OBJECT_LOCATIONCHANGE,
                    EVENT_OBJECT_LOCATIONCHANGE,
                    None,
                    self._loc_proc,
                    pid,
                    0,
                    WINEVENT_OUTOFCONTEXT,
                )
            self._timer.start()

        def _unhook_location(self) -> None:
            if self._loc_hook:
                _user32.UnhookWinEvent(self._loc_hook)
                self._loc_hook = None

        def _check(self) -> None:
            self.checks += 1
            result = self._is_fullscreen(self._foreground)
            if self.debug:
                log.info("tela cheia: checagem #%d -> %s", self.checks, result)
            if result is not None:
                self._set(result)

        def _is_fullscreen(self, hwnd: int) -> bool | None:
            """True/False, ou None para "ignorar" (a própria janela)."""
            if not hwnd:
                return False
            if _window_pid(hwnd) == self._own_pid:
                return None
            if _class_name(hwnd) in _SHELL_CLASSES:
                return False
            if not _user32.IsWindowVisible(hwnd) or _user32.IsIconic(hwnd):
                return False
            monitor = _user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONULL)
            if not monitor:
                return False
            info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
            if not _user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return False
            if not info.dwFlags & MONITORINFOF_PRIMARY:
                return False  # o notch fica no monitor principal
            rect = wintypes.RECT()
            if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return False
            m = info.rcMonitor
            covers = (
                rect.left <= m.left
                and rect.top <= m.top
                and rect.right >= m.right
                and rect.bottom >= m.bottom
            )
            if not covers:
                return False
            # Janela maximizada com barra de título (ex.: barra de tarefas oculta) não conta.
            style = _user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
            return not (_user32.IsZoomed(hwnd) and style & WS_CAPTION == WS_CAPTION)
