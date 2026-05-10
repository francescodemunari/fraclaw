"""OpenRouter — 200+ models via single API key."""

from src.providers.base import ProviderProfile

OPENROUTER_PROFILE = ProviderProfile(
    name="openrouter",
    display_name="OpenRouter (Multi-Model)",
    base_url="https://openrouter.ai/api/v1",
    api_key_env="OPENROUTER_API_KEY",
    default_model="anthropic/claude-sonnet-4",
    supports_tool_calling=True,
    supports_streaming=True,
    is_local=False,
    max_context=200000,
    requires_vram_management=False,
)
