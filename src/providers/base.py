"""
base.py — Provider abstraction base class and registry.

Each provider declares its auth, endpoint, and behavioral quirks.
The get_provider() factory returns the active provider based on config.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from openai import AsyncOpenAI
from loguru import logger


@dataclass
class ProviderProfile:
    """Declarative provider configuration."""

    name: str
    display_name: str = ""
    base_url: str = ""
    api_key_env: str = ""
    default_model: str = ""
    supports_tool_calling: bool = True
    supports_streaming: bool = True
    is_local: bool = False
    max_context: int = 128000
    requires_vram_management: bool = False

    def get_api_key(self) -> str:
        if not self.api_key_env:
            return "not-needed"
        key = os.getenv(self.api_key_env, "")
        if not key:
            logger.warning(f"API key not set for provider '{self.name}' (env: {self.api_key_env})")
        return key

    def get_base_url(self) -> str:
        return self.base_url

    def get_client(self, **kwargs) -> AsyncOpenAI:
        return AsyncOpenAI(
            base_url=self.get_base_url(),
            api_key=self.get_api_key(),
            **kwargs,
        )

    def get_default_model(self) -> str:
        return self.default_model


# ─── Provider Registry ────────────────────────────────────────────────────────

_PROVIDERS: dict[str, ProviderProfile] = {}


def register_provider(profile: ProviderProfile) -> None:
    _PROVIDERS[profile.name] = profile


def get_provider(name: str | None = None) -> ProviderProfile:
    if name is None:
        name = os.getenv("ACTIVE_PROVIDER", "lm_studio")
    if name not in _PROVIDERS:
        available = ", ".join(_PROVIDERS.keys())
        raise ValueError(f"Unknown provider '{name}'. Available: {available}")
    return _PROVIDERS[name]


def list_providers() -> list[str]:
    return list(_PROVIDERS.keys())


# ─── Register Built-in Providers ──────────────────────────────────────────────

def _register_builtins() -> None:
    from src.providers.lm_studio import LM_STUDIO_PROFILE
    from src.providers.openrouter import OPENROUTER_PROFILE
    from src.providers.anthropic_provider import ANTHROPIC_PROFILE
    from src.providers.openai_provider import OPENAI_PROFILE
    from src.providers.deepseek import DEEPSEEK_PROFILE
    from src.providers.ollama import OLLAMA_PROFILE
    from src.providers.gemini import GEMINI_PROFILE

    for profile in [
        LM_STUDIO_PROFILE,
        OPENROUTER_PROFILE,
        ANTHROPIC_PROFILE,
        OPENAI_PROFILE,
        DEEPSEEK_PROFILE,
        OLLAMA_PROFILE,
        GEMINI_PROFILE,
    ]:
        register_provider(profile)


_register_builtins()
