"""
preferences.py — CRUD per i fatti utente e il profilo conversazionale

Espone:
  - save_fact()           → salva/aggiorna un fatto sull'utente
  - get_all_facts()       → restituisce tutti i fatti
  - get_profile_summary() → stringa da iniettare nel system prompt
  - save_conversation_message() → salva un messaggio nella cronologia
  - get_recent_history()  → ultimi N messaggi per il contesto
"""

from loguru import logger

from src.memory.database import get_connection


# ─── Fatti Utente ─────────────────────────────────────────────────────────────

def save_fact(category: str, key: str, value: str) -> bool:
    """
    Salva o aggiorna un fatto sull'utente.

    Esempio:
        save_fact("identità", "nome", "Admin")
        save_fact("preferenza", "linguaggio", "Python")
        save_fact("progetto", "corrente", "Fraclaw")
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # INSERT OR REPLACE gestisce automaticamente aggiornamenti (key è UNIQUE)
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
        logger.info(f"💾 Fatto salvato: [{category}] {key} = {value}")
        sync_memory_to_disk()
        return True
    except Exception as e:
        logger.error(f"Errore salvataggio fatto: {e}")
        return False
    finally:
        conn.close()


def get_all_facts() -> list[dict]:
    """Restituisce tutti i fatti sull'utente, ordinati per categoria."""
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
    """Elimina un fatto specifico dall'utente."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_facts WHERE category = ? AND key = ?", (category, key))
        deleted = cursor.rowcount > 0
        conn.commit()
        if deleted:
            logger.info(f"🗑️ Fatto eliminato: [{category}] {key}")
            sync_memory_to_disk()
        return deleted
    except Exception as e:
        logger.error(f"Errore eliminazione fatto: {e}")
        return False
    finally:
        conn.close()



def get_profile_summary() -> str:
    """
    Genera un sommario leggibile del profilo utente.
    Viene iniettato nel system prompt ad ogni messaggio.
    """
    facts = get_all_facts()
    if not facts:
        return ""

    # Raggruppa per categoria
    by_category: dict[str, list[str]] = {}
    for f in facts:
        cat = f["category"]
        by_category.setdefault(cat, []).append(f"{f['key']}: {f['value']}")

    lines = ["## Quello che so di te:"]
    for cat, items in by_category.items():
        lines.append(f"**{cat.capitalize()}**")
        for item in items:
            lines.append(f"  - {item}")

    return "\n".join(lines)


def sync_memory_to_disk() -> None:
    """
    Esporta il profilo utente in Markdown nel file data/MEMORY.md.
    Viene chiamato in automatico ogni volta che un fatto viene salvato o cancellato.
    """
    try:
        from pathlib import Path
        mem_path = Path("data/MEMORY.md")
        mem_path.parent.mkdir(parents=True, exist_ok=True)
        summary = get_profile_summary()
        
        content = (
            "# 🧠 Diario di Bordo (MEMORY)\n\n"
            "Questo file viene sincronizzato automaticamente dal Database SQLite per consentirti l'ispezione umana.\n\n"
        )
        if summary:
            content += summary
        else:
            content += "*Nessun fatto ancora registrato.*"
            
        mem_path.write_text(content, encoding="utf-8")
        logger.debug("🔄 Sincronizzato data/MEMORY.md")
    except Exception as e:
        logger.error(f"Errore durante la sincronizzazione di MEMORY.md: {e}")


# ─── Storico Conversazioni ────────────────────────────────────────────────────

def save_conversation_message(role: str, content: str) -> None:
    """Salva un messaggio (user o assistant) nella cronologia persistente."""
    conn = get_connection()
    try:
        # Tronca contenuti troppo lunghi (base64 immagini, ecc.)
        truncated = content[:4000] if len(content) > 4000 else content
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (role, content) VALUES (?, ?)",
            (role, truncated),
        )
        conn.commit()
    except Exception as e:
        logger.warning(f"Errore salvataggio messaggio: {e}")
    finally:
        conn.close()


def get_recent_history(limit: int = 10) -> list[dict]:
    """
    Recupera gli ultimi N messaggi per costruire il contesto conversazionale.
    Restituisce la lista in ordine cronologico (dal più vecchio al più recente).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content FROM conversations
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        # Inverti: vogliamo cronologico, non decrescente
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    finally:
        conn.close()
# ─── Gestione Personalità (Personas) ──────────────────────────────────────────

def init_default_personas() -> None:
    """Inizializza le personalità predefinite (es. Jarvis) se la tabella è vuota."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM personas")
        if cursor.fetchone()["count"] == 0:
            logger.info("🎭 Inizializzazione personalità predefinite...")
            jarvis_prompt = (
                "Sei **Fraclaw**, un assistente AI personale JARVIS-style. Operi in locale sul PC dell'utente.\n"
                "Usa un tono professionale, efficiente e proattivo. Sei l'IA di bordo definitiva.\n"
                "Rispecchia l'identità di un maggiordomo digitale avanzato."
            )
            cursor.execute(
                """
                INSERT INTO personas (name, description, system_prompt, voice_id, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("Jarvis", "Assistente formale e proattivo", jarvis_prompt, "it-IT-GiuseppeNeural", 1)
            )
            # Aggiungiamo anche un Profilo "Amico" di base
            amico_prompt = (
                "Sei **Fraclaw**, un amico fidato dell'utente. Parla in modo informale, amichevole e rilassato.\n"
                "Usa pure espressioni colloquiali e sii meno rigido rispetto a Jarvis."
            )
            cursor.execute(
                """
                INSERT INTO personas (name, description, system_prompt, voice_id, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("Amico", "Tono informale e colloquiale", amico_prompt, "it-IT-DiegoNeural", 0)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Errore init personas: {e}")
    finally:
        conn.close()

def get_active_persona() -> dict:
    """Recupera la personalità attualmente attiva."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM personas WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        if not row:
            # Fallback se nulla è attivo
            return {
                "name": "Default",
                "system_prompt": "Sei un assistente AI locale.",
                "voice_id": "it-IT-GiuseppeNeural"
            }
        return dict(row)
    finally:
        conn.close()

def list_personas() -> list[dict]:
    """Lista tutte le personalità disponibili."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, is_active FROM personas ORDER BY name")
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()

def switch_persona(name: str) -> bool:
    """Cambia la personalità attiva."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Disattiva tutte
        cursor.execute("UPDATE personas SET is_active = 0")
        # Attiva quella scelta
        cursor.execute("UPDATE personas SET is_active = 1 WHERE name = ?", (name,))
        changed = cursor.rowcount > 0
        conn.commit()
        if changed:
            logger.info(f"🎭 Personalità cambiata in: {name}")
        return changed
    except Exception as e:
        logger.error(f"Errore switch persona: {e}")
        return False
    finally:
        conn.close()
def save_persona(name: str, description: str, system_prompt: str, voice_id: str) -> bool:
    """Salva o aggiorna una personalità nel database."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO personas (name, description, system_prompt, voice_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                description   = excluded.description,
                system_prompt = excluded.system_prompt,
                voice_id      = excluded.voice_id
            """,
            (name, description, system_prompt, voice_id)
        )
        conn.commit()
        logger.info(f"💾 Personalità salvata nel DB: {name}")
        return True
    except Exception as e:
        logger.error(f"Errore salvataggio persona: {e}")
        return False
    finally:
        conn.close()

def delete_persona(name: str) -> bool:
    """Elimina una personalità (non è possibile eliminare quella attiva o quelle di sistema)."""
    if name in ["Jarvis", "Amico"]:
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
# ─── Gestione Monitoraggi Web (Watchman) ──────────────────────────────────────

def add_web_monitor(title: str, query: str, url: str = None, interval: int = 6) -> bool:
    """Aggiunge una nuova sottoscrizione di monitoraggio web."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO web_monitors (title, query, url, interval_hours)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(title) DO UPDATE SET
                query = excluded.query,
                url = excluded.url,
                interval_hours = excluded.interval_hours
            """,
            (title, query, url, interval)
        )
        conn.commit()
        logger.info(f"🌐 Monitoraggio aggiunto: {title} (Ogni {interval} ore)")
        return True
    except Exception as e:
        logger.error(f"Errore add_web_monitor: {e}")
        return False
    finally:
        conn.close()

def list_active_monitors() -> list[dict]:
    """Recupera tutti i monitoraggi attivi."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM web_monitors WHERE is_active = 1")
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()

def update_monitor_status(monitor_id: int, last_hash: str) -> None:
    """Aggiorna il timestamp di controllo e l'hash del contenuto."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE web_monitors SET last_check = CURRENT_TIMESTAMP, last_hash = ? WHERE id = ?",
            (last_hash, monitor_id)
        )
        conn.commit()
    finally:
        conn.close()

def delete_web_monitor(title: str) -> bool:
    """Rimuove un monitoraggio."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM web_monitors WHERE title = ?", (title,))
        success = cursor.rowcount > 0
        conn.commit()
        return success
    finally:
        conn.close()
