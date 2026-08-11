from __future__ import annotations

import sqlite3

from system.settings import DATABASE_PATH


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_article_column(
    connection: sqlite3.Connection, name: str, definition: str
) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(articles)")}
    if name not in columns:
        connection.execute(f"ALTER TABLE articles ADD COLUMN {name} {definition}")


def initialize() -> None:
    with connect() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL,
                normalized_url TEXT, source TEXT NOT NULL, category TEXT NOT NULL,
                summary TEXT, published_at TEXT, collected_at TEXT NOT NULL,
                first_seen_at TEXT, score INTEGER NOT NULL, tags TEXT NOT NULL,
                content_fingerprint TEXT, duplicate_of TEXT,
                view INTEGER NOT NULL DEFAULT 1
            )""")
        for name, definition in (
            ("normalized_url", "TEXT"),
            ("first_seen_at", "TEXT"),
            ("content_fingerprint", "TEXT"),
            ("duplicate_of", "TEXT"),
            ("view", "INTEGER NOT NULL DEFAULT 1"),
        ):
            _ensure_article_column(connection, name, definition)
        connection.execute(
            "UPDATE articles SET first_seen_at = collected_at WHERE first_seen_at IS NULL"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(normalized_url)"
        )
        connection.execute("""CREATE TABLE IF NOT EXISTS source_health (
                source TEXT PRIMARY KEY, category TEXT, url TEXT,
                last_attempt_at TEXT, last_success_at TEXT, latency_ms INTEGER,
                http_status INTEGER, last_error TEXT,
                last_item_count INTEGER NOT NULL DEFAULT 0,
                total_successes INTEGER NOT NULL DEFAULT 0,
                total_failures INTEGER NOT NULL DEFAULT 0
            )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS rag_index_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                pending INTEGER NOT NULL DEFAULT 0,
                last_attempt_at TEXT, last_success_at TEXT, last_error TEXT
            )""")
        connection.execute(
            "INSERT OR IGNORE INTO rag_index_state (id, pending) VALUES (1, 0)"
        )
        connection.execute("""CREATE TABLE IF NOT EXISTS collection_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger TEXT NOT NULL, started_at TEXT NOT NULL,
                finished_at TEXT, status TEXT NOT NULL,
                result_json TEXT, error TEXT
            )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS signal_feedback (
                article_id TEXT PRIMARY KEY,
                candidate TEXT NOT NULL CHECK (candidate IN ('good','bad')),
                snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
