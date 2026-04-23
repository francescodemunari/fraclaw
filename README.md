![Fraclaw Banner](webapp/public/banner.png)

<p align="center">
  <img src="webapp/public/logo.png" width="120" alt="Fraclaw Logo">
</p>

<h1 align="center">FRACLAW — Your Recursive Local AI Agent</h1>

<p align="center">
  <strong>The privacy-first, multi-tool assistant that runs entirely on your hardware.</strong>
</p>

---

##  Core Capabilities

### Intelligent Orchestration (BASE & CODER)
Fraclaw uses a transparent **Intent Routing** logic to manage your VRAM efficiently:
- **BASE Engine**: Used for smart chat, summaries, and decision-making.
- **CODER Engine**: Automatically swapped in for deep technical tasks. Integrated with a **20,000 token context window** to maintain precision over large scripts.

###  Pro-Grade Filesystem Bridge
Fraclaw is aware of its surroundings. It can read, write, and manage your local environment:
- **Safe Operations**: All deletions are redirected to the **System Trash Bin** using `send2trash`.
- **Project Awareness**: Can analyze file structures recursively to help with migrations or refactoring.

###  Real-time Web & Knowledge Base
- **Smart Scraper**: Extracts clean markdown from any URL using Jina/Readability fallbacks.
- **Persistent RAG**: Uses **ChromaDB** to store personal knowledge and indexed documents.
- **Neural Memory**: Remembers user preferences and "facts" using a local SQLite database.

###  Advanced Multimodal Tools
- **Vision**: Analyzes photos, diagrams, and logs sent via Telegram or the Web App.
- **Local Generation**: High-quality SDXL image synthesis via ComfyUI.
- **Hybrid Voice**: Seamlessly switches between **Edge-TTS (Lite)** and **Chatterbox (Premium)**.

---

##  Tested Configuration
Fraclaw has been successfully tested on a mid-range local environment with the following specs:

###  Hardware Specs
- **VRAM**: 12 GB (Tested on RTX 3060/4070 series)
- **RAM**: 16 GB
- **Storage**: SSD recommended for model loading speed.

###  Verified Models
The following models have been confirmed as fully operational within the Fraclaw orchestrator:
- **Base Agent**: `Qwen 3.5 9B` (Fast and accurate for daily tasks).
- **Coder Agent**: `Qwen 3 Coder 30B` (High-tier reasoning for complex technical scripts).
- **Vision Agent**: `Qwen2-VL-7B-Instruct`.

---

##  Setup & Deployment

### 1. Installation
```bash
git clone https://github.com/your-username/fraclaw.git
cd fraclaw
pip install -r requirements.txt
```

### 2. Environment Configuration
Copy `.env.example` to `.env` and configure your API keys and model identifiers.

### 3. Execution
```bash
# Start the Backend
python main.py

# Start the Web App (In another terminal)
cd webapp
npm install
npm run dev
```

---