# Code Quality Review: `src/omnimash/state` Module

**Review Target:** [`src/omnimash/state`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state) (`session_manager.py`, `__init__.py`)  
**Associated Context:** [`src/omnimash/agent/orchestrator.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py), [`src/omnimash/storage/gcs.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py), [`tests/state/test_session_manager.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/state/test_session_manager.py)  
**Standard:** 5-Axes Code Review Framework (Correctness, Readability, Architecture, Security, Performance)

---

## Executive Summary

The `src/omnimash/state` module is the state engine of OmniMash, responsible for tracking non-linear conversational branching (Version Tree DAG), clip timelines, commit checkpoints, and persisting session manifests (`session_manifest.json`) to Google Cloud Storage.

While the core DAG branching and thread depth tracking concepts are conceptually solid and pass basic tests, the module exhibits several critical architectural, concurrency, and reliability issues:
1. **Asymmetric Storage Hydration:** `add_turn()` and `commit_turn()` bypass storage hydration and use raw dictionary lookups (`self._sessions[session_id]`), leading to unhandled `KeyError` crashes upon container restarts or cold starts.
2. **Blocking Network I/O Under Global Lock:** Cloud Storage HTTP calls (`get_session_manifest` and `save_session_manifest`) are executed synchronously inside `with self._lock:`, serializing all API requests across all users and threads during GCS network latency.
3. **Split-Brain State Management:** `CumulativeStateTracker` in `orchestrator.py` maintains an independent in-memory cache and directly reads/writes to `session_manifest.json`, competing with `SessionManager`'s own `session_manifest.json` persistence.
4. **Pydantic V2 Anti-Patterns:** Usage of `object.__setattr__` to inject undeclared private attributes, unvalidated `extra="allow"` with untyped dictionaries, and hardcoded fallback strings bypassing centralized settings.

---

## Severity-Labeled Findings Breakdown

### 1. Correctness

#### [CORR-01] Critical: Asymmetric Storage Hydration Causes Cold-Start `KeyError` Crashes in `add_turn` and `commit_turn`
- **Location:** [`src/omnimash/state/session_manager.py#L144`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L144), [`src/omnimash/state/session_manager.py#L252`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L252)
- **Problem:**
  `get_session()` properly attempts to hydrate from GCS via `self.storage.get_session_manifest()` when a session is not in memory. Similarly, `update_turn_video()` invokes `self.get_session(session_id)`.
  However, `add_turn()` and `commit_turn()` perform direct in-memory dictionary lookups:
  ```python
  def add_turn(self, session_id: str, ...):
      with self._lock:
          session = self._sessions[session_id]  # Crashes if cold-started!
  ```
  ```python
  def commit_turn(self, session_id: str, turn_id: str) -> TurnNode:
      with self._lock:
          session = self._sessions[session_id]  # Crashes if cold-started!
  ```
  If a Cloud Run container restarts, scales up, or handles a turn/commit request on a session that has been persisted to GCS but not yet cached in this process instance, `add_turn` and `commit_turn` immediately crash with an unhandled `KeyError: session_id`.
- **Proposed Remedy:**
  Replace raw `self._sessions[session_id]` with `session = self.get_session(session_id, project_id=project_id)`. If `session is None`, raise an explicit `KeyError(f"Session '{session_id}' not found in cache or persistent storage")`.

---

#### [CORR-02] Critical: Conflation of `clip_index` with `turn_index` Corrupts Turn Allocation Sequence
- **Location:** [`src/omnimash/state/session_manager.py#L223-L229`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L223-L229)
- **Problem:**
  `allocate_turn_index` calculates the next monotonic turn index using:
  ```python
  for t in session.turns.values():
      m = re.search(r"turn_(\d+)_video\.mp4", t.video_url or "")
      if m:
          max_idx = max(max_idx, int(m.group(1)))
      else:
          max_idx = max(max_idx, getattr(t, "clip_index", 0))
  ```
  `clip_index` is the horizontal position of a shot in the timeline sequence (e.g. shot 0, shot 1, shot 2), whereas turn allocation represents the chronological edit/render counter (turn 0, turn 1, turn 2...).
  If an artist renders clip index 5 on turn 1, `max_idx` artificially jumps to 5, skipping turn indices 2 through 5. Furthermore, if `video_url` points to a signed GCS URL or a different filename pattern, turn allocation fails to detect prior turns and can overwrite earlier video outputs.
- **Proposed Remedy:**
  Add an explicit typed `turn_index: int = 0` field to [`TurnNode`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L17) populated upon turn creation. Have `allocate_turn_index` compute `max(t.turn_index for t in session.turns.values()) + 1` directly from typed metadata, falling back to regex only for legacy manifests.

---

#### [CORR-03] Required: Silent Exception Swallowing (`except Exception: pass`) Masks Storage Failures
- **Location:** [`src/omnimash/state/session_manager.py#L99-L100`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L99-L100), [`src/omnimash/state/session_manager.py#L125-L126`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L125-L126), [`src/omnimash/state/session_manager.py#L208-L209`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L208-L209)
- **Problem:**
  `_persist_session`, `get_or_create_session`, and `get_session` catch all exceptions with `except Exception: pass`. If GCS write operations fail due to expired credentials, missing buckets, IAM misconfigurations, or network dropouts, the error is completely swallowed. The user assumes the session was saved, but on restart, data is lost without a single error trace in Cloud Logging.
- **Proposed Remedy:**
  Initialize structured logger `logger = logging.getLogger("omnimash.state")` and log detailed warnings/errors: `logger.warning("Failed to persist session manifest '%s': %s", session.session_id, exc, exc_info=True)`.

---

#### [CORR-04] Required: Disconnected Version DAG on Non-Existent `parent_turn_id`
- **Location:** [`src/omnimash/state/session_manager.py#L147-L150`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L147-L150)
- **Problem:**
  In `add_turn()`:
  ```python
  depth = 0
  if parent_turn_id and parent_turn_id in session.turns:
      parent = session.turns[parent_turn_id]
      if parent.interaction_thread_id == interaction_thread_id and not is_checkpoint:
          depth = parent.edit_depth_in_thread + 1
  ```
  If an API client or agent passes an invalid or stale `parent_turn_id` (e.g. from an aborted branch), the system silently assigns `parent_turn_id` to the node while resetting `depth = 0`. The node becomes an orphaned branch in the DAG that points to a non-existent parent.
- **Proposed Remedy:**
  Validate `parent_turn_id` against `session.turns`. If `parent_turn_id` is supplied but missing from `session.turns`, log a warning and either set `parent_turn_id = None` or raise a `ValueError`.

---

### 2. Performance

#### [PERF-01] Critical: Blocking Remote GCS Network I/O Inside Global Mutex Lock
- **Location:** [`src/omnimash/state/session_manager.py#L143-L179`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L143-L179), [`src/omnimash/state/session_manager.py#L241-L248`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L241-L248), [`src/omnimash/state/session_manager.py#L251-L257`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L251-L257)
- **Problem:**
  `SessionManager` uses a single instance-wide `threading.RLock()`. In `add_turn()`, `commit_turn()`, and `update_turn_video()`, `self._persist_session(session)` is called while holding `self._lock`.
  Inside `_persist_session()`, blocking network calls (`storage.get_session_manifest()` and `storage.save_session_manifest()`) execute synchronously.
  During high-concurrency requests or GCS network latency spikes (200ms–5s), every other thread attempting to access, create, or validate any session is blocked waiting for the global lock.
- **Proposed Remedy:**
  Separate in-memory state manipulation from remote network I/O:
  1. Under `self._lock`, perform the in-memory mutations and extract a snapshot of the manifest data via `session.model_dump(mode="json")`.
  2. Release the lock before performing `storage.save_session_manifest()`.
  3. Optionally introduce per-session locks (`dict[str, threading.Lock]`) for fine-grained concurrency.

---

#### [PERF-02] Required: Redundant Remote Read-Before-Write (`get_session_manifest`) on Every Persistence Call
- **Location:** [`src/omnimash/state/session_manager.py#L70-L93`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L70-L93)
- **Problem:**
  On every single turn generation, video URL update, or turn commit, `_persist_session()` performs:
  1. `existing = self.storage.get_session_manifest(...)` (Remote GCS GET)
  2. Iterates over 9 keys to backfill missing fields
  3. `self.storage.save_session_manifest(...)` (Remote GCS PUT)
  This doubles GCS latency on every mutation, adding 200–500ms of unnecessary network round-trips. Furthermore, because in-memory `session` already contains the authoritative state, re-fetching and backfilling from storage during an active session introduces race conditions where stale data can overwrite recent in-memory edits.
- **Proposed Remedy:**
  Remove the read-before-write logic from `_persist_session()`. Ensure hydration happens once at load time (`get_session` / `get_or_create_session`), and write the in-memory model directly to storage.

---

#### [PERF-03] Optional: Missing JSON Mode in `model_dump()` Serialization
- **Location:** [`src/omnimash/state/session_manager.py#L69`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L69)
- **Problem:**
  `manifest_data = session.model_dump()` uses default `mode='python'`, which preserves non-JSON types (such as `UUID`, `datetime`, or custom types) as Python objects. When passed to storage or serialization helpers, this can cause serialization overhead or `TypeError`.
- **Proposed Remedy:**
  Use `session.model_dump(mode="json")` to guarantee that all attributes are converted directly into JSON-safe primitives.
  *(Source: [Pydantic V2 Serialization Docs](https://docs.pydantic.dev/latest/concepts/serialization/#modelmodel_dump))*

---

### 3. Architecture

#### [ARCH-01] Critical: Split-Brain State Management Between `CumulativeStateTracker` and `SessionManager`
- **Location:** [`src/omnimash/agent/orchestrator.py#L46-L130`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L46-L130), [`src/omnimash/state/session_manager.py#L52`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L52)
- **Problem:**
  [`src/omnimash/agent/orchestrator.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py) defines a separate `CumulativeStateTracker` class with its own in-memory cache `_session_states: dict[str, CumulativeShotState]`.
  When `CumulativeStateTracker._persist_state()` runs, it loads `session_manifest.json` from GCS, writes `manifest["cumulative_state"] = ...`, and saves it back to GCS.
  Simultaneously, `ProjectSession` in `src/omnimash/state/session_manager.py` defines `cumulative_state: dict[str, Any]` and also writes `session_manifest.json`.
  These two independent state trackers run concurrently without shared synchronization, risking write-clobbering and state desynchronization.
- **Proposed Remedy:**
  Move `CumulativeStateTracker` into `src/omnimash/state/` (or integrate its tracking directly into `ProjectSession`), ensuring that `ProjectSession` is the single source of truth for both the Version Tree DAG and cumulative character/scene state.

---

#### [ARCH-02] Required: Duck-Typing on Storage Without Explicit Protocol
- **Location:** [`src/omnimash/state/session_manager.py#L61`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L61)
- **Problem:**
  `SessionManager.__init__` accepts `storage: Any | None = None` and repeatedly uses `hasattr(self.storage, "save_session_manifest")`.
  This untyped duck-typing prevents static type checking with `ty check` and lacks a clear contract for alternative storage backends (e.g. Memory, Firestore, GCS, Local Disk).
- **Proposed Remedy:**
  Define a `typing.Protocol` in `src/omnimash/state/session_manager.py`:
  ```python
  from typing import Protocol, runtime_checkable

  @runtime_checkable
  class SessionStorageProtocol(Protocol):
      def save_session_manifest(
          self, session_id: str, manifest_data: dict[str, Any], project_id: str | None = None
      ) -> str: ...

      def get_session_manifest(
          self, session_id: str, project_id: str | None = None
      ) -> dict[str, Any] | None: ...
  ```

---

#### [ARCH-03] Required: Hardcoded Model Strings Bypassing Central Configuration
- **Location:** [`src/omnimash/state/session_manager.py#L8-L14`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L8-L14), [`src/omnimash/state/session_manager.py#L47`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L47)
- **Problem:**
  `_normalize_image_model()` and `ProjectSession.image_model` default to `"gemini-nano-banana-2.1"` hardcoded as literal strings, ignoring `settings.image_model_id` from [`src/omnimash/config.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/config.py). If environment variables configure a different model, `session_manager.py` remains pinned to the hardcoded default.
- **Proposed Remedy:**
  Import `settings` from `omnimash.config` and use `getattr(settings, "image_model_id", "gemini-nano-banana-2.1")` as the canonical default.

---

#### [ARCH-04] Optional: Permissive `extra="allow"` with Untyped Collections in `ProjectSession`
- **Location:** [`src/omnimash/state/session_manager.py#L37-L52`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L37-L52)
- **Problem:**
  `model_config = ConfigDict(extra="allow")` allows arbitrary unknown keys into `ProjectSession`. Furthermore, `characters`, `products`, `shot_cards`, and `cumulative_state` are untyped lists of `dict[str, Any]`, bypassing Pydantic V2 schema validation and editor autocomplete.
- **Proposed Remedy:**
  Progressively type these fields or provide typed wrappers, ensuring structured validation when deserializing manifests.

---

### 4. Security

#### [SEC-01] Required: Inadequate Sanitization of Default Session Keys (`user_id:project_id`)
- **Location:** [`src/omnimash/state/session_manager.py#L106-L109`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L106-L109)
- **Problem:**
  ```python
  if session_name and session_name.strip():
      session_key = re.sub(r"[^a-zA-Z0-9_-]", "_", session_name.strip())
  else:
      session_key = f"{user_id}:{project_id}"
  ```
  When `session_name` is provided, it is sanitized against `[^a-zA-Z0-9_-]`. However, when `session_name` is omitted, `user_id` and `project_id` are concatenated with a colon (`:`).
  If `user_id` or `project_id` contain path traversal sequences (`../`, `/`), slashes, or special characters, they can lead to invalid GCS blob keys or directory traversal vulnerabilities when constructing storage paths (`sessions/{session_id}/prompts/`).
- **Proposed Remedy:**
  Apply strict regex sanitization to both components when constructing the default key:
  ```python
  clean_user = re.sub(r"[^a-zA-Z0-9_-]", "_", (user_id or "default").strip())
  clean_project = re.sub(r"[^a-zA-Z0-9_-]", "_", (project_id or "default").strip())
  session_key = f"{clean_user}_{clean_project}"
  ```

---

#### [SEC-02] Required: Unbounded In-Memory Collections (Denial of Service Vector)
- **Location:** [`src/omnimash/state/session_manager.py#L42-L43`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L42-L43), [`src/omnimash/state/session_manager.py#L62`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L62)
- **Problem:**
  `self._sessions: dict[str, ProjectSession]`, `session.turns: dict[str, TurnNode]`, and `session.timeline: list[ClipSegment]` have no upper limits or eviction policy (LRU / TTL). An automated loop or malicious actor repeatedly generating turns or sessions can cause unbounded memory growth and trigger container OOM crashes.
- **Proposed Remedy:**
  Enforce a sensible maximum turn limit per session (e.g. `MAX_TURNS_PER_SESSION = 500`) and cap in-memory session cache size with LRU eviction or an explicit cleanup method.

---

### 5. Readability & Simplicity

#### [READ-01] Required: Pydantic V2 Private Attribute Anti-Pattern (`object.__setattr__`)
- **Location:** [`src/omnimash/state/session_manager.py#L222`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L222), [`src/omnimash/state/session_manager.py#L230`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L230)
- **Problem:**
  `allocate_turn_index` writes to an undeclared attribute using `object.__setattr__(session, "_last_allocated_turn_index", next_idx)`.
  In Pydantic V2, undeclared private attributes trigger introspection overhead, confuse developers reading the model definition, and fail type checking.
- **Proposed Remedy:**
  Declare `_last_allocated_turn_index: int = PrivateAttr(default=-1)` directly on `ProjectSession`. Then update it cleanly with `session._last_allocated_turn_index = next_idx`.
  *(Source: [Pydantic V2 Private Model Attributes](https://docs.pydantic.dev/latest/concepts/models/#private-model-attributes))*

---

#### [READ-02] Optional: Repeated Regex Sanitization Across Functions
- **Location:** [`src/omnimash/state/session_manager.py#L107`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L107), [`src/omnimash/state/session_manager.py#L189`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L189)
- **Problem:**
  The regex `re.sub(r"[^a-zA-Z0-9_-]", "_", ...)` is duplicated across `get_or_create_session` and `get_session`.
- **Proposed Remedy:**
  Extract a single reusable helper function:
  ```python
  def sanitize_session_id(name: str) -> str:
      """Sanitizes session identifiers to be safe for GCS paths and file systems."""
      return re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip()) if name else "default"
  ```

---

#### [READ-03] Nit: Hardcoded Field List in `_persist_session`
- **Location:** [`src/omnimash/state/session_manager.py#L75-L85`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L75-L85)
- **Problem:**
  The 9-element tuple of keys to check is hardcoded inside the function body.
- **Proposed Remedy:**
  Define at module level or remove as part of eliminating redundant read-before-write (PERF-02).

---

## Action Plan & Structural Remedies

| Refactoring Step | Target Issues | Description |
| :--- | :--- | :--- |
| **PR 1: Correctness & Concurrency** | `CORR-01`, `PERF-01`, `PERF-02`, `CORR-03` | Fix asymmetric storage hydration in `add_turn` and `commit_turn`; release mutex lock before GCS I/O; eliminate redundant remote read-before-write; add structured logging. |
| **PR 2: Typing, Turn Indexing & Pydantic V2** | `CORR-02`, `READ-01`, `ARCH-02`, `ARCH-03`, `PERF-03` | Add typed `turn_index: int = 0` to `TurnNode`; declare `PrivateAttr` on `ProjectSession`; define `SessionStorageProtocol`; bind default image model to `settings.image_model_id`; use `model_dump(mode="json")`. |
| **PR 3: Security & Architecture Consolidation** | `SEC-01`, `SEC-02`, `ARCH-01`, `READ-02` | Sanitize all session keys; enforce turn/session caps; unify cumulative state tracking under `src/omnimash/state`; extract `sanitize_session_id` helper. |

---

## Verification Strategy
- **Unit Tests:** Run `uv run pytest tests/state/ -v` to ensure all existing and new turn/session/hydration tests pass.
- **Integration Tests:** Run `uv run pytest tests/api/test_architecture_remediation.py -v` and `tests/agent/test_orchestrator.py -v` to verify cold-start reloads, turn index allocation, and timeline stitching.
- **Static Analysis:**
  - `uv run ruff check .`
  - `uv run ty check`
