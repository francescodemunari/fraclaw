"""

Supporta:
  - Tool sincroni (filesystem, web, documenti)
  - Tool asincroni (generate_image via ComfyUI)
  - Messaggi multimodali con immagini (vision)
  - Loop multipli (il modello può chiamare più tool in sequenza)
"""

import inspect
import json
import time
import re
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from loguru import logger
from openai import AsyncOpenAI
from src.agent.prompts import build_system_prompt
from src.config import config
from src.memory.database import get_connection
from src.memory.preferences import save_conversation_message, get_recent_history
from src.tools.registry import TOOLS_SCHEMA, get_tool_map

# Numero massimo di iterazioni del loop (evita loop infiniti)
_MAX_ITERATIONS = 12

# Liste di estensioni che identifica file immagine per il tracking
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def _make_client() -> AsyncOpenAI:
    """Creates the OpenAI client pointed at LM Studio."""
    return AsyncOpenAI(
        base_url=config.lm_studio_base_url,
        api_key="lm-studio",
        timeout=300.0,         # Increased timeout to 5 min for heavy/slow models
        max_retries=0,
    )


def _is_image_file(path: str) -> bool:
    return Path(path).suffix.lower() in _IMAGE_EXTENSIONS


async def _execute_tool(tool_name: str, tool_args: dict, tool_map: dict) -> str:
    """
    Executes a tool (sync or async) and returns the result serialized as JSON.
    Handles exceptions robustly to avoid blocking the agent loop.
    """
    if tool_name not in tool_map:
        return json.dumps({"error": f"Tool '{tool_name}' not found in registry."})

    func = tool_map[tool_name]
    try:
        if inspect.iscoroutinefunction(func):
            result = await func(**tool_args)
        else:
            result = func(**tool_args)

        return json.dumps(result, ensure_ascii=False, default=str)

    except TypeError as e:
        logger.error(f"Invalid arguments for tool '{tool_name}': {e} | args: {tool_args}")
        return json.dumps({"error": f"Invalid arguments: {e}"})
    except Exception as e:
        logger.error(f"Tool execution error '{tool_name}': {e}")
        return json.dumps({"error": str(e)})


def _extract_generated_files(result_json: str) -> list[str]:
    """
    Checks if a tool result contains one or more generated files.
    Looks for common keys ('path', 'file_path', 'output_path') or analyzes values.
    """
    try:
        data = json.loads(result_json)
        if not isinstance(data, dict):
            return []
            
        found_paths = []
        # Priority keys
        for key in ["path", "file_path", "filepath", "output_path"]:
            val = data.get(key)
            if val and isinstance(val, str) and Path(val).exists():
                found_paths.append(val)
        
        # Generic scanning of all values if nothing found
        if not found_paths:
            for val in data.values():
                if isinstance(val, str) and (":" in val or "/" in val or "\\" in val):
                    if len(val) < 500 and Path(val).exists() and Path(val).is_file():
                        found_paths.append(val)
        
        return list(set(found_paths)) # Remove duplicates
    except Exception:
        pass
    return []


async def _consume_stream(response) -> SimpleNamespace:
    """Consuma uno stream OpenAI e restituisce un oggetto compatibile con il parser esistente."""
    full_content = ""
    full_reasoning = ""
    tool_calls_deltas = {}

    async for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        
        # Content standard
        if hasattr(delta, 'content') and delta.content:
            full_content += delta.content
            
        # Reasoning (Thinking) - Supporto per LM Studio 0.4+ e Qwen3
        if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
            full_reasoning += delta.reasoning_content
            
        # Tool Calls (Streaming Deltas)
        if hasattr(delta, 'tool_calls') and delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if idx not in tool_calls_deltas:
                    tool_calls_deltas[idx] = {
                        "id": tc_delta.id,
                        "type": "function",
                        "function": {"name": "", "arguments": ""}
                    }
                if tc_delta.id:
                    tool_calls_deltas[idx]["id"] = tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name:
                        tool_calls_deltas[idx]["function"]["name"] += tc_delta.function.name
                    if tc_delta.function.arguments:
                        tool_calls_deltas[idx]["function"]["arguments"] += tc_delta.function.arguments

    # Recomposizione tool calls
    final_tool_calls = []
    for idx in sorted(tool_calls_deltas.keys()):
        tc = tool_calls_deltas[idx]
        final_tool_calls.append(SimpleNamespace(
            id=tc["id"],
            type=tc["type"],
            function=SimpleNamespace(name=tc["function"]["name"], arguments=tc["function"]["arguments"])
        ))

    # Se il content è vuoto ma abbiamo il reasoning, usiamo quello come fallback testuale
    combined_content = full_content
    if not combined_content and full_reasoning:
        combined_content = f"> [Thinking]\n> {full_reasoning}\n\n" + full_content if full_content else full_reasoning

    return SimpleNamespace(
        content=combined_content if combined_content else None,
        tool_calls=final_tool_calls if final_tool_calls else None
    )


async def run_agent(
    user_message: str,
    image_path: str | None = None,
    agent_state: str | None = None,
    session_id: int | None = None,
    store_history: bool = True,
) -> dict:
    """
    Esegue il loop completo dell'agente per un messaggio.
    """
    tool_map = get_tool_map()

    # ── Costruisci la lista messaggi ──────────────────────────
    system_prompt = build_system_prompt(agent_state=agent_state)
    history = get_recent_history(limit=10, session_id=session_id)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)

    # ── Current message (text or multimodal) ──────────────
    if image_path and Path(image_path).exists():
        from src.tools.vision import build_vision_message
        user_msg = build_vision_message(user_message, image_path)
        # If vision fails, fallback to pure text
        if "_vision_error" in user_msg:
            logger.warning(f"Vision fallback: {user_msg['_vision_error']}")
            user_msg = {"role": "user", "content": user_message}
    else:
        user_msg = {"role": "user", "content": user_message}

    messages.append(user_msg)

    # Save user message to history
    save_conversation_message("user", user_message, session_id=session_id)

    # ── Reasoning loop ──────────────────────────────────
    generated_files: list[str] = []
    # Count of tools executed in current loop.
    # Sentinel activates ONLY if this is 0: so it doesn't block
    # legitimate final responses after tools have been used.
    tools_executed_count: int = 0

    for iteration in range(_MAX_ITERATIONS):
        logger.info(f"🤖 Agent loop — iteration {iteration + 1}/{_MAX_ITERATIONS}")

        # Creiamo un nuovo client pulito per ogni tentativo di inferenza
        async with _make_client() as client:
            try:
                # Diagnostic log for prompt size
                prompt_size = sum(len(m.get("content", "")) for m in messages if isinstance(m.get("content"), str))
                logger.debug(f"📤 Sending prompt to LM Studio ({prompt_size} chars, {len(messages)} messages)")
                
                response = await client.chat.completions.create(
                    model=config.lm_studio_model,
                    messages=messages,
                    tools=TOOLS_SCHEMA,
                    tool_choice="auto",
                    temperature=0.1,
                    max_tokens=4096,
                    stream=True
                )
                assistant_msg = await _consume_stream(response)
            except Exception as e:
                # Second attempt if the first fails with 400 error (Jinja template)
                if "400" in str(e) and "jinja" in str(e).lower():
                    logger.warning("⚠️ LM Studio template incompatible with 'tools' API. Falling back to Prompt Injection...")
                    from src.tools.registry import get_tools_description
                    tools_desc = get_tools_description()
                    
                    fallback_system = f"{system_prompt}\n\nAVAILABLE TOOLS:\n{tools_desc}\n\nTo use a tool, respond EXACTLY with: TOOL: tool_name(arg1='val', ...)"
                    fallback_messages = [{"role": "system", "content": fallback_system}]
                    for m in messages[1:]:
                        if m["role"] in ["user", "assistant"]:
                            fallback_messages.append(m)
                    
                    try:
                        response = await client.chat.completions.create(
                            model=config.lm_studio_model,
                            messages=fallback_messages,
                            temperature=0.1,
                            max_tokens=4096,
                            stream=True
                        )
                        assistant_msg = await _consume_stream(response)
                    except Exception as e2:
                        logger.error(f"Fallback failed: {e2}")
                        raise e2
                else:
                    logger.error(f"LLM call error (iter {iteration+1}): {e}")
                    return {
                        "text": f"❌ Error connecting to LLM: {e}",
                        "files": [],
                    }

        # ── MANUAL TOOL PARSER (Qwen & Fallback) ──────────────────
        # Support for native Qwen tags: <tool_call>{"name": "...", "arguments": {...}}</tool_call>
        if assistant_msg.content and "<tool_call>" in assistant_msg.content:
            try:
                # Find all <tool_call> blocks
                calls = re.findall(r"<tool_call>(.*?)</tool_call>", assistant_msg.content, re.DOTALL)
                for call_str in calls:
                    call_data = json.loads(call_str.strip())
                    tool_name = call_data.get("name")
                    tool_args = call_data.get("arguments", {})
                    
                    if tool_name:
                        logger.info(f"🔧 Qwen tool call detected: {tool_name}")
                        qwen_call = SimpleNamespace(
                            id=f"qwen_{iteration}_{tool_name}",
                            type="function",
                            function=SimpleNamespace(name=tool_name, arguments=json.dumps(tool_args))
                        )
                        if not assistant_msg.tool_calls:
                            assistant_msg.tool_calls = [qwen_call]
                        else:
                            assistant_msg.tool_calls.append(qwen_call)
            except Exception as qe:
                logger.warning(f"Qwen tag parsing error: {qe} | RAW: {assistant_msg.content[:200]}")

        # Support for legacy "TOOL: tool_name(...)" format
        if assistant_msg.content and "TOOL:" in assistant_msg.content and not assistant_msg.tool_calls:
            # Extracts "TOOL: tool_name(args)"
            match = re.search(r"TOOL:\s*(\w+)\s*\((.*)\)", assistant_msg.content)
            if match:
                tool_name = match.group(1)
                args_str = match.group(2)
                logger.info(f"🔧 Manual tool call detected: {tool_name}")
                
                # Try to parse arguments as Python dict
                try:
                    # Transforms arg1='val', arg2=123 into a dict
                    args = {}
                    if args_str.strip():
                        # Use regex to capture key=val
                        pairs = re.findall(r"(\w+)\s*=\s*(['\"]?.*?['\"]?)(?:\s*,\s*|$)", args_str)
                        for k, v in pairs:
                            # Clean quotes
                            v = v.strip().strip("'").strip('"')
                            args[k] = v
                    
                    manual_call = SimpleNamespace(
                        id=f"manual_{iteration}_{tool_name}",
                        type="function",
                        function=SimpleNamespace(name=tool_name, arguments=json.dumps(args))
                    )
                    if not assistant_msg.tool_calls:
                        assistant_msg.tool_calls = [manual_call]
                    else:
                        assistant_msg.tool_calls.append(manual_call)
                except Exception as pe:
                    logger.warning(f"Errore parsing argomenti manuali: {pe}")

        # ── INTEGRITY CONTROL (Sentinel 4.0 Pro) ─────────────────
        # Sentinel activates ONLY if no pending tool calls
        if not assistant_msg.tool_calls and assistant_msg.content:
            content_lower = assistant_msg.content.lower()
            
            # Words indicating an operational action that MUST have called a tool
            action_keywords = [
                "created", "generated", "sent", "prepared", "written", "saved",
                "completed", "updated", "set", "changed", "activated",
                "monitoring", "subscribed", "watchman", "indexed",
                "script", "write"
            ]
            
            # Common words excluding false positives (informational)
            false_positive_context = [
                "news", "results", "article", "source", "according to", "reports",
                "is a", "was", "been", "info about", "said that"
            ]

            is_coder = agent_state == "CODER"
            has_action = any(k in content_lower for k in action_keywords)
            is_informational = any(fp in content_lower for fp in false_positive_context)

            # Sentinel is ACTIVE ONLY for the CODER
            # If the Narrator (BASE) comments on a Coder action, it shouldn't be blocked.
            if is_coder and has_action and not is_informational:
                # If it's a coder claiming action, a tool call MUST have happened
                # (either in this iteration or previous ones)
                if tools_executed_count == 0:
                    logger.warning(f"🚨 Sentinel: Blocked action hallucination (iter {iteration+1}, CODER={is_coder}). Preview: {content_lower[:120]}...")
                    
                    messages.append({
                        "role": "assistant",
                        "content": assistant_msg.content
                    })
                    messages.append({
                        "role": "system",
                        "content": (
                            "CRITICAL INTEGRITY ERROR: You claimed to have performed an action (e.g. creating/saving a file, generating code on disk, updating system) "
                            "but you did NOT call any tool. As a CODER agent, you MUST use tools to interact with the system. "
                            "CALL THE CORRECT TOOL NOW (e.g., write_file) to actually perform the action you promised."
                        )
                    })
                    continue

        # ── No tool calls → final response ────────────────
        if not assistant_msg.tool_calls:
            final_text = assistant_msg.content or "✅ Task completed."
            if store_history:
                save_conversation_message("assistant", final_text, session_id=session_id)
            logger.info(f"💬 Final response generated ({len(final_text)} chars)")
            return {"text": final_text, "files": generated_files}

        # ── Pending tool calls to execute ────────────────────
        # Add assistant message with tool calls to history
        assistant_dict: dict = {
            "role": "assistant",
            "content": assistant_msg.content or "",
        }
        if assistant_msg.tool_calls:
            assistant_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in assistant_msg.tool_calls
            ]
        messages.append(assistant_dict)

        # Execute all tool calls
        for tool_call in assistant_msg.tool_calls:
            tool_name = tool_call.function.name

            # Parse JSON arguments
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            logger.info(f"🔧 Executing tool: {tool_name} | args: {tool_args}")

            # Execute tool
            result_str = await _execute_tool(tool_name, tool_args, tool_map)

            # Update counter — sentinel won't trigger anymore
            tools_executed_count += 1

            # Check if a file was generated to send
            new_files = _extract_generated_files(result_str)
            generated_files.extend(new_files)
            if new_files:
                logger.info(f"📎 Generated file: {new_files}")

            # Add tool result to history
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_str,
                }
            )

    # Fallback: if max iterations reached, force LLM to summarize
    logger.warning("Agent loop: max iterations reached. Forcing final summary.")
    
    # Add invisible system message to force conclusion
    messages.append({
        "role": "system", 
        "content": "TIME EXHAUSTED / MAX ITERATIONS REACHED. Do NOT call more tools. Summarize IMMEDIATELY what you found in the previous steps for the user as completely as possible."
    })
    
    try:
        final_response = await client.chat.completions.create(
            model=config.lm_studio_model,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="none", # Disable tools to force response
            temperature=0.5,
        )
        fallback = final_response.choices[0].message.content or "I gathered a lot of info but couldn't summarize it in time."
    except Exception as e:
        logger.error(f"Summary fallback failed: {e}")
        fallback = "I finished the search operations. Check if I found what you were looking for in previous messages (if any)."

    save_conversation_message("assistant", fallback, session_id=session_id)
    return {"text": fallback, "files": generated_files}
