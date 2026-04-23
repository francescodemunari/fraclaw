![Fraclaw Banner](webapp/public/banner.jpg)

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

##  Tested & Recommended Models
For optimal stability and reasoning, Fraclaw has been extensively tested with the following models (via LM Studio):

| Role | Recommended Model | Quantization | Why? |
| :--- | :--- | :--- | :--- |
| **Coder** | `Qwen2.5-Coder-14B-Instruct` | Q4_K_M / Q6_K | State-of-the-art coding logic for 14B models. |
| **Base** | `Qwen2.5-14B-Instruct` | Q4_K_M | Excellent general reasoning and consistent tone. |
| **Alternative Base** | `Llama-3.1-8B-Instruct` | Q8_0 | Fast, reliable, and lower VRAM usage. |
| **Vision** | `Qwen2-VL-7B-Instruct` | BF16 / Q4_K_M | High accuracy in document and image analysis. |
| **Image Gen** | `Juggernaut XL (SDXL)` | -- | Best-in-class local image generation via ComfyUI. |

---

##  Hardware Requirements

| Component | Minimum | Recommended |
| :--- | :--- | :--- |
| **RAM** | 16 GB | 32 GB+ |
| **GPU (VRAM)** | 8 GB | 12 GB+ (RTX 3060/4070+) |
| **Storage** | 20 GB (SSD) | 50 GB+ (for multiple models) |

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

##  Pushing Updates to GitHub
1. **Stage changes**: `git add .`
2. **Commit**: `git commit -m "description of what you changed"`
3. **Push**: `git push origin main`

###  Creating Your First Release (v1.0.0)
```bash
git tag -a v1.0.0 -m "Official Release 1.0: Hybrid Audio & Orchestration stable"
git push origin v1.0.0
```

---

*Fraclaw — More than a chatbot, your local silicon companion.*