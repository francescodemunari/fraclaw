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
from src.agent.utils import get_client
from src.agent.prompts import get_narrator_prompt
from src.agent.manager import ModelManager
from src.config import config

class Orchestrator:
    """Coordinates specialized agents and manages model switching."""

    @staticmethod
    def _fast_route(message: str) -> str | None:
        """
        Quickly detects obvious intents using keywords to avoid LLM latency.
        """
        msg = message.lower()
        
        # 1. AUDIO TRIGGER — check BEFORE greetings so "hi, use your voice" routes correctly
        audio_patterns = [
            r"\bspeak\b", r"\baloud\b", r"\bvoice message\b", r"\baudio\b",
            r"\bvoice\b", r"\btalk\b", r"\bsay it\b", r"\bread.*aloud\b",
            r"\busing.*voice\b", r"\bwith.*voice\b", r"\bedge voice\b",
            r"\btell me.*voice\b", r"\brespond.*voice\b", r"\banswer.*voice\b",
            r"\bspeak.*response\b", r"\bsing\b"
        ]
        if any(re.search(p, msg) for p in audio_patterns):
            logger.info("⚡ [FAST ROUTE] Detected AUDIO intent via keywords")
            return "AUDIO"

        # 2. CODER TRIGGER (Technical keywords)
        coder_patterns = [
            r"\bpython\b", r"\bscript\b", r"\bcoding\b", r"\bdevelop\b",
            r"\bprogram\b", r"\bclass\s+\w+", r"\bdef\s+\w+\(",
            r"\b\.py\b", r"\b\.js\b", r"\b\.cpp\b", r"\b\.java\b"
        ]
        if any(re.search(p, msg) for p in coder_patterns):
            if "txt" not in msg or any(p in msg for p in ["python", "script", ".py"]):
                logger.info("⚡ [FAST ROUTE] Detected CODER intent via keywords")
                return "CODER"

        # 3. BASE TRIGGER (Greetings/Social)
        base_patterns = [
            r"\bciao\b", r"\bhello\b", r"\bhi\b", r"\bhey\b",
            r"\bmi chiamo\b", r"\bi am\b", r"\bi'm\b", r"\bnice to meet you\b"
        ]
        if any(re.search(p, msg) for p in base_patterns):
            logger.info("⚡ [FAST ROUTE] Detected BASE intent via conversational keywords")
            return "BASE"
            
        return None

    @staticmethod
    async def classify_intent(message: str) -> str:
        """
        Uses keywords first, then falls back to a constrained LLM call.
        """
        fast_intent = Orchestrator._fast_route(message)
        if fast_intent:
            return fast_intent

        if len(message) < 15:
            return "BASE"

        async with get_client() as client:
            prompt = (
                "Analyze the user's message and respond ONLY with one of these words:\n"
                "- 'CODER': For complex coding, full scripts, advanced debugging.\n"
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
                
                if intent in ["CODER", "AUDIO", "BASE"]:
                    return intent
            except Exception as e:
                logger.error(f"Intent classification error: {e}")
        
        return "BASE"

    @staticmethod
    async def run(user_message: str, telegram_update=None, image_path: str = None, session_id: int = None) -> dict:
        """Executes the full orchestration cycle."""
        target_base = config.lm_studio_model
        
        # 1. Understand user intent
        user_lower = user_message.lower()
        if any(kw in user_lower for kw in ["create persona", "personality", "new persona", "manage_persona", "save_persona", "switch persona"]):
            intent = "BASE"
            logger.info(f"🎭 Intent forced to BASE (Persona management detected via keywords)")
        else:
            intent = await Orchestrator.classify_intent(user_message)
            logger.info(f"🧠 Intent detected: {intent}")

        # 2. Sequential Orchestration for CODER
        if intent == "CODER":
            target_coder = config.llm_model_coder
            logger.info(f"👨‍💻 STEP 1: Technical Execution with {target_coder}")
            
            coder_result = {"text": "Operation interrupted or not completed.", "files": []}
            
            try:
                await ModelManager.ensure_model(target_coder, min_context=20000)
                config.lm_studio_model = target_coder
                
                logger.info("🕒 Stabilizing inference engine (2s)...")
                await asyncio.sleep(2)
                
                coder_result = await run_agent(user_message, image_path=image_path, agent_state="CODER", session_id=session_id, store_history=False)
                session_id = coder_result.get("session_id", session_id)
                
            except Exception as e:
                logger.error(f"❌ Error during Coder execution: {e}")
                coder_result = {"text": f"Error during technical execution: {str(e)}", "files": []}
            
            finally:
                logger.warning("🧹 [FORCE CLEANUP] Mandatory VRAM liberation...")
                await ModelManager.unload_all_models()
                
            # --- PHASE 2: Narrator Reload and Final Response ---
            logger.info(f"🔄 STEP 2: Reloading Narrator {target_base}")
            try:
                await ModelManager.ensure_model(target_base)
                config.lm_studio_model = target_base
                
                logger.info("🕒 Stabilizing inference engine (2s)...")
                await asyncio.sleep(2)
                
                logger.info(f"✨ Model {target_base} operational. Generating final confirmation...")
                
                # Retrieve persona info for the narrator
                from src.memory.preferences import get_active_persona
                persona = get_active_persona()
                
                narrative_prompt = get_narrator_prompt(
                    persona_name=persona['name'],
                    persona_instructions=persona['system_prompt'],
                    context_notes=f"TECHNICAL OUTCOME: {coder_result['text']}\nFILES CREATED: {coder_result['files']}"
                )
                
                final_result = await run_agent(narrative_prompt, agent_state="BASE", session_id=session_id, store_history=False)
                
                # MANUALLY save only the final assistant response to DB
                from src.memory.preferences import save_conversation_message
                _, session_id = save_conversation_message("assistant", final_result["text"], session_id=session_id)
                final_result["session_id"] = session_id
                
                coder_files = coder_result.get("files", [])
                if "files" not in final_result:
                    final_result["files"] = []
                
                final_result["files"] = list(set(final_result["files"] + coder_files))
                
                logger.success(f"🏁 Cycle CODER -> BASE completed. Total files: {len(final_result['files'])}")
                return final_result
                
            except Exception as base_e:
                logger.error(f"Failed to reload base model: {base_e}")
                return coder_result

        elif intent == "AUDIO":
            logger.info("🎤 Starting Audio module (Chatterbox)")
            await ModelManager.ensure_model(target_base)
            text_result = await run_agent(user_message, image_path=image_path, agent_state=intent, session_id=session_id)
            session_id = text_result.get("session_id", session_id)
            
            from src.memory.preferences import get_active_persona
            persona = get_active_persona()
            is_premium = persona.get("premium_voice", False)
            
            if is_premium:
                await ModelManager.unload_all_models()
                
            from src.tools.tts_tool import generate_speech
            audio_res = await generate_speech(text_result["text"])
            if audio_res and "path" in audio_res:
                text_result["files"].append(str(Path(audio_res["path"]).absolute()))
            
            if is_premium:
                logger.info(f"🔄 Final cleanup: Reloading {target_base}")
                await ModelManager.ensure_model(target_base)
                
            return text_result
        
        # 3. Standard BASE flow
        logger.debug(f"⚖️ Standard flow for {intent}: Ensuring {target_base}")
        await ModelManager.ensure_model(target_base)
        config.lm_studio_model = target_base
        return await run_agent(user_message, image_path=image_path, agent_state="BASE", session_id=session_id)
