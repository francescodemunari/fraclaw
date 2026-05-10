"""Ollama — Local inference alternative to LM Studio."""

import os
from src.providers.base import ProviderProfile

OLLAMA_PROFILE = ProviderProfile(
    name="ollama",
    display_name="Ollama (Local)",
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    api_key_env="",
    default_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
    supports_tool_calling=True,
    supports_streaming=True,
    is_local=True,
    max_context=32000,
    requires_vram_management=True,
)
