import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Nenhum teste toca a pasta de dados real."""
    path = tmp_path / "data"
    monkeypatch.setenv("AUREUM_ISLAND_DATA_DIR", str(path))
    return path
