"""
telegram.py — Telegram platform adapter.

Wraps the existing handler.py logic into the gateway interface.
This is the primary adapter and maintains full feature parity.
"""

from pathlib import Path

from loguru import logger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from src.gateway.base import PlatformAdapter, IncomingMessage, OutgoingResponse
from src.config import config

TEMP_DIR = Path("data/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def escape_markdown(text: str) -> str:
    reserved = r'_*[]()~`>#+-=|{}.!'
    for char in reserved:
        text = text.replace(char, f"\\{char}")
    return text


def _is_authorized(update: Update) -> bool:
    return update.effective_user is not None and \
           update.effective_user.id == config.telegram_allowed_user_id


async def _reject(update: Update) -> None:
    uid = update.effective_user.id if update.effective_user else "?"
    logger.warning(f"Access denied for user_id={uid}")
    await update.message.reply_text("You are not authorized to use this bot.")


async def _send_result(update: Update, context: ContextTypes.DEFAULT_TYPE, result: dict) -> None:
    """Sends the agent's result back to the user."""
    text: str = result.get("text", "")
    files: list[str] = result.get("files", [])

    if text:
        max_len = 4096
        chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)]
        for chunk in chunks:
            try:
                await update.message.reply_text(chunk, parse_mode="Markdown")
            except Exception:
                try:
                    await update.message.reply_text(chunk)
                except Exception as e:
                    logger.error(f"Error sending text: {e}")

    for file_path in files:
        fp = Path(file_path)
        if not fp.exists():
            continue

        try:
            suffix = fp.suffix.lower()
            image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
            voice_exts = {".mp3", ".ogg", ".wav"}

            with open(fp, "rb") as f:
                if suffix in image_exts:
                    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=f, caption=fp.name)
                elif suffix in voice_exts:
                    await context.bot.send_voice(chat_id=update.effective_chat.id, voice=f)
                else:
                    await context.bot.send_document(chat_id=update.effective_chat.id, document=f, filename=fp.name)
        except Exception as e:
            logger.error(f"Error sending file '{fp}': {e}")


# ─── Command Handlers ────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    await update.message.reply_text(
        "Hello! I am **Fraclaw**, your local personal AI assistant.\n\n"
        "Here is what I can do for you:\n\n"
        "- *Filesystem* — read, write, and explore files\n"
        "- *Web Search* — search the internet\n"
        "- *Documents* — generate PDF, Word, Excel, PowerPoint\n"
        "- *Images* — generate images with Stable Diffusion\n"
        "- *Voice* — transcribe voice notes via Whisper\n"
        "- *Vision* — analyze photos you send me\n"
        "- *Memory* — remember your preferences over time\n"
        "- *Skills* — learn and reuse complex procedures\n\n"
        "Let me know how I can assist you today!",
        parse_mode="Markdown",
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    from src.memory.database import get_connection
    try:
        conn = get_connection()
        conn.execute("DELETE FROM conversations")
        conn.commit()
        conn.close()
        await update.message.reply_text("Short-term memory cleared!")
    except Exception as e:
        await update.message.reply_text(f"Error during clearing: {e}")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    from src.memory.database import get_connection
    try:
        conn = get_connection()
        conn.execute("DELETE FROM conversations")
        conn.execute("DELETE FROM user_facts")
        conn.commit()
        conn.close()
        await update.message.reply_text("Total reset completed. All memory wiped. Clean slate.")
    except Exception as e:
        await update.message.reply_text(f"Error during reset: {e}")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /search — searches conversation history."""
    if not _is_authorized(update):
        await _reject(update)
        return

    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Usage: `/search your query here`", parse_mode="Markdown")
        return

    from src.memory.database import search_conversations
    results = search_conversations(query, limit=5)

    if not results:
        await update.message.reply_text(f"No results found for: *{query}*", parse_mode="Markdown")
        return

    lines = [f"*Search results for:* _{query}_\n"]
    for r in results:
        role = r["role"].capitalize()
        content = r["content"][:150] + "..." if len(r["content"]) > 150 else r["content"]
        lines.append(f"**[{role}]** {content}\n")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /status — shows system diagnostics."""
    if not _is_authorized(update):
        await _reject(update)
        return

    from src.providers.base import get_provider
    from src.memory.preferences import get_active_persona

    provider = get_provider()
    persona = get_active_persona()

    status_text = (
        f"*Fraclaw Status*\n\n"
        f"Provider: `{provider.display_name}`\n"
        f"Model: `{config.lm_studio_model}`\n"
        f"Persona: `{persona['name']}`\n"
        f"VRAM Mode: `{config.vram_mode}`\n"
        f"History Limit: `{config.history_limit}`\n"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")


async def persona_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return
    from src.memory.preferences import list_personas
    personas = list_personas()

    keyboard = []
    for p in personas:
        label = f"[Active] {p['name']}" if p['is_active'] else p['name']
        keyboard.append([InlineKeyboardButton(label, callback_data=f"set_persona:{p['name']}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "*Persona Engine*\nChoose Fraclaw's identity:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def persona_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    await query.answer()

    if not _is_authorized(update):
        return

    if data.startswith("set_persona:"):
        name = data.split(":")[1]
        from src.memory.preferences import switch_persona
        if switch_persona(name):
            await query.edit_message_text(f"Persona switched to: *{name}*", parse_mode="Markdown")
        else:
            await query.edit_message_text("Error during persona switch.")


# ─── Message Handlers ────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return

    user_message = update.message.text
    logger.info(f"[TG] Text: {user_message[:100]!r}")

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    from src.agent.orchestrator import Orchestrator
    result = await Orchestrator.run(user_message, telegram_update=update)
    await _send_result(update, context, result)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return

    caption = update.message.caption or "Analyze this image in detail."
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    image_path = TEMP_DIR / f"photo_{update.message.message_id}.jpg"
    await tg_file.download_to_drive(str(image_path))

    try:
        from src.agent.orchestrator import Orchestrator
        result = await Orchestrator.run(caption, telegram_update=update, image_path=str(image_path))
        await _send_result(update, context, result)
    finally:
        try:
            image_path.unlink(missing_ok=True)
        except Exception:
            pass


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return

    status_msg = None
    audio_path = None
    try:
        status_msg = await update.message.reply_text("Transcribing your message...")

        voice = update.message.voice
        if not voice:
            return

        tg_file = await context.bot.get_file(voice.file_id)
        audio_path = TEMP_DIR / f"voice_{update.message.message_id}.ogg"
        await tg_file.download_to_drive(str(audio_path))

        from src.tools.whisper_tool import transcribe_audio
        transcript_result = transcribe_audio(str(audio_path))

        if "error" in transcript_result:
            await status_msg.edit_text(f"Transcription error: {transcript_result['error']}")
            return

        transcript = transcript_result["transcript"]
        lang = str(transcript_result.get("language", "?"))
        duration = str(transcript_result.get("duration_seconds", 0))

        try:
            s_trans = escape_markdown(transcript)
            s_lang = escape_markdown(lang)
            s_dur = escape_markdown(duration)
            await status_msg.edit_text(
                f"*You said* \\({s_lang}, {s_dur}s\\):\n_{s_trans}_",
                parse_mode="MarkdownV2",
            )
        except Exception:
            await status_msg.edit_text(f"You said ({lang}, {duration}s):\n{transcript}")

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        from src.agent.orchestrator import Orchestrator
        result = await Orchestrator.run(transcript, telegram_update=update)
        await _send_result(update, context, result)

    except Exception as e:
        logger.error(f"Error in handle_voice: {e}")
        await update.message.reply_text("Error handling your voice message.")
    finally:
        if audio_path and audio_path.exists():
            try:
                audio_path.unlink()
            except Exception:
                pass


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        await _reject(update)
        return

    doc = update.message.document
    caption = update.message.caption or f"Analyze the file '{doc.file_name}'."

    tg_file = await context.bot.get_file(doc.file_id)
    doc_path = TEMP_DIR / doc.file_name
    await tg_file.download_to_drive(str(doc_path))

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    text_exts = {".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".yaml", ".yml", ".xml", ".html", ".css", ".log"}
    suffix = doc_path.suffix.lower()

    try:
        if suffix in image_exts:
            from src.agent.orchestrator import Orchestrator
            result = await Orchestrator.run(caption, telegram_update=update, image_path=str(doc_path))
        elif suffix in text_exts:
            try:
                content = doc_path.read_text(encoding="utf-8", errors="replace")
                if len(content) > 6000:
                    content = content[:6000] + "\n\n[... content truncated ...]"
                message = f"{caption}\n\nContent of `{doc.file_name}`:\n```\n{content}\n```"
            except Exception as e:
                message = f"I received the file '{doc.file_name}'. I couldn't read it: {e}"
            from src.agent.orchestrator import Orchestrator
            result = await Orchestrator.run(message, telegram_update=update)
        else:
            message = f"I received the file '{doc.file_name}' ({doc.file_size} bytes, type: {doc.mime_type}). {caption}"
            from src.agent.orchestrator import Orchestrator
            result = await Orchestrator.run(message, telegram_update=update)

        await _send_result(update, context, result)
    finally:
        try:
            doc_path.unlink(missing_ok=True)
        except Exception:
            pass


# ─── App Factory ──────────────────────────────────────────────────────────────

def create_telegram_app() -> Application:
    """Creates and configures the Telegram application with all handlers."""
    app = Application.builder().token(config.telegram_token).build()

    app.add_handler(CallbackQueryHandler(persona_callback))

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("persona", persona_command))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    from src.tools.cron_tool import init_job_queue
    init_job_queue(app.job_queue, config.telegram_allowed_user_id)

    logger.info("Telegram handlers registered")
    return app
