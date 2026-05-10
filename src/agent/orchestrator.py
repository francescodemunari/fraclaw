"""
orchestrator.py — Fraclaw's "Central Brain"

Receives input, decides the most suitable agent (Routing),
handles model switching via ModelManager, and coordinates responses.
"""

import json
import time
import re
import asyncio
from pathlib import Path
from loguru import logger

from src.agent.core import run_agent
from src.agent.utils import get_client, is_local_provider
from src.agent.prompts import get_narrator_prompt
from src.agent.manager import ModelManager
from src.config import config

class Orchestrator:
    """Coordinates specialized agents and manages model switching."""

    @staticmethod
    def _fast_route(message: str) -> str | None:
        """Quickly detects obvious intents using keywords."""
        msg = message.lower()

        audio_patterns = [
            r"\bspeak\b", r"\baloud\b", r"\bvoice message\b", r"\baudio\b",
            r"\bvoice\b", r"\btalk\b", r"\bsay it\b", r"\bread.*aloud\b",
            r"\busing.*voice\b", r"\bwith.*voice\b", r"\bedge voice\b",
            r"\btell me.*voice\b", r"\brespond.*voice\b", r"\banswer.*voice\b",
            r"\bspeak.*response\b", r"\bsing\b"
        ]
        if any(re.search(p, msg) for p in audio_patterns):
            logger.info("[FAST ROUTE] Detected AUDIO intent")
            return "AUDIO"

        image_patterns = [
            r"\bgenerate.*image\b", r"\bcreate.*image\b", r"\bdraw\b",
            r"\bgenerate.*picture\b", r"\bcreate.*picture\b",
            r"\bgenerate.*photo\b", r"\billustrat\b", r"\brender\b",
            r"\bimage of\b", r"\bpicture of\b", r"\bphoto of\b",
            r"\bdesign.*logo\b", r"\bcreate.*art\b", r"\bgenerate.*art\b"
        ]
        if any(re.search(p, msg) for p in image_patterns):
            logger.info("[FAST ROUTE] Detected IMAGE intent")
            return "IMAGE"

        coder_patterns = [
            r"\bpython\b", r"\bscript\b", r"\bcoding\b", r"\bdevelop\b",
            r"\bprogram\b", r"\bclass\s+\w+", r"\bdef\s+\w+\(",
            r"\b\.py\b", r"\b\.js\b", r"\b\.cpp\b", r"\b\.java\b"
        ]
        if any(re.search(p, msg) for p in coder_patterns):
            if "txt" not in msg or any(p in msg for p in ["python", "script", ".py"]):
                logger.info("[FAST ROUTE] Detected CODER intent")
                return "CODER"

        base_patterns = [
            r"\bciao\b", r"\bhello\b", r"\bhi\b", r"\bhey\b",
            r"\bmi chiamo\b", r"\bi am\b", r"\bi'm\b", r"\bnice to meet you\b"
        ]
        if any(re.search(p, msg) for p in base_patterns):
            logger.info("[FAST ROUTE] Detected BASE intent")
            return "BASE"

        return None

    @staticmethod
    async def classify_intent(message: str) -> str:
        """Uses keywords first, then falls back to a constrained LLM call."""
        fast_intent = Orchestrator._fast_route(message)
        if fast_intent:
            return fast_intent

        if len(message) < 15:
            return "BASE"

        async with get_client() as client:
            prompt = (
                "Analyze the user's message and respond ONLY with one of these words:\n"
                "- 'CODER': For complex coding, full scripts, advanced debugging.\n"
                "- 'IMAGE': For image generation, drawing, illustration requests.\n"
                "- 'AUDIO': For voice/speech/audio requests.\n"
                "- 'BASE': For general chat, small fixes, info, or .txt files.\n\n"
                f"Message: {message}\n"
                "Category:"
            )

            try:
                response = await client.chat.completions.create(
                    model=config.lm_studio_model,
                    messages=[
                        {"role": "system", "content": "You are a conservative intent router. Respond with ONLY ONE WORD. NO REASONING. NO THOUGHTS. STOP IMMEDIATELY."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=5,
                    temperature=0.0,
                    stop=["\n", "<thought>", "Reasoning:", "Thought:"]
                )
                intent = response.choices[0].message.content.strip().upper()
                intent = re.sub(r'[^A-Z]', '', intent)

                if intent in ["CODER", "IMAGE", "AUDIO", "BASE"]:
                    return intent
            except Exception as e:
                logger.error(f"Intent classification error: {e}")

        return "BASE"

    @staticmethod
    async def run(user_message: str, telegram_update=None, image_path: str = None, session_id: int = None) -> dict:
        """Executes the full orchestration cycle."""
        target_base = config.lm_studio_model
        use_vram_management = is_local_provider()

        # 1. Understand user intent
        user_lower = user_message.lower()
        if any(kw in user_lower for kw in ["create persona", "personality", "new persona", "manage_persona", "save_persona", "switch persona"]):
            intent = "BASE"
            logger.info(f"Intent forced to BASE (Persona management)")
        else:
            intent = await Orchestrator.classify_intent(user_message)
            logger.info(f"Intent detected: {intent}")

        # 2. Sequential Orchestration for CODER
        if intent == "CODER":
            target_coder = config.llm_model_coder
            logger.info(f"STEP 1: Technical Execution with {target_coder}")

            coder_result = {"text": "Operation interrupted or not completed.", "files": []}

            try:
                if use_vram_management:
                    await ModelManager.ensure_model(target_coder, min_context=20000)
                    config.lm_studio_model = target_coder
                    await asyncio.sleep(2)

                coder_result = await run_agent(user_message, image_path=image_path, agent_state="CODER", session_id=session_id, store_history=False)
                session_id = coder_result.get("session_id", session_id)

            except Exception as e:
                logger.error(f"Error during Coder execution: {e}")
                coder_result = {"text": f"Error during technical execution: {str(e)}", "files": []}

            finally:
                if use_vram_management:
                    logger.warning("[FORCE CLEANUP] Mandatory VRAM liberation...")
                    await ModelManager.unload_all_models()

            # --- PHASE 2: Narrator Reload and Final Response ---
            logger.info(f"STEP 2: Reloading Narrator {target_base}")
            try:
                if use_vram_management:
                    await ModelManager.ensure_model(target_base)
                    config.lm_studio_model = target_base
                    await asyncio.sleep(2)

                from src.memory.preferences import get_active_persona
                persona = get_active_persona()

                narrative_prompt = get_narrator_prompt(
                    persona_name=persona['name'],
                    persona_instructions=persona['system_prompt'],
                    context_notes=f"TECHNICAL OUTCOME: {coder_result['text']}\nFILES CREATED: {coder_result['files']}"
                )

                final_result = await run_agent(narrative_prompt, agent_state="BASE", session_id=session_id, store_history=False)

                from src.memory.preferences import save_conversation_message
                _, session_id = save_conversation_message("assistant", final_result["text"], session_id=session_id)
                final_result["session_id"] = session_id

                coder_files = coder_result.get("files", [])
                if "files" not in final_result:
                    final_result["files"] = []

                final_result["files"] = list(set(final_result["files"] + coder_files))

                logger.success(f"Cycle CODER -> BASE completed. Total files: {len(final_result['files'])}")
                return final_result

            except Exception as base_e:
                logger.error(f"Failed to reload base model: {base_e}")
                return coder_result

        elif intent == "IMAGE":
            logger.info("Starting Image Generation module")

            if not use_vram_management:
                logger.warning("IMAGE engine requires a local provider for VRAM management. Falling back to BASE.")
                return await run_agent(user_message, image_path=image_path, agent_state="BASE", session_id=session_id)

            try:
                logger.info("STEP 1: Ejecting conversation model for ComfyUI VRAM")
                await ModelManager.unload_all_models()
                await asyncio.sleep(2)

                from src.tools.image_gen import generate_image
                image_result = await generate_image(prompt=user_message)

                if "error" in image_result:
                    logger.error(f"Image generation failed: {image_result['error']}")
                    result = {"text": f"Image generation failed: {image_result['error']}", "files": [], "session_id": session_id}
                else:
                    result = {"text": "Image generated successfully.", "files": [image_result["path"]], "session_id": session_id}

            except Exception as e:
                logger.error(f"Error during image generation: {e}")
                result = {"text": f"Error during image generation: {str(e)}", "files": [], "session_id": session_id}

            finally:
                logger.info(f"STEP 2: Reloading base model {target_base}")
                await ModelManager.ensure_model(target_base)
                config.lm_studio_model = target_base

            # Run narrator to describe what happened
            from src.memory.preferences import get_active_persona
            persona = get_active_persona()
            narrative_prompt = get_narrator_prompt(
                persona_name=persona['name'],
                persona_instructions=persona['system_prompt'],
                context_notes=f"IMAGE GENERATION RESULT: {result['text']}\nFILES: {result['files']}"
            )
            final_result = await run_agent(narrative_prompt, agent_state="BASE", session_id=session_id, store_history=False)

            from src.memory.preferences import save_conversation_message
            _, session_id = save_conversation_message("assistant", final_result["text"], session_id=session_id)
            final_result["session_id"] = session_id
            final_result["files"] = result.get("files", []) + final_result.get("files", [])
            return final_result

        elif intent == "AUDIO":
            logger.info("Starting Audio module")
            if use_vram_management:
                await ModelManager.ensure_model(target_base)
            text_result = await run_agent(user_message, image_path=image_path, agent_state=intent, session_id=session_id)
            session_id = text_result.get("session_id", session_id)

            from src.tools.tts_tool import generate_speech
            audio_res = await generate_speech(text_result["text"])
            if audio_res and "path" in audio_res:
                text_result["files"].append(str(Path(audio_res["path"]).absolute()))

            return text_result

        # 3. Standard BASE flow
        if use_vram_management:
            await ModelManager.ensure_model(target_base)
            config.lm_studio_model = target_base
        return await run_agent(user_message, image_path=image_path, agent_state="BASE", session_id=session_id)
