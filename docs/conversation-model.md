# Conversation model and isolation boundary

## Verified current model

Jarvis is currently a **single-owner, single persistent conversation** application, not a multi-user or multi-session chat service.

Evidence in the current code:

- The README describes Jarvis as a personal assistant and explicitly selects SQLite for a single-user local Windows setup.
- The installed CLI entry point is `jarvis = "jarvis.cli:main"`; `main()` creates one `MemoryStore` and one `JarvisAgent` for its interactive terminal loop.
- The CLI has no conversation-selection command, login/authentication flow, profile selection, or session identifier.
- `MemoryStore` stores messages in one SQLite `messages` table. `add_message()` and `recent_messages()` have no conversation parameter, so all instances pointed at the same database use the same timeline.
- The default database path is `data/jarvis.db`, and the same configured database is reused between application runs. This makes history intentionally persistent across restarts.

These facts establish the current single-owner application design. They do **not** establish that concurrent Jarvis processes are isolated: two processes pointed at the same database share history. That is consistent with the current one-conversation design, but it is not safe isolation for independent users or conversations.

## Decision for JARVIS-SEC-04

No session schema or migration is introduced. Adding a session framework now would invent a product capability that the current entry points do not expose. Existing rows remain untouched, ordered by their current autoincrementing message IDs, and readable through the existing single-conversation API.

The JARVIS-SEC-03 controls remain required: writes accept only non-empty `user` and `assistant` messages; reads filter invalid/privileged roles before applying the history limit; and outgoing LLM history is validated again by the agent.

## Boundary and limitations

- This design is for one owner using one continuous local conversation.
- It does not provide tenant isolation, per-window/per-process isolation, or authorization between users.
- A shared SQLite file is not a safe boundary between independent conversations. Do not expose this database-backed agent as a multi-user service or run separate user contexts against the same database and assume their histories are isolated.
- Learning notes, Project Guardian history, and Project Mesh are also persistent context sources with their own scopes. This document does not claim that the message-history model isolates those sources.

## Minimum change required before multi-session or multi-user support

Before adding independent conversations, define the supported identity/session model and trusted source of active context. Then add a stable conversation key to message storage, require that context on every message write/read/clear operation, scope queries and history limits by that key, and ensure callers cannot select another user's conversation by supplying an arbitrary identifier. A future migration must preserve existing rows and their order without silently assigning legacy messages to an arbitrary user. The legacy history should remain explicitly designated as unscoped/single-owner history until the owner chooses a documented migration policy.

Add integration tests for separate contexts, missing/invalid context rejection, scoped ordering/limits, legacy-row policy, and the existing role-validation boundary before advertising multi-session support.
