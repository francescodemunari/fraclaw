"""
registry.py — Registry of available tools for the LLM

Contains:
  1. TOOLS_SCHEMA: List of JSON schemas passed to the LLM
  2. get_tool_map(): Dictionary {tool_name: function} used by the agent core.
"""

from typing import Callable

# ─── JSON Schema for Function Calling ─────────────────────────────────────────

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the text content of a file from the local filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path of the file to read (e.g., C:\\Users\\Admin\\Documents\\note.txt).",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Creates or overwrites a text file in the local filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path of the file to create/write.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write into the file.",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "If true, overwrites the file if it already exists. Default: false.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_item",
            "description": "Moves a file or a folder (with all its contents) to the system trash/recycle bin.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path of the item to move to trash.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Creates a new directory (and parents if necessary) in the local filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path of the directory to create.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists files and folders inside a local directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute path of the directory to explore.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Searches for information on the internet using DuckDuckGo. Useful for news, documentation, prices, weather, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5, max: 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "news_search",
            "description": "Explicitly searches for the most recent NEWS (sports, politics, world events). Better than web_search for today's events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The news query (e.g., 'serie a results', 'apple news'). No need to include the current year.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": "Reads the full text of a webpage given the URL. Use IMMEDIATELY after a search provides a relevant link, or when the user provides an URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL of the webpage to scrape via Jina Reader.",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_pdf",
            "description": "Generates a professional PDF document with title and body. Automatically sent to the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Document title."},
                    "content": {"type": "string", "description": "Body text (use \\n\\n for paragraphs)."},
                    "filename": {"type": "string", "description": "Filename (e.g., 'report.pdf'). Optional."},
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_docx",
            "description": "Generates a Word document (.docx). Automatically sent to the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Document title."},
                    "content": {"type": "string", "description": "Body text."},
                    "filename": {"type": "string", "description": "Filename. Optional."},
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_xlsx",
            "description": "Generates an Excel spreadsheet (.xlsx). Automatically sent to the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Sheet name."},
                    "headers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Column headers (optional).",
                    },
                    "data": {
                        "type": "array",
                        "items": {"type": "array"},
                        "description": "Data table (list of lists).",
                    },
                    "filename": {"type": "string", "description": "Filename (optional)."},
                },
                "required": ["title", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_pptx",
            "description": "Generates a PowerPoint presentation (.pptx). Automatically sent to the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Presentation title."},
                    "slides": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "content": {"type": "string"},
                            },
                        },
                        "description": "List of slides, each with a title and content.",
                    },
                    "filename": {"type": "string", "description": "Filename (optional)."},
                },
                "required": ["title", "slides"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generates a high-quality image from a text description using ComfyUI. Returns the local path to the generated image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Detailed description of the image to generate.",
                    }
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_user_fact",
            "description": "Saves a relevant fact about the user (preferences, identity, projects) to the long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Category (e.g., 'identity', 'preference', 'project', 'knowledge').",
                    },
                    "key": {
                        "type": "string",
                        "description": "A short, unique key for the fact (e.g., 'favourite_color').",
                    },
                    "value": {
                        "type": "string",
                        "description": "The information to remember.",
                    },
                },
                "required": ["category", "key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": "Retrieves the full profile of the user, containing all remembered facts.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_user_fact",
            "description": "Removes a specific fact from the user's memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "key": {"type": "string"},
                },
                "required": ["category", "key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Schedules a reminder or a task to be executed later.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The text content of the reminder (e.g., 'Take the medicine')."},
                    "delay_minutes": {"type": "integer", "description": "Minutes from now until the reminder is sent."},
                },
                "required": ["message", "delay_minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_web_monitor",
            "description": "Adds or removes a web monitoring subscription. The agent will periodically check the URL or search query for changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "remove", "list"]},
                    "title": {"type": "string", "description": "Unique title for the monitor."},
                    "query": {"type": "string", "description": "Search query or URL to monitor."},
                    "interval_hours": {"type": "integer", "description": "Check frequency (default: 6)."},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "learn_from_document",
            "description": "Analyzes a document (PDF, Word, TXT) and stores its knowledge in the RAG Vector Database for future semantic search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Local path of the document."},
                    "label": {"type": "string", "description": "Short label/category for this knowledge."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Searches the local RAG Vector Database for information learned from past documents or chats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                    "limit": {"type": "integer", "description": "Max results (default: 3)."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_persona",
            "description": "Creates, updates or switches the AI's active personality (Persona). Can configure system prompts and voices.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["switch", "save", "delete", "list"]},
                    "name": {"type": "string", "description": "Name of the persona."},
                    "description": {"type": "string", "description": "Short bio (for 'save' action)."},
                    "system_prompt": {"type": "string", "description": "Full system instruction (for 'save' action)."},
                    "voice_id": {"type": "string", "description": "Edge-TTS voice ID (e.g., 'en-US-AndrewNeural')."},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_speech",
            "description": "Synthesizes text into an audio file (WAV) using Edge-TTS. Use this when the user asks for an audio version of a script, a tutorial voiceover, or a standalone audio file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The exact text to convert to speech.",
                    },
                    "voice": {
                        "type": "string",
                        "description": "Optional Edge-TTS voice ID (e.g., 'en-US-AndrewNeural').",
                    }
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_manage",
            "description": "Manage reusable skills (procedures you've learned). Use 'create' after completing a complex multi-step task to save it for future reuse. Use 'list' to see available skills, 'view' to read one.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "edit", "patch", "delete", "list", "view"],
                        "description": "The action to perform.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Skill name (lowercase, hyphens/underscores, 3-64 chars).",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full SKILL.md content with YAML frontmatter (for create/edit).",
                    },
                    "category": {
                        "type": "string",
                        "description": "Category folder (e.g., 'coding', 'documents', 'automation'). Default: 'general'.",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "Text to find (for patch action).",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "Replacement text (for patch action).",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_conversations",
            "description": "Search through past conversation history using full-text search. Use when user asks 'have we talked about...', 'what did we do with...', or needs to recall past interactions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (keywords or phrases).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 5).",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# ─── Tool Map ─────────────────────────────────────────────────────────────────

def get_tools_description() -> str:
    """
    Returns a human-readable string description of all tools in TOOLS_SCHEMA.
    Used for prompt injection fallback.
    """
    desc = []
    for t in TOOLS_SCHEMA:
        func = t.get("function", {})
        name = func.get("name")
        description = func.get("description")
        params = func.get("parameters", {}).get("properties", {})
        required = func.get("parameters", {}).get("required", [])
        
        p_list = []
        for p_name, p_info in params.items():
            req_label = "(required)" if p_name in required else "(optional)"
            p_list.append(f"  - {p_name}: {p_info.get('description')} {req_label}")
            
        desc.append(f"NAME: {name}\nDESCRIPTION: {description}\nPARAMETERS:\n" + "\n".join(p_list))
    
    return "\n\n".join(desc)

def get_tool_map() -> dict[str, Callable]:
    """
    Returns a dictionary {tool_name: callable_function}.
    Lazy imports to avoid circular dependencies and load heavy models only when needed.
    """
    from src.memory.preferences import get_all_facts, save_fact, delete_fact
    from src.tools.documents import (
        generate_docx,
        generate_pdf,
        generate_pptx,
        generate_xlsx,
    )
    from src.tools.filesystem import list_directory, read_file, write_file, create_directory, delete_item
    from src.tools.image_gen import generate_image
    from src.tools.web_search import web_search, news_search
    from src.tools.web_scraper import read_webpage
    from src.tools.cron_tool import set_reminder
    from src.tools.tts_tool import generate_speech
    from src.tools.monitor_tool import manage_web_monitor
    from src.tools.rag_tool import learn_from_document, search_knowledge
    from src.tools.persona_tool import manage_persona

    # Synchronous wrappers for memory functions
    def _save_user_fact(category: str, key: str, value: str) -> dict:
        success = save_fact(category, key, value)
        return {
            "success": success,
            "message": f"Fact saved: [{category}] {key} = {value}" if success else "Error saving fact.",
        }

    def _get_user_profile() -> dict:
        facts = get_all_facts()
        return {
            "facts": facts,
            "count": len(facts),
            "message": f"{len(facts)} facts found in user profile.",
        }

    def _delete_user_fact(category: str, key: str) -> dict:
        success = delete_fact(category, key)
        return {"success": success, "message": "Fact deleted." if success else "Not found or error."}

    from src.skills.manager import skill_manage
    from src.memory.database import search_conversations

    def _search_conversations(query: str, limit: int = 5) -> dict:
        results = search_conversations(query, limit)
        return {"results": results, "count": len(results), "query": query}

    return {
        "read_file": read_file,
        "write_file": write_file,
        "create_directory": create_directory,
        "delete_item": delete_item,
        "list_directory": list_directory,
        "web_search": web_search,
        "news_search": news_search,
        "read_webpage": read_webpage,
        "generate_pdf": generate_pdf,
        "generate_docx": generate_docx,
        "generate_xlsx": generate_xlsx,
        "generate_pptx": generate_pptx,
        "generate_image": generate_image,
        "save_user_fact": _save_user_fact,
        "delete_user_fact": _delete_user_fact,
        "get_user_profile": _get_user_profile,
        "set_reminder": set_reminder,
        "manage_persona": manage_persona,
        "manage_web_monitor": manage_web_monitor,
        "learn_from_document": learn_from_document,
        "search_knowledge": search_knowledge,
        "generate_speech": generate_speech,
        "skill_manage": skill_manage,
        "search_conversations": _search_conversations,
    }
