"""Ponto de entrada do executável (PyInstaller). Igual a `python -m aureum_island`."""

import sys

from aureum_island.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
