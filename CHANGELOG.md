# Changelog

## v1.2.0 (2026-05-11)

### Added
- **Multi-Provider System**: Support for 7 LLM providers (LM Studio, OpenRouter, Anthropic, OpenAI, DeepSeek, Ollama, Google Gemini) via unified adapter interface.
- **Multi-Platform Gateway**: Discord and WhatsApp support alongside existing Telegram. Unified `src/gateway/` architecture with abstract adapter pattern.
- **Skills System**: Autonomous skill learning — agent creates reusable procedures after complex tasks. Skills stored as markdown with YAML frontmatter, discoverable at runtime.
- **FTS5 Conversation Search**: Full-text search across all past conversations. New `/search` command on Telegram, `!search` on Discord, and `search_conversations` tool for the agent.
- **Image Engine in Orchestrator**: Image generation is now a first-class intent (like CODER and AUDIO). The orchestrator ejects the conversation model, runs ComfyUI generation, and reloads the base model automatically. Only activates with local providers.
- **`/status` Command**: System diagnostics showing active provider, model, persona, and VRAM state.
- **Configurable History Window**: `HISTORY_LIMIT` env var (default 25, was hardcoded to 10).
- **New Tools**: `skill_manage` (create/edit/patch/delete/list/view skills), `search_conversations` (FTS5 search).

### Changed
- **Provider Abstraction**: `get_client()` now routes through provider registry instead of hardcoding LM Studio. Supports async context manager pattern.
- **VRAM Management**: Only activates for local providers (LM Studio, Ollama). Cloud providers skip model loading/unloading entirely. Coder and Image engines are local-only.
- **Voice System**: Simplified to Edge-TTS only. Removed Chatterbox premium voice cloning and associated dependencies (torch, soundfile, torchaudio).
- **ComfyUI Default Port**: Fixed from 8000 to 8188 (correct default).
- **Config Validation**: Now requires at least one platform token (Telegram OR Discord) instead of mandating Telegram.
- **README**: Complete rewrite reflecting new architecture and capabilities.

### Removed
- Chatterbox premium voice engine and `requirements-premium.txt`.
- `torch` removed from core requirements (was only needed for Chatterbox).

### Fixed
- ComfyUI URL default was conflicting with FastAPI web server port.
- History window too small (10 messages) causing agent to lose context mid-conversation.

---

## v1.1.0

- Mobile App overhaul with Glassmorphism and Aurora theme
- ComfyUI auto-launch and VRAM safety shield
- Full feature parity between web and mobile apps

## v1.0.0

- Initial release with Telegram bot, web dashboard, and core agent capabilities.
