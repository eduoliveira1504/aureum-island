import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta, timezone

import pytest

from aureum_island.services.storage import db, paths, settings
from aureum_island.services.storage.settings import Settings
from aureum_island.services.storage.tasks import TaskRepo

TABLES = {"tasks", "events", "ics_sources", "water_log", "reminders_fired", "schema_version"}


# --- pasta de dados ----------------------------------------------------------


def test_data_dir_uses_override(isolated_data_dir):
    assert paths.data_dir() == isolated_data_dir
    assert isolated_data_dir.is_dir()


# --- banco -------------------------------------------------------------------


def test_migration_from_scratch(tmp_path):
    conn = db.connect(tmp_path / "data.db")
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert names >= TABLES
    assert db.schema_version(conn) == len(db.MIGRATIONS)
    conn.close()


def test_migration_is_idempotent(tmp_path):
    path = tmp_path / "data.db"
    db.connect(path).close()
    conn = db.connect(path)
    rows = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    assert rows == len(db.MIGRATIONS)
    conn.close()


def test_lyrics_cache_dropped_on_upgrade(tmp_path, monkeypatch):
    path = tmp_path / "data.db"
    monkeypatch.setattr(db, "MIGRATIONS", db.MIGRATIONS[:4])  # banco do Bloco 5
    old = db.connect(path)
    old.execute("INSERT INTO lyrics_cache VALUES ('k', 'plain', 'oi', 2, 'x', 'x')")
    old.commit()
    old.close()
    monkeypatch.undo()
    conn = db.connect(path)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
    assert "lyrics_cache" not in names and "lyrics_cache_lru" not in names
    assert db.schema_version(conn) == 5
    conn.close()


def test_old_lyrics_setting_is_ignored(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"lyrics_enabled": False, "mode": "minimal"}), encoding="utf-8")
    loaded = settings.load(path)
    assert loaded.mode == "minimal"
    assert "lyrics_enabled" not in settings.to_dict(loaded)


def test_failed_migration_rolls_back(tmp_path, monkeypatch):
    path = tmp_path / "data.db"
    db.connect(path).close()
    monkeypatch.setattr(db, "MIGRATIONS", [*db.MIGRATIONS, "CREATE TABLE ok (x); SELECT nope("])
    with pytest.raises(sqlite3.OperationalError):
        db.connect(path)
    raw = sqlite3.connect(path)
    names = {r[0] for r in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "ok" not in names
    assert (
        raw.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        == len(db.MIGRATIONS) - 1
    )
    raw.close()


def test_datetimes_stored_as_utc():
    brt = timezone(timedelta(hours=-3))
    local = datetime(2026, 10, 29, 15, 0, tzinfo=brt)
    assert db.to_db(local) == "2026-10-29T18:00:00Z"
    assert db.from_db("2026-10-29T18:00:00Z") == datetime(2026, 10, 29, 18, 0, tzinfo=UTC)
    with pytest.raises(ValueError):
        db.to_db(datetime(2026, 10, 29, 15, 0))


def test_tasks_crud(tmp_path):
    conn = db.connect(tmp_path / "data.db")
    repo = TaskRepo(conn)
    due = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)

    task = repo.add("  Comprar café  ", due_at=due, remind_offset_min=10)
    assert task.title == "Comprar café"
    assert task.due_at == due
    assert not task.done

    assert repo.rename(task.id, "Comprar pó de café").title == "Comprar pó de café"
    assert repo.set_done(task.id).done
    assert repo.list_tasks(include_done=False) == []
    assert repo.set_done(task.id, done=False).done_at is None

    other = repo.add("Sem horário")
    assert [t.id for t in repo.list_tasks()] == [task.id, other.id]

    assert repo.delete(task.id)
    assert repo.get(task.id) is None
    assert not repo.delete(task.id)
    with pytest.raises(ValueError):
        repo.add("   ")
    conn.close()


# --- settings.json -----------------------------------------------------------


def test_settings_defaults_when_missing(tmp_path):
    loaded = settings.load(tmp_path / "settings.json")
    assert loaded == Settings()
    assert loaded.hotkey == "Ctrl+Alt+I"
    assert loaded.hide_on_fullscreen is True


def test_settings_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    changed = Settings().with_changes(mode="minimal", last_page="water", accent="#8B5CF6")
    settings.save(changed, path)
    assert settings.load(path) == changed
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == settings.SCHEMA_VERSION


def test_corrupted_settings_fall_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ isso não é json", encoding="utf-8")
    assert settings.load(path) == Settings()
    assert (tmp_path / "settings.json.corrupt").exists()


def test_invalid_and_unknown_values_fall_back(tmp_path):
    path = tmp_path / "settings.json"
    raw = {
        "schema_version": 1,
        "mode": "gigante",
        "last_page": "tasks",
        "hide_on_fullscreen": "sim",
        "hotkey": "   ",
        "accent": "dourado",
        "notch_bg": "grafite",  # chave removida (0009): ignorada
        "chave_nova": 42,
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    loaded = settings.load(path)
    assert loaded == Settings(last_page="tasks")


def test_non_object_settings_fall_back(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert settings.load(path) == Settings()


def test_atomic_write_keeps_old_file_on_failure(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    original = Settings().with_changes(mode="minimal")
    settings.save(original, path)

    def boom(src, dst):
        raise OSError("disco cheio")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        settings.save(Settings().with_changes(last_page="calendar"), path)
    monkeypatch.undo()

    assert settings.load(path) == original
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]


def test_old_default_hotkey_migrates(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"schema_version": 1, "hotkey": "Ctrl+Alt+Space"}), encoding="utf-8")
    assert settings.load(path).hotkey == "Ctrl+Alt+I"


def test_custom_hotkey_survives_migration(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"schema_version": 1, "hotkey": "Ctrl+Alt+N"}), encoding="utf-8")
    assert settings.load(path).hotkey == "Ctrl+Alt+N"
