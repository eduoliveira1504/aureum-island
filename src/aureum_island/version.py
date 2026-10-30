"""Versão do app (do pacote instalado; no executável vem do dist-info empacotado) e o
User-Agent dos pedidos externos (links ICS e releases do GitHub)."""

from __future__ import annotations

from importlib import metadata

HOMEPAGE = "https://github.com/eduoliveira1504/aureum-island"


def app_version() -> str:
    try:
        return metadata.version("aureum-island")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def user_agent() -> str:
    return f"AureumIsland/{app_version()} ({HOMEPAGE})"
