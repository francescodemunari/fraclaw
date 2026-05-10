"""Google Gemini — via OpenAI-compatible endpoint."""

import os
from src.providers.base import ProviderProfile

GEMINI_PROFILE = ProviderProfile(
    name="gemini",
    display_name="Google Gemini",
    base_url=os.getenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    ),
    api_key_env="GEMINI_API_KEY",
    default_model="gemini-2.5-flash",
    supports_tool_calling=True,
    supports_streaming=True,
    is_local=False,
    max_context=1000000,
    requires_vram_management=False,
)
