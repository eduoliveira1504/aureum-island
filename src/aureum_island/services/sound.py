"""Som dos avisos (QSoundEffect, QtMultimedia do PySide6)."""

from __future__ import annotations

import logging
from importlib import resources

from PySide6.QtCore import QObject, QUrl

log = logging.getLogger(__name__)


class Sound(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.enabled = True
        self.volume = 0.6
        self._effect = None  # criado no primeiro uso

    def configure(self, *, enabled: bool, volume: float) -> None:
        self.enabled = enabled
        self.volume = volume

    def preload(self) -> None:
        """Carrega o .wav antes do primeiro aviso (o QSoundEffect carrega assíncrono)."""
        if self._effect is None:
            from PySide6.QtMultimedia import QSoundEffect

            path = resources.files("aureum_island.assets.sounds").joinpath("chime.wav")
            self._effect = QSoundEffect(self)
            self._effect.setSource(QUrl.fromLocalFile(str(path)))

    def play(self) -> None:
        if not self.enabled or self.volume <= 0:
            return
        self.preload()
        self._effect.setVolume(self.volume)
        self._effect.play()
        log.debug("som do aviso")
