"""
handler.py — Telegram Handlers for all message types
Handles:
  - /start → Welcome message
  - Text → Send to Agent
  - Photo → Download + Send to Agent with Vision
  - Voice → Download → Transcribe with Whisper → Send to Agent
  - Document → Download → Read text (or analyze as image)

Security: Each handler verifies that the sender is the authorized user
(comparison with TELEGRAM_ALLOWED_USER_ID).
"""

from pathlib import Path

from loguru import logger
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.agent.core import run_agent
from src.config import config

# Temporary folder for files downloaded from Telegram — anchored to the project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent
TEMP_DIR = _PROJECT_ROOT / "data" / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def escape_markdown(text: str) -> str:
    """Escapes reserved characters for Telegram's MarkdownV2."""
    reserved = r'_*[]()~`>#+-=|{}.!'
    for char in reserved:
        text = text.replace(char, f"\\{char}")
    return text


# ─── Security ────────────────────────────────────────────────────────────────

def _is_authorized(update: Update) -> bool:
    """Verifies that the sender is the authorized user."""
    return update.effective_user is not None and \
           update.effective_user.id == config.telegram_allowed_user_id


async def _reject(update: Update) -> None:
    """Responds with a rejection message to unauthorized users."""
    uid = update.effective_user.id if update.effective_user else "?"
    logger.warning(f"🚫 Access denied for user_id={uid}")
    await update.message.reply_text("🚫 You are not authorized to use this bot.")


# ─── Result Dispatch ──────────────────────────────────────────────────────────

async def _send_result(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    result: dict,
) -> None:
    """
    Sends the agent's result back to the user:
      - Text is sent (split if >4096 characters)
      - Generated files are sent as documents/media
    """
    text: str = result.get("text", "")
    files: list[str] = result.get("files", [])

    # ── Text ─────────────────────────────────────────────────
    if text:
        max_len = 4096
        chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)]
        for chunk in chunks:
            try:
                await update.message.reply_text(chunk, parse_mode="Markdown")
            except Exception:
                # Malformed Markdown → fallback to plain text
                try:
                    await update.message.reply_text(chunk)
                except Exception as e:
                    logger.error(f"Error sending text: {e}")

    # ── Attachments ─────────────────────────────────────────
    for file_path in files:
        fp = Path(file_path)
        if not fp.exists():
            logger.warning(f"File to send not found: {fp}")
            continue

        try:
            suffix = fp.suffix.lower()
            image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
            voice_exts = {".mp3", ".ogg", ".wav"}

            with open(fp, "rb") as f:
                if suffix in image_exts:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=f,
                        caption=f"🖼️ {fp.name}",
                    )
                elif suffix in voice_exts:
                    await context.bot.send_voice(
                        chat_id=update.effective_chat.id,
                        voice=f,
                        caption="🎙️ Voice Message",
                    )
                else:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=f,
                        filename=fp.name,
                    )
            logger.info(f"📤 File sent to Telegram: {fp.name}")
        except Exception as e:
            logger.error(f"Error sending file '{fp}': {e}")
            await update.message.reply_text(f"⚠️ Error sending file: `{fp.name}`", parse_mode="Markdown")


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /start command."""
    if not _is_authorized(update):
        await _reject(update)
        return

    await update.message.reply_text(
        "👋 Hello\\! I am **Fraclaw**, your local personal AI assistant\\.\n\n"
        "Here is what I can do for you:\n\n"
        "📂 *Filesystem* — read, write, and explore files on your PC\n"
        "🌐 *Web Search* — search the internet with DuckDuckGo\n"
        "📄 *Documents* — generate PDF, Word, Excel, PowerPoint\n"
        "🖼️ *Images* — generate images with Stable Diffusion \\(SDXL\\)\n"
        "🎙️ *Voice* — transcribe voice notes via Whisper\n"
        "👁️ *Vision* — analyze photos you send me\n"
        "🧠 *Memory* — remember your preferences over time\n\n"
        "Let me know how I can assist you today\\!",
        parse_mode="MarkdownV2",
    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /clear — empties short-term conversation history."""
    if not _is_authorized(update):
        await _reject(update)
        return
        
    from src.memory.database import get_connection
    conn = None
    try:
        conn = get_connection()
        conn.execute("DELETE FROM conversations")
        conn.commit()
        await update.message.reply_text("🧹 Short-term memory cleared!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error during clearing: {e}")
    finally:
        if conn:
            conn.close()


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /reset — wipes both short and long-term memory."""
    if not _is_authorized(update):
        await _reject(update)
        return
        
    from src.memory.database import get_connection
    conn = None
    try:
        conn = get_connection()
        conn.execute("DELETE FROM conversations")
        conn.execute("DELETE FROM user_facts")
        conn.commit()
        await update.message.reply_text("💥 Total reset completed.\n\nAll short-term memory and long-term facts have been formatted. Fraclaw is now a clean slate.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error during reset: {e}")


async def persona_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /persona — Shows menu to switch identities."""
    if not _is_authorized(update):
        await _reject(update)
        return

    from src.memory.preferences import list_personas
    personas = list_personas()
    
    keyboard = []
    for p in personas:
        label = f"✅ {p['name']}" if p['is_active'] else p['name']
        keyboard.append([InlineKeyboardButton(label, callback_data=f"set_persona:{p['name']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎭 **Persona Engine**\nChoose Fraclaw's identity. Switching personas will change the tone and voice settings:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def persona_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles button clicks in the persona menu."""
    query = update.callback_query
    data = query.data
    
    await query.answer()

    if not _is_authorized(update):
        logger.warning(f"🚫 Unauthorized persona change attempt from UID: {update.effective_user.id}")
        return

    if data.startswith("set_persona:"):
        name = data.split(":")[1]
        logger.info(f"🎭 Persona change requested: {name}")
        
        from src.memory.preferences import switch_persona
        if switch_persona(name):
            await query.edit_message_text(
                f"🎭 Persona switched to: **{name}**\nI will now respond with this character and voice! ✨",
                parse_mode="Markdown"
            )
        else:
            logger.error(f"❌ Database error while switching to {name}")
            await query.edit_message_text("❌ Database error during persona switch.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for text messages."""
    if not _is_authorized(update):
        await _reject(update)
        return

    user_message = update.message.text
    logger.info(f"✉️ Text: {user_message[:100]!r}")

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    from src.agent.orchestrator import Orchestrator
    result = await Orchestrator.run(user_message, telegram_update=update)
    await _send_result(update, context, result)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for photos sent directly (not as documents)."""
    if not _is_authorized(update):
        await _reject(update)
        return

    caption = update.message.caption or "Analyze this image in detail."
    logger.info(f"📷 Photo received — caption: {caption!r}")

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    # Download largest available version
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    image_path = TEMP_DIR / f"photo_{update.message.message_id}.jpg"
    await tg_file.download_to_drive(str(image_path))

    try:
        from src.agent.orchestrator import Orchestrator
        result = await Orchestrator.run(caption, telegram_update=update, image_path=str(image_path))
        await _send_result(update, context, result)
    finally:
        # Cleanup temp file
        try:
            image_path.unlink(missing_ok=True)
        except Exception:
            pass


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for voice messages — transcribes with Whisper then sends to agent."""
    if not _is_authorized(update):
        await _reject(update)
        return

    status_msg = None
    audio_path = None
    try:
        status_msg = await update.message.reply_text("🎙️ Transcribing your message...")

        # Download audio file
        voice = update.message.voice
        if not voice:
            logger.warning("Voice message received without voice object")
            return

        tg_file = await context.bot.get_file(voice.file_id)
        audio_path = TEMP_DIR / f"voice_{update.message.message_id}.ogg"
        await tg_file.download_to_drive(str(audio_path))

        # Transcribe via Whisper
        from src.tools.whisper_tool import transcribe_audio
        transcript_result = transcribe_audio(str(audio_path))

        if "error" in transcript_result:
            await status_msg.edit_text(f"❌ Transcription error: {transcript_result['error']}")
            return

        transcript = transcript_result["transcript"]
        lang = str(transcript_result.get("language", "?"))
        duration = str(transcript_result.get("duration_seconds", 0))

        logger.info(f"✅ Transcribed ({lang}, {duration}s): {transcript[:80]}")

        # Update existing message with transcript
        try:
            s_trans = escape_markdown(transcript)
            s_lang = escape_markdown(lang)
            s_dur = escape_markdown(duration)
            await status_msg.edit_text(
                f"🎙️ *You said* \\({s_lang}, {s_dur}s\\):\n_{s_trans}_",
                parse_mode="MarkdownV2",
            )
        except Exception as e:
            logger.warning(f"MarkdownV2 error during edit, falling back to plain text: {e}")
            await status_msg.edit_text(f"🎙️ You said ({lang}, {duration}s):\n{transcript}")

        # Send transcript to Agent
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        from src.agent.orchestrator import Orchestrator
        result = await Orchestrator.run(transcript, telegram_update=update)
        await _send_result(update, context, result)

    except Exception as e:
        logger.error(f"Critical error during handle_voice: {e}")
        await update.message.reply_text("❌ Sorry, an error occurred while handling your voice message.")
    finally:
        if audio_path and audio_path.exists():
            try:
                audio_path.unlink()
            except Exception:
                pass


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for documents/files sent as attachments.
    - Images → Vision analysis
    - Text/Code → Read content and pass to agent
    - Other formats → Inform agent of the path
    """
    if not _is_authorized(update):
        await _reject(update)
        return

    doc = update.message.document
    caption = update.message.caption or f"Analyze the file '{doc.file_name}'."
    logger.info(f"📎 Document received: {doc.file_name}")

    tg_file = await context.bot.get_file(doc.file_id)
    doc_path = TEMP_DIR / doc.file_name
    await tg_file.download_to_drive(str(doc_path))

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    text_exts = {".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".yaml", ".yml", ".xml", ".html", ".css", ".log"}

    suffix = doc_path.suffix.lower()

    try:
        if suffix in image_exts:
            # Treat as image for vision
            from src.agent.orchestrator import Orchestrator
            result = await Orchestrator.run(caption, telegram_update=update, image_path=str(doc_path))

        elif suffix in text_exts:
            # Read text content and pass to Agent
            try:
                content = doc_path.read_text(encoding="utf-8", errors="replace")
                # Truncate if too long for context
                if len(content) > 6000:
                    content = content[:6000] + "\n\n[... content truncated ...]"
                message = f"{caption}\n\nContent of `{doc.file_name}`:\n```\n{content}\n```"
            except Exception as e:
                message = f"I received the file '{doc.file_name}'. I couldn't read it: {e}"
            from src.agent.orchestrator import Orchestrator
            result = await Orchestrator.run(message, telegram_update=update)

        else:
            # Unhandled file type directly
            message = (
                f"I received the file '{doc.file_name}' "
                f"({doc.file_size} bytes, type: {doc.mime_type}). "
                f"{caption}"
            )
            from src.agent.orchestrator import Orchestrator
            result = await Orchestrator.run(message, telegram_update=update)

        await _send_result(update, context, result)

    finally:
        try:
            doc_path.unlink(missing_ok=True)
        except Exception:
            pass


# ─── App Factory ──────────────────────────────────────────────────────────────

def create_application() -> Application:
    """Creates and configures the Telegram application with all handlers registered."""
    app = Application.builder().token(config.telegram_token).build()

    # Priority 1: Buttons and menus (Callback queries)
    app.add_handler(CallbackQueryHandler(persona_callback))

    # Priority 2: Explicit commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("persona", persona_command))

    # Priority 3: Generic messages (text, photo, voice, doc)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    from src.tools.cron_tool import init_job_queue
    init_job_queue(app.job_queue, config.telegram_allowed_user_id)

    logger.info("✅ Telegram handlers registered")
    return app
