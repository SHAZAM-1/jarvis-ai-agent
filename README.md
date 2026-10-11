# Jarvis AI Agent

Jarvis is a modular personal AI assistant built in Python. The first phase focuses on a safe, testable foundation: a local Ollama connection, persistent SQLite conversation memory, a terminal interface, and automated tests.

## Current plan

- **Default model:** `qwen3.5:2b` through Ollama, prioritizing a lighter local setup.
- **Optional upgrade:** try `qwen3.5:4b` only if speed and RAM use are acceptable.
- **Optional future fallback:** Gemini API, disabled by default and only added after the local path is verified.
- **Privacy:** conversations are stored locally in SQLite. No cloud model or external tool is called by this phase.
- **Safety:** no shell execution, browser automation, social posting, or other external actions are enabled in this phase.

## Requirements

- Python 3.11 or newer
- [Ollama](https://ollama.com/) installed and running
- Enough free disk space for the model and memory overhead

## Setup (Windows PowerShell)

1. Install Ollama from its official website and open it.
2. In PowerShell, download the default model:

   ```powershell
   ollama pull qwen3.5:2b
   ```

3. In the repository folder, create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev]"
   ```

4. Start Jarvis:

   ```powershell
   jarvis
   ```

   Or run `python -m jarvis.cli` after installation.

If Ollama is not available, check that the Ollama application is running. To change the model later, set `JARVIS_MODEL=qwen3.5:4b` in your environment before launching Jarvis.

## Configuration

Environment variables are optional. Defaults use `http://localhost:11434`, model `qwen3.5:2b`, local database `data/jarvis.db`, and a 120-second request timeout. The app intentionally does not load a `.env` file automatically in this phase; set environment variables in PowerShell. `.env.example` documents the supported names but is not loaded automatically. Never commit API keys or real credentials.

## Run tests

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

## Roadmap

1. Foundation and tests (current): config, local model adapter, SQLite memory, CLI.
2. Verify the model on the target computer; measure response time and memory use.
3. Add structured planning and research/writing/critic modules with tests.
4. Consider Gemini API as an optional fallback with explicit quotas and privacy controls.
5. Add Moltbook integration only with rate limits, human-reviewed posting, and anti-spam safeguards.
6. Evaluate free hosting and analytics only after local behavior is stable.

No phase is considered complete until its tests and practical checks are verified. Free tiers and 24/7 hosting are not assumed to be unlimited.
