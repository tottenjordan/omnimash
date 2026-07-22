# Session Store: Concurrency & Single-Process Limitation

`SessionManager` (`src/omnimash/state/session_manager.py`) is the in-memory
store for project sessions, their turn version-trees, and clip timelines.

## What was hardened
- **Thread safety:** all mutations (`get_or_create_session`, `add_turn`,
  `commit_turn`) run under a single `threading.Lock`. This removes the previous
  check-then-mutate races when FastAPI's threadpool runs multiple sync handlers
  concurrently.
- **Bounded memory (LRU):** sessions live in an `OrderedDict`. Reads/writes mark
  a session most-recently-used; once the count exceeds `settings.max_sessions`
  (default **512**, env `MAX_SESSIONS`; `0` disables eviction) the
  least-recently-used session is dropped.
- **Domain error:** missing sessions/turns raise `SessionNotFound` (a
  `KeyError` subclass) instead of a bare `KeyError`.
- **Encapsulated lookup:** `find_session(session_id)` performs the
  raw-key → sanitized-key → stored-`session_id` fallback. Callers
  (e.g. `OmniMashAgent._get_session`) use it instead of reaching into the
  private `_sessions` dict.

## The limitation to remember
**This store is single-process only.** State lives in one process's memory and
is **not** shared across `uvicorn`/`gunicorn` workers or replicas:

- Running more than one worker means a follow-up turn can be routed to a process
  that never saw the session → the turn appears "lost" or starts a fresh tree.
- LRU eviction is per-process; capacity is effectively `max_sessions × workers`,
  unevenly distributed.
- All state is lost on restart/redeploy.

**Deploy with a single worker** for correct behavior today. A durable,
cross-process store (Redis / Firestore / a DB) is the real fix and is out of
scope for the current remediation (user chose the minimal lock + eviction fix,
no new infra).
