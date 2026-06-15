from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    system_prompt TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL,
    model TEXT,
    model_provider TEXT NOT NULL DEFAULT '',
    api_key TEXT NOT NULL DEFAULT '',
    workspace TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    heartbeat_enabled INTEGER NOT NULL DEFAULT 1,
    heartbeat_interval INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('chain', 'fanout', 'workflow')),
    agent_ids TEXT NOT NULL,
    leader_agent TEXT NOT NULL DEFAULT '',
    max_rounds INTEGER NOT NULL DEFAULT 1,
    stop_when_idle INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_workflows (
    id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    definition TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(team_id, id),
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target TEXT NOT NULL,
    content TEXT NOT NULL,
    sender TEXT NOT NULL DEFAULT 'api',
    metadata TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    result TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'todo',
    assignee TEXT,
    assignee_type TEXT NOT NULL DEFAULT '',
    project_id TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    prefix TEXT NOT NULL DEFAULT 'PS',
    color TEXT NOT NULL DEFAULT '#84cc16',
    workspace TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_comments (
    id TEXT PRIMARY KEY,
    task_id INTEGER NOT NULL,
    author TEXT NOT NULL,
    author_type TEXT NOT NULL DEFAULT 'user',
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    cron TEXT NOT NULL DEFAULT '',
    run_at TEXT,
    agent_id TEXT NOT NULL,
    message TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'web',
    sender TEXT NOT NULL DEFAULT 'Web',
    enabled INTEGER NOT NULL DEFAULT 1,
    last_fired_at INTEGER,
    last_fire_key TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    role TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'web',
    sender TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'web',
    sender TEXT NOT NULL DEFAULT '',
    sender_id TEXT,
    message TEXT NOT NULL,
    original_message TEXT NOT NULL DEFAULT '',
    agent TEXT,
    files TEXT,
    metadata TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at INTEGER NOT NULL,
    acked_at INTEGER
);

CREATE TABLE IF NOT EXISTS pairing_pending (
    code TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS pairing_approved (
    channel TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    approved_at INTEGER NOT NULL,
    approved_code TEXT,
    PRIMARY KEY(channel, sender_id)
);

CREATE TABLE IF NOT EXISTS channel_defaults (
    channel TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    target TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY(channel, sender_id)
);

CREATE TABLE IF NOT EXISTS custom_providers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    harness TEXT NOT NULL,
    base_url TEXT NOT NULL DEFAULT '',
    api_key TEXT NOT NULL DEFAULT '',
    model TEXT
);

CREATE TABLE IF NOT EXISTS heartbeat_state (
    agent_id TEXT PRIMARY KEY,
    last_sent_at INTEGER NOT NULL,
    last_message_id INTEGER,
    FOREIGN KEY(agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, path: Path, journal_mode: str = "MEMORY") -> None:
        self.path = path
        self.journal_mode = journal_mode
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA journal_mode = {self.journal_mode}")
        return conn

    def initialize(self) -> None:
        try:
            with self.connect() as conn:
                conn.executescript(SCHEMA)
                self._migrate(conn)
        except sqlite3.OperationalError as exc:
            if self.journal_mode.upper() == "OFF":
                raise
            self.journal_mode = "OFF"
            for suffix in ("", "-journal", "-wal", "-shm"):
                stale_path = Path(f"{self.path}{suffix}")
                if stale_path.exists():
                    stale_path.unlink()
            with self.connect() as conn:
                conn.executescript(SCHEMA)
                self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        self._add_column(conn, "tasks", "number", "INTEGER NOT NULL DEFAULT 0")
        self._add_column(conn, "messages", "metadata", "TEXT NOT NULL DEFAULT '{}'")
        self._add_column(conn, "tasks", "assignee_type", "TEXT NOT NULL DEFAULT ''")
        self._add_column(conn, "tasks", "project_id", "TEXT")
        self._add_column(conn, "tasks", "position", "INTEGER NOT NULL DEFAULT 0")
        self._add_column(conn, "projects", "workspace", "TEXT")
        self._add_column(conn, "schedules", "last_fired_at", "INTEGER")
        self._add_column(conn, "schedules", "last_fire_key", "TEXT")
        self._add_column(conn, "agents", "heartbeat_enabled", "INTEGER NOT NULL DEFAULT 1")
        self._add_column(conn, "agents", "heartbeat_interval", "INTEGER")
        self._add_column(conn, "agents", "model_provider", "TEXT NOT NULL DEFAULT ''")
        self._add_column(conn, "agents", "api_key", "TEXT NOT NULL DEFAULT ''")
        self._add_column(conn, "teams", "leader_agent", "TEXT NOT NULL DEFAULT ''")
        self._add_column(conn, "teams", "max_rounds", "INTEGER NOT NULL DEFAULT 1")
        self._add_column(conn, "teams", "stop_when_idle", "INTEGER NOT NULL DEFAULT 1")
        self._migrate_team_mode_check(conn)
        self._migrate_agent_model_provider(conn)
        self._backfill_task_numbers(conn)

    @staticmethod
    def _add_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _migrate_team_mode_check(conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'teams'").fetchone()
        create_sql = row["sql"] if row else ""
        if "'workflow'" in create_sql:
            return
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            """
            CREATE TABLE teams_new (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mode TEXT NOT NULL CHECK (mode IN ('chain', 'fanout', 'workflow')),
                agent_ids TEXT NOT NULL,
                leader_agent TEXT NOT NULL DEFAULT '',
                max_rounds INTEGER NOT NULL DEFAULT 1,
                stop_when_idle INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO teams_new (
                id, name, mode, agent_ids, leader_agent, max_rounds, stop_when_idle, created_at, updated_at
            )
            SELECT id, name, mode, agent_ids, leader_agent, max_rounds, stop_when_idle, created_at, updated_at
            FROM teams
            """
        )
        conn.execute("DROP TABLE teams")
        conn.execute("ALTER TABLE teams_new RENAME TO teams")
        conn.execute("PRAGMA foreign_keys = ON")

    @staticmethod
    def _migrate_agent_model_provider(conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(agents)").fetchall()}
        if "nanobot_provider" in columns:
            conn.execute(
                """
                UPDATE agents
                SET model_provider = COALESCE(NULLIF(model_provider, ''), nanobot_provider),
                    api_key = COALESCE(NULLIF(api_key, ''), nanobot_api_key),
                    model = COALESCE(NULLIF(model, ''), nanobot_model)
                WHERE
                    (model_provider IS NULL OR model_provider = '')
                    OR (api_key IS NULL OR api_key = '')
                    OR (model IS NULL OR model = '')
                """
            )

    @staticmethod
    def _backfill_task_numbers(conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT id, project_id
            FROM tasks
            WHERE number = 0
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
        counters: dict[str, int] = {}
        for row in rows:
            key = row["project_id"] or "__global__"
            if key not in counters:
                if row["project_id"]:
                    current = conn.execute(
                        "SELECT COALESCE(MAX(number), 0) FROM tasks WHERE project_id = ? AND number > 0",
                        (row["project_id"],),
                    ).fetchone()[0]
                else:
                    current = conn.execute(
                        "SELECT COALESCE(MAX(number), 0) FROM tasks WHERE project_id IS NULL AND number > 0"
                    ).fetchone()[0]
                counters[key] = current
            counters[key] += 1
            conn.execute("UPDATE tasks SET number = ? WHERE id = ?", (counters[key], row["id"]))

    def execute(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self.connect() as conn:
            cursor = conn.execute(query, tuple(params))
            conn.commit()
            return cursor

    def fetch_one(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(query, tuple(params)).fetchone()

    def fetch_all(self, query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(query, tuple(params)).fetchall()
