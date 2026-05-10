"""
database.py — SQLite Setup, Connection, and FTS5 Search
"""

import sqlite3
from pathlib import Path
from loguru import logger
from src.config import config


def get_connection() -> sqlite3.Connection:
    """Opens (or creates) the connection to the SQLite database."""
    db_path = Path(config.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Creates tables if they don't exist. Safe to call multiple times."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_facts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                category   TEXT    NOT NULL,
                key        TEXT    NOT NULL UNIQUE,
                value      TEXT    NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT    NOT NULL,
                tags       TEXT    DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                role       TEXT    NOT NULL,
                content    TEXT    NOT NULL,
                timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id    INTEGER NOT NULL,
                file_path     TEXT NOT NULL,
                file_name     TEXT NOT NULL,
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS personas (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL UNIQUE,
                description   TEXT,
                system_prompt TEXT    NOT NULL,
                voice_id      TEXT    DEFAULT 'en-US-AndrewNeural',
                premium_voice INTEGER DEFAULT 0,
                is_active     INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS web_monitors (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT    NOT NULL,
                query           TEXT    NOT NULL,
                interval_hours  INTEGER DEFAULT 6,
                last_check      DATETIME,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ─── FTS5 Full-Text Search ───────────────────────────────
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts
            USING fts5(content, role, session_id UNINDEXED)
        """)

        # Trigger to keep FTS in sync with conversations table
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS conversations_fts_insert
            AFTER INSERT ON conversations
            BEGIN
                INSERT INTO conversations_fts(rowid, content, role, session_id)
                VALUES (new.id, new.content, new.role, new.session_id);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS conversations_fts_delete
            AFTER DELETE ON conversations
            BEGIN
                INSERT INTO conversations_fts(conversations_fts, rowid, content, role, session_id)
                VALUES ('delete', old.id, old.content, old.role, old.session_id);
            END
        """)

        conn.commit()
        logger.info("Database initialized (FTS5 enabled)")
    except Exception as e:
        logger.error(f"Database init error: {e}")
    finally:
        conn.close()


def search_conversations(query: str, limit: int = 5) -> list[dict]:
    """Search all conversations using FTS5 full-text search."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.role, c.content, c.session_id, c.timestamp
            FROM conversations_fts fts
            JOIN conversations c ON c.id = fts.rowid
            WHERE conversations_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit))

        results = []
        for row in cursor.fetchall():
            results.append({
                "role": row["role"],
                "content": row["content"],
                "session_id": row["session_id"],
                "timestamp": row["timestamp"],
            })
        return results
    except Exception as e:
        logger.error(f"FTS5 search error: {e}")
        return []
    finally:
        conn.close()
