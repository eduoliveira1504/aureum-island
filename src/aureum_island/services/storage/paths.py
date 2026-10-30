"""Pasta de dados do app."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QStandardPaths

APP_NAME = "Aureum Island"

# Override só para testes e depuração; não aparece para o usuário.
DATA_DIR_ENV = "AUREUM_ISLAND_DATA_DIR"


def updates_dir() -> Path:
    """Instaladores baixados pela atualização automática. Em %LOCALAPPDATA% (cache, não
    vai junto num perfil móvel do Windows)."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override) / "updates"
    location = QStandardPaths.StandardLocation.GenericCacheLocation
    return Path(QStandardPaths.writableLocation(location)) / APP_NAME / "updates"


def data_dir() -> Path:
    """%APPDATA%/Aureum Island (criada se não existir)."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        path = Path(override)
    else:
        # Sem organização, o Qt monta <AppData>/<applicationName>.
        QCoreApplication.setOrganizationName("")
        QCoreApplication.setApplicationName(APP_NAME)
        location = QStandardPaths.StandardLocation.AppDataLocation
        path = Path(QStandardPaths.writableLocation(location))
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return data_dir() / "settings.json"


def db_path() -> Path:
    return data_dir() / "data.db"
