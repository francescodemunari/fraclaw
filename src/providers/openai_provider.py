"""OpenAI — GPT models via official API."""

from src.providers.base import ProviderProfile

OPENAI_PROFILE = ProviderProfile(
    name="openai",
    display_name="OpenAI",
    base_url="https://api.openai.com/v1",
    api_key_env="OPENAI_API_KEY",
    default_model="gpt-4o",
    supports_tool_calling=True,
    supports_streaming=True,
    is_local=False,
    max_context=128000,
    requires_vram_management=False,
)
