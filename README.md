![Fraclaw Banner](webapp/public/banner.png)

<h1 align="center">FRACLAW - Your Recursive Local AI Agent</h1>

<p align="center">
  <strong>A multi-tool assistant that runs entirely on your hardware.</strong>
</p>

---

## Core Capabilities

### Intelligent Orchestration (BASE and CODER)
Fraclaw uses a transparent Intent Routing logic to manage your VRAM efficiently:
- Base Engine: Used for smart chat, summaries, and decision-making.
- Coder Engine: Automatically swapped in for deep technical tasks. Integrated with a 20,000 token context window to maintain precision over large scripts.

### ComfyUI Integration and VRAM Safety Shield
High-quality SDXL image generation running entirely offline:
- Auto-Launch and Stealth Mode: Sends a signal to silently wake up the ComfyUI backend locally when an image is requested. No user intervention is needed.
- Model Ejection Barrier: Integrates with LM Studio v1 APIs to forcefully eject the conversation model from VRAM, blocking execution until the GPU is 100% empty to give ComfyUI maximum breathing room.
- Smart Image Serving: Automatically captures, saves locally, and serves the generated images seamlessly to all frontends.

### Hybrid Voice System
- Edge-TTS: Ultra-fast, lightweight voice generation.
- Chatterbox: High-fidelity, premium audio model wrapper.

### Pro-Grade Filesystem Bridge
Fraclaw is aware of its surroundings. It can read, write, and manage your local environment:
- Safe Operations: All deletions are redirected to the System Trash Bin using the `send2trash` dependency, avoiding accidental permanent file loss.

### Real-time Web and Knowledge Base
- Smart Scraper: Extracts clean markdown from any URL.
- Persistent RAG: Uses ChromaDB to store personal knowledge and indexed documents.
- Neural Memory: Remembers user preferences and "facts" using a local SQLite database.

---

## The Mobile Experience (Flutter App)

Fraclaw comes with a fully-fledged, compiled native mobile application prioritizing ultra-premium aesthetics:
- Fluid UI and Glassmorphism: Complete user interface restyled with frosted-glass containers over animated, dynamic Aurora backgrounds.
- 100% Feature Parity:
  - Browse conversations, listen to audio answers directly inside the chat bubbles, and visualize output code with live syntax highlighting.
  - Interactive Full-Screen Image Preview allowing pinch-to-zoom and direct save-to-device hooks.
- Personas and Memory Dashboard: Tweak how Fraclaw remembers details and change system interaction styles dynamically on the phone without touching the backend code.

---

## Tested Configuration
Fraclaw has been successfully tested on a mid-range local environment:
- VRAM: 12 GB (Tested on RTX 3060/4070 series)
- RAM: 16 GB
- Base Agent: Qwen 3.5 9B / Llama 3 8B
- Coder Agent: Qwen 2.5 Coder 7B Instruct 

---

## Setup and Deployment Guide

### 1. Project Initialization
First, clone the repository and set up a Python virtual environment. This is required because the automated launch scripts (.bat) look for a `.venv` folder in the project root.
```bash
git clone https://github.com/francescodemunari/fraclaw
cd fraclaw
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration
Copy the `.env.example` file and rename the copy to `.env`. This file holds your local paths, models, and private tokens. Do not share your `.env` file publicly.

### 3. Telegram Bot Setup
To interface with Fraclaw via Telegram, you need to set up a private bot:
1. Open Telegram and search for `@BotFather`.
2. Send the `/newbot` command and follow the prompts to name your assistant and choose a username.
3. BotFather will provide an HTTP API Token. Copy this exact string and paste it as the `TELEGRAM_TOKEN` variable in your `.env` file.
4. To ensure only you can communicate with your AI, use a service like `@userinfobot` on Telegram to get your numeric User ID.
5. Paste your numeric ID into the `TELEGRAM_ALLOWED_USER_ID` variable in the `.env` file. Fraclaw will strictly ignore messages from anyone else.

### 4. Running the Ecosystem

Fraclaw consists of three separate entities: the backend core, the web application, and the mobile application. You can launch them independently based on your needs.

#### Backend Core (Mandatory Engine)
This terminal runs the AI logic, LM Studio bridging, ComfyUI integrations, and the Telegram listener.
```bash
python main.py
```

#### Web Application
To access the dashboard on your browser, navigate to the `webapp` folder. You do not need to deal with node commands directly. Simply double click the batch launcher:
- Run `start.bat` located inside the `webapp` directory. This script will automatically boot up the Vite development server and provide you with the localhost address to view the dashboard.

#### Mobile Application
To launch the native mobile application on your Windows machine, navigate to the `mobile_app` folder. 

**Important:** The **Backend Core** must be actively running for the mobile application to communicate with the AI.

- **For Testing (Windows):** Run the `test_windows.bat` script located inside the `mobile_app` directory. This will compile the app and launch a standalone Windows window to preview the interface and test all functionalities immediately.
- **For Android (APK):** If you wish to install Fraclaw on your physical Android device:
  1. Open a terminal in the `mobile_app` folder.
  2. Run the command: `flutter build apk --split-per-abi`.
  3. The generated file will be located in `build/app/outputs/flutter-apk/app-release.apk`.
- **Pre-compiled Versions:** You can find the latest stable `.apk` ready for installation in the **Releases** section of this GitHub repository.

---
