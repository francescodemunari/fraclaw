"""
utils.py — Client factory using the multi-provider system.
"""

from contextlib import asynccontextmanager
from openai import AsyncOpenAI
from loguru import logger

from src.providers.base import get_provider


@asynccontextmanager
async def get_client(provider_name: str | None = None):
    """
    Returns an AsyncOpenAI client configured for the active provider.

    Usage:
        async with get_client() as client:
            response = await client.chat.completions.create(...)
    """
    provider = get_provider(provider_name)
    client = provider.get_client()
    try:
        yield client
    finally:
        await client.close()


def get_active_model(provider_name: str | None = None) -> str:
    """Returns the default model for the active provider."""
    provider = get_provider(provider_name)
    return provider.get_default_model()


def is_local_provider(provider_name: str | None = None) -> bool:
    """Check if the active provider requires VRAM management."""
    provider = get_provider(provider_name)
    return provider.requires_vram_management
