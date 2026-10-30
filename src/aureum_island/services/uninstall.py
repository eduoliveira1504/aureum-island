"""Limpeza pedida pelo desinstalador: `AureumIsland.exe --uninstall-cleanup [...]`.

O desinstalador (packaging/aureum-island.iss) pergunta cada parte ao usuário e só passa
a flag do que ele confirmou. Sem flag nenhuma, nada é apagado. Ver
docs/decisions/0011-empacotamento.md.
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)


def cleanup(
    *,
    autostart: bool = False,
    secrets: bool = False,
    data: bool = False,
    remove_autostart: Callable[[], object] | None = None,
    remove_secrets: Callable[[], object] | None = None,
    data_dir: Path | None = None,
) -> bool:
    """Remove só o que foi pedido. Devolve False se alguma parte falhou (as outras
    seguem mesmo assim)."""
    ok = True
    if autostart:
        try:
            if remove_autostart is None:
                from aureum_island.services.autostart import VALUE_NAME, RunKey

                RunKey().delete(VALUE_NAME)
            else:
                remove_autostart()
        except OSError:
            log.exception("desinstalação: não foi possível remover o início automático")
            ok = False
    if secrets:
        try:
            if remove_secrets is None:
                from aureum_island.services.storage.secrets import delete_all_ics_urls

                delete_all_ics_urls()
            else:
                remove_secrets()
        except Exception:  # o cofre pode falhar de vários jeitos; segue com o resto
            log.exception("desinstalação: não foi possível apagar os links ICS do cofre")
            ok = False
    if data:
        if data_dir is None:
            from aureum_island.services.storage import paths

            data_dir = paths.data_dir()
        try:
            shutil.rmtree(data_dir)
        except FileNotFoundError:
            pass
        except OSError:
            log.exception("desinstalação: não foi possível apagar a pasta de dados")
            ok = False
    return ok
