"""Anthropic — Claude models via native Messages API (OpenAI-compatible proxy)."""

from src.providers.base import ProviderProfile

ANTHROPIC_PROFILE = ProviderProfile(
    name="anthropic",
    display_name="Anthropic (Claude)",
    base_url="https://api.anthropic.com/v1",
    api_key_env="ANTHROPIC_API_KEY",
    default_model="claude-sonnet-4-20250514",
    supports_tool_calling=True,
    supports_streaming=True,
    is_local=False,
    max_context=200000,
    requires_vram_management=False,
)
