"""
vision.py — Image conversion for multimodal models

Qwen3.5-9B-Vision accepts images as base64 data URLs.
This module converts image files → base64 and builds
the correct message format for the OpenAI-compatible API.
"""

import base64
from pathlib import Path

from loguru import logger

# Supported extensions and relative MIME types
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
    Converts an image on disk to a base64 string.

    Returns dict with:
        - base64: base64 string
        - mime_type: e.g. "image/jpeg"
        - data_url: full string for API use (data:image/jpeg;base64,...)
        - path: absolute path
    """
    try:
        p = Path(image_path)
        if not p.exists():
            return {"error": f"Image not found: {image_path}"}
        if not p.is_file():
            return {"error": f"Path is not a file: {image_path}"}

        suffix = p.suffix.lower()
        if suffix not in _MIME_MAP:
            return {"error": f"Unsupported image format: {suffix}"}
        
        mime_type = _MIME_MAP[suffix]

        with open(p, "rb") as f:
            raw = f.read()

        encoded = base64.b64encode(raw).decode("utf-8")
        data_url = f"data:{mime_type};base64,{encoded}"

        logger.debug(f"🖼️ Image converted to base64: {p.name} ({len(raw)} bytes)")
        return {
            "base64": encoded,
            "mime_type": mime_type,
            "data_url": data_url,
            "path": str(p),
        }

    except Exception as e:
        logger.error(f"Image conversion error: {e}")
        return {"error": str(e)}


def build_vision_message(text: str, image_path: str) -> dict:
    """
    Builds a multimodal message for the LLM in OpenAI format.

    The content is a list containing:
      1. An image_url object (base64 encoded)
      2. A text object with the question/instruction

    Returns:
        Message dictionary with role="user" and content as a list,
        or a dict with "error" if the image is inaccessible.
    """
    img = image_to_base64(image_path)
    if "error" in img:
        logger.warning(f"Falling back to text message: {img['error']}")
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
