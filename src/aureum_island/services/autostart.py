"""Iniciar com o Windows: valor em HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.

Sem admin. Instalado (PyInstaller, sys.frozen), o comando é o AureumIsland.exe. Pelo
código, o pythonw.exe do mesmo Python que roda o app (no .venv), sem janela de console.
Ver docs/decisions/0007-configuracoes.md e 0011-empacotamento.md.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Protocol

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Aureum Island"


def command(executable: str | None = None, frozen: bool | None = None) -> str:
    """'"...\\Aureum Island\\AureumIsland.exe"' instalado;
    '"...\\.venv\\Scripts\\pythonw.exe" -m aureum_island' pelo código."""
    exe = Path(executable or sys.executable)
    if frozen if frozen is not None else getattr(sys, "frozen", False):
        return f'"{exe}"'
    pythonw = exe.with_name("pythonw.exe")
    if exe.name.lower() == "python.exe" and pythonw.exists():
        exe = pythonw
    return f'"{exe}" -m aureum_island'


class Registry(Protocol):
    def get(self, name: str) -> str | None: ...
    def set(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...


class RunKey:
    """Chave Run do usuário atual (winreg)."""

    def get(self, name: str) -> str | None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _kind = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            return None
        return value if isinstance(value, str) else None

    def set(self, name: str, value: str) -> None:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

    def delete(self, name: str) -> None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass


class Autostart:
    def __init__(self, registry: Registry | None = None, cmd: str | None = None) -> None:
        self._registry = registry if registry is not None else RunKey()
        self._command = cmd or command()

    def set_enabled(self, enabled: bool) -> bool:
        """Liga ou desliga. Devolve False se o registro recusou (fica como estava)."""
        try:
            if enabled:
                self._registry.set(VALUE_NAME, self._command)
            else:
                self._registry.delete(VALUE_NAME)
        except OSError:
            log.exception("início automático: não foi possível alterar o registro")
            return False
        return True

    def repair(self) -> bool:
        """Com a opção ligada: corrige a entrada se o caminho mudou (pasta movida) ou sumiu.
        Devolve True se precisou corrigir."""
        try:
            current = self._registry.get(VALUE_NAME)
        except OSError:
            log.exception("início automático: não foi possível ler o registro")
            return False
        if current == self._command:
            return False
        log.info("início automático: entrada corrigida para o caminho atual")
        return self.set_enabled(True)
