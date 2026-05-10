"""DeepSeek — High-quality reasoning models at low cost."""

from src.providers.base import ProviderProfile

DEEPSEEK_PROFILE = ProviderProfile(
    name="deepseek",
    display_name="DeepSeek",
    base_url="https://api.deepseek.com/v1",
    api_key_env="DEEPSEEK_API_KEY",
    default_model="deepseek-chat",
    supports_tool_calling=True,
    supports_streaming=True,
    is_local=False,
    max_context=128000,
    requires_vram_management=False,
)
