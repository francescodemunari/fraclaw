"""
handler.py — Handler Telegram per tutti i tipi di messaggio

Gestisce:
  - /start → messaggio di benvenuto
  - Testo → invia all'agente
  - Foto → scarica + invia all'agente con vision
  - Vocale → scarica → trascrive con Whisper → invia all'agente
  - Documento → scarica → legge testo (o analizza come immagine)

Sicurezza: ogni handler verifica che il mittente sia l'utente autorizzato
prima di fare qualsiasi cosa (confronto con TELEGRAM_ALLOWED_USER_ID).
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

# Cartella temporanea per file scaricati da Telegram
TEMP_DIR = Path("data/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)


# ─── Sicurezza ────────────────────────────────────────────────────────────────

def _is_authorized(update: Update) -> bool:
    """Verifica che il mittente sia l'utente autorizzato."""
    return update.effective_user is not None and \
           update.effective_user.id == config.telegram_allowed_user_id


async def _reject(update: Update) -> None:
    """Risponde con un messaggio di rifiuto agli utenti non autorizzati."""
    uid = update.effective_user.id if update.effective_user else "?"
    logger.warning(f"🚫 Accesso negato per user_id={uid}")
    await update.message.reply_text("🚫 Non sei autorizzato ad usare questo bot.")


# ─── Invio Risultati ──────────────────────────────────────────────────────────

async def _send_result(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    result: dict,
) -> None:
    """
    Invia il risultato dell'agente all'utente:
      - Il testo viene inviato (splittato se >4096 caratteri)
      - I file generati vengono inviati come documenti allegati
    """
    text: str = result.get("text", "")
    files: list[str] = result.get("files", [])

    # ── Testo ─────────────────────────────────────────────────
    if text:
        max_len = 4096
        chunks = [text[i : i + max_len] for i in range(0, len(text), max_len)]
        for chunk in chunks:
            try:
                await update.message.reply_text(chunk, parse_mode="Markdown")
            except Exception:
                # Markdown malformato → invia come plain text
                try:
                    await update.message.reply_text(chunk)
                except Exception as e:
                    logger.error(f"Errore invio testo: {e}")

    # ── File allegati ─────────────────────────────────────────
    for file_path in files:
        fp = Path(file_path)
        if not fp.exists():
            logger.warning(f"File da inviare non trovato: {fp}")
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
                        caption="🎙️ Messaggio vocale",
                    )
                else:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=f,
                        filename=fp.name,
                    )
            logger.info(f"📤 File inviato su Telegram: {fp.name}")
        except Exception as e:
            logger.error(f"Errore invio file '{fp}': {e}")
            await update.message.reply_text(f"⚠️ Errore nell'invio del file: `{fp.name}`", parse_mode="Markdown")


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler per il comando /start."""
    if not _is_authorized(update):
        await _reject(update)
        return

    await update.message.reply_text(
        "👋 Ciao\\! Sono **Demuclaw**, il tuo assistente AI personale locale\\.\n\n"
        "Ecco cosa posso fare per te:\n\n"
        "📂 *Filesystem* — leggere, scrivere, esplorare file sul tuo PC\n"
        "🌐 *Web Search* — cercare su internet con DuckDuckGo\n"
        "📄 *Documenti* — generare PDF, Word, Excel, PowerPoint\n"
        "🖼️ *Immagini* — generare immagini con Stable Diffusion \\(SDXL\\)\n"
        "🎙️ *Voice* — trascrivere messaggi vocali con Whisper\n"
        "👁️ *Vision* — analizzare foto che mi invii\n"
        "🧠 *Memoria* — ricordare le tue preferenze nel tempo\n\n"
        "Dimmi pure come posso aiutarti\\!",
        parse_mode="MarkdownV2",
    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler per il comando /clear — svuota la cronologia a breve termine."""
    if not _is_authorized(update):
        await _reject(update)
        return
        
    from src.memory.database import get_connection
    try:
        conn = get_connection()
        conn.execute("DELETE FROM conversations")
        conn.commit()
        conn.close()
        await update.message.reply_text("🧹 Memoria a breve termine svuotata!")
    except Exception as e:
        await update.message.reply_text(f"❌ Errore durante la pulizia: {e}")


async def persona_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler /persona — Mostra il menu per cambiare personalità."""
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
        "🎭 **Persona Engine**\nScegli l'identità di Demuclaw. Cambiando persona, cambieranno anche il tono e la voce:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def persona_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce il click sui bottoni del menu personalità."""
    query = update.callback_query
    data = query.data
    
    await query.answer()

    if not _is_authorized(update):
        logger.warning(f"🚫 Tentativo di cambio personalità non autorizzato da UID: {update.effective_user.id}")
        return

    if data.startswith("set_persona:"):
        name = data.split(":")[1]
        logger.info(f"🎭 Cambio personalità richiesto: {name}")
        
        from src.memory.preferences import switch_persona
        if switch_persona(name):
            await query.edit_message_text(
                f"🎭 Personalità cambiata in: **{name}**\nDa ora risponderò con questo carattere e questa voce! ✨",
                parse_mode="Markdown"
            )
        else:
            logger.error(f"❌ Errore nel database durante lo switch a {name}")
            await query.edit_message_text("❌ Errore nel database durante il cambio personalità.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler per i messaggi di testo."""
    if not _is_authorized(update):
        await _reject(update)
        return

    user_message = update.message.text
    logger.info(f"✉️ Testo: {user_message[:100]!r}")

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    result = await run_agent(user_message)
    await _send_result(update, context, result)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler per foto inviate direttamente (non come documento)."""
    if not _is_authorized(update):
        await _reject(update)
        return

    caption = update.message.caption or "Descrivi questa immagine in dettaglio."
    logger.info(f"📷 Foto ricevuta — caption: {caption!r}")

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    # Scarica la versione più grande disponibile
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    image_path = TEMP_DIR / f"photo_{update.message.message_id}.jpg"
    await tg_file.download_to_drive(str(image_path))

    try:
        result = await run_agent(caption, image_path=str(image_path))
        await _send_result(update, context, result)
    finally:
        # Pulizia file temporaneo
        try:
            image_path.unlink(missing_ok=True)
        except Exception:
            pass


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler per messaggi vocali — trascrive con Whisper poi invia all'agente."""
    if not _is_authorized(update):
        await _reject(update)
        return

    logger.info("🎙️ Messaggio vocale ricevuto")
    await update.message.reply_text("🎙️ Trascrivo il tuo messaggio...")

    # Scarica il file audio
    voice = update.message.voice
    tg_file = await context.bot.get_file(voice.file_id)
    audio_path = TEMP_DIR / f"voice_{update.message.message_id}.ogg"
    await tg_file.download_to_drive(str(audio_path))

    try:
        # Trascrivi con Whisper
        from src.tools.whisper_tool import transcribe_audio

        transcript_result = transcribe_audio(str(audio_path))

        if "error" in transcript_result:
            await update.message.reply_text(
                f"❌ Errore trascrizione: {transcript_result['error']}"
            )
            return

        transcript = transcript_result["transcript"]
        lang = transcript_result.get("language", "?")
        duration = transcript_result.get("duration_seconds", 0)

        logger.info(f"✅ Trascritto ({lang}, {duration}s): {transcript[:80]}")

        # Mostra la trascrizione all'utente
        await update.message.reply_text(
            f"🎙️ *Hai detto* \\({lang}, {duration}s\\):\n_{transcript}_",
            parse_mode="MarkdownV2",
        )

        # Invia il testo trascritto all'agente
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )
        result = await run_agent(transcript)
        await _send_result(update, context, result)

    finally:
        try:
            audio_path.unlink(missing_ok=True)
        except Exception:
            pass


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler per documenti/file inviati come allegato.
    - Immagini → analisi vision
    - Testo/codice → legge il contenuto e lo passa all'agente
    - Altri formati → informa l'agente del percorso
    """
    if not _is_authorized(update):
        await _reject(update)
        return

    doc = update.message.document
    caption = update.message.caption or f"Analizza il file '{doc.file_name}'."
    logger.info(f"📎 Documento ricevuto: {doc.file_name}")

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
            # Tratta come immagine per vision
            result = await run_agent(caption, image_path=str(doc_path))

        elif suffix in text_exts:
            # Leggi il contenuto testuale e passalo all'agente
            try:
                content = doc_path.read_text(encoding="utf-8", errors="replace")
                # Tronca se troppo lungo per il contesto
                if len(content) > 6000:
                    content = content[:6000] + "\n\n[... contenuto troncato ...]"
                message = f"{caption}\n\nContenuto di `{doc.file_name}`:\n```\n{content}\n```"
            except Exception as e:
                message = f"Ho ricevuto il file '{doc.file_name}'. Non riesco a leggerlo: {e}"
            result = await run_agent(message)

        else:
            # Tipo file non gestito direttamente
            message = (
                f"Ho ricevuto il file '{doc.file_name}' "
                f"({doc.file_size} bytes, tipo: {doc.mime_type}). "
                f"{caption}"
            )
            result = await run_agent(message)

        await _send_result(update, context, result)

    finally:
        try:
            doc_path.unlink(missing_ok=True)
        except Exception:
            pass


# ─── App Factory ──────────────────────────────────────────────────────────────

def create_application() -> Application:
    """Crea e configura l'applicazione Telegram con tutti gli handler registrati."""
    app = Application.builder().token(config.telegram_token).build()

    # Priority 1: Bottoni e menu (Callback queries)
    app.add_handler(CallbackQueryHandler(persona_callback))

    # Priority 2: Comandi espliciti
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("persona", persona_command))

    # Priority 3: Messaggi generici (testo, foto, voce, doc)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    from src.tools.cron_tool import init_job_queue
    init_job_queue(app.job_queue, config.telegram_allowed_user_id)

    logger.info("✅ Handler Telegram registrati")
    return app
