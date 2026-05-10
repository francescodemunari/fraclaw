"""
whatsapp.py — WhatsApp platform adapter via whatsapp-web.js bridge.

Uses a Node.js subprocess running whatsapp-web.js to handle the
WhatsApp Web protocol. Communication happens over a local HTTP bridge.
No Facebook Business account needed — just scan a QR code with your phone.

Setup:
    1. Install Node.js (v18+)
    2. cd data/whatsapp-bridge && npm install
    3. Set WHATSAPP_ENABLED=true in .env
    4. On first run, scan the QR code shown in the terminal
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

import aiohttp
from loguru import logger

from src.gateway.base import PlatformAdapter, IncomingMessage, OutgoingResponse
from src.config import config

BRIDGE_DIR = Path(__file__).parent.parent.parent / "data" / "whatsapp-bridge"
BRIDGE_PORT = 3478
BRIDGE_URL = f"http://localhost:{BRIDGE_PORT}"


class WhatsAppAdapter(PlatformAdapter):
    """WhatsApp adapter using Node.js whatsapp-web.js bridge."""

    name = "whatsapp"

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._polling_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if not config.whatsapp_enabled:
            logger.info("[WhatsApp] Disabled in config. Skipping.")
            return

        if not BRIDGE_DIR.exists():
            logger.warning(
                f"[WhatsApp] Bridge not found at {BRIDGE_DIR}. "
                "Run the setup script first. See README for instructions."
            )
            return

        # Start the Node.js bridge subprocess
        try:
            self._process = subprocess.Popen(
                ["node", "index.js"],
                cwd=str(BRIDGE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logger.info(f"[WhatsApp] Bridge started (PID: {self._process.pid})")
        except FileNotFoundError:
            logger.error("[WhatsApp] Node.js not found. Install Node.js v18+.")
            return
        except Exception as e:
            logger.error(f"[WhatsApp] Failed to start bridge: {e}")
            return

        # Wait for bridge to become ready
        await asyncio.sleep(3)
        self._running = True
        self._polling_task = asyncio.create_task(self._poll_messages())

    async def stop(self) -> None:
        self._running = False
        if self._polling_task:
            self._polling_task.cancel()
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)
            logger.info("[WhatsApp] Bridge stopped.")

    async def _poll_messages(self) -> None:
        """Long-poll the bridge for new messages."""
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{BRIDGE_URL}/messages", timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            for msg in data.get("messages", []):
                                await self._handle_incoming(msg)
            except asyncio.CancelledError:
                break
            except aiohttp.ClientError:
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"[WhatsApp] Polling error: {e}")
                await asyncio.sleep(5)

    async def _handle_incoming(self, raw_msg: dict) -> None:
        """Process a message from the bridge."""
        text = raw_msg.get("body", "")
        chat_id = raw_msg.get("from", "")
        user_id = raw_msg.get("author", chat_id)
        msg_id = raw_msg.get("id", "")

        if not text:
            return

        logger.info(f"[WhatsApp] Message from {chat_id}: {text[:80]}")

        from src.agent.orchestrator import Orchestrator
        result = await Orchestrator.run(user_message=text)

        response_text = result.get("text", "")
        if response_text:
            await self.send_text(chat_id, response_text)

        for file_path in result.get("files", []):
            await self.send_file(chat_id, file_path)

    async def send_text(self, chat_id: str, text: str) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{BRIDGE_URL}/send",
                    json={"chatId": chat_id, "message": text},
                    timeout=aiohttp.ClientTimeout(total=10),
                )
        except Exception as e:
            logger.error(f"[WhatsApp] Send error: {e}")

    async def send_file(self, chat_id: str, file_path: str, caption: str = "") -> None:
        try:
            fp = Path(file_path)
            if not fp.exists():
                return
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field("chatId", chat_id)
                data.add_field("caption", caption)
                data.add_field("file", open(fp, "rb"), filename=fp.name)
                await session.post(
                    f"{BRIDGE_URL}/send-file",
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=30),
                )
        except Exception as e:
            logger.error(f"[WhatsApp] File send error: {e}")

    async def send_typing(self, chat_id: str) -> None:
        pass
