"""
base.py — Abstract platform adapter interface.

All platform adapters inherit from this and implement the required methods.
Messages are normalized to a common format before reaching the Orchestrator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class IncomingMessage:
    """Platform-agnostic incoming message."""
    text: str
    user_id: str
    platform: str
    chat_id: str
    message_id: str = ""
    image_path: Optional[str] = None
    audio_path: Optional[str] = None
    document_path: Optional[str] = None
    caption: Optional[str] = None


@dataclass
class OutgoingResponse:
    """Platform-agnostic response from the agent."""
    text: str
    files: list[str] = field(default_factory=list)
    session_id: Optional[int] = None


class PlatformAdapter(ABC):
    """Base class for all messaging platform adapters."""

    name: str = "base"

    @abstractmethod
    async def start(self) -> None:
        """Start listening for messages."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop the adapter."""
        ...

    @abstractmethod
    async def send_text(self, chat_id: str, text: str) -> None:
        """Send a text message to a chat."""
        ...

    @abstractmethod
    async def send_file(self, chat_id: str, file_path: str, caption: str = "") -> None:
        """Send a file to a chat."""
        ...

    async def send_typing(self, chat_id: str) -> None:
        """Send typing indicator (optional, not all platforms support it)."""
        pass

    async def handle_message(self, msg: IncomingMessage) -> OutgoingResponse:
        """Process an incoming message through the Orchestrator."""
        from src.agent.orchestrator import Orchestrator

        result = await Orchestrator.run(
            user_message=msg.text or msg.caption or "Analyze this.",
            image_path=msg.image_path,
            session_id=None,
        )

        return OutgoingResponse(
            text=result.get("text", ""),
            files=result.get("files", []),
            session_id=result.get("session_id"),
        )
