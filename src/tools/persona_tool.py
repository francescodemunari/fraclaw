from loguru import logger
from src.memory.preferences import save_persona, switch_persona, get_active_persona

def manage_persona(action: str, name: str = None, description: str = "", system_prompt: str = "", voice_id: str = "en-GB-ThomasNeural") -> dict:
    """Manages the persona lifecycle (Persona Engine)."""
    if action == "save":
        logger.info(f"TOOL: Saving/Updating Persona '{name}'...")
        success = save_persona(name, description, system_prompt, voice_id)
        if success:
            return {"status": "success", "message": f"Persona '{name}' saved successfully."}
        else:
            return {"status": "error", "message": "Error saving persona."}

    elif action == "switch":
        logger.info(f"TOOL: Switching active Persona to '{name}'...")
        success = switch_persona(name)
        if success:
            return {"status": "success", "message": f"Persona '{name}' activated successfully."}
        else:
            return {"status": "error", "message": f"Error: Persona '{name}' not found or switch failed."}

    elif action == "list":
        return {"status": "success", "message": "Listing personas delegated to memory database."}

    else:
        return {"status": "error", "message": f"Action '{action}' not supported."}
