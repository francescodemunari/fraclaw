"""
vision.py — Conversione immagini per il modello multimodale

Qwen3.5-9B-Vision accetta immagini come data URL base64.
Questo modulo converte file immagine → base64 e costruisce
il formato messaggio corretto per l'API OpenAI-compatible.
"""

import base64
from pathlib import Path

from loguru import logger

# Estensioni supportate e relativi MIME type
_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def image_to_base64(image_path: str) -> dict:
    """
    Converte un'immagine su disco in una stringa base64.

    Returns dict con:
        - base64: stringa base64
        - mime_type: es. "image/jpeg"
        - data_url: stringa completa da usare nell'API (data:image/jpeg;base64,...)
        - path: percorso assoluto
    """
    try:
        p = Path(image_path)
        if not p.exists():
            return {"error": f"Immagine non trovata: {image_path}"}
        if not p.is_file():
            return {"error": f"Il percorso non è un file: {image_path}"}

        suffix = p.suffix.lower()
        mime_type = _MIME_MAP.get(suffix, "image/jpeg")

        with open(p, "rb") as f:
            raw = f.read()

        encoded = base64.b64encode(raw).decode("utf-8")
        data_url = f"data:{mime_type};base64,{encoded}"

        logger.debug(f"🖼️ Immagine convertita in base64: {p.name} ({len(raw)} bytes)")
        return {
            "base64": encoded,
            "mime_type": mime_type,
            "data_url": data_url,
            "path": str(p),
        }

    except Exception as e:
        logger.error(f"Errore conversione immagine: {e}")
        return {"error": str(e)}


def build_vision_message(text: str, image_path: str) -> dict:
    """
    Costruisce un messaggio multimodale per il LLM nel formato OpenAI.

    Il contenuto è una lista con:
      1. Un oggetto image_url (base64 encoded)
      2. Un oggetto text con la domanda/istruzione

    Returns:
        Dizionario messaggio con role="user" e content come lista,
        oppure dict con "error" se l'immagine non è accessibile.
    """
    img = image_to_base64(image_path)
    if "error" in img:
        logger.warning(f"Fallback a messaggio testuale: {img['error']}")
        return {"role": "user", "content": text, "_vision_error": img["error"]}

    return {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": img["data_url"]},
            },
            {
                "type": "text",
                "text": text,
            },
        ],
    }
