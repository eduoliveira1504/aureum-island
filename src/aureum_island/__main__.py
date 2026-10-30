"""Ponto de entrada: `python -m aureum_island [--debug-paint]`."""

from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtWidgets import QApplication

from aureum_island.island import debug
from aureum_island.services.single_instance import SingleInstance
from aureum_island.services.storage import paths
from aureum_island.theme.fonts import register_fonts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aureum_island")
    parser.add_argument(
        "--debug-paint",
        action="store_true",
        help="loga cada paintEvent e cada checagem de tela cheia",
    )
    # Só o desinstalador usa: limpa o que o usuário confirmou e sai, sem abrir a UI.
    parser.add_argument("--uninstall-cleanup", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--autostart", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--secrets", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--data", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if args.uninstall_cleanup:
        from aureum_island.services.uninstall import cleanup

        ok = cleanup(autostart=args.autostart, secrets=args.secrets, data=args.data)
        return 0 if ok else 1

    app = QApplication(sys.argv[:1])
    app.setApplicationName(paths.APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    instance = SingleInstance(paths.data_dir() / "instance.lock")
    if not instance.acquire():
        # Já existe um Aureum Island rodando: ele abre o notch e esta sai.
        if not instance.notify():
            logging.getLogger(__name__).warning("instância única: a outra não respondeu")
        return 0

    register_fonts()
    if args.debug_paint:
        debug.enable(app)

    # Import tardio: os módulos da UI criam fontes e precisam do app pronto.
    from aureum_island.app import AureumIsland

    island = AureumIsland(app, debug_paint=args.debug_paint)
    instance.activated.connect(island.controller.open)
    island.start()
    try:
        return app.exec()
    finally:
        instance.release()


if __name__ == "__main__":
    sys.exit(main())
