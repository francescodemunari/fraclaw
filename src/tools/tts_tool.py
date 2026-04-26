"""
tts_tool.py — Hybrid Speech Synthesis Engine.
Supports Premium (Chatterbox / Local) and Lite (Edge-TTS / Fast) synthesis.
"""

import os
import torch
import soundfile as sf
import asyncio
import edge_tts
from pathlib import Path
from datetime import datetime
from loguru import logger
from src.memory.preferences import get_active_persona
from src.config import config

# Directories — resolved relative to project root regardless of working directory
_PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_DIR = _PROJECT_ROOT / "data" / "output"
VOICES_DIR = _PROJECT_ROOT / "data" / "voices"

# Check for premium support
try:
    import torch
    from chatterbox import ChatterboxTTS
    HAS_PREMIUM_LIBS = True
except ImportError:
    HAS_PREMIUM_LIBS = False
    logger.warning("💎 Premium Audio components not found. Running in LITE mode only.")

# Global model cache for Chatterbox
_MODEL_CACHE = {}

def _ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    VOICES_DIR.mkdir(parents=True, exist_ok=True)

def _get_chatterbox():
    """Initializes/Caches Chatterbox. (Premium Mode)"""
    if not HAS_PREMIUM_LIBS:
        return None

    if "chatterbox" in _MODEL_CACHE:
        return _MODEL_CACHE["chatterbox"]
    
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"🚀 Initializing Premium Voice Engine (Chatterbox) on {device.upper()}...")
        model = ChatterboxTTS.from_pretrained(device=device)
        _MODEL_CACHE["chatterbox"] = model
        return model
    except Exception as e:
        logger.error(f"Chatterbox fail: {e}")
        return None

async def generate_speech(text: str, voice: str = None) -> dict:
    """
    Orchestrates speech generation using selected engine.
    """
    _ensure_dirs()
    persona = get_active_persona()
    is_premium = persona.get("premium_voice", False)
    persona_name = persona.get("name", "Jarvis")
    voice_id = voice or persona.get("voice_id", "en-US-AndrewNeural")

    filename = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    filepath = OUTPUT_DIR / filename

    if is_premium and HAS_PREMIUM_LIBS:
        logger.info(f"💎 Using PREMIUM Engine (Chatterbox) for {persona_name}...")
        return await _generate_premium(text, persona_name, filepath, filename)
    else:
        if is_premium and not HAS_PREMIUM_LIBS:
            logger.warning(f"⚠️ Premium requested for {persona_name} but components missing. Falling back to LITE.")
        logger.info(f"⚡ Using LITE Engine (Edge-TTS) for {persona_name}...")
        return await _generate_lite(text, voice_id, filepath, filename)

async def _generate_lite(text: str, voice_id: str, filepath: Path, filename: str) -> dict:
    """Fast synthesis using Edge-TTS."""
    try:
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(str(filepath))
        logger.success(f"🔊 Lite Audio generated: {filename}")
        return {
            "success": True,
            "path": str(filepath.absolute()),
            "filename": filename,
            "engine": "edge-tts"
        }
    except Exception as e:
        logger.error(f"Lite TTS error: {e}")
        return {"error": str(e)}

async def _generate_premium(text: str, persona_name: str, filepath: Path, filename: str) -> dict:
    """High-quality cloning using Chatterbox."""
    if not HAS_PREMIUM_LIBS:
        return {
            "error": "Premium Audio components are not installed. Please run 'pip install -r requirements-premium.txt' to enable this feature."
        }
    
    try:
        # Reference voice search
        ref_path = VOICES_DIR / f"{persona_name}_ref.wav"
        if not ref_path.exists():
            ref_path = VOICES_DIR / "default_ref.wav"
        
        audio_prompt_path = str(ref_path) if ref_path.exists() else None
        
        model = _get_chatterbox()
        if not model:
            return {"error": "Chatterbox engine not available."}

        def _synth():
            audio_tensor = model.generate(
                text=text, 
                audio_prompt_path=audio_prompt_path,
                exaggeration=0.4
            )
            audio_np = audio_tensor.squeeze().cpu().numpy()
            sf.write(str(filepath), audio_np, model.sr)
            return filepath

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _synth)

        logger.success(f"🔊 Premium Audio generated: {filename}")
        return {
            "success": True,
            "path": str(filepath.absolute()),
            "filename": filename,
            "engine": "chatterbox"
        }
    except Exception as e:
        logger.error(f"Premium TTS error: {e}")
        return {"error": str(e)}
