# Jarvis AI Agent

Jarvis is a modular personal AI assistant built in Python. It starts with a local Ollama model, persistent SQLite memory, and a terminal interface. The current learning loop lets you explicitly save corrections and preferences so future replies can use them.

## Current capabilities

- **Local model:** `qwen3.5:2b` through Ollama by default.
- **Persistent chat history:** conversations are stored in a local SQLite database.
- **User-approved learning notes:** save corrections, preferences, and lessons with `/learn`; Jarvis includes these notes as context in later replies.
- **Memory controls:** inspect notes with `/lessons`, remove an individual note with `/forget <id>`, and clear chat history without deleting learning notes with `/clear`.
- **Privacy-first default:** no cloud model, shell execution, browser automation, or social posting is enabled.
- **Tested foundation:** unit tests run in GitHub Actions on Python 3.11, 3.12, and 3.13.

### What “learning” means right now

Jarvis does **not** train or change the model's neural-network weights. It learns through persistent, user-approved notes and uses them as context. This is lightweight, reversible, and suitable for a small computer. It cannot reliably identify every mistake on its own: when an answer is wrong, tell it the correct rule with `/learn <correction>`.

Future self-maintenance must be separate from conversation learning: Jarvis may propose code changes, run tests in an isolated branch, and show a reviewable diff, but it must never silently rewrite its own source, install arbitrary packages, expose secrets, or deploy changes without explicit approval.

## Requirements

- Python 3.11 or newer
- [Ollama](https://ollama.com/) installed and running
- Enough free disk space for the model and memory overhead

## Setup (Windows PowerShell)

1. Install Ollama from its official website and open it.
2. Download the default model:

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

## Learning from corrections

Inside Jarvis, use:

- `/learn <correction or preference>` — save a note for future conversations.
- `/lessons` — list saved notes and their IDs.
- `/forget <id>` — remove one note.
- `/clear` — clear conversation history but keep saved learning notes.
- `/help` — show commands.
- `/exit` — quit.

Example:

```text
/learn When I ask for explanations, prefer simple Moroccan Darija and concrete steps.
/lessons
```

Only save notes you actually want Jarvis to remember. Review and delete outdated notes; stored notes are context, not guaranteed truth.

## Configuration

Environment variables are optional. Defaults use `http://localhost:11434`, model `qwen3.5:2b`, local database `data/jarvis.db`, and a 120-second request timeout. The app does not load a `.env` file automatically; set environment variables in PowerShell. `.env.example` documents supported names but is not loaded automatically. Never commit API keys or real credentials.

To change the model, set `JARVIS_MODEL=qwen3.5:4b` before launching Jarvis, if your computer can run it comfortably.

## Run tests

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

## Roadmap

1. Foundation: configuration, local model adapter, SQLite memory, and CLI.
2. **Feedback learning (current):** persistent, user-approved corrections and preferences.
3. Verify local model latency and RAM use on the target computer.
4. Add a bounded planner and research/writing/critic pipeline with evidence tracking.
5. Add optional web research with source citations, timeouts, and prompt-injection defenses.
6. Consider a cloud fallback only with explicit opt-in, privacy warnings, and spending limits.
7. Build a safe self-maintenance workflow: propose a patch, create an isolated branch, run tests and security checks, and require human approval before merge or deployment.
8. Consider external integrations only after permissions, rate limits, logging, and human review are in place.

No phase is considered complete until its tests and practical checks are verified. Free tiers and 24/7 hosting are not assumed to be unlimited.
