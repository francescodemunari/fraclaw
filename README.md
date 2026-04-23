![Fraclaw Banner](banner.jpg)

# FRACLAW — Your Recursive Local AI Agent

Fraclaw is a **100% private and local** AI assistant. It integrates a Multi-Agent orchestrator, filesystem operations, real-time web monitoring, and a high-performance **Hybrid Voice Engine**. Designed for maximum privacy, Fraclaw operates entirely on your hardware, accessible via **Telegram** or **Web App**.

---

## Modular Architecture

Fraclaw is designed to be lightweight by default, with optional "Premium" extensions for heavy AI tasks.

```
Devices (Phone/PC) ◄───▶ Tailscale VPN ◀───▶ Vite Dev Server (:5173)
                                               │
                                               ▼
                                         Python Backend (:8000)
                                               │
          ┌────────────────────────────────────┴────────────────────────────────────┐
          │                                    │                                    │
    LLM Core                            Audio Engine                          Persistence
   (LM Studio)                          (Hybrid Mode)                       (SQLite + RAG)
  Qwen 3.5 / Llama 3                 Lite: Edge-TTS (Fast)                 Memory Database
  Context: 20,000 tokens             Premium: Chatterbox (Cloning)         Vector Knowledge
```

---

## Installation

### 1. Prerequisites
- **Python 3.12** (Mandatory for stable CUDA/Torch support)
- **Node.js** (LTS)
- **FFmpeg** (Installed and in system PATH)
- **LM Studio** (Started on port `1234`)

### 2. Choose Your Deployment

#### 🔹 Core Installation (Lite & Fast)
Perfect for standard use. Highly responsive, minimal disk space.
```powershell
pip install -r requirements.txt
```

#### Premium Installation (Heavy & High-Quality)
Includes **Chatterbox TTS** for zero-shot local voice cloning. 
*Note: Requires ~6GB of additional disk space and a CUDA-capable GPU.*
```powershell
pip install -r requirements-premium.txt

# Ensure PyTorch is optimized for your GPU (CUDA 12.4)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124 --force-reinstall
```

---

## Voice & Cloning Guide

### Hybrid Voice Engine
Fraclaw can switch engine on-the-fly. Just ask:
- *"Switch to Lite voice"* ➜ Uses **Edge-TTS** (Instant, cloud-echo, high reliability).
- *"Switch to Premium voice"* ➜ Uses **Chatterbox** (Local, realistic, supports cloning).

### How to Clone a Voice
1. Obtain a **5-10 second** audio sample (`.wav`) of the target voice.
2. Place it in `data/voices/` and name it `PersonaName_ref.wav` (e.g., `Jarvis_ref.wav`).
3. Fraclaw will automatically detect the reference and clone that voice in Premium mode.

---

## Remote Access via Tailscale

Fraclaw is built for remote use without security risks.
1. Install **Tailscale** on your PC and Phone.
2. Login to the same account on both.
3. Access your Web App from anywhere using: `http://<your-pc-tailscale-ip>:5173`

---

## Key Features

- ** Smart Filesystem**: Drag & drop PDF, DOCX, or Images for instant RAG analysis or Vision tasks.
- ** Active Watchman**: Automatically monitors web changes/news and pushes alerts to you.
- ** Recursive Memory**: Remembers your preferences and projects in a local SQL database.
- ** Context Protection**: Managed 20,000-token context window with automatic VRAM clearing.

---

## Running Fraclaw

Use the provided automation scripts:
- `start_webapp.bat`: Launches Backend + Frontend in separate windows.
- `stop_webapp.bat`: Gracefully kills all project processes.
- `main.py`: Starts the Telegram Bot only.

---