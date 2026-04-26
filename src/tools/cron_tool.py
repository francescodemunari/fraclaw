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
_broadcast_callback = None


def init_job_queue(job_queue: JobQueue, user_id: int) -> None:
    """Inizializza il modulo con i riferimenti a Telegram."""
    global _job_queue, _user_id
    _job_queue = job_queue
    _user_id = user_id
    logger.debug("CronTool inizializzato con JobQueue Telegram.")


def init_broadcast_callback(callback) -> None:
    """Inizializza il callback per broadcast universale (Web/Mobile)."""
    global _broadcast_callback
    _broadcast_callback = callback
    logger.debug("CronTool inizializzato con Broadcast Callback.")


async def _dispatch_notification(message: str) -> None:
    """Invia la notifica su tutti i canali disponibili."""
    # 1. Telegram
    if _job_queue and _user_id:
        try:
            await _job_queue.run_once(
                _send_telegram_callback, 1, data=message
            )  # Esegui quasi subito
        except Exception as e:
            logger.error(f"Errore dispatch Telegram: {e}")

    # 2. Broadcast (Socket.IO / Mobile)
    if _broadcast_callback:
        try:
            if callable(_broadcast_callback):
                await _broadcast_callback(message)
        except Exception as e:
            logger.error(f"Errore dispatch Broadcast: {e}")


async def _send_telegram_callback(context) -> None:
    """Callback per JobQueue Telegram."""
    job = context.job
    try:
        await context.bot.send_message(
            chat_id=_user_id, text=f"⏰ *PROMEMORIA*\n\n{job.data}", parse_mode="Markdown"
        )
        logger.info(f"Telegram reminder inviato: {job.data[:50]}...")
    except Exception as e:
        logger.error(f"Errore invio Telegram reminder: {e}")


async def _async_delay_task(delay_seconds: float, message: str) -> None:
    """Fallback asincrono per sistemi senza JobQueue Telegram."""
    import asyncio
    await asyncio.sleep(delay_seconds)
    await _dispatch_notification(message)
    logger.info(f"Async reminder triggered: {message[:50]}...")


def set_reminder(message: str, delay_minutes: float) -> dict:
    """
    Imposta un promemoria che verrà inviato all'utente tra X minuti.
    Supporta sia Telegram che il broadcast Socket.IO.
    """
    import asyncio

    try:
        delay_seconds = float(delay_minutes) * 60.0

        if _job_queue:
            # Sfruttiamo la JobQueue di Telegram se presente per persistenza
            _job_queue.run_once(_send_telegram_callback, delay_seconds, data=message)
        else:
            # Fallback nativo asincrono (valido finché il processo api è vivo)
            asyncio.create_task(_async_delay_task(delay_seconds, message))

        logger.info(
            f"⏰ Promemoria impostato tra {delay_minutes} minuti: {message[:30]}..."
        )

        return {
            "success": True,
            "message": f"Promemoria salvato. Ti avviserò tra {delay_minutes} min.",
        }
    except Exception as e:
        logger.error(f"Errore impostazione promemoria: {e}")
        return {"error": str(e)}

