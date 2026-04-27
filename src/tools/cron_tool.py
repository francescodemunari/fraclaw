"""
cron_tool.py — Native tool for setting reminders and delayed alerts.
Leverages python-telegram-bot's JobQueue.
"""

from loguru import logger
from telegram.ext import JobQueue

import hashlib
from datetime import datetime

_job_queue: JobQueue | None = None
_user_id: int | None = None
_broadcast_callback = None


def init_job_queue(job_queue: JobQueue, user_id: int) -> None:
    """Initializes the module with Telegram references."""
    global _job_queue, _user_id
    _job_queue = job_queue
    _user_id = user_id
    logger.debug("CronTool initialized with Telegram JobQueue.")


def init_broadcast_callback(callback) -> None:
    """Initializes the callback for universal broadcast (Web/Mobile)."""
    global _broadcast_callback
    _broadcast_callback = callback
    logger.debug("CronTool initialized with Broadcast Callback.")


async def _dispatch_notification(message: str) -> None:
    """Sends notification across all available channels."""
    # 1. Telegram
    if _job_queue and _user_id:
        try:
            await _job_queue.run_once(
                _send_telegram_callback, 1, data=message
            )  # Execute almost immediately
        except Exception as e:
            logger.error(f"Telegram dispatch error: {e}")

    # 2. Broadcast (Socket.IO / Mobile)
    if _broadcast_callback:
        try:
            if callable(_broadcast_callback):
                await _broadcast_callback(message)
        except Exception as e:
            logger.error(f"Broadcast dispatch error: {e}")


async def _send_telegram_callback(context) -> None:
    """Callback for Telegram JobQueue."""
    job = context.job
    try:
        await context.bot.send_message(
            chat_id=_user_id, text=f"⏰ *REMINDER*\n\n{job.data}", parse_mode="Markdown"
        )
        logger.info(f"Telegram reminder sent: {job.data[:50]}...")
    except Exception as e:
        logger.error(f"Error sending Telegram reminder: {e}")


async def _async_delay_task(delay_seconds: float, message: str) -> None:
    """Asynchronous fallback for systems without Telegram JobQueue."""
    import asyncio
    await asyncio.sleep(delay_seconds)
    await _dispatch_notification(message)
    logger.info(f"Async reminder triggered: {message[:50]}...")


def set_reminder(message: str, delay_minutes: float) -> dict:
    """
    Sets a reminder to be sent to the user in X minutes.
    Supports both Telegram and Socket.IO broadcast.
    """
    import asyncio

    try:
        delay_seconds = float(delay_minutes) * 60.0

        if _job_queue:
            # Leverage Telegram JobQueue if present for persistence
            _job_queue.run_once(_send_telegram_callback, delay_seconds, data=message)
        else:
            # Native async fallback (valid as long as the api process is alive)
            asyncio.create_task(_async_delay_task(delay_seconds, message))

        logger.info(
            f"⏰ Reminder set for {delay_minutes} minutes: {message[:30]}..."
        )

        return {
            "success": True,
            "message": f"Reminder saved. I will notify you in {delay_minutes} min.",
        }
    except Exception as e:
        logger.error(f"Error setting reminder: {e}")
        return {"error": str(e)}

