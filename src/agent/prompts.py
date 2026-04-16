"""
prompts.py — System prompt dinamico per Demuclaw
"""

from src.memory.preferences import get_profile_summary, get_active_persona

def build_system_prompt() -> str:
    """
    Costruisce il system prompt completo iniettando la personalità attiva
    e il profilo utente aggiornato.
    """
    # 1. Recupera la personalità attiva (Jarvis, Amico, ecc.)
    persona = get_active_persona()
    base_instructions = persona["system_prompt"]
    
    # 🚨 REGOLA D'ORO: INTEGRITÀ DEI TOOL (Sempre inclusa per sicurezza)
    integrity_rule = """
### 🚨 REGOLA D'ORO: INTEGRITÀ DEI TOOL 🚨
1. **L'azione precede la parola**: Se l'utente chiede di creare un file o eseguire una ricerca, **DEVI** chiamare il tool corrispondente subito.
2. **Vietato mentire**: Non dire MAI "Ho fatto [azione]" se non hai ricevuto successo dal tool.
"""

    # 2. Informazioni di sistema (Data/Ora)
    import datetime
    current_time = datetime.datetime.now().strftime("%d %B %Y, %H:%M:%S")
    system_info = f"\n\n## Informazioni di Sistema\n- **Data e ora attuale**: {current_time}\n- **Personalità Attiva**: {persona['name']}\n"
    
    extra_capabilities = """
---

## 🛠️ Moduli Attivi
- **Watchman (Web Monitoring)**: Puoi monitorare siti/notizie. Verrai svegliato ogni X ore per controllare novità. Usa `manage_web_monitor`.
- **Knowledge Base (RAG)**: Puoi leggere PDF/TXT e salvarli nella tua memoria a lungo termine. Usa `learn_from_document` e `search_knowledge`.
"""

    # 3. Profilo utente (Fatti salvati)
    profile = get_profile_summary()
    profile_section = f"\n\n---\n\n{profile}" if profile else "\n\n---\n\n*Nessun profilo utente ancora registrato.*"

    return base_instructions + integrity_rule + system_info + extra_capabilities + profile_section
