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
import subprocess
from pathlib import Path

import httpx
from loguru import logger

from src.config import config
from src.agent.manager import ModelManager

_PROJECT_ROOT = Path(__file__).parent.parent.parent
OUTPUT_DIR = _PROJECT_ROOT / "data" / "generated_images"

# ─── ComfyUI Autostart ───────────────────────────────────────────────────────

async def _ensure_comfyui_running() -> bool:
    """Checks if ComfyUI is running, and if not, attempts to auto-start it."""
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            await client.get(f"{config.comfyui_url}/system_stats")
            return True
    except httpx.RequestError:
        logger.warning("ComfyUI non rilevato, provo ad avviarlo in automatico...")
        comfy_exe = Path.home() / "AppData/Local/Programs/ComfyUI/ComfyUI.exe"
        if comfy_exe.exists():
            # Force minimization of the electron app window so it doesn't interrupt the user
            subprocess.Popen(
                f'start /min "" "{comfy_exe}"', 
                shell=True, 
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            logger.info("ComfyUI avviato. Attendo 15 secondi per il caricamento...")
            await asyncio.sleep(15) # Wait for ComfyUI to fully boot
            return True
        else:
            logger.error(f"Impossibile trovare ComfyUI.exe in {comfy_exe}")
            return False

# ─── Base SDXL Workflow ───────────────────────────────────────────────────────
# ComfyUI node structure (API format, not UI)
_WORKFLOW_TEMPLATE = {
  "10": {
    "inputs": {
      "text": "PLACEHOLDER_NEGATIVE",
      "clip": ["11", 1]
    },
    "class_type": "CLIPTextEncode"
  },
  "11": {
    "inputs": {
      "ckpt_name": "PLACEHOLDER_MODEL"
    },
    "class_type": "CheckpointLoaderSimple"
  },
  "12": {
    "inputs": {
      "seed": 42,
      "steps": 6,
      "cfg": 2,
      "sampler_name": "dpmpp_sde",
      "scheduler": "karras",
      "denoise": 1,
      "model": ["11", 0],
      "positive": ["17", 0],
      "negative": ["10", 0],
      "latent_image": ["13", 0]
    },
    "class_type": "KSampler"
  },
  "13": {
    "inputs": {
      "width": 1024,
      "height": 1024,
      "batch_size": 1
    },
    "class_type": "EmptyLatentImage"
  },
  "14": {
    "inputs": {
      "samples": ["12", 0],
      "vae": ["11", 2]
    },
    "class_type": "VAEDecode"
  },
  "15": {
    "inputs": {
      "upscale_method": "bicubic",
      "scale_by": 1.5,
      "image": ["14", 0]
    },
    "class_type": "ImageScaleBy"
  },
  "16": {
    "inputs": {
      "pixels": ["15", 0],
      "vae": ["11", 2]
    },
    "class_type": "VAEEncode"
  },
  "17": {
    "inputs": {
      "text": "PLACEHOLDER_POSITIVE",
      "clip": ["11", 1]
    },
    "class_type": "CLIPTextEncode"
  },
  "18": {
    "inputs": {
      "filename_prefix": "fraclaw_base",
      "images": ["14", 0]
    },
    "class_type": "SaveImage"
  },
  "19": {
    "inputs": {
      "seed": 43,
      "steps": 6,
      "cfg": 2,
      "sampler_name": "dpmpp_sde",
      "scheduler": "karras",
      "denoise": 0.5,
      "model": ["11", 0],
      "positive": ["17", 0],
      "negative": ["10", 0],
      "latent_image": ["16", 0]
    },
    "class_type": "KSampler"
  },
  "20": {
    "inputs": {
      "filename_prefix": "fraclaw_upscale",
      "images": ["21", 0]
    },
    "class_type": "SaveImage"
  },
  "21": {
    "inputs": {
      "samples": ["19", 0],
      "vae": ["11", 2]
    },
    "class_type": "VAEDecode"
  }
}

_DEFAULT_NEGATIVE = "easynegative, badhandv4"



# ─── LM Studio VRAM Management ───────────────────────────────────────────────

async def _unload_llm() -> None:
    """Unloads the LLM model from VRAM via ModelManager."""
    await ModelManager.unload_all_models()


async def _load_llm() -> None:
    """Reloads the LLM model into VRAM via ModelManager."""
    await ModelManager.ensure_model(config.lm_studio_model)


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


async def _poll_for_result(prompt_id: str, max_wait_seconds: int = 600) -> str | None:
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
                
                target_node = "20" if "20" in outputs else (list(outputs.keys())[-1] if outputs else None)
                
                if target_node:
                    images = outputs[target_node].get("images", [])
                    if images:
                        fname = images[0]["filename"]
                        logger.info(f"✅ Image generated (Node {target_node}): {fname} (after {attempt * 2}s)")
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
        prompt:          You MUST rewrite the user's request from scratch into a highly detailed, dense, cinematic description of the image in English. DO NOT just copy the user's text.
        negative_prompt: What to avoid.
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
        # ── Step 0: Ensure ComfyUI is up and running ────────
        await _ensure_comfyui_running()

        # ── Step 1: Unload LLM from VRAM ─────────────────────
        if config.vram_mode == "exclusive":
            logger.info("⚡ VRAM exclusive: unloading LLM...")
            await _unload_llm()
            await asyncio.sleep(3)  # Pause to free VRAM

        # ── Step 2: Prepare and submit workflow ──────────────
        workflow = json.loads(json.dumps(_WORKFLOW_TEMPLATE))  # deep copy
        workflow["11"]["inputs"]["ckpt_name"] = config.comfyui_model
        # Use the highly detailed prompt generated by the AI
        workflow["17"]["inputs"]["text"] = prompt
        
        # Enforce ONLY the two embeddings in the negative prompt
        workflow["10"]["inputs"]["text"] = _DEFAULT_NEGATIVE
        
        workflow["12"]["inputs"]["seed"] = seed
        workflow["19"]["inputs"]["seed"] = seed + 1000

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
        # ── Step 5: Unload ComfyUI Models ──────────────────
        if config.vram_mode == "exclusive":
            try:
                logger.info("🧹 Freeing ComfyUI VRAM...")
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(f"{config.comfyui_url}/free", json={"unload_models": True, "free_memory": True})
            except Exception as e:
                logger.warning(f"Could not free ComfyUI VRAM: {e}")
                
        # ── Step 6: Reload LLM (always, even on error) ─────
        if config.vram_mode == "exclusive":
            logger.info("⚡ VRAM exclusive: reloading LLM...")
            await _load_llm()
