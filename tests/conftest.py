import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Nenhum teste toca a pasta de dados real."""
    path = tmp_path / "data"
    monkeypatch.setenv("AUREUM_ISLAND_DATA_DIR", str(path))
    return path


def _dispose_controller(ctrl, center=None):
    """Para animação e timers antes do qtbot destruir as janelas."""
    ctrl._stop_animation()
    ctrl.machine._listeners.clear()
    if center is not None:
        center._timer.stop()
        center.queue.clear()
        center.current = None


@pytest.fixture
def dispose():
    return _dispose_controller


APP_CMD = r'"C:\app\pythonw.exe" -m aureum_island'


class FakeRegistry:
    """Chave Run em memória (nenhum teste toca o registro real)."""

    def __init__(self):
        self.values: dict[str, str] = {}
        self.fail = False

    def get(self, name):
        return self.values.get(name)

    def set(self, name, value):
        if self.fail:
            raise OSError("acesso negado")
        self.values[name] = value

    def delete(self, name):
        if self.fail:
            raise OSError("acesso negado")
        self.values.pop(name, None)


class FakeHotkeyBackend:
    """RegisterHotKey falso: `taken` lista combinações em uso por outro app."""

    def __init__(self):
        self.taken: set = set()
        self.active = None

    def register(self, hotkey):
        if hotkey in self.taken:
            return False
        self.active = hotkey
        return True

    def unregister(self):
        self.active = None


@pytest.fixture
def settings_deps(qapp):
    from PySide6.QtCore import QObject, Signal

    from aureum_island.services.autostart import Autostart
    from aureum_island.services.hotkey import GlobalHotkey
    from aureum_island.services.sound import Sound
    from aureum_island.settings.store import SettingsStore

    class Events(QObject):
        hotkey = Signal(int)

    events = Events()
    backend = FakeHotkeyBackend()
    registry = FakeRegistry()
    deps = type("Deps", (), {})()
    deps.events = events
    deps.backend = backend
    deps.registry = registry
    deps.store = SettingsStore(None)
    deps.hotkey = GlobalHotkey(events, backend=backend)
    deps.hotkey.register(deps.store.value.hotkey)
    deps.autostart = Autostart(registry, cmd=APP_CMD)
    deps.sound = Sound()
    deps.sound.preview = lambda: None  # sem áudio nos testes
    return deps
