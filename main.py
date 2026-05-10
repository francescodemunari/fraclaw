import sys
import asyncio
from pathlib import Path

from loguru import logger


def main() -> None:

    logger.info("=" * 60)
    logger.info("  FRACLAW v1.2 — Multi-Provider Local AI Agent")
    logger.info("=" * 60)

    # Initialize SQLite database (creates tables if missing)
    from src.memory.database import init_db
    init_db()

    # Initialize default personas
    from src.memory.preferences import init_default_personas
    init_default_personas()

    # Initialize skills directory
    from src.skills.loader import SKILLS_DIR
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    from src.config import config
    from src.providers.base import get_provider

    provider = get_provider()
    logger.info(f"Active Provider: {provider.display_name}")

    # Start platform adapters
    platforms_started = []

    # Telegram
    if config.telegram_token:
        from src.gateway.telegram import create_telegram_app
        app = create_telegram_app()
        platforms_started.append("Telegram")

        logger.info(f"Platforms active: {', '.join(platforms_started)}")
        logger.info("Listening... (Ctrl+C to stop)")

        # Telegram's run_polling is blocking — start it last
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "inline_query"],
        )
    else:
        logger.warning("No TELEGRAM_TOKEN set. Running in API-only mode.")
        logger.info("Start the web API with: python -m src.web.api")


if __name__ == "__main__":
    main()
