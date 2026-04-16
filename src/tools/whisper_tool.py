"""
whisper_tool.py — Trascrizione audio con faster-whisper

faster-whisper è una versione ottimizzata di Whisper (OpenAI) che gira
interamente in locale, senza nessuna chiamata a server esterni.

Il modello viene caricato in modo lazy (solo al primo utilizzo) e
mantenuto in memoria per chiamate successive più veloci.

Configurazione:
  - WHISPER_MODEL=base → buon bilanciamento velocità/qualità (74M parametri)
  - device="cpu" + compute_type="int8" → funziona anche senza GPU dedicata
"""

from pathlib import Path

from loguru import logger

# Singleton del modello (caricato una sola volta)
_whisper_model = None


def _get_model():
    """Carica (o restituisce) il modello Whisper."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        from src.config import config

        logger.info(f"🎙️ Caricamento modello Whisper '{config.whisper_model}'...")
        _whisper_model = WhisperModel(
            config.whisper_model,
            device="cpu",
            compute_type="int8",  # Quantizzazione: più veloce, meno RAM
        )
        logger.info("✅ Whisper pronto")
    return _whisper_model


def transcribe_audio(audio_path: str) -> dict:
    """
    Trascrive un file audio in testo.

    Formati supportati: .ogg, .mp3, .wav, .m4a, .flac, .webm

    Args:
        audio_path: Percorso assoluto al file audio.

    Returns dict con:
        - transcript: testo trascritto
        - language:   lingua rilevata automaticamente (es. "it", "en")
        - duration_seconds: durata del file audio
    """
    try:
        p = Path(audio_path)
        if not p.exists():
            return {"error": f"File audio non trovato: {audio_path}"}

        logger.info(f"🎙️ Trascrizione: {p.name}")
        model = _get_model()

        # beam_size=5: buon compromesso velocità/accuratezza
        segments, info = model.transcribe(str(p), beam_size=5)

        # Itera tutti i segmenti e concatena
        transcript = " ".join(seg.text.strip() for seg in segments).strip()

        logger.info(
            f"✅ Trascritto ({info.language}, {info.duration:.1f}s): "
            f"{transcript[:80]}{'...' if len(transcript) > 80 else ''}"
        )
        return {
            "transcript": transcript,
            "language": info.language,
            "duration_seconds": round(info.duration, 1),
        }

    except Exception as e:
        logger.error(f"Errore trascrizione audio: {e}")
        return {"error": str(e)}
