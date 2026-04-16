import sys
from pathlib import Path

from loguru import logger


# ─── Logging ──────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    """Configura loguru con output su console (colorato) e file rotante."""
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Rimuovi il sink di default di loguru
    logger.remove()

    # Console colorata — solo INFO e superiori
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

    # File rotante — tutti i livelli (DEBUG incluso)
    logger.add(
        log_dir / "fraclaw_{time:YYYY-MM-DD}.log",
        rotation="00:00",       # Ruota ogni giorno a mezzanotte
        retention="7 days",     # Mantieni 7 giorni di log
        level="DEBUG",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {module}:{line} — {message}",
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    setup_logging()

    logger.info("=" * 60)
    logger.info("  🤖 FRACLAW — Avvio agente AI personale locale")
    logger.info("=" * 60)

    # Inizializza il database SQLite (crea le tabelle se non esistono)
    from src.memory.database import init_db
    init_db()

    # Inizializza personalità predefinite
    from src.memory.preferences import init_default_personas
    init_default_personas()

    # Crea l'applicazione Telegram
    from src.bot.handler import create_application
    app = create_application()

    logger.info("🚀 In ascolto su Telegram... (Ctrl+C per fermare)")

    # Avvia il polling — bloccante, rimane attivo finché non viene fermato
    app.run_polling(
        drop_pending_updates=True,  # Ignora messaggi arrivati mentre era offline
        allowed_updates=["message", "callback_query", "inline_query"],
    )


if __name__ == "__main__":
    main()
