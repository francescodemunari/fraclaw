"""
database.py — SQLite Setup and Connection
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
    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON")
    # Row factory: results behave like dictionaries
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Creates tables if they don't exist. Safe to call multiple times."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # User facts table
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

        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT    NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Conversation history table
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

        # Message attachments table (NEW)
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

        # Personas table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS personas (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL UNIQUE,
                description   TEXT,
                system_prompt TEXT    NOT NULL,
                voice_id      TEXT    NOT NULL,
                premium_voice BOOLEAN DEFAULT 0,
                is_active     BOOLEAN DEFAULT 0
            )
        """)

        # Web Monitoring table (Watchman)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS web_monitors (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                title         TEXT    NOT NULL UNIQUE,
                query         TEXT    NOT NULL,
                url           TEXT,
                interval_hours INTEGER NOT NULL DEFAULT 6,
                last_hash     TEXT,
                is_active     BOOLEAN DEFAULT 1,
                last_check    DATETIME,
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migration: Add session_id if missing
        try:
            cursor.execute("ALTER TABLE conversations ADD COLUMN session_id INTEGER")
            logger.info("➕ Added 'session_id' column to conversations table.")
        except sqlite3.OperationalError:
            pass

        # Migration: Add premium_voice if missing
        try:
            cursor.execute("ALTER TABLE personas ADD COLUMN premium_voice BOOLEAN DEFAULT 0")
            logger.info("➕ Added 'premium_voice' column to personas table.")
        except sqlite3.OperationalError:
            pass

        # REMOVED: Automatic insertion of default session ('Conversazione Iniziale').
        # The user wants an empty sidebar after purge/init.

        conn.commit()
        logger.info(f"✅ SQLite Database initialized: {config.db_path}")
    finally:
        conn.close()
