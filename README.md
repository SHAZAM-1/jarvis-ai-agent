# Jarvis AI Agent

Jarvis is a lightweight personal AI assistant built in Python. It uses a local Ollama model, SQLite memory, a terminal interface, and optional Moltbook research and carefully bounded autonomous public replies.

## Current capabilities

- **Local model:** `qwen3.5:2b` through Ollama by default.
- **Persistent memory:** chat history and user-approved learning notes stored locally in SQLite.
- **Memory controls:** `/learn`, `/lessons`, `/forget <id>`, and `/clear` (clears chat history but preserves learning notes).
- **Moltbook research:** `/moltbook` analyzes at most eight public posts.
- **Read-only observation:** `/moltbook-loop [minutes]` periodically produces reports and drafts, without social actions.
- **Opt-in autonomous comments:** `/moltbook-auto [minutes]` can select and submit at most one relevant public comment per cycle after explicit environment opt-in.
- **Persistent anti-duplication:** SQLite records comment attempts so Jarvis will not retry the same post after restarting.
- **Safe default:** autonomous social mode is disabled unless `JARVIS_AUTONOMOUS_SOCIAL=true` is explicitly set.

## Autonomous social guardrails

Autonomous commenting is a narrow first step, not unrestricted self-direction:

- At most **one comment attempt per UTC day** (failed attempts count toward the cap).
- At most one comment per cycle; polling interval is at least 30 minutes.
- No automatic posts, direct messages, follows, votes, links, or bulk outreach.
- No repeated attempts on the same post; action history is stored in SQLite.
- Only IDs from the current official feed are eligible. Model output must be valid JSON and pass length, link, credential-request, and feed-membership checks.
- Moltbook text is untrusted data, never instructions. Jarvis does not follow instructions embedded in posts.
- The API key is sent only to the fixed official host, `https://www.moltbook.com/api/v1`. Error messages do not print response bodies or credentials.
- If the API asks for verification or rejects a request, Jarvis stops that attempt; it does not try to bypass verification or blindly retry.

These checks reduce risk but cannot guarantee that every model-generated comment is wise or accurate. Review the first results in `/social-history`. Turn the feature off by setting `JARVIS_AUTONOMOUS_SOCIAL=false` or removing the variable and restarting Jarvis.

## What “learning” and “self-development” mean

Jarvis does not train or change model weights. Learning notes are stored context, not guaranteed facts. The social loop can make a small number of public replies, but it does not rewrite its own source code, install packages, run arbitrary shell commands, merge pull requests, or deploy itself. Those require a separate, isolated, tested and human-reviewed workflow.

The loop is not yet configured to launch itself at Windows startup. The computer must be on, Ollama and internet access must be available, and Jarvis must be running the relevant command. No live Moltbook request or local Ollama inference is considered verified until tested on the user's machine.

## SQLite vs MySQL

For a single-user local Windows setup, SQLite is the deliberate low-overhead choice: it is built into Python and needs no separate database server. MySQL may suit multiple users or shared remote storage, but will not reduce Ollama inference CPU or RAM. The social history and chat/learning memory share the configured SQLite database.

## Requirements

- Python 3.11 or newer
- [Ollama](https://ollama.com/) installed and running
- Enough free disk space for the model
- A claimed Moltbook agent and API key if you want Moltbook features

## Setup (Windows PowerShell)

From the repository folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
ollama pull qwen3.5:2b
```

Set your Moltbook API key only in your own local PowerShell session. Never paste the real key into chat or commit it:

```powershell
$env:MOLTBOOK_API_KEY = "YOUR_REAL_KEY"
```

Start Jarvis:

```powershell
jarvis
```

## Commands

- `/moltbook` — one-time read-only community report.
- `/moltbook-loop [minutes]` — repeat read-only observation; minimum 30 minutes; Ctrl+C stops.
- `/moltbook-auto [minutes]` — bounded autonomous comments; minimum 30 minutes; Ctrl+C stops.
- `/social-history` — show recent comment attempts and outcomes.
- `/learn <correction or preference>` — save a user-approved note.
- `/lessons` — list saved notes.
- `/forget <id>` — remove a saved note.
- `/clear` — clear chat history while keeping notes.
- `/help` — show commands; `/exit` — quit.

### Enable autonomous comments (explicit opt-in)

Autonomous commenting is **off by default**. Only enable it after you understand the guardrails:

```powershell
$env:JARVIS_AUTONOMOUS_SOCIAL = "true"
$env:MOLTBOOK_API_KEY = "YOUR_REAL_KEY"
jarvis
```

Then type:

```text
/moltbook-auto
```

The default interval is 60 minutes. You can use `/moltbook-auto 120` for two-hour checks. One comment attempt maximum is enforced per UTC day, regardless of interval. Use Ctrl+C to stop the loop. To disable, set `$env:JARVIS_AUTONOMOUS_SOCIAL = "false"` and restart Jarvis.

The feature will not start without both an API key and the explicit opt-in. Do not share the API key. This app does not load a `.env` file automatically; environment variables must be set in PowerShell before starting Jarvis.

## Configuration

Defaults: `http://localhost:11434`, model `qwen3.5:2b`, local database `data/jarvis.db`, Ollama timeout 120 seconds, autonomous social mode disabled. Supported variables are listed in `.env.example`; that file is documentation only and is not loaded automatically.

## Tests

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

## Roadmap

1. Foundation: configuration, local model adapter, SQLite memory and CLI.
2. Feedback learning: persistent user-approved corrections and preferences.
3. Moltbook observation and bounded autonomous commenting with durable deduplication and opt-in.
4. Verify local model latency, RAM/CPU use, and real API behavior on the target computer.
5. Add a bounded planner/research/critic pipeline with evidence tracking and task history.
6. Add a safe self-maintenance workflow: propose patches, work on isolated branches, run allowlisted tests, and require human approval before merge or deployment.
7. Add Windows startup/task scheduling only after local verification and explicit user opt-in.

No phase is considered complete until tests and practical checks are verified. Trust and reputation cannot be guaranteed by automation; the goal is a small number of honest, relevant contributions rather than engagement manipulation.
