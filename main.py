import sys
from pathlib import Path

from loguru import logger


# ─── Logging ──────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    """Configures loguru with colorized console output and a rotating log file."""
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Remove loguru's default sink
    logger.remove()

    # Colorized console — INFO and above only
    logger.add(
        sys.stdout,
        level="INFO",
        colorize=True,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{module}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
    )

    # Rotating file — all levels (including DEBUG)
    logger.add(
        log_dir / "fraclaw_{time:YYYY-MM-DD}.log",
        rotation="00:00",       # Rotate every day at midnight
        retention="7 days",     # Keep 7 days of logs
        level="DEBUG",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {module}:{line} — {message}",
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_logging()

    logger.info("=" * 60)
    logger.info("  🤖 FRACLAW — Starting personal local AI agent")
    logger.info("=" * 60)

    # Initialize SQLite database (creates tables if missing)
    from src.memory.database import init_db
    init_db()

    # Initialize default personas in English
    from src.memory.preferences import init_default_personas
    init_default_personas()

    # Create the Telegram application
    from src.bot.handler import create_application
    app = create_application()

    logger.info("🚀 Listening on Telegram... (Ctrl+C to stop)")

    # Start polling — blocking, stays active until interrupted
    app.run_polling(
        drop_pending_updates=True,  # Ignore messages received while offline
        allowed_updates=["message", "callback_query", "inline_query"],
    )


if __name__ == "__main__":
    main()
