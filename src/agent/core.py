"""
core.py — Orchestratore dell'agente: loop Reasoning → Tool Calling → Risposta

Flusso per ogni messaggio:
  1. Carica storico recente da SQLite
  2. Costruisce il system prompt con profilo utente aggiornato
  3. Invia i messaggi a LM Studio (Qwen3.5-9B)
  4. Se il modello richiede tool → esegui → reinvia risultati
  5. Quando il modello risponde in linguaggio naturale → ritorna la risposta
  6. Salva messaggio utente e risposta finale in SQLite

Supporta:
  - Tool sincroni (filesystem, web, documenti)
  - Tool asincroni (generate_image via ComfyUI)
  - Messaggi multimodali con immagini (vision)
  - Loop multipli (il modello può chiamare più tool in sequenza)
"""

import inspect
import json
from pathlib import Path

from loguru import logger
from openai import AsyncOpenAI

from src.agent.prompts import build_system_prompt
from src.config import config
from src.memory.preferences import get_recent_history, save_conversation_message
from src.tools.registry import TOOLS_SCHEMA, get_tool_map

# Numero massimo di iterazioni del loop (evita loop infiniti)
_MAX_ITERATIONS = 12

# Liste di estensioni che identifica file immagine per il tracking
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def _make_client() -> AsyncOpenAI:
    """Crea il client OpenAI puntato a LM Studio."""
    return AsyncOpenAI(
        base_url=config.lm_studio_base_url,
        api_key="lm-studio",  # LM Studio non richiede una vera API key
        timeout=60.0,         # Timeout per evitare freeze infiniti se LM Studio si blocca
        max_retries=0,        # Non riprovare se fallisce (vogliamo fallire fast)
    )


def _is_image_file(path: str) -> bool:
    return Path(path).suffix.lower() in _IMAGE_EXTENSIONS


async def _execute_tool(tool_name: str, tool_args: dict, tool_map: dict) -> str:
    """
    Esegue un tool (sync o async) e restituisce il risultato serializzato come JSON.
    Gestisce eccezioni in modo robusto per non bloccare il loop dell'agente.
    """
    if tool_name not in tool_map:
        return json.dumps({"error": f"Tool '{tool_name}' non trovato nel registry."})

    func = tool_map[tool_name]
    try:
        if inspect.iscoroutinefunction(func):
            result = await func(**tool_args)
        else:
            result = func(**tool_args)

        return json.dumps(result, ensure_ascii=False, default=str)

    except TypeError as e:
        logger.error(f"Argomenti errati per tool '{tool_name}': {e} | args: {tool_args}")
        return json.dumps({"error": f"Argomenti non validi: {e}"})
    except Exception as e:
        logger.error(f"Errore esecuzione tool '{tool_name}': {e}")
        return json.dumps({"error": str(e)})


def _extract_generated_files(result_json: str) -> list[str]:
    """
    Controlla se il risultato di un tool contiene uno o più file generati.
    Cerca le chiavi comuni ('path', 'file_path', 'output_path') o analizza i valori.
    """
    try:
        data = json.loads(result_json)
        if not isinstance(data, dict):
            return []
            
        found_paths = []
        # Chiavi prioritarie
        for key in ["path", "file_path", "filepath", "output_path"]:
            val = data.get(key)
            if val and isinstance(val, str) and Path(val).exists():
                found_paths.append(val)
        
        # Scansione generica di tutti i valori se non trovato nulla
        if not found_paths:
            for val in data.values():
                if isinstance(val, str) and (":" in val or "/" in val or "\\" in val):
                    if len(val) < 500 and Path(val).exists() and Path(val).is_file():
                        found_paths.append(val)
        
        return list(set(found_paths)) # Rimuove duplicati
    except Exception:
        pass
    return []


async def run_agent(
    user_message: str,
    image_path: str | None = None,
) -> dict:
    """
    Esegue il loop completo dell'agente per un messaggio.

    Args:
        user_message: Il testo del messaggio dell'utente.
        image_path:   Percorso opzionale a un'immagine da analizzare con Qwen Vision.

    Returns dict con:
        - text:  La risposta testuale finale da inviare su Telegram.
        - files: Lista di path di file generati da inviare come allegati.
    """
    client = _make_client()
    tool_map = get_tool_map()

    # ── Costruisci la lista messaggi ──────────────────────────
    system_prompt = build_system_prompt()
    history = get_recent_history(limit=10)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)

    # ── Messaggio corrente (testo o multimodale) ──────────────
    if image_path and Path(image_path).exists():
        from src.tools.vision import build_vision_message
        user_msg = build_vision_message(user_message, image_path)
        # Se la vision fallisce, fallback a testo puro
        if "_vision_error" in user_msg:
            logger.warning(f"Vision fallback: {user_msg['_vision_error']}")
            user_msg = {"role": "user", "content": user_message}
    else:
        user_msg = {"role": "user", "content": user_message}

    messages.append(user_msg)

    # Salva il messaggio utente nella cronologia
    save_conversation_message("user", user_message)

    # ── Loop di ragionamento ──────────────────────────────────
    generated_files: list[str] = []

    for iteration in range(_MAX_ITERATIONS):
        logger.info(f"🤖 Agent loop — iterazione {iteration + 1}/{_MAX_ITERATIONS}")

        # Chiama il modello
        try:
            response = await client.chat.completions.create(
                model=config.lm_studio_model,
                messages=messages,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
                parallel_tool_calls=False,
                temperature=0.1,  # Temperatura bassa per massimizzare la fedeltà ai dati e ai tool
                max_tokens=2048,
            )
        except Exception as e:
            logger.error(f"Errore chiamata LLM: {e}")
            return {
                "text": (
                    f"❌ Errore di connessione al modello LLM.\n"
                    f"Assicurati che LM Studio sia avviato con il server API attivo.\n"
                    f"Dettaglio: `{e}`"
                ),
                "files": [],
            }

        choice = response.choices[0]
        assistant_msg = choice.message

        # ── CONTROLLO INTEGRITÀ (Sentinel 2.0) ────────────────────
        # Se l'agente dichiara un'azione fisica senza tool call, è un'allucinazione.
        if not assistant_msg.tool_calls and assistant_msg.content:
            content_lower = assistant_msg.content.lower()
            
            # Parole chiave che indicano un'azione fisica o di ricerca che RICHIEDE un tool
            action_keywords = [
                "creato", "generato", "inviato", "preparato", "fatto il", 
                "monitoraggio", "iscritto", "watchman",
                "studiato", "indicizzato", "imparato il file"
            ]
            
            # Se l'agente dice di aver fatto una di queste cose ma i tool_calls sono vuoti...
            if any(k in content_lower for k in action_keywords):
                logger.warning(f"🚨 Sentinel: Bloccata allucinazione d'azione. Content: {content_lower[:100]}...")
                
                # Inseriamo un errore di sistema forzato per obbligarlo a riprovare usando i tool
                messages.append({
                    "role": "assistant",
                    "content": assistant_msg.content
                })
                messages.append({
                    "role": "system",
                    "content": (
                        "ERRORE DI INTEGRITÀ: Hai dichiarato un successo o un'azione proattiva (es. creazione file, monitoraggio, studio documenti) "
                        "ma NON hai chiamato alcun tool. L'utente non ha ricevuto nulla. "
                        "DEVI chiamare il tool appropriato ORA. Non rispondere con solo testo se l'azione richiede un tool."
                    )
                })
                continue

        # ── Nessun tool call → risposta finale ────────────────
        if not assistant_msg.tool_calls:
            final_text = assistant_msg.content or "✅ Operazione completata."
            save_conversation_message("assistant", final_text)
            logger.info(f"💬 Risposta finale generata ({len(final_text)} chars)")
            return {"text": final_text, "files": generated_files}

        # ── Ci sono tool calls da eseguire ────────────────────
        # Aggiungi il messaggio assistant con i tool calls alla history
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

        # Esegui tutti i tool calls (in sequenza per sicurezza)
        for tool_call in assistant_msg.tool_calls:
            tool_name = tool_call.function.name

            # Parse degli argomenti JSON
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            logger.info(f"🔧 Eseguo tool: {tool_name} | args: {tool_args}")

            # Esegui il tool
            result_str = await _execute_tool(tool_name, tool_args, tool_map)

            # Controlla se è stato generato un file da inviare
            new_files = _extract_generated_files(result_str)
            generated_files.extend(new_files)
            if new_files:
                logger.info(f"📎 File generato: {new_files}")

            # Aggiungi il risultato del tool alla history
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_str,
                }
            )

    # Fallback: se superiamo max_iterations, forziamo l'LLM a dare un senso a ciò che ha trovato finora.
    logger.warning("Loop agente: raggiunto max iterations. Forzo riassunto finale.")
    
    # Aggiungi un messaggio di sistema invisibile per forzare la conclusione
    messages.append({
        "role": "system", 
        "content": "HAI ESAURITO IL TEMPO/ITERAZIONI. Non chiamare altri tool. Riassumi SUBITO all'utente quello che hai trovato nei passaggi precedenti nel modo più completo possibile."
    })
    
    try:
        final_response = await client.chat.completions.create(
            model=config.lm_studio_model,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="none", # Disabilita i tool per forzare la risposta
            temperature=0.5,
        )
        fallback = final_response.choices[0].message.content or "Ho raccolto molte informazioni ma non sono riuscito a riassumerle in tempo."
    except Exception as e:
        logger.error(f"Errore nel fallback riassunto: {e}")
        fallback = "Ho terminato le operazioni di ricerca. Controlla se ho trovato quello che cercavi nei messaggi precedenti (se presenti)."

    save_conversation_message("assistant", fallback)
    return {"text": fallback, "files": generated_files}
