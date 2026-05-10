"""
discord.py — Discord platform adapter.

Requires a Discord bot token from the Developer Portal.
Features: text messages, image attachments, voice transcription,
slash commands, typing indicators.
"""

import asyncio
from pathlib import Path
from loguru import logger

try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

from src.gateway.base import PlatformAdapter, IncomingMessage, OutgoingResponse
from src.config import config

TEMP_DIR = Path("data/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class DiscordAdapter(PlatformAdapter):
    """Discord bot adapter using discord.py."""

    name = "discord"

    def __init__(self):
        if not DISCORD_AVAILABLE:
            raise ImportError("discord.py is not installed. Run: pip install discord.py")

        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True

        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self._setup_handlers()

    def _is_authorized(self, user_id: int) -> bool:
        allowed = config.discord_allowed_user_ids
        if not allowed or allowed == ['']:
            return True
        return str(user_id) in allowed

    def _setup_handlers(self):
        @self.bot.event
        async def on_ready():
            logger.info(f"[Discord] Connected as {self.bot.user}")

        @self.bot.event
        async def on_message(message: discord.Message):
            if message.author == self.bot.user:
                return
            if message.author.bot:
                return
            if not self._is_authorized(message.author.id):
                return

            # Process commands first
            await self.bot.process_commands(message)

            # Skip if it was a command
            if message.content.startswith("!"):
                return

            await self._process_message(message)

        @self.bot.command(name="status")
        async def cmd_status(ctx: commands.Context):
            if not self._is_authorized(ctx.author.id):
                return
            from src.providers.base import get_provider
            from src.memory.preferences import get_active_persona
            provider = get_provider()
            persona = get_active_persona()
            embed = discord.Embed(title="Fraclaw Status", color=0x7289DA)
            embed.add_field(name="Provider", value=provider.display_name, inline=True)
            embed.add_field(name="Model", value=config.lm_studio_model, inline=True)
            embed.add_field(name="Persona", value=persona['name'], inline=True)
            await ctx.send(embed=embed)

        @self.bot.command(name="clear")
        async def cmd_clear(ctx: commands.Context):
            if not self._is_authorized(ctx.author.id):
                return
            from src.memory.database import get_connection
            conn = get_connection()
            conn.execute("DELETE FROM conversations")
            conn.commit()
            conn.close()
            await ctx.send("Memory cleared.")

        @self.bot.command(name="search")
        async def cmd_search(ctx: commands.Context, *, query: str = ""):
            if not self._is_authorized(ctx.author.id):
                return
            if not query:
                await ctx.send("Usage: `!search your query here`")
                return
            from src.memory.database import search_conversations
            results = search_conversations(query, limit=5)
            if not results:
                await ctx.send(f"No results for: **{query}**")
                return
            embed = discord.Embed(title=f"Search: {query}", color=0x7289DA)
            for r in results:
                content = r["content"][:200] + "..." if len(r["content"]) > 200 else r["content"]
                embed.add_field(name=f"[{r['role'].capitalize()}]", value=content, inline=False)
            await ctx.send(embed=embed)

    async def _process_message(self, message: discord.Message):
        """Process a Discord message through the agent."""
        image_path = None

        # Handle image attachments
        if message.attachments:
            for att in message.attachments:
                if att.content_type and att.content_type.startswith("image/"):
                    image_path = TEMP_DIR / f"discord_{message.id}_{att.filename}"
                    await att.save(str(image_path))
                    break

        user_text = message.content or (message.attachments[0].filename if message.attachments else "")
        if not user_text and not image_path:
            return

        async with message.channel.typing():
            from src.agent.orchestrator import Orchestrator
            result = await Orchestrator.run(
                user_message=user_text,
                image_path=str(image_path) if image_path else None,
            )

        # Send response
        text = result.get("text", "")
        files = result.get("files", [])

        if text:
            # Discord has 2000 char limit
            chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]
            for chunk in chunks:
                await message.channel.send(chunk)

        for file_path in files:
            fp = Path(file_path)
            if fp.exists():
                try:
                    await message.channel.send(file=discord.File(str(fp)))
                except Exception as e:
                    logger.error(f"[Discord] Error sending file: {e}")

        # Cleanup temp image
        if image_path and image_path.exists():
            try:
                image_path.unlink()
            except Exception:
                pass

    async def start(self) -> None:
        if not config.discord_token:
            logger.warning("[Discord] No DISCORD_TOKEN set. Skipping.")
            return
        logger.info("[Discord] Starting bot...")
        await self.bot.start(config.discord_token)

    async def stop(self) -> None:
        if self.bot and not self.bot.is_closed():
            await self.bot.close()

    async def send_text(self, chat_id: str, text: str) -> None:
        channel = self.bot.get_channel(int(chat_id))
        if channel:
            await channel.send(text)

    async def send_file(self, chat_id: str, file_path: str, caption: str = "") -> None:
        channel = self.bot.get_channel(int(chat_id))
        if channel:
            await channel.send(content=caption, file=discord.File(file_path))
