"""Ponto de entrada: `python -m aureum_island [--debug-paint]`."""

from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtWidgets import QApplication

from aureum_island.island import debug
from aureum_island.services.storage import paths
from aureum_island.theme.fonts import register_fonts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aureum_island")
    parser.add_argument(
        "--debug-paint",
        action="store_true",
        help="loga cada paintEvent e cada checagem de tela cheia",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    app = QApplication(sys.argv[:1])
    app.setApplicationName(paths.APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    register_fonts()
    if args.debug_paint:
        debug.enable(app)

    # Import tardio: os módulos da UI criam fontes e precisam do app pronto.
    from aureum_island.app import AureumIsland

    island = AureumIsland(app, debug_paint=args.debug_paint)
    island.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
