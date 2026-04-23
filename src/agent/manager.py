"""
manager.py — Dynamic Model Manager for LM Studio (Barrier 5.0)

This module handles loading and unloading models via REST API v1, 
implementing a blocking safety barrier to prevent VRAM saturation.
"""

import aiohttp
import asyncio
import time
from loguru import logger
from src.config import config

class ModelManager:
    """Manages model lifecycle with blocking VRAM verification."""

    @staticmethod
    def _get_api_url() -> str:
        return config.lm_studio_api_url.rstrip("/")

    @staticmethod
    async def get_active_instances() -> list[dict]:
        """
        Returns data for all loaded instances in VRAM.
        Returns a list of dicts: [{'id': str, 'context_length': int}]
        """
        api_url = ModelManager._get_api_url()
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{api_url}/api/v1/models") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models_data = data.get("models", [])
                        instances_info = []
                        for m in models_data:
                            instances = m.get("loaded_instances", [])
                            for inst in instances:
                                iid = inst.get("id")
                                if iid:
                                    # Extract context from LM Studio v1 internal config
                                    ctx = inst.get("config", {}).get("context_length", 0)
                                    instances_info.append({"id": iid, "context_length": ctx})
                        return instances_info
        except Exception as e:
            logger.error(f"Detailed VRAM check error: {e}")
        return []

    @staticmethod
    async def verify_vram_empty(timeout_sec: float = 5.0) -> bool:
        """Waits until VRAM is completely empty."""
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            instances = await ModelManager.get_active_instances()
            if not instances:
                logger.info("🛡️ Safety Barrier: VRAM confirmed empty.")
                return True
            logger.debug(f"⏳ Waiting for {len(instances)} instances to be removed...")
            await asyncio.sleep(0.5)
        
        # Timeout reached
        remaining = await ModelManager.get_active_instances()
        if remaining:
            logger.critical(f"🚨 SAFETY FAILED: {len(remaining)} instances still in VRAM after {timeout_sec}s!")
            return False
        return True

    @staticmethod
    async def unload_all_models() -> bool:
        """Clears VRAM and VERIFIES success."""
        api_url = ModelManager._get_api_url()
        instance_ids = await ModelManager.get_active_instances()
        
        if not instance_ids:
            logger.debug("🧹 VRAM already clean.")
            return True

        logger.warning(f"⚠️ VRAM FORCE CLEANUP: Ejecting {len(instance_ids)} instances...")
        
        # Send unload commands
        async with aiohttp.ClientSession() as session:
            for inst in instance_ids:
                iid = inst["id"]
                try:
                    await session.post(f"{api_url}/api/v1/models/unload", json={"instance_id": iid})
                except Exception as e:
                    logger.error(f"Unload error for {iid}: {e}")

        # BLOCKING VERIFICATION
        return await ModelManager.verify_vram_empty(timeout_sec=5.0)

    @staticmethod
    async def load_model(model_identifier: str, context_length: int = 20000) -> bool:
        """Loads a model ONLY if VRAM is confirmed empty."""
        api_url = ModelManager._get_api_url()
        
        # 1. Guaranteed cleanup with verification
        vram_safe = await ModelManager.unload_all_models()
        if not vram_safe:
            logger.critical(f"❌ LOAD ABORTED: VRAM saturation danger for {model_identifier}!")
            return False

        # 2. Actual loading
        logger.info(f"🚀 Safe model load: {model_identifier}")
        try:
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {
                    "model": model_identifier,
                    "context_length": context_length,
                    "flash_attention": True
                }
                async with session.post(f"{api_url}/api/v1/models/load", json=payload) as resp:
                    if resp.status == 200:
                        logger.success(f"🎊 Model {model_identifier} loaded and ready.")
                        return True
                    else:
                        err = await resp.text()
                        logger.error(f"Load error: {resp.status} - {err}")
        except Exception as e:
            logger.error(f"Connection failed during loading: {e}")
        
        return False

    @staticmethod
    async def ensure_model(model_identifier: str, min_context: int = 20000) -> bool:
        """
        Ensures the requested model is the only one active and has 
        sufficient context.
        """
        active_instances = await ModelManager.get_active_instances()
        
        # If there is only one instance, verify name AND context
        if len(active_instances) == 1:
            inst = active_instances[0]
            loaded_id = inst["id"]
            current_ctx = inst["context_length"]
            
            # Name check
            name_match = (model_identifier in loaded_id or loaded_id in model_identifier)
            # Min required context check
            ctx_match = (current_ctx >= min_context)

            if name_match and ctx_match:
                logger.debug(f"✨ Model {model_identifier} (Ctx: {current_ctx}) already active. Skipping load.")
                return True
            
            if name_match and not ctx_match:
                logger.warning(f"📏 Insufficient context ({current_ctx} < {min_context}). Reloading required.")
            else:
                logger.info(f"🔄 Model switch requested: {loaded_id} -> {model_identifier}")

        elif len(active_instances) > 1:
            logger.warning(f"⚠️ Detected {len(active_instances)} instances. Cleanup required.")

        return await ModelManager.load_model(model_identifier, context_length=min_context)
