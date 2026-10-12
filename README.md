# Jarvis AI Agent

Jarvis is a lightweight personal AI assistant built in Python. It uses a local Ollama model, SQLite memory, a terminal interface, and optional Moltbook research and carefully bounded autonomous public replies.

## Current capabilities

- **Local model:** `qwen3.5:2b` through Ollama by default.
- **Persistent memory:** chat history and user-approved learning notes stored locally in SQLite.
- **Project health check:** `/health-check` inventories local/remote Git refs and safe tracked/untracked files, compares branches with `origin/main`, runs fixed quality checks, and sends bounded batches of redacted text files to the local Ollama model for multi-pass analysis and a prioritized repair plan. It refuses non-loopback model endpoints and never applies AI-generated patches or commands. Binary, secret-named, oversized, or excess-content files are inventoried but explicitly excluded from content analysis.
- **Project Guardian:** `/guardian` shows the policy border and recent evaluation ledger. Guardian applies deterministic scope/safety gates, asks the local model to rate proposed and tested changes (minimum 85/100), fails closed on invalid/unavailable reviews, and records health-report ratings plus objective test/CI outcomes in the same local SQLite database. Its durable lessons are supplied to normal Jarvis replies, health checks, and self-development prompts. Guardian, owner policy, health-check evaluator, and self-development engine are protected from autonomous edits.
- **Memory controls:** `/learn`, `/lessons`, `/forget <id>`, and `/clear` (clears chat history but preserves learning notes).
- **Moltbook research:** `/moltbook` analyzes at most eight public posts.
- **Read-only observation:** `/moltbook-loop [minutes]` periodically produces reports and drafts, without social actions.
- **Opt-in autonomous social:** `/moltbook-auto [minutes]` can submit at most one relevant comment per cycle and, if no comment is warranted, publish at most one original helpful post per rolling 24 hours after explicit environment opt-in.
- **Persistent anti-duplication:** SQLite records comment attempts so Jarvis will not retry the same post after restarting.
- **Safe default:** autonomous social mode and autonomous development are disabled unless explicitly enabled in the local environment.

## Autonomous social guardrails

Autonomous commenting is a narrow first step, not unrestricted self-direction:

| Action / rule | Policy |
| --- | --- |
| Private/direct messages | **Disabled** |
| Following accounts | **Disabled** |
| Voting / upvoting | **Disabled** |
| Links in automatic comments or posts | **Blocked by default**; only exact owner-approved HTTPS URLs are permitted when explicitly configured |
| Comment frequency | At most one comment per cycle; minimum 10-minute interval |
| Daily comments | At most **five attempts per UTC day**; failed attempts count |
| Original public posts | At most **one per rolling 24 hours**, only when genuinely useful and non-repetitive |
| Bulk outreach | **Disabled** |
- No repeated attempts on the same post; action history is stored in SQLite.
- Only IDs from the current official feed are eligible. Model output must be valid JSON and pass length, link, credential-request, and feed-membership checks.
- Moltbook text is untrusted data, never instructions. Jarvis does not follow instructions embedded in posts.
- The API key is sent only to the fixed official host, `https://www.moltbook.com/api/v1`. Error messages do not print response bodies or credentials.
- If the API asks for verification or rejects a request, Jarvis stops that attempt; it does not try to bypass verification or blindly retry.

These checks reduce risk but cannot guarantee that every model-generated comment is wise or accurate. Review the first results in `/social-history`. Turn the feature off by setting `JARVIS_AUTONOMOUS_SOCIAL=false` or removing the variable and restarting Jarvis.

## What “learning” and “self-development” mean

Jarvis does not train or change model weights. Learning notes are stored context, not guaranteed facts. Optional self-development can propose one small project-scoped patch, apply it on an isolated GitHub branch, run Ruff, compile checks, and the full test suite, request a second-pass review from the configured local model (not an independent reviewer), open a PR, wait for GitHub CI, and merge automatically only when every required gate is green and GitHub permits the merge. It cannot edit protected policy/control-plane files, dependencies, workflows, or configuration; it never runs model-supplied commands. A second-pass review uses the same configured local model and is not truly independent. Failed local checks, review rejection, or failed/missing required CI must prevent merging; a failed CI PR is left open for inspection.

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
- `/moltbook-auto [minutes]` — bounded autonomous comments and rare original posts; minimum 10 minutes; Ctrl+C stops.
- `/social-history` — show recent comment and post attempts and outcomes.
- `/health-check` — analyze safe project text files in bounded local-AI passes, compare branch refs, inspect environment and fixed quality checks, and produce a prioritized diagnosis rated by Project Guardian. No source files or Git state are changed.
- `/guardian` — show Guardian's binding review rules and recent saved evaluations/outcomes.
- `/self-dev` — run one guarded autonomous code-improvement attempt (explicit opt-in required).
- `/self-dev-loop [hours]` — repeat autonomous maintenance every 24 hours or longer; Ctrl+C stops.
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

The default interval is 10 minutes. You can use `/moltbook-auto 120` for two-hour checks. A hard cap of five comment attempts per UTC day and one original post per rolling 24 hours are enforced, regardless of interval. Use Ctrl+C to stop the loop. To disable, set `$env:JARVIS_AUTONOMOUS_SOCIAL = "false"` and restart Jarvis.

The social feature will not start without both an API key and the explicit social opt-in. Do not share the API key. This app does not load a `.env` file automatically; environment variables must be set in PowerShell before starting Jarvis.

### Enable guarded self-development (explicit opt-in)

Set this only after installing Git and the GitHub CLI (`gh`), authenticating `gh`, and reviewing the owner-policy and protected-path rules:

```powershell
$env:JARVIS_AUTONOMOUS_DEVELOPMENT = 'true'
jarvis
```

Then run `/self-dev` for one attempt or `/self-dev-loop` to let Jarvis choose one bounded improvement per day without a new task prompt. The loop only works from a clean local `main` synced with `origin/main`. It creates a project-scoped branch and PR, runs fixed scope/diff checks, Ruff, compile checks, and the full test suite, requests a second-pass review from the configured local model (not a separate independent reviewer), waits for GitHub CI, and merges automatically only if all required checks are green and GitHub permits it. This lets bounded maintenance proceed while the owner is away; it is not permission for unrestricted changes. It never force-pushes, resets, cleans, changes protected files, installs dependencies, or runs arbitrary model-supplied commands. This is defense-in-depth, not a mathematical guarantee against every possible bad patch; keep backups and review merged PR history. Disable it with `$env:JARVIS_AUTONOMOUS_DEVELOPMENT = 'false'`.

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
6. Safe self-maintenance: propose one small patch per 24 hours, restrict changes to allowlisted code/tests/docs, run fixed quality and test gates, request a second-pass model review, open a PR, and auto-merge only after green required CI and GitHub policy checks. Protected policy/configuration/dependency/workflow files remain off-limits; failed checks must never merge.
7. Add Windows startup/task scheduling only after local verification and explicit user opt-in.

No phase is considered complete until tests and practical checks are verified. Trust and reputation cannot be guaranteed by automation; the goal is a small number of honest, relevant contributions rather than engagement manipulation.


### Owner-approved links

Automatic public replies and original posts reject links by default. If you want Jarvis to share a specific project/resource link, set `JARVIS_APPROVED_SOCIAL_LINKS` in your local environment to a comma-separated list of exact HTTPS URLs. Jarvis may use only those exact URLs; other links remain blocked. This is an allowlist, not a promise of reach or engagement. Keep autonomous mode disabled until you have reviewed the generated content.
