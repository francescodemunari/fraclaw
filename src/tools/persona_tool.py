"""
persona_tool.py — Tool per la gestione del Persona Engine
"""

from src.memory.preferences import save_persona

def manage_persona(name: str, description: str, system_prompt: str, voice_id: str) -> dict:
    """
    Crea o aggiorna una personalità nel Persona Engine.
    
    Args:
        name: Nome univoco della persona (es. 'Alice', 'Tutor').
        description: Breve descrizione del ruolo.
        system_prompt: Le istruzioni dettagliate su come la persona deve comportarsi.
        voice_id: ID voce edge-tts. Disponibili: 
                  - it-IT-GiuseppeNeural (Uomo, formale)
                  - it-IT-DiegoNeural (Uomo, amichevole)
                  - it-IT-ElsaNeural (Donna, amichevole)
                  - it-IT-IsabellaNeural (Donna, rassicurante)
    """
    success = save_persona(name, description, system_prompt, voice_id)
    if success:
        return {"status": "success", "message": f"Personalità '{name}' salvata correttamente nel Persona Engine."}
    else:
        return {"status": "error", "message": "Errore durante il salvataggio della personalità."}
