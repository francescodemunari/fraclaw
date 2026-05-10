"""LM Studio — Local inference via OpenAI-compatible API."""

import os
from src.providers.base import ProviderProfile

LM_STUDIO_PROFILE = ProviderProfile(
    name="lm_studio",
    display_name="LM Studio (Local)",
    base_url=os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"),
    api_key_env="",
    default_model=os.getenv("LLM_MODEL_BASE", "qwen/qwen3.5-9b"),
    supports_tool_calling=True,
    supports_streaming=True,
    is_local=True,
    max_context=20000,
    requires_vram_management=True,
)
