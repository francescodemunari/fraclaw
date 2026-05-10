"""
tts_tool.py — Voice Synthesis via Edge-TTS.
"""

import edge_tts
from pathlib import Path
from datetime import datetime
from loguru import logger
from src.memory.preferences import get_active_persona

_PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_DIR = _PROJECT_ROOT / "data" / "output"


def _ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def generate_speech(text: str, voice: str = None) -> dict:
    """Generates speech audio using Edge-TTS."""
    _ensure_dirs()
    persona = get_active_persona()
    voice_id = voice or persona.get("voice_id", "en-US-AndrewNeural")

    filename = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    filepath = OUTPUT_DIR / filename

    try:
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(str(filepath))
        logger.success(f"Audio generated: {filename}")
        return {
            "success": True,
            "path": str(filepath.absolute()),
            "filename": filename,
            "engine": "edge-tts"
        }
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return {"error": str(e)}
