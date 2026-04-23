"""
preferences.py — CRUD for user facts and conversational profiling
"""

from loguru import logger
from src.memory.database import get_connection

# ─── User Facts ───────────────────────────────────────────────────────────────

def save_fact(category: str, key: str, value: str) -> bool:
    """Saves or updates a fact about the user."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_facts (category, key, value, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value      = excluded.value,
                category   = excluded.category,
                updated_at = CURRENT_TIMESTAMP
            """,
            (category, key, value),
        )
        conn.commit()
        logger.info(f"💾 Fact saved: [{category}] {key} = {value}")
        sync_memory_to_disk()
        return True
    except Exception as e:
        logger.error(f"Error saving fact: {e}")
        return False
    finally:
        conn.close()


def get_all_facts() -> list[dict]:
    """Returns all user facts, ordered by category."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT category, key, value FROM user_facts ORDER BY category, key"
        )
        rows = cursor.fetchall()
        return [{"category": r["category"], "key": r["key"], "value": r["value"]} for r in rows]
    finally:
        conn.close()

def delete_fact(category: str, key: str) -> bool:
    """Deletes a specific fact from the user profile."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_facts WHERE category = ? AND key = ?", (category, key))
        deleted = cursor.rowcount > 0
        conn.commit()
        if deleted:
            logger.info(f"🗑️ Fact deleted: [{category}] {key}")
            sync_memory_to_disk()
        return deleted
    except Exception as e:
        logger.error(f"Error deleting fact: {e}")
        return False
    finally:
        conn.close()


def get_profile_summary() -> str:
    """Generates a readable summary of the user profile for the system prompt."""
    facts = get_all_facts()
    if not facts:
        return ""

    # Group by category
    by_category: dict[str, list[str]] = {}
    for f in facts:
        cat = f["category"]
        by_category.setdefault(cat, []).append(f"{f['key']}: {f['value']}")

    lines = ["## User Knowledge (What I know about you):"]
    for cat, items in by_category.items():
        lines.append(f"**{cat.capitalize()}**")
        for item in items:
            lines.append(f"  - {item}")

    return "\n".join(lines)


def sync_memory_to_disk() -> None:
    """Syncs the user profile to data/MEMORY.md in Markdown format."""
    try:
        from pathlib import Path
        root = Path(__file__).parent.parent.parent
        mem_path = root / "data" / "MEMORY.md"
        mem_path.parent.mkdir(parents=True, exist_ok=True)
        
        summary = get_profile_summary()
        
        content = (
            "# 🧠 Memory Logbook (LOG)\n\n"
            "This file is automatically synced from the SQLite database for human inspection.\n\n"
            "---\n\n"
        )
        if summary:
            content += summary
        else:
            content += "*No facts recorded yet.*"
            
        mem_path.write_text(content, encoding="utf-8")
        logger.debug(f"🔄 Synced {mem_path}")
    except Exception as e:
        logger.error(f"Error syncing MEMORY.md: {e}")


# ─── Conversation History ─────────────────────────────────────────────────────

def save_conversation_message(role: str, content: str, session_id: int = None) -> int:
    """
    Saves a message in the persistent history tied to a session.
    Returns the message ID (integer).
    """
    conn = get_connection()
    try:
        if session_id is None:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1")
            row = cursor.fetchone()
            session_id = row["id"] if row else 1

        truncated = content[:4000] if len(content) > 4000 else content
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (role, content, session_id) VALUES (?, ?, ?)",
            (role, truncated, session_id),
        )
        msg_id = cursor.lastrowid
        conn.commit()
        return msg_id
    except Exception as e:
        logger.warning(f"Error saving message: {e}")
        return 0
    finally:
        conn.close()

def save_attachment(message_id: int, file_path: str) -> bool:
    """Links a file path to a specific message in the database."""
    if not message_id or not file_path:
        return False
        
    import os
    file_name = os.path.basename(file_path)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO attachments (message_id, file_path, file_name) VALUES (?, ?, ?)",
            (message_id, str(file_path), file_name)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving attachment: {e}")
        return False
    finally:
        conn.close()


def get_recent_history(limit: int = 10, session_id: int = None) -> list[dict]:
    """Retrieves the last N messages of a specific session."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if session_id is None:
            cursor.execute("SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1")
            row = cursor.fetchone()
            session_id = row["id"] if row else 1

        cursor.execute(
            """
            SELECT role, content FROM conversations
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (session_id, limit),
        )
        rows = cursor.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    finally:
        conn.close()


# ─── Persona Management ───────────────────────────────────────────────────────

def init_default_personas() -> None:
    """Initializes default personas with English descriptions and prompts."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Ensure premium voice is set for existing
        cursor.execute("UPDATE personas SET premium_voice = 1")
        
        # Ensure Jarvis is present and in English
        jarvis_prompt = (
            "You are **Fraclaw**, a JARVIS-style personal AI assistant operating locally on the user's PC. "
            "You must respond ALWAYS in English. Maintain a professional, efficient, and proactive tone."
        )
        cursor.execute("SELECT id FROM personas WHERE name = 'Jarvis'")
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE personas SET system_prompt = ?, description = ?, voice_id = ?, premium_voice = 1 WHERE name = 'Jarvis'",
                (jarvis_prompt, "Formal and proactive assistant", "en-GB-ThomasNeural") 
            )
        else:
            cursor.execute(
                "INSERT INTO personas (name, description, system_prompt, voice_id, premium_voice, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                ("Jarvis", "Formal and proactive assistant", jarvis_prompt, "en-GB-ThomasNeural", 1, 1)
            )
        
        conn.commit()
    except Exception as e:
        logger.error(f"Error resetting personas: {e}")
    finally:
        conn.close()

def get_active_persona() -> dict:
    """Retrieves the currently active persona."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM personas WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return {
                "name": "Default",
                "system_prompt": "You are a local AI assistant.",
                "voice_id": "en-US-AndrewNeural"
            }
        return dict(row)
    finally:
        conn.close()

def list_personas() -> list[dict]:
    """Lists all available personas."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, is_active FROM personas ORDER BY name")
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()

def switch_persona(name: str) -> bool:
    """Switches the active persona."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE personas SET is_active = 0")
        cursor.execute("UPDATE personas SET is_active = 1 WHERE name = ?", (name,))
        changed = cursor.rowcount > 0
        conn.commit()
        if changed:
            logger.info(f"🎭 Personality switched to: {name}")
        return changed
    except Exception as e:
        logger.error(f"Error switching persona: {e}")
        return False
    finally:
        conn.close()

def toggle_premium_voice(enabled: bool = None) -> bool:
    """Toggles the premium voice setting for the active persona."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if enabled is None:
            # Flip current state
            cursor.execute("UPDATE personas SET premium_voice = 1 - premium_voice WHERE is_active = 1")
        else:
            cursor.execute("UPDATE personas SET premium_voice = ? WHERE is_active = 1", (1 if enabled else 0,))
        
        changed = cursor.rowcount > 0
        conn.commit()
        if changed:
            state = "PREMIUM (Chatterbox)" if (enabled or enabled is None) else "LITE (Edge-TTS)"
            logger.info(f"🔊 Voice engine changed for active persona: {state}")
        return changed
    finally:
        conn.close()

def save_persona(name: str, description: str, system_prompt: str, voice_id: str, premium_voice: bool = False) -> bool:
    """Saves or updates a persona in the database."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO personas (name, description, system_prompt, voice_id, premium_voice)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                description   = excluded.description,
                system_prompt = excluded.system_prompt,
                voice_id      = excluded.voice_id,
                premium_voice = excluded.premium_voice
            """,
            (name, description, system_prompt, voice_id, 1 if premium_voice else 0)
        )
        conn.commit()
        logger.info(f"💾 Persona saved: {name} (Premium: {premium_voice})")
        return True
    except Exception as e:
        logger.error(f"Error saving persona: {e}")
        return False
    finally:
        conn.close()

def delete_persona(name: str) -> bool:
    """Deletes a persona (prevents deleting active or system personas)."""
    if name in ["Jarvis"]:
        return False
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM personas WHERE name = ? AND is_active = 0", (name,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()


# ─── Web Monitoring (Watchman) ────────────────────────────────────────────────

def add_web_monitor(title: str, query: str, interval: int = 6) -> bool:
    """Adds a new web monitoring subscription."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO web_monitors (title, query, interval_hours) VALUES (?, ?, ?)",
            (title, query, interval)
        )
        conn.commit()
        logger.info(f"🛰️ Web monitor added: {title} (Query: {query})")
        return True
    except Exception as e:
        logger.error(f"Error adding web monitor: {e}")
        return False
    finally:
        conn.close()

def delete_web_monitor(title: str) -> bool:
    """Removes a web monitoring subscription."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM web_monitors WHERE title = ?", (title,))
        deleted = cursor.rowcount > 0
        conn.commit()
        if deleted:
            logger.info(f"🛰️ Web monitor removed: {title}")
        return deleted
    finally:
        conn.close()
