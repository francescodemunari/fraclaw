from loguru import logger
from src.memory.preferences import save_persona, switch_persona, get_active_persona, toggle_premium_voice, list_personas, delete_persona

def manage_persona(action: str, name: str = None, description: str = "", system_prompt: str = "", voice_id: str = "en-GB-ThomasNeural", premium: bool = False, premium_voice: bool = False) -> dict:
    """
    Manages the persona lifecycle (Persona Engine).
    """
    # Unify premium parameters from old signatures
    is_premium = premium or premium_voice

    if action == "save":
        if not name:
            return {"status": "error", "message": "'name' is required for saving a persona."}
        logger.info(f"🎭 TOOL: Saving/Updating Persona '{name}'... (Premium: {is_premium})")
        success = save_persona(name, description, system_prompt, voice_id, is_premium)
        if success:
            p_msg = " [PREMIUM ENABLED]" if is_premium else ""
            return {"status": "success", "message": f"Persona '{name}' saved successfully in the Persona Engine.{p_msg}"}
        return {"status": "error", "message": "Error saving persona."}

    elif action == "switch":
        if not name:
            return {"status": "error", "message": "'name' is required for switching persona."}
        logger.info(f"🎭 TOOL: Switching active Persona to '{name}'...")
        success = switch_persona(name)
        if success:
            return {"status": "success", "message": f"Persona '{name}' activated successfully."}
        return {"status": "error", "message": f"Error: Persona '{name}' not found or switch failed."}

    elif action == "list":
        personas = list_personas()
        active = get_active_persona()
        return {
            "status": "success",
            "personas": personas,
            "active": active.get("name"),
            "count": len(personas),
        }

    elif action == "delete":
        if not name:
            return {"status": "error", "message": "'name' is required for deleting a persona."}
        success = delete_persona(name)
        if success:
            return {"status": "success", "message": f"Persona '{name}' deleted."}
        return {"status": "error", "message": f"Cannot delete '{name}' — it may be active or a protected system persona."}

    return {"status": "error", "message": f"Action '{action}' not supported. Use: save, switch, list, delete."}


def manage_voice_engine(premium: bool = None) -> dict:
    """
    Toggles between Premium (Chatterbox - Local Cloning) and Lite (Edge-TTS - Fast) engines.
    """
    logger.info(f"🔊 TOOL: Adjusting Voice Engine (Premium={premium})...")
    success = toggle_premium_voice(enabled=premium)
    
    if success:
        state = "PREMIUM (Local Cloning)" if premium else "LITE (Edge-TTS Fast)"
        if premium is None:
            state = "TOGGLED"
        return {"status": "success", "message": f"Voice engine updated to {state}."}
    else:
        return {"status": "error", "message": "Failed to update voice engine."}
