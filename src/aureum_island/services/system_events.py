"""Mensagens do Windows que o app precisa ouvir (atalho global, troca de horário, retorno
da suspensão), via QAbstractNativeEventFilter. Fora do Windows, nada é instalado."""

from __future__ import annotations

import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal

WM_TIMECHANGE = 0x001E
WM_POWERBROADCAST = 0x0218
WM_HOTKEY = 0x0312
PBT_APMRESUMESUSPEND = 0x0007
PBT_APMRESUMEAUTOMATIC = 0x0012


class SystemEvents(QObject):
    hotkey = Signal(int)
    time_changed = Signal()
    resumed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._filter: _Filter | None = None
        if sys.platform == "win32":
            self._filter = _Filter(self)
            QCoreApplication.instance().installNativeEventFilter(self._filter)

    def close(self) -> None:
        if self._filter is not None:
            QCoreApplication.instance().removeNativeEventFilter(self._filter)
            self._filter = None


if sys.platform == "win32":
    from ctypes import wintypes

    class _Filter(QAbstractNativeEventFilter):
        def __init__(self, events: SystemEvents) -> None:
            super().__init__()
            self._events = events

        def nativeEventFilter(self, event_type, message):  # noqa: N802
            if event_type != b"windows_generic_MSG":
                return False, 0
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                self._events.hotkey.emit(int(msg.wParam))
            elif msg.message == WM_TIMECHANGE:
                self._events.time_changed.emit()
            elif msg.message == WM_POWERBROADCAST and msg.wParam in (
                PBT_APMRESUMESUSPEND,
                PBT_APMRESUMEAUTOMATIC,
            ):
                self._events.resumed.emit()
            return False, 0
