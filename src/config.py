"""
config.py — Loads and validates all configuration from the .env file.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
import sys

# ─── Global Logging Setup ─────────────────────────────────────────────────────
log_dir = Path(__file__).parent.parent / "data" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
logger.remove()
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
logger.add(
    log_dir / "fraclaw_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    level="DEBUG",
    encoding="utf-8",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {module}:{line} — {message}",
)

# Load the .env file from the project root
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


@dataclass
class Config:
    # ── Active Provider ──────────────────────────────────────
    active_provider: str = field(
        default_factory=lambda: os.getenv("ACTIVE_PROVIDER", "lm_studio")
    )

    # ── Telegram ─────────────────────────────────────────────
    telegram_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_TOKEN", "")
    )
    telegram_allowed_user_id: int = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))
    )

    # ── Discord ──────────────────────────────────────────────
    discord_token: str = field(
        default_factory=lambda: os.getenv("DISCORD_TOKEN", "")
    )
    discord_allowed_user_ids: list = field(
        default_factory=lambda: [
            uid.strip() for uid in os.getenv("DISCORD_ALLOWED_USER_IDS", "").split(",") if uid.strip()
        ]
    )

    # ── WhatsApp ─────────────────────────────────────────────
    whatsapp_enabled: bool = field(
        default_factory=lambda: os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
    )

    # ── LM Studio (Local) ────────────────────────────────────
    lm_studio_base_url: str = field(
        default_factory=lambda: os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
    )
    lm_studio_api_url: str = field(
        default_factory=lambda: os.getenv("LM_STUDIO_API_URL", "http://localhost:1234")
    )
    lm_studio_model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL_BASE", "qwen/qwen3.5-9b")
    )
    llm_model_coder: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL_CODER", "qwen2.5-coder-7b-instruct")
    )
    llm_model_audio: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL_AUDIO", "qwen2-audio")
    )

    # ── Cloud Provider API Keys ──────────────────────────────
    openrouter_api_key: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "")
    )
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    deepseek_api_key: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", "")
    )
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )

    # ── ComfyUI ──────────────────────────────────────────────
    comfyui_url: str = field(
        default_factory=lambda: os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
    )
    comfyui_model: str = field(
        default_factory=lambda: os.getenv("COMFYUI_MODEL", "juggernautXL_v9Rundiffusion.safetensors")
    )
    vram_mode: str = field(
        default_factory=lambda: os.getenv("VRAM_MODE", "exclusive")
    )

    # ── Filesystem ───────────────────────────────────────────
    filesystem_allowed_paths: list = field(
        default_factory=lambda: [
            p.strip()
            for p in os.getenv("FILESYSTEM_ALLOWED_PATHS", r"C:\Users\Admin").split(",")
            if p.strip()
        ]
    )

    # ── Whisper ──────────────────────────────────────────────
    whisper_model: str = field(
        default_factory=lambda: os.getenv("WHISPER_MODEL", "base")
    )

    # ── Agent Behaviour ──────────────────────────────────────
    history_limit: int = field(
        default_factory=lambda: int(os.getenv("HISTORY_LIMIT", "25"))
    )

    # ── Project Root ─────────────────────────────────────────
    project_root: Path = field(
        default_factory=lambda: Path(__file__).parent.parent
    )

    # ── Database ─────────────────────────────────────────────
    db_path: str = field(
        default_factory=lambda: str(Path(__file__).parent.parent / os.getenv("DB_PATH", "data/fraclaw.db"))
    )
    chroma_path: str = field(
        default_factory=lambda: str(Path(__file__).parent.parent / os.getenv("CHROMA_PATH", "data/chroma"))
    )

    def validate(self) -> "Config":
        """Validates critical fields and raises an error if missing."""
        errors = []
        if not self.telegram_token and not self.discord_token:
            errors.append("At least one platform token must be set (TELEGRAM_TOKEN or DISCORD_TOKEN)")
        if self.telegram_token and not self.telegram_allowed_user_id:
            errors.append("TELEGRAM_ALLOWED_USER_ID not set (required when using Telegram)")
        if errors:
            for e in errors:
                logger.error(f"Config error: {e}")
            raise ValueError(f"Invalid configuration: {', '.join(errors)}")
        logger.info(
            f"Config loaded — Provider: {self.active_provider} "
            f"| Model: {self.lm_studio_model} "
            f"| VRAM: {self.vram_mode} "
            f"| History: {self.history_limit}"
        )
        return self


# Global instance
config = Config().validate()
