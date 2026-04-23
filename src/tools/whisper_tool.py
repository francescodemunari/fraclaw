"""
whisper_tool.py — Audio transcription via faster-whisper

faster-whisper is an optimized version of OpenAI's Whisper that runs
entirely locally, ensuring total privacy.

The model is loaded lazily (only on first use) and cached for faster
subsequent calls.
"""

from pathlib import Path

from loguru import logger

# Model singleton (loaded once)
_whisper_model = None


def _get_model():
    """Loads (or returns) the Whisper model."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        from src.config import config

        logger.info(f"🎙️ Loading Whisper model '{config.whisper_model}'...")
        _whisper_model = WhisperModel(
            config.whisper_model,
            device="cpu",
            compute_type="int8",  # Quantization: faster, less RAM usage
        )
        logger.info("✅ Whisper ready")
    return _whisper_model


def transcribe_audio(audio_path: str) -> dict:
    """
    Transcribes an audio file into text.

    Supported formats: .ogg, .mp3, .wav, .m4a, .flac, .webm

    Args:
        audio_path: Absolute path to the audio file.

    Returns dict with:
        - transcript: transcribed text
        - language:   automatically detected language (e.g., "en", "it")
        - duration_seconds: audio file duration
    """
    try:
        p = Path(audio_path)
        if not p.exists():
            return {"error": f"Audio file not found: {audio_path}"}

        logger.info(f"🎙️ Transcription: {p.name}")
        model = _get_model()

        # beam_size=5: good compromise between speed and accuracy
        # language=None allows automatic language detection
        segments, info = model.transcribe(str(p), beam_size=5, language=None)

        # Iterate all segments and join them
        transcript = " ".join(seg.text.strip() for seg in segments).strip()

        logger.info(
            f"✅ Transcribed ({info.language}, {info.duration:.1f}s): "
            f"{transcript[:80]}{'...' if len(transcript) > 80 else ''}"
        )
        return {
            "transcript": transcript,
            "language": info.language,
            "duration_seconds": round(info.duration, 1),
        }

    except Exception as e:
        logger.error(f"Audio transcription error: {e}")
        return {"error": str(e)}
