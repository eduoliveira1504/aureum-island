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
