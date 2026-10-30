"""data.db (SQLite): conexão, migrações numeradas e conversão de datas.

Datas ficam em UTC, ISO 8601 com 'Z'. Conversão para o fuso local só na UI.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

# Cada item é uma migração. Nunca editar uma migração já publicada: adicionar outra.
MIGRATIONS: list[str] = [
    # 1: tabelas iniciais
    """
    CREATE TABLE tasks (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        due_at TEXT,
        remind_offset_min INTEGER,
        done_at TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE ics_sources (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        color TEXT NOT NULL,
        last_sync_at TEXT
    );

    CREATE TABLE events (
        id INTEGER PRIMARY KEY,
        source TEXT NOT NULL CHECK (source IN ('local', 'ics')),
        source_id INTEGER REFERENCES ics_sources(id) ON DELETE CASCADE,
        uid TEXT NOT NULL,
        title TEXT NOT NULL,
        start_at TEXT NOT NULL,
        end_at TEXT,
        all_day INTEGER NOT NULL DEFAULT 0,
        location TEXT,
        remind_offset_min INTEGER
    );
    CREATE UNIQUE INDEX events_identity
        ON events (source, IFNULL(source_id, 0), uid, start_at);
    CREATE INDEX events_start ON events (start_at);

    CREATE TABLE water_log (
        id INTEGER PRIMARY KEY,
        ml INTEGER NOT NULL CHECK (ml > 0),
        at TEXT NOT NULL
    );
    CREATE INDEX water_log_at ON water_log (at);

    CREATE TABLE reminders_fired (
        item_type TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        fire_at TEXT NOT NULL,
        fired_at TEXT,
        PRIMARY KEY (item_type, item_id, fire_at)
    );
    """,
    # 2: adiar avisos de tarefa ("+10 min")
    """
    ALTER TABLE tasks ADD COLUMN snoozed_until TEXT;
    """,
    # 3: cache de letras (LRCLIB)
    """
    CREATE TABLE lyrics_cache (
        key TEXT PRIMARY KEY,
        status TEXT NOT NULL CHECK (status IN ('synced', 'plain', 'instrumental', 'not_found')),
        content TEXT NOT NULL DEFAULT '',
        size INTEGER NOT NULL DEFAULT 0,
        fetched_at TEXT NOT NULL,
        last_used_at TEXT NOT NULL
    );
    CREATE INDEX lyrics_cache_lru ON lyrics_cache (last_used_at);
    """,
    # 4: estado da sincronização ICS (cache HTTP e última tentativa)
    """
    ALTER TABLE ics_sources ADD COLUMN etag TEXT;
    ALTER TABLE ics_sources ADD COLUMN last_modified TEXT;
    ALTER TABLE ics_sources ADD COLUMN parsed_at TEXT;
    ALTER TABLE ics_sources ADD COLUMN last_attempt_at TEXT;
    ALTER TABLE ics_sources ADD COLUMN last_status TEXT;
    """,
    # 5: sem letras (ver 0008): o cache da migração 3 sai
    """
    DROP INDEX IF EXISTS lyrics_cache_lru;
    DROP TABLE IF EXISTS lyrics_cache;
    """,
]


def connect(path: Path | str) -> sqlite3.Connection:
    """Abre o banco e aplica as migrações pendentes."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    migrate(conn)
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return row[0] or 0


def migrate(conn: sqlite3.Connection) -> int:
    """Aplica as migrações que faltam, cada uma numa transação. Devolve a versão final."""
    current = schema_version(conn)
    conn.commit()
    for number, script in enumerate(MIGRATIONS, start=1):
        if number <= current:
            continue
        try:
            conn.executescript(
                f"BEGIN;\n{script}\nINSERT INTO schema_version (version) VALUES ({number});\n"
                "COMMIT;"
            )
        except sqlite3.Error:
            conn.rollback()
            raise
        current = number
    return current


def to_db(dt: datetime) -> str:
    """datetime com fuso -> texto UTC ISO 8601 ('2026-10-29T18:00:00Z')."""
    if dt.tzinfo is None:
        raise ValueError("datetime sem fuso; use um datetime com tzinfo")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_db(value: str | None) -> datetime | None:
    """Texto do banco -> datetime em UTC."""
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)
