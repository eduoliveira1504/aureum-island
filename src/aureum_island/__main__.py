"""Ponto de entrada: `python -m aureum_island`.

Bloco 0: só registra as fontes, mostra a pasta de dados e sai.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtGui import QGuiApplication

from aureum_island.services.storage import db, paths, settings
from aureum_island.theme.fonts import register_fonts


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = QGuiApplication(sys.argv)
    app.setApplicationName(paths.APP_NAME)

    families = register_fonts()
    data = paths.data_dir()
    current = settings.load(paths.settings_path())
    conn = db.connect(paths.db_path())
    version = db.schema_version(conn)
    conn.close()

    print(f"Fontes: {', '.join(families) or 'nenhuma'}")
    print(f"Pasta de dados: {data}")
    print(f"Banco: schema v{version} | modo: {current.mode} | accent: {current.accent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
