"""Volume geral do sistema (pycaw / Core Audio).

Mudanças feitas fora do app (teclas de volume, mixer) chegam pelo callback do Windows
(IAudioEndpointVolumeCallback), sem polling. O dispositivo padrão é lido de novo em
`refresh()` (ao abrir a página), para o caso de o usuário ter trocado de saída.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication

log = logging.getLogger(__name__)


class VolumeService(QObject):
    """Interface + no-op (fora do Windows e nos testes)."""

    changed = Signal(float, bool)  # nível 0..1, mudo
    _incoming = Signal(float, bool)  # do callback (thread do COM) para a UI

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.level = 0.0
        self.muted = False
        self.available = False
        self._incoming.connect(self._apply, Qt.ConnectionType.QueuedConnection)

    def refresh(self) -> None:
        pass

    def set_level(self, level: float) -> None:
        self._apply(max(0.0, min(1.0, level)), self.muted)

    def set_muted(self, muted: bool) -> None:
        self._apply(self.level, muted)

    def close(self) -> None:
        pass

    def _apply(self, level: float, muted: bool) -> None:
        if (level, muted) != (self.level, self.muted):
            self.level, self.muted = level, muted
            self.changed.emit(level, muted)


def create_volume_service(parent: QObject | None = None) -> VolumeService:
    if sys.platform == "win32" and QGuiApplication.platformName() == "windows":
        return _WinVolumeService(parent)
    return VolumeService(parent)


if sys.platform == "win32":
    from pycaw.callbacks import AudioEndpointVolumeCallback
    from pycaw.pycaw import AudioUtilities

    class _Callback(AudioEndpointVolumeCallback):
        def __init__(self, service: _WinVolumeService) -> None:
            super().__init__()
            self._service = service

        def on_notify(self, new_volume, new_mute, event_context, channels, channel_volumes):
            self._service._incoming.emit(float(new_volume), bool(new_mute))

    class _WinVolumeService(VolumeService):
        def __init__(self, parent: QObject | None = None) -> None:
            super().__init__(parent)
            self._endpoint = None
            self._callback = None
            self.refresh()

        def refresh(self) -> None:
            self.close()
            try:
                self._endpoint = AudioUtilities.GetSpeakers().EndpointVolume
                self._callback = _Callback(self)
                self._endpoint.RegisterControlChangeNotify(self._callback)
                self.available = True
                self._apply(
                    float(self._endpoint.GetMasterVolumeLevelScalar()),
                    bool(self._endpoint.GetMute()),
                )
            except (OSError, AttributeError):
                log.exception("volume: dispositivo de saída indisponível")
                self._endpoint = self._callback = None
                self.available = False

        def set_level(self, level: float) -> None:
            level = max(0.0, min(1.0, level))
            if self._endpoint is not None:
                self._endpoint.SetMasterVolumeLevelScalar(level, None)
                if self.muted and level > 0:
                    self._endpoint.SetMute(False, None)
            self._apply(level, self.muted and level == 0)

        def set_muted(self, muted: bool) -> None:
            if self._endpoint is not None:
                self._endpoint.SetMute(muted, None)
            self._apply(self.level, muted)

        def close(self) -> None:
            if self._endpoint is not None and self._callback is not None:
                try:
                    self._endpoint.UnregisterControlChangeNotify(self._callback)
                except OSError:
                    log.info("volume: falha ao remover o callback", exc_info=True)
            self._endpoint = self._callback = None
