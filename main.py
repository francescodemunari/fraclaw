import sys
from pathlib import Path

from loguru import logger


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:

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
