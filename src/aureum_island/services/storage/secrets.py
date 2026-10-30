"""Links ICS no cofre do Windows (keyring).

O link ICS secreto do Google dá acesso à agenda inteira: é segredo. Nunca vai
para JSON, log ou banco, nem aparece em mensagens de erro.
"""

from __future__ import annotations

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

SERVICE = "Aureum Island"


class SecretStoreError(RuntimeError):
    """Falha ao acessar o cofre. A mensagem nunca contém o segredo."""


def _key(source_id: int) -> str:
    return f"ics:{int(source_id)}"


def set_ics_url(source_id: int, url: str) -> None:
    try:
        keyring.set_password(SERVICE, _key(source_id), url)
    except KeyringError:
        # 'from None': a exceção original poderia carregar o link.
        raise SecretStoreError(
            f"não foi possível salvar o link da fonte ICS {source_id} no cofre"
        ) from None


def get_ics_url(source_id: int) -> str | None:
    try:
        return keyring.get_password(SERVICE, _key(source_id))
    except KeyringError:
        raise SecretStoreError(
            f"não foi possível ler o link da fonte ICS {source_id} no cofre"
        ) from None


def delete_all_ics_urls() -> int:
    """Apaga todos os links ICS do cofre, mesmo sem o banco (desinstalação). Devolve
    quantos apagou. O keyring grava o alvo como 'Aureum Island' ou 'ics:N@Aureum Island'."""
    from win32ctypes.pywin32 import pywintypes, win32cred

    try:
        creds = win32cred.CredEnumerate()
    except pywintypes.error:
        return 0  # cofre vazio
    targets = [
        c["TargetName"]
        for c in creds
        if c.get("Type") == win32cred.CRED_TYPE_GENERIC
        and str(c.get("UserName") or "").startswith("ics:")
        and (c["TargetName"] == SERVICE or c["TargetName"].endswith(f"@{SERVICE}"))
    ]
    removed = 0
    for target in targets:
        try:
            win32cred.CredDelete(Type=win32cred.CRED_TYPE_GENERIC, TargetName=target)
            removed += 1
        except pywintypes.error:
            pass
    return removed


def delete_ics_url(source_id: int) -> None:
    try:
        keyring.delete_password(SERVICE, _key(source_id))
    except PasswordDeleteError:
        return  # já não existia
    except KeyringError:
        raise SecretStoreError(
            f"não foi possível apagar o link da fonte ICS {source_id} no cofre"
        ) from None
