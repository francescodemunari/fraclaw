"""
database.py — Setup e connessione SQLite

SQLite è un database che vive in un singolo file .db sul tuo PC.
Non richiede nessun server: funziona zero-config, leggero e veloce.

Struttura:
  - user_facts: fatti sull'utente (nome, preferenze, progetti)
  - conversations: storico messaggi per il contesto conversazionale
"""

import sqlite3
from pathlib import Path

from loguru import logger

from src.config import config


def get_connection() -> sqlite3.Connection:
    """Apre (o crea) la connessione al database SQLite."""
    db_path = Path(config.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    # Row factory: i risultati si comportano come dizionari
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crea le tabelle se non esistono già. Sicuro da chiamare più volte."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Tabella fatti utente (key-value con categoria)
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

        # Tabella storico conversazioni
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                role      TEXT    NOT NULL,
                content   TEXT    NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabella Personalità (Personas)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS personas (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL UNIQUE,
                description   TEXT,
                system_prompt TEXT    NOT NULL,
                voice_id      TEXT    NOT NULL,
                is_active     BOOLEAN DEFAULT 0
            )
        """)

        # Tabella Monitoraggio Web (Watchman)
        # last_hash: hash del contenuto cercato per rilevare cambiamenti
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

        conn.commit()
        logger.info(f"✅ Database SQLite inizializzato: {config.db_path}")
    finally:
        conn.close()
