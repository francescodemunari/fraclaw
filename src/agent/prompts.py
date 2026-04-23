"""
prompts.py — Dynamic System Prompt for Fraclaw
"""

from src.memory.preferences import get_profile_summary, get_active_persona

def build_system_prompt(agent_state: str = None) -> str:
    """
    Builds the complete system prompt by injecting the active persona
    and the updated user profile.
    """
    # 1. Retrieve active persona (Jarvis, Friend, etc.)
    persona = get_active_persona()
    # 🚨 MANDATORY: LANGUAGE RULE
    language_rule = """
### 🚨 MANDATORY LANGUAGE RULE 🚨
- **YOU MUST RESPOND ONLY AND EXCLUSIVELY IN ENGLISH.**
- Even if the user speaks to you in Italian, German, French, or any other language, your response MUST be in English.
- This is a system-wide internationalization requirement. No exceptions.
- Avoid using Italian greetings like "Piacere di conoscerti" or "Buongiorno". Use English equivalents.
"""

    # 🚨 GOLDEN RULE: TOOL INTEGRITY (Always included for safety)
    integrity_rule = """
### 🚨 GOLDEN RULE: TOOL INTEGRITY 🚨
1. **OPERATIONAL ACTIONS**: If the user asks to create or modify something (e.g., "Create a persona...", "Write a file..."), you MUST call the tool BEFORE replying.
2. **NO FALSE CONFIRMATION**: It is strictly forbidden to say "Done", "Operation completed", or "I have created..." unless you have just received a success signal from the tool in THIS iteration.
3. **CALL THE TOOL NOW**: If you are thinking of replying "I've created the persona", STOP and call `manage_persona` instead.
"""

    # 2. System information (Date/Time)
    import datetime
    current_time = datetime.datetime.now().strftime("%d %B %Y, %H:%M:%S")
    system_info = f"\n\n## System Information\n- **Current date and time**: {current_time}\n- **Active Persona**: {persona['name']}\n"
    
    extra_capabilities = """
---

## 🛠️ Active Modules
- **Persona Engine**: You can create and switch personas (character and voice). If the user asks for a high-quality voice or a specific voice actor, set `premium_voice=True` in `manage_persona`. 
- **Watchman (Web Monitoring)**: You can monitor websites/news. You will be awakened every X hours to check for updates. Use `manage_web_monitor`.
- **Knowledge Base (RAG)**: You can read PDF/TXT files and save them to your long-term memory. Use `learn_from_document` and `search_knowledge`.
"""

    # 4. Agent-specific instructions (Multi-Agent)
    agent_instructions = ""
    if agent_state == "CODER":
        agent_instructions = """
### 💻 CODER MODULE ACTIVE
You are in advanced programming mode. 
- **FILE STORAGE**: You MUST save all generated files and scripts into the directory: `data/workspace/`.
- **PATHS**: When you call `write_file`, use paths like `data/workspace/myscript.py`.
- **ABSOLUTE PATHS**: Always return the FULL absolute path of the generated files to the user so they can be tracked and appeared in the UI for download.
- **BEST PRACTICES**: Write clean, documented code and follow requested best practices.
"""
    elif agent_state == "AUDIO":
        agent_instructions = "\n\n### 🎤 AUDIO MODULE ACTIVE\nThe user has explicitly requested a voice response. Be concise and natural, as these words will be synthesized into speech. Keep the tone conversational.\n"

    # 3. User profile (Saved facts)
    profile = get_profile_summary()
    profile_section = f"\n\n---\n\n{profile}" if profile else "\n\n---\n\n*No user profile recorded yet.*"

    return persona["system_prompt"] + language_rule + integrity_rule + system_info + extra_capabilities + agent_instructions + profile_section
