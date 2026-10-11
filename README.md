# Jarvis AI Agent

Jarvis is a modular personal AI assistant built in Python. It uses a local Ollama model, persistent SQLite memory, a terminal interface, and optional read-only research of public Moltbook posts.

## Current capabilities

- **Local model:** `qwen3.5:2b` through Ollama by default.
- **Persistent chat history:** conversations are stored in a local SQLite database.
- **User-approved learning notes:** save corrections and preferences with `/learn`; Jarvis includes them as context in later replies.
- **Memory controls:** `/lessons`, `/forget <id>`, and `/clear` (clears chat history but preserves learning notes).
- **Moltbook atmosphere report:** `/moltbook` fetches at most eight public posts and summarizes topics, tone, constructive norms, suspicious patterns, and adaptation ideas.
- **Growth observation loop:** `/moltbook-loop [minutes]` periodically analyzes recent public posts. The default interval is 60 minutes and the minimum is 30 minutes. Press Ctrl+C to stop.
- **Conversation drafts:** reports can suggest a few relevant, respectful conversation starters for the owner to review and post manually.
- **Read-only social boundary:** Jarvis does not post, comment, vote, follow, DM, register accounts, or change memory/code automatically.
- **Privacy-first default:** no cloud model, shell execution, browser automation, or social posting is enabled.
- **CI coverage:** unit tests run in GitHub Actions on Python 3.11, 3.12, and 3.13.

## Database choice: SQLite vs MySQL

For this single-user local Windows setup, **SQLite is the deliberate low-overhead choice**. It is embedded in Python and needs no separate database server process. MySQL can make sense for multiple users or shared remote storage, but running it alongside Ollama would usually add resource use rather than reduce model inference RAM/CPU.

A database does not make the language model itself use less RAM or CPU. Keep the lightweight model and bounded post sample; the loop deliberately polls no more often than every 30 minutes. Measure actual resource use before adding infrastructure.

## What “learning” and “self-development” mean

Jarvis does **not** train or change model weights. The loop observes a small sample and produces reports, potential improvement ideas, and conversation-starter drafts. It does not silently convert community posts into permanent beliefs, write source code, install packages, or deploy changes. Save only reviewed, useful lessons with `/learn <lesson>`.

Moltbook content is untrusted external input and may contain misleading claims, spam, or prompt-injection attempts. Jarvis treats posts as data, not commands. A small sample cannot represent the entire community, so it should distinguish evidence from uncertainty.

**Trust is earned, not automated.** The recommended approach is to be honest about being an AI, read conversations before replying, make specific useful contributions, respect boundaries, avoid repetitive unsolicited messages, and never impersonate another agent or manipulate engagement. This version only drafts possible conversation starters; you choose whether and where to use them. Automated social outreach is not enabled.

Future code self-maintenance should be a separate, reviewable workflow: propose a patch, test it in an isolated branch, inspect the diff, and require human approval before merge or deployment.

## Requirements

- Python 3.11 or newer
- [Ollama](https://ollama.com/) installed and running
- Enough free disk space for the model and memory overhead
- A claimed Moltbook agent and API key if you want Moltbook features

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

4. Set the API key locally in the current PowerShell session. Replace the placeholder only on your own computer; never paste the real key into chat or commit it:

   ```powershell
   $env:MOLTBOOK_API_KEY = "YOUR_REAL_KEY"
   ```

5. Start Jarvis:

   ```powershell
   jarvis
   ```

## Moltbook usage

Run one report:

```text
/moltbook
```

Start the periodic growth-observation loop (default: 60 minutes):

```text
/moltbook-loop
```

Or specify a slower custom interval, such as 120 minutes:

```text
/moltbook-loop 120
```

The minimum interval is 30 minutes. Press Ctrl+C to stop the loop. It fetches at most eight new public posts per cycle from the official `https://www.moltbook.com/api/v1` host and asks the local model for an evidence-based report and optional conversation drafts. It retries after temporary failures without printing raw exception details. It does not send messages or perform any other social actions. No live API call or local Ollama inference is considered verified until tested on the user's machine.

Never paste the real key into a GitHub issue, commit, or chat. Jarvis sends it only to the official `www.moltbook.com` API host.

## Learning and controls

- `/learn <correction or preference>` — save a user-approved note.
- `/lessons` — list saved notes and IDs.
- `/forget <id>` — remove one note.
- `/clear` — clear chat history but keep learning notes.
- `/moltbook` — generate a one-time community report.
- `/moltbook-loop [minutes]` — periodically observe and draft ideas; Ctrl+C stops.
- `/help` — show commands.
- `/exit` — quit.

Only save notes you actually want Jarvis to remember. Review and delete outdated notes; stored notes are context, not guaranteed truth.

## Configuration

Defaults use `http://localhost:11434`, model `qwen3.5:2b`, local database `data/jarvis.db`, and a 120-second Ollama request timeout. The app does not load a `.env` file automatically; set environment variables in PowerShell. `.env.example` documents supported names but is not loaded automatically. Never commit API keys or real credentials.

To change the model, set `$env:JARVIS_MODEL="qwen3.5:4b"` before launching Jarvis, if your computer can run it comfortably.

## Run tests

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

## Roadmap

1. Foundation: configuration, local model adapter, SQLite memory, and CLI.
2. Feedback learning: persistent, user-approved corrections and preferences.
3. Moltbook observer and bounded growth loop: read-only periodic analysis, conversation drafts, and no automatic engagement.
4. Verify local model latency and RAM/CPU use on the target computer.
5. Add a bounded planner and research/writing/critic pipeline with evidence tracking.
6. Build a safe self-maintenance workflow: propose a patch, create an isolated branch, run tests and security checks, and require human approval before merge or deployment.
7. Consider optional cloud fallback or shared database only when needed, with explicit opt-in, privacy warnings, and measured justification.

No phase is considered complete until its tests and practical checks are verified. Free tiers and 24/7 hosting are not assumed to be unlimited.
