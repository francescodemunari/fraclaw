"""
registry.py — Registro dei tool disponibili per il LLM

Contiene due cose:
  1. TOOLS_SCHEMA: lista di JSON schema che vengono passati all'LLM
     così sa quali tool può chiamare e con quali parametri.
  2. get_tool_map(): dizionario {nome_tool: funzione} usato dall'agent
     core per eseguire il tool chiamato dall'LLM.
"""

from typing import Callable

# ─── JSON Schema per il Function Calling ─────────────────────────────────────

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Legge il contenuto testuale di un file dal filesystem del PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Percorso assoluto del file da leggere (es. C:\\Users\\Admin\\Documents\\nota.txt).",
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
            "description": "Crea o sovrascrive un file testuale nel filesystem del PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Percorso assoluto del file da creare/scrivere.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Contenuto da scrivere nel file.",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": "Se true, sovrascrive il file se esiste già. Default: false.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lista file e cartelle contenuti in una directory del PC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Percorso assoluto della cartella da esplorare.",
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
            "description": "Cerca informazioni su internet usando DuckDuckGo. Utile per notizie, documentazione, prezzi, meteo, ecc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La query di ricerca.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Numero massimo di risultati da restituire (default: 5, max: 10).",
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
            "description": "Cerca esplicitamente le NOTIZIE più recenti (sport, cronaca, politica). Molto più indicato di web_search per eventi odierni (es. risultati calcio, elezioni oggi).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La query della notizia (es. 'risultati calcio serie a', 'notizie apple'). Non necessita di inserire l'anno odierno.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Numero massimo di risultati.",
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
            "description": "Legge il testo completo di una pagina web fornita l'URL. Da utilizzare IMMEDIATAMENTE dopo che una ricerca fornisce un link rilevante per esplorarne il contenuto, o quando l'utente fornisce un URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL della pagina web da scaricare via Jina Reader.",
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
            "description": "Genera un documento PDF professionale con titolo e testo. Il file viene inviato automaticamente su Telegram.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titolo del documento."},
                    "content": {"type": "string", "description": "Corpo del testo (usa \\n\\n per separare paragrafi)."},
                    "filename": {"type": "string", "description": "Nome del file (es. 'report.pdf'). Opzionale."},
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_docx",
            "description": "Genera un documento Word (.docx) con titolo e testo. Il file viene inviato automaticamente su Telegram.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titolo del documento."},
                    "content": {"type": "string", "description": "Corpo del testo (usa \\n\\n per separare paragrafi)."},
                    "filename": {"type": "string", "description": "Nome del file (es. 'documento.docx'). Opzionale."},
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_xlsx",
            "description": "Genera un foglio Excel (.xlsx) con dati tabulari. Il file viene inviato su Telegram.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Nome del foglio/tab."},
                    "headers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Intestazioni delle colonne (opzionale).",
                    },
                    "data": {
                        "type": "array",
                        "items": {"type": "array"},
                        "description": "Tabella dati (lista di liste). Ogni sotto-lista è una riga.",
                    },
                    "filename": {"type": "string", "description": "Nome file (opzionale)."},
                },
                "required": ["title", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_pptx",
            "description": "Genera una presentazione PowerPoint (.pptx). Il file viene inviato su Telegram.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titolo della presentazione."},
                    "slides": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "content": {"type": "string"},
                            },
                        },
                        "description": "Lista di slide. Ogni slide è un oggetto con 'title' e 'content'.",
                    },
                    "filename": {"type": "string", "description": "Nome file (opzionale)."},
                },
                "required": ["title", "slides"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_persona",
            "description": "Crea o aggiorna una personalità nel Persona Engine (cambia carattere e voce).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome della personalità (es. Alice)"},
                    "description": {"type": "string", "description": "Breve descrizione del ruolo (es. Amica d'infanzia)"},
                    "system_prompt": {"type": "string", "description": "Il prompt di sistema completo che definisce il carattere"},
                    "voice_id": {
                        "type": "string", 
                        "description": "ID voce (it-IT-GiuseppeNeural, it-IT-DiegoNeural, it-IT-ElsaNeural, it-IT-IsabellaNeural)"
                    }
                },
                "required": ["name", "description", "system_prompt", "voice_id"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_web_monitor",
            "description": "Iscrive l'utente a ricerche periodiche sul web (Watchman) per ricevere notifiche su novità.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "delete"]},
                    "title": {"type": "string", "description": "Nome del monitoraggio (es. 'News RTX 5090')"},
                    "query": {"type": "string", "description": "Cosa cercare?"},
                    "interval_hours": {"type": "integer", "description": "Pausa tra i controlli (ore, default 6)"}
                },
                "required": ["action", "title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "learn_from_document",
            "description": "Legge un file locale (PDF/TXT) e lo indicizza nella Knowledge Base per ricordarlo per sempre.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Percorso assoluto del file da studiare."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Cerca informazioni all'interno dei documenti precedentemente 'studiati' dall'AI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Cosa cercare nella biblioteca personale?"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": (
                "Genera un'immagine usando Stable Diffusion (SDXL) via ComfyUI. "
                "ATTENZIONE: questo tool richiede 30-40 secondi extra per gestire la VRAM. "
                "Scrivi il prompt sempre in inglese per risultati migliori."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Descrizione dettagliata dell'immagine in inglese (es. 'a futuristic city at night, neon lights, cinematic, 8k').",
                    },
                    "negative_prompt": {
                        "type": "string",
                        "description": "Cosa evitare nell'immagine (opzionale, ha un default sensato).",
                    },
                    "seed": {
                        "type": "integer",
                        "description": "Seed per la riproducibilità (-1 = casuale). Default: -1.",
                    },
                },
                "required": ["prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_user_fact",
            "description": (
                "Salva un fatto o una preferenza sull'utente nella memoria persistente. "
                "Usalo ogni volta che l'utente rivela qualcosa di importante su di sé: "
                "nome, preferenze, progetti in corso, abitudini, ecc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Categoria del fatto: 'identità', 'preferenza', 'progetto', 'abitudine', 'altro'.",
                    },
                    "key": {
                        "type": "string",
                        "description": "Nome breve del fatto (es. 'nome', 'linguaggio_preferito', 'progetto_corrente').",
                    },
                    "value": {
                        "type": "string",
                        "description": "Valore del fatto (es. 'Admin', 'Python', 'Demuclaw').",
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
            "description": "Recupera tutte le informazioni e preferenze conosciute sull'utente dal database.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_user_fact",
            "description": "Elimina un fatto o una preferenza dalla memoria persistente (usare se l'utente chiede esplicitamente di dimenticare qualcosa).",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "key": {"type": "string"}
                },
                "required": ["category", "key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Imposta un promemoria (allarme) che l'Agente invierà AUTOMATICAMENTE all'utente su Telegram dopo N minuti specificati. Usalo ogniqualvolta l'utente ti chiede di 'ricordargli' di fare qualcosa, o come auto-reminder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Il messaggio esatto che l'agente manderà su Telegram quando scatta il timer."
                    },
                    "delay_minutes": {
                        "type": "number",
                        "description": "Tra quanti minuti far suonare la notifica. Può essere decimale (es. 0.5 per 30 secondi)."
                    }
                },
                "required": ["message", "delay_minutes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_speech",
            "description": "Converte un testo in un messaggio vocale (audio) con voce maschile italiana di alta qualità. Usalo quando l'utente vuole 'sentire' qualcosa, ti chiede di parlare o vuoi mandare un messaggio vocale.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Il testo da convertire in voce."
                    }
                },
                "required": ["text"]
            }
        }
    }
]


# ─── Tool Map ─────────────────────────────────────────────────────────────────

def get_tool_map() -> dict[str, Callable]:
    """
    Restituisce il dizionario {nome_tool: funzione_callable}.
    Import lazy per evitare import circolari e caricare modelli pesanti
    (Whisper, ChromaDB) solo quando necessario.
    """
    from src.memory.preferences import get_all_facts, save_fact, delete_fact
    from src.tools.documents import (
        generate_docx,
        generate_pdf,
        generate_pptx,
        generate_xlsx,
    )
    from src.tools.filesystem import list_directory, read_file, write_file
    from src.tools.image_gen import generate_image
    from src.tools.web_search import web_search, news_search
    from src.tools.web_scraper import read_webpage
    from src.tools.cron_tool import set_reminder
    from src.tools.tts_tool import generate_speech
    from src.tools.monitor_tool import manage_web_monitor
    from src.tools.rag_tool import learn_from_document, search_knowledge
    from src.tools.persona_tool import manage_persona

    # Wrapper sincroni per le funzioni di memoria
    def _save_user_fact(category: str, key: str, value: str) -> dict:
        success = save_fact(category, key, value)
        return {
            "success": success,
            "message": f"Fatto salvato: [{category}] {key} = {value}" if success else "Errore nel salvataggio.",
        }

    def _get_user_profile() -> dict:
        facts = get_all_facts()
        return {
            "facts": facts,
            "count": len(facts),
            "message": f"{len(facts)} fatti trovati sul profilo utente.",
        }

    def _delete_user_fact(category: str, key: str) -> dict:
        success = delete_fact(category, key)
        return {"success": success, "message": "Fatto eliminato." if success else "Non trovato o errore."}

    return {
        "read_file": read_file,
        "write_file": write_file,
        "list_directory": list_directory,
        "web_search": web_search,
        "news_search": news_search,
        "read_webpage": read_webpage,
        "generate_pdf": generate_pdf,
        "generate_docx": generate_docx,
        "generate_xlsx": generate_xlsx,
        "generate_pptx": generate_pptx,
        "generate_image": generate_image,   # async
        "save_user_fact": _save_user_fact,
        "delete_user_fact": _delete_user_fact,
        "get_user_profile": _get_user_profile,
        "set_reminder": set_reminder,
        "generate_speech": generate_speech,
        "manage_persona": manage_persona,
        "manage_web_monitor": manage_web_monitor,
        "learn_from_document": learn_from_document,
        "search_knowledge": search_knowledge,
    }
