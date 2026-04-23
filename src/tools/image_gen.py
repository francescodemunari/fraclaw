"""
image_gen.py — Image generation via ComfyUI + VRAM Exclusive Mode

Exclusive mode flow:
  1. Unload LLM model from VRAM (LM Studio API)
  2. Send workflow to ComfyUI
  3. Poll every 2 seconds until the image is ready
  4. Download image from ComfyUI server
  5. Reload LLM model into VRAM

Uses standard ComfyUI nodes (KSampler + SDXL).
Compatible with any .safetensors checkpoint.
"""

import asyncio
import json
import random
from pathlib import Path

import httpx
from loguru import logger

from src.config import config

OUTPUT_DIR = Path("data/generated_images")

# ─── Base SDXL Workflow ───────────────────────────────────────────────────────
# ComfyUI node structure (API format, not UI)
_WORKFLOW_TEMPLATE = {
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "PLACEHOLDER_MODEL"},
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "PLACEHOLDER_POSITIVE", "clip": ["4", 1]},
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "PLACEHOLDER_NEGATIVE", "clip": ["4", 1]},
    },
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 42,
            "steps": 25,
            "cfg": 7.0,
            "sampler_name": "dpmpp_2m",
            "scheduler": "karras",
            "denoise": 1.0,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "fraclaw", "images": ["8", 0]},
    },
}

_DEFAULT_NEGATIVE = (
    "blurry, lowres, bad anatomy, bad hands, cropped, worst quality, "
    "watermark, text, logo, deformed, ugly, disfigured"
)


# ─── LM Studio VRAM Management ───────────────────────────────────────────────

async def _unload_llm() -> None:
    """Unloads the LLM model from VRAM via LM Studio API."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{config.lm_studio_api_url}/api/v0/models/unload",
                json={"identifier": config.lm_studio_model},
            )
            logger.info(f"🔽 LLM unload → HTTP {resp.status_code}")
    except Exception as e:
        # Do not block generation if unload fails
        logger.warning(f"Unload LLM failed (continuing anyway): {e}")


async def _load_llm() -> None:
    """Reloads the LLM model into VRAM via LM Studio API."""
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{config.lm_studio_api_url}/api/v0/models/load",
                json={"identifier": config.lm_studio_model},
            )
            logger.info(f"🔼 LLM reload → HTTP {resp.status_code}")
    except Exception as e:
        logger.error(f"Reload LLM failed: {e}")


# ─── ComfyUI API ─────────────────────────────────────────────────────────────

async def _submit_workflow(workflow: dict) -> str | None:
    """Submits the workflow to ComfyUI and returns the prompt_id."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{config.comfyui_url}/prompt",
                json={"prompt": workflow},
            )
            resp.raise_for_status()
            prompt_id = resp.json().get("prompt_id")
            logger.info(f"🎨 ComfyUI prompt submitted — id: {prompt_id}")
            return prompt_id
    except Exception as e:
        logger.error(f"Error submitting ComfyUI workflow: {e}")
        return None


async def _poll_for_result(prompt_id: str, max_wait_seconds: int = 180) -> str | None:
    """
    Polls ComfyUI every 2 seconds to check for completion.
    Returns the generated image filename, or None if timeout expires.
    """
    iterations = max_wait_seconds // 2
    for attempt in range(iterations):
        await asyncio.sleep(2)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{config.comfyui_url}/history/{prompt_id}")
                history = resp.json()

            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_output in outputs.values():
                    images = node_output.get("images", [])
                    if images:
                        fname = images[0]["filename"]
                        logger.info(f"✅ Image generated: {fname} (after {attempt * 2}s)")
                        return fname

        except Exception as e:
            logger.warning(f"Polling ComfyUI error: {e}")

        logger.debug(f"⏳ Waiting for ComfyUI result... ({attempt * 2}s/{max_wait_seconds}s)")

    logger.error("Timeout: ComfyUI generation not completed")
    return None


async def _download_image(filename: str) -> Path | None:
    """Downloads the generated image from ComfyUI and saves it locally."""
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / filename

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{config.comfyui_url}/view",
                params={"filename": filename},
            )
            resp.raise_for_status()
            out_path.write_bytes(resp.content)

        logger.info(f"📥 Image saved: {out_path}")
        return out_path

    except Exception as e:
        logger.error(f"Error downloading image: {e}")
        return None


# ─── Main Entrypoint ─────────────────────────────────────────────────────────

async def generate_image(
    prompt: str,
    negative_prompt: str = "",
    seed: int = -1,
) -> dict:
    """
    Generates an image using ComfyUI with VRAM exclusive mode.

    Args:
        prompt:          Image description in English (detailed is better).
        negative_prompt: What to avoid (default: common artifacts).
        seed:            Reproducibility seed (-1 = random).

    Returns dict with:
        - success: True
        - path: absolute image path
        - filename: filename
        - seed: used seed
    """
    if seed == -1:
        seed = random.randint(0, 2**31 - 1)

    logger.info(f"🖼️ Generating image — prompt: '{prompt[:60]}...' | seed: {seed}")

    try:
        # ── Step 1: Unload LLM from VRAM ─────────────────────
        if config.vram_mode == "exclusive":
            logger.info("⚡ VRAM exclusive: unloading LLM...")
            await _unload_llm()
            await asyncio.sleep(3)  # Pause to free VRAM

        # ── Step 2: Prepare and submit workflow ──────────────
        workflow = json.loads(json.dumps(_WORKFLOW_TEMPLATE))  # deep copy
        workflow["4"]["inputs"]["ckpt_name"] = config.comfyui_model
        workflow["6"]["inputs"]["text"] = prompt
        workflow["7"]["inputs"]["text"] = negative_prompt or _DEFAULT_NEGATIVE
        workflow["3"]["inputs"]["seed"] = seed

        prompt_id = await _submit_workflow(workflow)
        if not prompt_id:
            return {"error": "Could not connect to ComfyUI. Ensure it is running."}

        # ── Step 3: Wait for completion ─────────────────────
        image_filename = await _poll_for_result(prompt_id)
        if not image_filename:
            return {"error": "Image generation timeout (>3 minutes)."}

        # ── Step 4: Download image ──────────────────────────
        image_path = await _download_image(image_filename)
        if not image_path:
            return {"error": "Error downloading image from ComfyUI."}

        return {
            "success": True,
            "path": str(image_path),
            "filename": image_filename,
            "seed": seed,
        }

    except Exception as e:
        logger.error(f"Image generation error: {e}")
        return {"error": str(e)}

    finally:
        # ── Step 5: Reload LLM (always, even on error) ─────
        if config.vram_mode == "exclusive":
            logger.info("⚡ VRAM exclusive: reloading LLM...")
            await _load_llm()
