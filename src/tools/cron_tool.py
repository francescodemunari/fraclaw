"""
cron_tool.py — Tool nativo per impostare promemoria e avvisi ritardati.
Sfrutta la JobQueue di python-telegram-bot.
"""

from loguru import logger
from telegram.ext import JobQueue

import hashlib
from datetime import datetime

_job_queue: JobQueue | None = None
_user_id: int | None = None

def init_job_queue(job_queue: JobQueue, user_id: int) -> None:
    """Inizializza il modulo con i riferimenti a Telegram e avvia i monitoraggi persistenti."""
    global _job_queue, _user_id
    _job_queue = job_queue
    _user_id = user_id
    logger.debug("CronTool inizializzato con JobQueue.")
    
    # Avvia il loop di monitoraggio dei siti web (ogni ora controlla chi deve girare)
    if _job_queue:
        _job_queue.run_repeating(_watchman_cycle, interval=3600, first=10)

async def _watchman_cycle(context) -> None:
    """Ciclo periodico che controlla se ci sono monitoraggi web da eseguire."""
    from src.memory.preferences import list_active_monitors, update_monitor_status
    from src.tools.web_search import web_search
    
    monitors = list_active_monitors()
    if not monitors:
        return

    logger.info(f"🔍 Watchman: Controllo di {len(monitors)} monitoraggi...")
    
    for m in monitors:
        # Qui potremmo aggiungere logica per controllare se è passata l'ora (m['interval_hours'])
        # Per semplicità ora eseguiamo un controllo
        try:
            results = web_search(m['query'], max_results=3)
            # Creiamo un hash dei titoli dei risultati per vedere se è cambiato qualcosa
            content_str = "|".join([r.get('title', '') for r in results or []])
            new_hash = hashlib.md5(content_str.encode()).hexdigest()
            
            if m['last_hash'] and m['last_hash'] != new_hash:
                # Novità trovata!
                msg = f"🌍 *AGGIORNAMENTO WEB: {m['title']}*\n\nHo trovato novità riguardo alla tua ricerca: '{m['query']}'.\n\n"
                for r in results[:3]:
                    msg += f"🔹 [{r['title']}]({r['url']})\n"
                
                await context.bot.send_message(chat_id=_user_id, text=msg, parse_mode="Markdown")
                logger.info(f"🔔 Notifica Watchman inviata per: {m['title']}")
            
            # Aggiorna il DB con l'ultimo controllo
            update_monitor_status(m['id'], new_hash)
            
        except Exception as e:
            logger.error(f"Errore ciclo Watchman per {m['title']}: {e}")

async def _send_reminder_callback(context) -> None:
    """Callback richiamato dalla JobQueue allo scadere del timer."""
    job = context.job
    try:
        await context.bot.send_message(
            chat_id=_user_id,
            text=f"⏰ *PROMEMORIA*\n\n{job.data}",
            parse_mode="Markdown"
        )
        logger.info(f"Promemoria inviato: {job.data[:50]}...")
    except Exception as e:
        logger.error(f"Errore invio promemoria: {e}")


def set_reminder(message: str, delay_minutes: float) -> dict:
    """
    Imposta un promemoria che verrà inviato all'utente tra X minuti.
    """
    global _job_queue
    if _job_queue is None:
        return {"error": "Il sistema di allarmi (JobQueue) non è attivo / non è stato inizializzato."}
        
    try:
        # job_queue.run_once richiede i secondi
        delay_seconds = float(delay_minutes) * 60.0
        
        _job_queue.run_once(_send_reminder_callback, delay_seconds, data=message)
        logger.info(f"⏰ Promemoria impostato tra {delay_minutes} minuti per il messaggio: {message[:30]}...")
        
        return {
            "success": True,
            "message": f"Promemoria salvato con successo. Verrà recapitato tra {delay_minutes} min."
        }
    except Exception as e:
        logger.error(f"Errore impostazione promemoria: {e}")
        return {"error": str(e)}
