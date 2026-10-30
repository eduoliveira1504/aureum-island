"""Configurações em memória + settings.json, com aviso das chaves que mudaram.

A janela de Configurações grava aqui; o app escuta `changed` e aplica na hora.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from aureum_island.services.storage import settings
from aureum_island.services.storage.settings import Settings, is_valid

log = logging.getLogger(__name__)


class SettingsStore(QObject):
    changed = Signal(object)  # frozenset com as chaves que mudaram

    def __init__(
        self, path: Path | None, value: Settings | None = None, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._path = path
        if value is not None:
            self.value = value
        else:
            self.value = settings.load(path) if path is not None else Settings()

    def update(self, **changes: object) -> Settings:
        """Aplica e grava. Valor inválido levanta ValueError (nada muda)."""
        for key, value in changes.items():
            if not is_valid(key, value):
                raise ValueError(f"configuração inválida: {key}")
        new = self.value.with_changes(**changes)
        keys = frozenset(k for k in changes if getattr(new, k) != getattr(self.value, k))
        self.value = new
        if self._path is not None:
            try:
                settings.save(new, self._path)
            except OSError:
                log.exception("não foi possível salvar as configurações")
        if keys:
            self.changed.emit(keys)
        return new
