![Fraclaw Banner](webapp/public/banner.png)

<h1 align="center">FRACLAW — AI Agent</h1>

<p align="center">
  <strong>A multi-tool assistant that runs on your hardware or connects to any cloud LLM.</strong>
</p>

---

## Core Capabilities

### Multi-Provider LLM Support
Use any model you want — switch providers with one environment variable:

| Provider | Type | Setup |
|----------|------|-------|
| **LM Studio** | Local | Default, no API key needed |
| **Ollama** | Local | `ACTIVE_PROVIDER=ollama` |
| **OpenRouter** | Cloud | `OPENROUTER_API_KEY=sk-or-...` |
| **Anthropic** | Cloud | `ANTHROPIC_API_KEY=sk-ant-...` |
| **OpenAI** | Cloud | `OPENAI_API_KEY=sk-...` |
| **DeepSeek** | Cloud | `DEEPSEEK_API_KEY=sk-...` |
| **Google Gemini** | Cloud | `GEMINI_API_KEY=AI...` |

VRAM management (model loading/unloading) only activates for local providers.

### Intelligent Orchestration (BASE, CODER, IMAGE)
Transparent Intent Routing manages your VRAM efficiently. The specialized engines (Coder and Image) only activate with local providers — cloud providers handle everything through the base model.

- **Base Engine**: Smart chat, summaries, decision-making, and general tasks.
- **Coder Engine** (local only): Automatically swapped in for deep technical tasks with 20,000 token context. Ejects the base model, loads the coder model, then reloads base after completion.
- **Image Engine** (local only): Ejects the conversation model from VRAM to free resources for ComfyUI image generation, then reloads the base model after generation completes.

### Skills System (Learning Loop)
The agent creates reusable skills after complex tasks:
- Skills stored as markdown files with YAML frontmatter
- Auto-suggested after multi-step procedures
- Searchable and editable via `skill_manage` tool
- Usage tracking and lifecycle management

### Multi-Platform Gateway
Talk to Fraclaw from anywhere:
- **Telegram** — Full feature support (voice, photos, documents, inline buttons)
- **Discord** — Text, images, embeds, commands
- **WhatsApp** — Via whatsapp-web.js bridge (QR code auth, no business account needed)
- **Web App** — React dashboard with real-time Socket.IO
- **Mobile App** — Native Flutter application

### ComfyUI Integration and VRAM Safety Shield
High-quality SDXL image generation running entirely offline:
- Auto-Launch: Silently wakes up the ComfyUI backend when an image is requested.
- Model Ejection Barrier: Forcefully ejects the conversation model from VRAM before image generation.
- Smart Image Serving: Captures, saves, and serves generated images to all frontends.

### Conversation Search (FTS5)
Full-text search across your entire conversation history:
- `/search python regex` on Telegram finds all relevant past messages
- Agent can search its own history to recall past solutions
- Indexed in real-time as conversations happen

### Voice System (Edge-TTS)
Ultra-fast, lightweight voice generation with configurable voice per persona.

### Pro-Grade Filesystem Bridge
Read, write, and manage your local environment:
- Safe Operations: Deletions redirected to System Trash Bin via `send2trash`.

### Real-time Web and Knowledge Base
- **Smart Scraper**: Extracts clean markdown from any URL.
- **Persistent RAG**: ChromaDB for personal knowledge and indexed documents.
- **Neural Memory**: Remembers user preferences and facts via local SQLite.

---

## The Mobile Experience (Flutter App)

Native mobile application with premium aesthetics:
- Fluid UI with glassmorphism and animated Aurora backgrounds.
- Full feature parity with web app.
- Interactive full-screen image preview with pinch-to-zoom.
- Personas and Memory Dashboard.

---

## Tested Configuration (Local Inference)

These specs are for running models locally via LM Studio or Ollama. Cloud providers have no local hardware requirements beyond network access.

- **VRAM**: 12 GB (Tested on RTX 3060/4070 series)
- **RAM**: 16 GB
- **Base Agent**: Qwen 3.5 9B / Llama 3 8B
- **Coder Agent**: Qwen 2.5 Coder 7B Instruct

---

## Setup and Deployment Guide

### 1. Project Initialization
```bash
git clone https://github.com/francescodemunari/fraclaw
cd fraclaw
pip install -r requirements.txt
```

### 2. Environment Configuration
```bash
cp .env.example .env
# Edit .env with your tokens and API keys
```

Key settings:
- `ACTIVE_PROVIDER` — Which LLM to use (default: `lm_studio`)
- `TELEGRAM_TOKEN` — Your Telegram bot token (from @BotFather)
- `TELEGRAM_ALLOWED_USER_ID` — Your numeric Telegram user ID

### 3. Platform Setup

#### Telegram (Primary)
1. Message `@BotFather` on Telegram → `/newbot`
2. Copy the token to `TELEGRAM_TOKEN` in `.env`
3. Get your user ID from `@userinfobot` → set `TELEGRAM_ALLOWED_USER_ID`

#### Discord (Optional)
1. Create app at [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a Bot, copy the token to `DISCORD_TOKEN` in `.env`
3. Invite the bot to your server with Message + Attachment permissions

#### WhatsApp (Optional)
1. Install Node.js v18+
2. Set `WHATSAPP_ENABLED=true` in `.env`
3. On first run, scan the QR code displayed in the terminal with your phone

### 4. Running the Ecosystem

#### Backend Core (Mandatory Engine)
```bash
python main.py
```

#### React Web Application
```bash
cd webapp && npm run dev
```
Or double-click `start.bat` inside the `webapp` directory.

#### Flutter Mobile Application
Run `test_windows.bat` inside the `mobile_app` directory.

---

## Commands

### Telegram
| Command | Description |
|---------|-------------|
| `/start` | Welcome message and capabilities |
| `/search [query]` | Search past conversations |
| `/status` | Show active model, persona, and system state |
| `/persona` | Switch AI personality |
| `/clear` | Clear short-term memory |
| `/reset` | Full memory wipe |

### Discord
| Command | Description |
|---------|-------------|
| `!status` | Show system diagnostics |
| `!search [query]` | Search past conversations |
| `!clear` | Clear conversation memory |

---

## Architecture

```
fraclaw/
├── main.py                    # Entry point
├── src/
│   ├── providers/             # Multi-LLM provider abstraction
│   │   ├── base.py            # Provider registry & factory
│   │   ├── lm_studio.py      # Local inference
│   │   ├── openrouter.py     # Cloud models
│   │   ├── anthropic_provider.py
│   │   ├── openai_provider.py
│   │   ├── deepseek.py
│   │   ├── ollama.py
│   │   └── gemini.py
│   ├── gateway/               # Multi-platform messaging
│   │   ├── base.py            # Abstract adapter interface
│   │   ├── telegram.py        # Telegram bot
│   │   ├── discord.py         # Discord bot
│   │   └── whatsapp.py        # WhatsApp bridge
│   ├── skills/                # Learning system
│   │   ├── loader.py          # Skill discovery & FTS
│   │   └── manager.py         # CRUD operations
│   ├── agent/                 # Core AI logic
│   │   ├── core.py            # Agent loop with tool use
│   │   ├── orchestrator.py    # Intent routing & model switching
│   │   ├── manager.py         # VRAM management
│   │   └── prompts.py         # Dynamic system prompt
│   ├── memory/                # Persistence
│   │   ├── database.py        # SQLite + FTS5
│   │   ├── preferences.py     # Facts, personas, history
│   │   └── vector.py          # ChromaDB RAG
│   ├── tools/                 # Agent tools
│   │   ├── registry.py        # Tool schema + dispatch
│   │   └── ...                # 12+ tools
│   └── web/
│       └── api.py             # FastAPI + Socket.IO
├── data/
│   ├── skills/                # Learned skills (markdown)
│   └── ...
├── webapp/                    # React frontend
└── mobile_app/                # Flutter app
```
