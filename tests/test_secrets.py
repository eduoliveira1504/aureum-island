import logging

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import KeyringError, PasswordDeleteError

from aureum_island.services.storage import secrets

URL = "https://calendar.google.com/calendar/ical/x%40gmail.com/private-abc123/basic.ics"


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.store: dict[tuple[str, str], str] = {}
        self.fail = False

    def _check(self, password=None):
        if self.fail:
            raise KeyringError(f"cofre indisponível ({password})")

    def get_password(self, service, username):
        self._check()
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self._check(password)
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        self._check()
        if (service, username) not in self.store:
            raise PasswordDeleteError("não existe")
        del self.store[(service, username)]


@pytest.fixture
def memory_keyring():
    previous = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


def test_roundtrip(memory_keyring):
    secrets.set_ics_url(7, URL)
    assert memory_keyring.store == {("Aureum Island", "ics:7"): URL}
    assert secrets.get_ics_url(7) == URL
    secrets.delete_ics_url(7)
    assert secrets.get_ics_url(7) is None
    secrets.delete_ics_url(7)  # apagar de novo não quebra


def test_url_never_leaks_in_errors_or_logs(memory_keyring, caplog):
    memory_keyring.fail = True
    caplog.set_level(logging.DEBUG)
    with pytest.raises(secrets.SecretStoreError) as info:
        secrets.set_ics_url(7, URL)
    assert URL not in str(info.value)
    assert URL not in repr(info.value)
    assert info.value.__cause__ is None
    assert info.value.__suppress_context__
    assert URL not in caplog.text


def test_delete_all_ics_urls_only_touches_our_links(monkeypatch):
    # Cofre falso: o teste nunca mexe no Gerenciador de Credenciais de verdade.
    win32ctypes = pytest.importorskip("win32ctypes.pywin32")
    generic = 1

    class FakeCred:
        CRED_TYPE_GENERIC = generic

        def __init__(self):
            self.creds = [
                {"Type": generic, "TargetName": "Aureum Island", "UserName": "ics:1"},
                {"Type": generic, "TargetName": "ics:2@Aureum Island", "UserName": "ics:2"},
                {"Type": generic, "TargetName": "Outro App", "UserName": "ics:1"},
                {"Type": generic, "TargetName": "x@Aureum Island", "UserName": "x"},
            ]

        def CredEnumerate(self):
            return list(self.creds)

        def CredDelete(self, Type, TargetName):
            self.creds = [c for c in self.creds if c["TargetName"] != TargetName]

    fake = FakeCred()
    monkeypatch.setattr(win32ctypes, "win32cred", fake)
    assert secrets.delete_all_ics_urls() == 2
    assert [c["TargetName"] for c in fake.creds] == ["Outro App", "x@Aureum Island"]
