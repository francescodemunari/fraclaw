"""
tts_tool.py — Sintesi vocale (Text-To-Speech) con edge-tts.
Genera file audio realistici usando le voci neurali di Microsoft Edge.
"""

import asyncio
from pathlib import Path
from datetime import datetime
from loguru import logger
import edge_tts

from src.memory.preferences import get_active_persona

OUTPUT_DIR = Path("data/output")

def _ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

async def generate_speech(text: str, voice: str = None) -> dict:
    """
    Converte il testo in un file audio (messaggio vocale).
    
    Args:
        text: Il testo da leggere.
        voice: Identificativo della voce. Se None, usa quella della persona attiva.
        
    Returns dict con il path del file generato.
    """
    try:
        _ensure_output_dir()
        
        # Se non specificato, prendi la voce dalla personalità attuale
        if voice is None:
            persona = get_active_persona()
            voice = persona.get("voice_id", "it-IT-GiuseppeNeural")
        
        # Nome file con timestamp per evitare collisioni
        filename = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        filepath = OUTPUT_DIR / filename
        
        logger.info(f"🎙️ Generazione sintesi vocale: {text[:50]}...")
        
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(filepath))
        
        logger.info(f"✅ Vocale generato: {filepath}")
        
        return {
            "success": True,
            "path": str(filepath),
            "filename": filename,
            "type": "audio" # Segnaliamo che è un audio per l'handler
        }
        
    except Exception as e:
        logger.error(f"Errore sintesi vocale: {e}")
        return {"error": str(e)}
