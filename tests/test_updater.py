"""Atualização automática: escolha do release, download conferido e instalação."""

import hashlib

import pytest

from aureum_island.services import updater as up
from aureum_island.services.updater import Updater, is_newer, parse_version, pick_release

INSTALLER = b"MZ instalador falso da 0.2.0" * 100
SHA = hashlib.sha256(INSTALLER).hexdigest()


def release_payload(tag="v0.2.0", data=INSTALLER, digest=None, **extra):
    return {
        "tag_name": tag,
        "draft": False,
        "prerelease": False,
        "assets": [
            {"name": "notas.txt", "size": 3, "digest": "sha256:00", "browser_download_url": "x"},
            {
                "name": f"AureumIsland-Setup-{tag.lstrip('v')}.exe",
                "size": len(data),
                "digest": digest if digest is not None else f"sha256:{SHA}",
                "browser_download_url": f"https://example.invalid/{tag}.exe",
            },
        ],
        **extra,
    }


class FakeHttp:
    def __init__(self, payload, data=INSTALLER, ok=True):
        self.payload, self.data, self.ok = payload, data, ok
        self.checks = 0
        self.downloads = []

    def get_json(self, url, callback):
        assert url == up.LATEST_URL
        self.checks += 1
        callback(self.payload)

    def download(self, url, path, callback):
        self.downloads.append(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.data)
        callback(self.ok)


@pytest.fixture
def make(tmp_path, qapp):
    def factory(http, current="0.1.0"):
        u = Updater(tmp_path / "updates", current=current, enabled=True, http=http)
        got = []
        u.ready.connect(got.append)
        return u, got

    return factory


def test_versions():
    assert parse_version("v0.2.0") == (0, 2, 0)
    assert parse_version("0.2.0-beta.1") is None  # pré-release não conta
    assert is_newer("v0.2.0", "0.1.0")
    assert is_newer("0.10.0", "0.9.9")
    assert is_newer("1.0", "0.9.9")
    assert not is_newer("v0.1.0", "0.1.0")
    assert not is_newer("v0.0.9", "0.1.0")


def test_pick_release_needs_newer_installer_with_sha256():
    r = pick_release(release_payload(), "0.1.0")
    assert (r.version, r.name, r.sha256) == ("0.2.0", "AureumIsland-Setup-0.2.0.exe", SHA)
    assert pick_release(release_payload(), "0.2.0") is None
    assert pick_release(release_payload(digest=""), "0.1.0") is None  # sem SHA-256: recusa
    assert pick_release(release_payload(prerelease=True), "0.1.0") is None
    assert pick_release(release_payload(draft=True), "0.1.0") is None
    assert pick_release({"message": "rate limit"}, "0.1.0") is None
    assert pick_release(None, "0.1.0") is None


def test_downloads_verifies_and_gets_ready(make, tmp_path):
    http = FakeHttp(release_payload())
    u, got = make(http)
    u.check()
    assert got == ["0.2.0"]
    assert u.installer == tmp_path / "updates" / "AureumIsland-Setup-0.2.0.exe"
    assert u.installer.read_bytes() == INSTALLER
    assert not list((tmp_path / "updates").glob("*.part"))
    u.check()  # já pronta: não baixa de novo nem avisa de novo
    assert len(http.downloads) == 1 and got == ["0.2.0"]


def test_tampered_download_is_discarded(make, tmp_path):
    http = FakeHttp(release_payload(), data=b"MZ outro arquivo" * 100)
    http.payload["assets"][1]["size"] = len(http.data)  # mesmo tamanho, hash diferente
    u, got = make(http)
    u.check()
    assert got == [] and u.ready_version is None
    assert not any((tmp_path / "updates").iterdir())


def test_offline_or_failed_download_tries_again_later(make):
    http = FakeHttp(None)  # sem internet
    u, got = make(http)
    u.check()
    assert got == []
    http.payload, http.ok = release_payload(), False
    u.check()
    assert got == []
    http.ok = True
    u.check()
    assert got == ["0.2.0"]


def test_reuses_installer_downloaded_before(make, tmp_path):
    folder = tmp_path / "updates"
    folder.mkdir()
    (folder / "AureumIsland-Setup-0.2.0.exe").write_bytes(INSTALLER)
    http = FakeHttp(release_payload())
    u, got = make(http)
    u.check()
    assert got == ["0.2.0"] and http.downloads == []


def test_cleans_installers_already_installed(tmp_path, qapp):
    folder = tmp_path / "updates"
    folder.mkdir()
    for name in ("AureumIsland-Setup-0.1.0.exe", "AureumIsland-Setup-0.2.0.exe", "x.exe.part"):
        (folder / name).write_bytes(b"x")
    u = Updater(folder, current="0.2.0", enabled=True, http=FakeHttp(None))
    u.start()
    u._timer.stop()
    assert sorted(p.name for p in folder.iterdir()) == []


def test_disabled_outside_installed_app(tmp_path, qapp):
    http = FakeHttp(release_payload())
    u = Updater(tmp_path, current="0.1.0", enabled=False, http=http)
    u.start()
    assert not u._timer.isActive() and http.checks == 0


def test_launches_installer_silently(make, monkeypatch):
    calls = []
    monkeypatch.setattr(up.subprocess, "Popen", lambda args, **kw: calls.append(args))
    u, _ = make(FakeHttp(release_payload()))
    assert u.launch_installer(relaunch=True) is False  # nada pronto ainda
    u.check()
    assert u.launch_installer(relaunch=True)
    assert u.launch_installer(relaunch=False)
    assert calls[0][1:] == ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH=1"]
    assert calls[1][-1] == "/RELAUNCH=0"
