"""
image_gen.py — Generazione immagini via ComfyUI + VRAM Exclusive Mode

Flusso in modalità exclusive:
  1. Scarica il modello LLM dalla VRAM (LM Studio API)
  2. Manda il workflow a ComfyUI
  3. Polling ogni 2 secondi finché l'immagine è pronta
  4. Scarica l'immagine dal server ComfyUI
  5. Ricarica il modello LLM in VRAM

Il workflow usa i nodi base di ComfyUI (KSampler + SDXL).
Compatibile con qualsiasi checkpoint .safetensors.
"""

import asyncio
import json
import random
from pathlib import Path

import httpx
from loguru import logger

from src.config import config

OUTPUT_DIR = Path("data/generated_images")

# ─── Workflow SDXL base ───────────────────────────────────────────────────────
# Struttura nodi ComfyUI (formato API, non UI)
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
        "inputs": {"filename_prefix": "demuclaw", "images": ["8", 0]},
    },
}

_DEFAULT_NEGATIVE = (
    "blurry, lowres, bad anatomy, bad hands, cropped, worst quality, "
    "watermark, text, logo, deformed, ugly, disfigured"
)


# ─── LM Studio VRAM Management ───────────────────────────────────────────────

async def _unload_llm() -> None:
    """Scarica il modello LLM dalla VRAM tramite LM Studio API."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{config.lm_studio_api_url}/api/v0/models/unload",
                json={"identifier": config.lm_studio_model},
            )
            logger.info(f"🔽 LLM unload → HTTP {resp.status_code}")
    except Exception as e:
        # Non blocchiamo la generazione se l'unload fallisce
        logger.warning(f"Unload LLM fallito (continuo comunque): {e}")


async def _load_llm() -> None:
    """Ricarica il modello LLM in VRAM tramite LM Studio API."""
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{config.lm_studio_api_url}/api/v0/models/load",
                json={"identifier": config.lm_studio_model},
            )
            logger.info(f"🔼 LLM reload → HTTP {resp.status_code}")
    except Exception as e:
        logger.error(f"Reload LLM fallito: {e}")


# ─── ComfyUI API ─────────────────────────────────────────────────────────────

async def _submit_workflow(workflow: dict) -> str | None:
    """Invia il workflow a ComfyUI e restituisce il prompt_id."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{config.comfyui_url}/prompt",
                json={"prompt": workflow},
            )
            resp.raise_for_status()
            prompt_id = resp.json().get("prompt_id")
            logger.info(f"🎨 ComfyUI prompt inviato — id: {prompt_id}")
            return prompt_id
    except Exception as e:
        logger.error(f"Errore invio workflow ComfyUI: {e}")
        return None


async def _poll_for_result(prompt_id: str, max_wait_seconds: int = 180) -> str | None:
    """
    Fa polling a ComfyUI ogni 2 secondi per verificare il completamento.
    Restituisce il filename dell'immagine generata, o None se scade il timeout.
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
                        logger.info(f"✅ Immagine generata: {fname} (dopo {attempt * 2}s)")
                        return fname

        except Exception as e:
            logger.warning(f"Polling ComfyUI error: {e}")

        logger.debug(f"⏳ Attendo risultato ComfyUI... ({attempt * 2}s/{max_wait_seconds}s)")

    logger.error("Timeout: generazione ComfyUI non completata")
    return None


async def _download_image(filename: str) -> Path | None:
    """Scarica l'immagine generata da ComfyUI e la salva localmente."""
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

        logger.info(f"📥 Immagine salvata: {out_path}")
        return out_path

    except Exception as e:
        logger.error(f"Errore download immagine: {e}")
        return None


# ─── Entrypoint principale ────────────────────────────────────────────────────

async def generate_image(
    prompt: str,
    negative_prompt: str = "",
    seed: int = -1,
) -> dict:
    """
    Genera un'immagine usando ComfyUI con VRAM exclusive mode.

    Args:
        prompt:          Descrizione dell'immagine in inglese (dettagliata = meglio).
        negative_prompt: Cosa evitare (default: artefatti comuni).
        seed:            Seed per riproducibilità (-1 = casuale).

    Returns dict con:
        - success: True
        - path: percorso assoluto dell'immagine
        - filename: nome del file
        - seed: seed utilizzato
    """
    if seed == -1:
        seed = random.randint(0, 2**31 - 1)

    logger.info(f"🖼️ Generazione immagine — prompt: '{prompt[:60]}...' | seed: {seed}")

    try:
        # ── Step 1: Scarica LLM dalla VRAM ───────────────────
        if config.vram_mode == "exclusive":
            logger.info("⚡ VRAM exclusive: scarico LLM...")
            await _unload_llm()
            await asyncio.sleep(3)  # Pausa per liberare la VRAM

        # ── Step 2: Prepara e invia workflow ─────────────────
        workflow = json.loads(json.dumps(_WORKFLOW_TEMPLATE))  # deep copy
        workflow["4"]["inputs"]["ckpt_name"] = config.comfyui_model
        workflow["6"]["inputs"]["text"] = prompt
        workflow["7"]["inputs"]["text"] = negative_prompt or _DEFAULT_NEGATIVE
        workflow["3"]["inputs"]["seed"] = seed

        prompt_id = await _submit_workflow(workflow)
        if not prompt_id:
            return {"error": "Impossibile connettersi a ComfyUI. Assicurati che sia in esecuzione."}

        # ── Step 3: Attendi il completamento ─────────────────
        image_filename = await _poll_for_result(prompt_id)
        if not image_filename:
            return {"error": "Timeout nella generazione immagine (>3 minuti)."}

        # ── Step 4: Scarica l'immagine ────────────────────────
        image_path = await _download_image(image_filename)
        if not image_path:
            return {"error": "Errore nel download dell'immagine da ComfyUI."}

        return {
            "success": True,
            "path": str(image_path),
            "filename": image_filename,
            "seed": seed,
        }

    except Exception as e:
        logger.error(f"Errore generazione immagine: {e}")
        return {"error": str(e)}

    finally:
        # ── Step 5: Ricarica LLM (sempre, anche in caso di errore) ──
        if config.vram_mode == "exclusive":
            logger.info("⚡ VRAM exclusive: ricarico LLM...")
            await _load_llm()
