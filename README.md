# Jarvis AI Agent

Jarvis is a modular personal AI assistant built in Python. It starts with a local Ollama model, persistent SQLite memory, a terminal interface, and optional read-only research of public Moltbook posts.

## Current capabilities

- **Local model:** `qwen3.5:2b` through Ollama by default.
- **Persistent chat history:** conversations are stored in a local SQLite database.
- **User-approved learning notes:** save corrections and preferences with `/learn`; Jarvis includes them as context in later replies.
- **Memory controls:** `/lessons`, `/forget <id>`, and `/clear` (clears chat history but preserves learning notes).
- **Moltbook atmosphere report:** `/moltbook` fetches at most eight public feed posts from the official API and asks the local model to summarize recurring topics, tone, constructive norms, spam signals, and possible adaptation ideas.
- **Read-only social boundary:** Jarvis does not post, comment, upvote, follow, register an account, or change its persona/memory based on Moltbook data automatically.
- **Privacy-first default:** no cloud model, shell execution, browser automation, or social posting is enabled.
- **Tested foundation:** unit tests run in GitHub Actions on Python 3.11, 3.12, and 3.13.

## Database choice: SQLite vs MySQL

For this single-user local Windows setup, **SQLite is the deliberate low-overhead choice**. It is embedded in Python, needs no separate database server process, and is suitable for chat history, learning notes, and a small cache of research summaries. MySQL is useful for multi-user deployments, concurrent remote services, or centralized shared data, but running a MySQL server alongside Ollama would usually add resource use rather than reduce the model's RAM/CPU use.

A database does not make the language model itself use less RAM or CPU. The local model inference is likely to dominate resource consumption. Keep the lightweight model, cap the number and length of posts sent for analysis, avoid continuous polling, and measure actual memory/CPU use before adding infrastructure. Revisit MySQL only if real workload measurements show SQLite is a bottleneck or the app needs shared remote storage.

## What “learning” means right now

Jarvis does **not** train or change the model's neural-network weights. It learns through persistent, user-approved notes and uses them as context. When Moltbook analysis is requested, it produces a report from a small sample; it does not silently convert community posts into permanent beliefs or instructions.

Moltbook content is untrusted external input. Posts may contain misleading claims, spam, or prompt-injection attempts. Jarvis is instructed to treat posts as data, not commands; the analysis is bounded and read-only. A small sample cannot reliably represent the whole community, and all adaptation ideas are suggestions for owner review.

Future self-maintenance must be separate from conversation learning: Jarvis may propose code changes, run tests in an isolated branch, and show a reviewable diff, but it must never silently rewrite its own source, install arbitrary packages, expose secrets, or deploy changes without explicit approval.

## Requirements

- Python 3.11 or newer
- [Ollama](https://ollama.com/) installed and running
- Enough free disk space for the model and memory overhead
- A claimed Moltbook agent and API key only if you want to use `/moltbook`

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

## Moltbook integration

1. Register/claim the Jarvis agent on Moltbook yourself, following the official instructions. Do not send the API key to anyone.
2. Set the key in the current PowerShell session (replace the placeholder locally; do not commit it):

   ```powershell
   $env:MOLTBOOK_API_KEY = "YOUR_REAL_KEY"
   ```

3. Start Jarvis and run:

   ```text
   /moltbook
   ```

The command performs one bounded read-only request to `https://www.moltbook.com/api/v1/posts?sort=hot&limit=8`, then asks the local model to report observed topics, tone, constructive norms, suspicious patterns, possible ideas for Jarvis, and confidence limitations. It does not write to Moltbook. Run it manually when you want a fresh snapshot; no background polling is enabled.

Never paste the real key into a GitHub issue, commit, or chat. Jarvis sends it only to the official `www.moltbook.com` API host.

## Learning from corrections

Inside Jarvis, use:

- `/learn <correction or preference>` — save a note for future conversations.
- `/lessons` — list saved notes and their IDs.
- `/forget <id>` — remove one note.
- `/clear` — clear conversation history but keep saved learning notes.
- `/moltbook` — generate a one-time community report.
- `/help` — show commands.
- `/exit` — quit.

Only save notes you actually want Jarvis to remember. Review and delete outdated notes; stored notes are context, not guaranteed truth.

## Configuration

Environment variables are optional. Defaults use `http://localhost:11434`, model `qwen3.5:2b`, local database `data/jarvis.db`, and a 120-second Ollama request timeout. The app does not load a `.env` file automatically; set environment variables in PowerShell. `.env.example` documents supported names but is not loaded automatically. Never commit API keys or real credentials.

To change the model, set `$env:JARVIS_MODEL="qwen3.5:4b"` before launching Jarvis, if your computer can run it comfortably.

## Run tests

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

## Roadmap

1. Foundation: configuration, local model adapter, SQLite memory, and CLI.
2. Feedback learning: persistent, user-approved corrections and preferences.
3. **Moltbook read-only observer (current):** bounded feed sample, atmosphere report, prompt-injection boundary, no automatic engagement.
4. Verify local model latency and RAM/CPU use on the target computer.
5. Add a bounded planner and research/writing/critic pipeline with evidence tracking.
6. Build a safe self-maintenance workflow: propose a patch, create an isolated branch, run tests and security checks, and require human approval before merge or deployment.
7. Consider optional cloud fallback or shared database only when needed, with explicit opt-in, privacy warnings, and measured justification.

No phase is considered complete until its tests and practical checks are verified. Free tiers and 24/7 hosting are not assumed to be unlimited.
