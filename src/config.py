"""
config.py — Carica e valida tutta la configurazione dal file .env

Usa python-dotenv + dataclass per mantenere la config centralizzata
e accessibile da qualsiasi modulo tramite `from src.config import config`.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Carica il file .env dalla root del progetto
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


@dataclass
class Config:
    # ── Telegram ─────────────────────────────────────────────
    telegram_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_TOKEN", "")
    )
    telegram_allowed_user_id: int = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))
    )

    # ── LM Studio ────────────────────────────────────────────
    lm_studio_base_url: str = field(
        default_factory=lambda: os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
    )
    lm_studio_api_url: str = field(
        default_factory=lambda: os.getenv("LM_STUDIO_API_URL", "http://localhost:1234")
    )
    lm_studio_model: str = field(
        default_factory=lambda: os.getenv("LM_STUDIO_MODEL", "qwen3.5-9b")
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

    # ── Database ─────────────────────────────────────────────
    db_path: str = field(
        default_factory=lambda: os.getenv("DB_PATH", "data/fraclaw.db")
    )
    chroma_path: str = field(
        default_factory=lambda: os.getenv("CHROMA_PATH", "data/chroma")
    )

    def validate(self) -> "Config":
        """Valida i campi critici e lancia un errore se mancanti."""
        errors = []
        if not self.telegram_token:
            errors.append("TELEGRAM_TOKEN non impostato nel .env")
        if not self.telegram_allowed_user_id:
            errors.append("TELEGRAM_ALLOWED_USER_ID non impostato nel .env")
        if errors:
            for e in errors:
                logger.error(f"❌ Config error: {e}")
            raise ValueError(f"Configurazione non valida: {', '.join(errors)}")
        logger.info(
            f"✅ Config caricata — Modello: {self.lm_studio_model} "
            f"| VRAM: {self.vram_mode} "
            f"| Whisper: {self.whisper_model}"
        )
        return self


# Istanza globale — importa sempre da qui
config = Config().validate()
