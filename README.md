# fraclaw

Fraclaw is a modular, 100% local AI assistant developed to run on personal hardware. It uses local model (via LM Studio) and is controlled through a **Telegram** interface. 

The project focuses on privacy and local execution for document management, web monitoring, and automated media generation.

---

## Core Features

- **Long-term Memory (RAG)**: Index PDF/TXT documents into a vector database (ChromaDB) for semantic search and contextual awareness.
- **Watchman (Web Monitoring)**: Automated periodic web searches to notify the user about specific topics or news updates.
- **Persona Engine**: Dynamic system prompts and specific voices (Edge-TTS) for different interaction styles (e.g., Jarvis, Friend).
- **Media Generation**: Integrated with **ComfyUI** for SDXL image generation and **Whisper** for voice message transcription.
- **Persistent Profile**: Saves user facts, preferences, and project history in a local SQLite database.

---

## Architecture & Tech Stack

- **Linguistic Core**: Qwen 3.5 9B (via [LM Studio](https://lmstudio.ai/))
- **Interface**: [python-telegram-bot](https://python-telegram-bot.org/)
- **Databases**: SQLite (Structured facts) & ChromaDB (Unstructured knowledge)
- **Audio/Vision**: Edge-TTS, Whisper, ComfyUI (SDXL API)

---

## Getting Started

### Prerequisites
- **Python 3.10+**
- **LM Studio**: Load a tool-compatible model and start the Local Server on port 1234.
- **ComfyUI** (Optional): For image generation features.

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/fraclaw.git
   cd fraclaw
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Configuration
1. Edit `.env` with your **TELEGRAM_TOKEN** and local paths.

### Running
```bash
python main.py
```

---

## Privacy
All processing and data storage occur locally on your machine. No data is sent to external cloud services except for those explicitly configured (e.g., Telegram API for communication).
