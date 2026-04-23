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
from src.agent.core import run_agent, _make_client
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
        
        # 1. CODER TRIGGER (Technical keywords)
        # We notice "python" and "script" or code-specific terms.
        # We explicitly EXCLUDE simple file creation like ".txt".
        coder_patterns = [
            r"\bpython\b", r"\bscript\b", r"\bcoding\b", r"\bdevelop\b",
            r"\bprogram\b", r"\bclass\s+\w+", r"\bdef\s+\w+\(",
            r"\b\.py\b", r"\b\.js\b", r"\b\.cpp\b", r"\b\.java\b"
        ]
        if any(re.search(p, msg) for p in coder_patterns):
            # Verify it's not JUST a txt file
            if "txt" not in msg or any(p in msg for p in ["python", "script", ".py"]):
                logger.info("⚡ [FAST ROUTE] Detected CODER intent via keywords")
                return "CODER"

        # 2. AUDIO TRIGGER
        audio_patterns = [r"\bspeak\b", r"\baloud\b", r"\bvoice message\b", r"\baudio\b", r"\bvoice\b", r"\btalk\b"]
        if any(re.search(p, msg) for p in audio_patterns):
            logger.info("⚡ [FAST ROUTE] Detected AUDIO intent via keywords")
            return "AUDIO"
            
        return None

    @staticmethod
    async def classify_intent(message: str) -> str:
        """
        Uses keywords first, then falls back to a constrained LLM call.
        """
        # Step 1: Fast Routing
        fast_intent = Orchestrator._fast_route(message)
        if fast_intent:
            return fast_intent

        # Step 2: LLM Validation for ambiguous cases
        if len(message) < 15:
            return "BASE"

        client = _make_client()
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
                # Kill reasoning instantly
                stop=["\n", "<thought>", "Reasoning:", "Thought:"] 
            )
            intent = response.choices[0].message.content.strip().upper()
            # Clean possible trailing punctuation
            intent = re.sub(r'[^A-Z]', '', intent)
            
            if intent in ["CODER", "AUDIO", "BASE"]:
                return intent
        except Exception as e:
            logger.error(f"Intent classification error: {e}")
        
        return "BASE"

    @staticmethod
    async def run(user_message: str, telegram_update=None, image_path: str = None, session_id: int = None) -> dict:
        """Executes the full orchestration cycle."""
        # Save the FINAL base model from initial configuration 
        # to ensure we always return to it regardless of what happens next.
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
            
            # Safety initialization to avoid UnboundLocalError in case of crash/reload
            coder_result = {"text": "Operation interrupted or not completed.", "files": []}
            
            try:
                await ModelManager.ensure_model(target_coder)
                config.lm_studio_model = target_coder
                
                # Inference engine stabilization
                logger.info("🕒 Stabilizing inference engine (2s)...")
                await asyncio.sleep(2)
                
                # Silent execution of Coder (technical work)
                coder_result = await run_agent(user_message, image_path=image_path, agent_state="CODER", session_id=session_id, store_history=False)
                
            except Exception as e:
                logger.error(f"❌ Error during Coder execution: {e}")
                coder_result = {"text": f"Error during technical execution: {str(e)}", "files": []}
            
            finally:
                # --- GUARANTEED VRAM CLEANUP ---
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
                
                # Narrative message from Base model (Narrator)
                narrative_prompt = (
                    "OPERATION COMPLETED. Act as Fraclaw's Narrator.\n"
                    f"TECHNICAL OUTCOME: {coder_result['text']}\n"
                    f"FILES CREATED: {coder_result['files']}\n\n"
                    "INSTRUCTIONS FOR YOU:\n"
                    "1. Announce to the user that the task has been finished successfully.\n"
                    "2. Use your premium and elegant style.\n"
                    "3. Start DIRECTLY with your message.\n"
                    "4. DO NOT add separators like '---', '***' or labels like 'Fraclaw Narrator:'.\n"
                    "5. DO NOT repeat technical data or these instructions word for word."
                )
                
                # Load narration result
                final_result = await run_agent(narrative_prompt, agent_state="BASE", session_id=session_id, store_history=False)
                
                # MANUALLY save only the final assistant response to DB
                from src.memory.preferences import save_conversation_message
                save_conversation_message("assistant", final_result["text"], session_id=session_id)
                
                # Add coder files to the final dictionary for the download button
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
            logger.info("🎤 Starting Premium Audio module (Chatterbox)")
            # Standard audio flow
            await ModelManager.ensure_model(target_base, min_context=20000)
            text_result = await run_agent(user_message, image_path=image_path, agent_state=intent, session_id=session_id)
            
            # Unload LLM to free VRAM for Chatterbox GPU generation
            await ModelManager.unload_all_models()
            from src.tools.tts_tool import generate_speech
            audio_res = await generate_speech(text_result["text"])
            if audio_res and "path" in audio_res:
                text_result["files"].append(str(Path(audio_res["path"]).absolute()))
            
            logger.info(f"🔄 Final cleanup: Reloading {target_base}")
            await ModelManager.ensure_model(target_base, min_context=20000)
            return text_result
        
        # 3. Standard BASE flow
        logger.debug(f"⚖️ Standard flow for {intent}: Ensuring {target_base}")
        await ModelManager.ensure_model(target_base, min_context=20000)
        config.lm_studio_model = target_base
        return await run_agent(user_message, image_path=image_path, agent_state="BASE", session_id=session_id)
