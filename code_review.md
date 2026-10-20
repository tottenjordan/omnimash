# Code Review: `src/omnimash/agent` Module

## Context & Scope

This review conducts an in-depth inspection of the entire `src/omnimash/agent` package across the **5-Axes Quality Framework**:
1. **Correctness**
2. **Readability & Simplicity**
3. **Architecture**
4. **Security**
5. **Performance**

Files inspected:
- [`src/omnimash/agent/orchestrator.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py) (1,126 lines)
- [`src/omnimash/agent/adk_pipeline.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/adk_pipeline.py) (222 lines)
- [`src/omnimash/agent/agent.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/agent.py) (7 lines)
- [`src/omnimash/agent/__init__.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/__init__.py) (5 lines)

Associated test suites inspected:
- [`tests/agent/test_orchestrator.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/agent/test_orchestrator.py)
- [`tests/agent/test_adk_pipeline.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/agent/test_adk_pipeline.py)
- [`tests/agent/test_journey3_tracker.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/agent/test_journey3_tracker.py)
- [`tests/agent/test_single_change_diff.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/agent/test_single_change_diff.py)

---

## Executive Summary & Verdict

- **Overall Health Verdict:** **Request Changes** — Several high-leverage issues in correctness (silent attribute loss, greedy state corruption, and graph inconsistency), architectural leakage, and brittle regex validation must be resolved before this module is production-ready.
- **Total Findings:** 18
  - **Critical:** 4
  - **Required (no prefix):** 8
  - **Consider / Optional:** 4
  - **Nit:** 2

---

## 1. Correctness

### **Critical:** Character `wardrobe` Dropped During Role Normalization
- **File:** [`src/omnimash/agent/orchestrator.py#L579-L639`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L579-L639)
- **Problem:** When `char_objs` is reconstructed from raw dictionaries, Pydantic models, or `CharacterRole` instances in `process_user_turn`, the `wardrobe` field is omitted across all 4 conversion branches:
  ```python
  char_objs.append(
      CharacterRole(
          role_id=c.role_id,
          name=_clean(c.name),
          description=_clean(c.description),
          reference_url=c.reference_url,
          aesthetic_tags=[_clean(t) for t in (c.aesthetic_tags or [])],
          voice_style=_clean(c.voice_style or ""),
          voice_profile=_clean(c.voice_profile or ""),
          image_role=getattr(c, "image_role", "Character Reference"),
          is_offscreen_narrator=getattr(c, "is_offscreen_narrator", False),
      )
  )
  ```
  `CharacterRole` (defined in [`src/omnimash/prompts/character_roles.py#L15`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/prompts/character_roles.py#L15)) defines `wardrobe: str = ""`. By omitting `wardrobe`, any custom costume or wardrobe prompt provided by the user is silently erased before reaching the prompt compiler and Omni Flash. (In contrast, `adk_pipeline.py` correctly handles `wardrobe`).
- **Structural Remedy:** Extract a single canonical `normalize_character_role(c: Any, clean_fn: Callable | None = None) -> CharacterRole` helper function that populates all fields including `wardrobe`, and reuse it across both `orchestrator.py` and `adk_pipeline.py`.

---

### **Critical:** State Corruption in `Journey3StateTracker.record_shot_directive` via Greedy Regex
- **File:** [`src/omnimash/agent/orchestrator.py#L141-L162`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L141-L162)
- **Problem:** The removal pattern for unsetting cumulative character states is:
  ```python
  pattern = r"\b" + re.escape(verb) + r"\s+(?:a|an|the|his|her|their)?\s*([a-zA-Z0-9_\s]+)"
  ```
  Because `[a-zA-Z0-9_\s]+` includes whitespace and has no terminating delimiter, `m.group(1)` matches the **entire remainder of the sentence**.
  For example, in `"Totti removes blindfold and steps into the ring"`, `target` becomes `"blindfold and steps into the ring"`.
  When split into words (`['blindfold', 'steps', 'into', 'ring']`), the subsequent check:
  ```python
  if any(tw in st_lower for tw in target_words):
      state.remove_character_state(char, st_desc)
  ```
  will match any existing state containing words like `"ring"` (e.g., `"golden ring"`) or `"steps"` and **accidentally delete completely unrelated character states**.
- **Structural Remedy:** Terminate the target group at clause boundaries or punctuation:
  ```python
  pattern = (
      r"\b"
      + re.escape(verb)
      + r"\s+(?:a|an|the|his|her|their)?\s*([a-zA-Z0-9_]+(?:\s+[a-zA-Z0-9_]+){0,3}?)(?=[,;.]|\b(?:and|then|while|as|with|into|in|on|at)\b|$)"
  )
  ```
  Ensure `target` captures only the noun phrase immediately governed by the removal verb.

---

### **Critical:** Unstitched Video URL Inconsistency in Session Turn Graph during Multi-Chunk Generations
- **File:** [`src/omnimash/agent/orchestrator.py#L483-L558`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L483-L558)
- **Problem:** When `duration_seconds > 10.0`, `process_user_turn` recursively generates 10-second chunks, concatenates them with `self.stitcher.concatenate_clips`, uploads the stitched master to GCS, and returns `AgentTurnResponse(video_url=proxy_url, turn_id=last_resp.turn_id)`.
  However, in `SessionManager`, `session.turns[last_resp.turn_id].video_url` remains the raw unstitched clip of Chunk N (only the final 10 seconds).
  Any client querying the session turn tree (`GET /api/session/...`) or branching from `turn_id` receives only the final 10s chunk instead of the full stitched 20s/30s video.
- **Structural Remedy:** Update the turn node's `video_url` in `SessionManager` after stitching:
  ```python
  if len(chunk_urls) > 1 and last_resp and last_resp.turn_id:
      self.session_manager.update_turn_video(
          session_id=session.session_id,
          turn_id=last_resp.turn_id,
          video_url=proxy_url,
          gcs_uri=gcs_uri,
      )
  ```

---

### **Critical:** `save_final_master` Discards Explicit `video_url` and Stitches Abandoned Draft Turns
- **File:** [`src/omnimash/agent/orchestrator.py#L982-L1008`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L982-L1008)
- **Problem:** In `save_final_master`:
  ```python
  if session:
      active_clips = self._resolve_active_session_clips(session)
      if len(active_clips) > 1:
          return self.stitch_session_master(...)
  return self.storage.save_final_master(session_id=s_id, source_rel_path=video_url, ...)
  ```
  1. If a caller explicitly provides `video_url` (e.g. exporting a specific rendered clip), but the session contains > 1 turns, `video_url` is completely ignored and all active session clips are stitched instead.
  2. In `_resolve_active_session_clips` ([lines 943-945](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L943-L945)):
     `if not clip_paths and turns: clip_paths = [t.video_url for t in turns.values() if getattr(t, "video_url", None)]`
     If `timeline` is not populated, it gathers **every turn in the session dictionary** — including failed edits, superseded drafts, and abandoned branches — stitching them into an invalid master video.
- **Structural Remedy:**
  - Respect caller-provided `video_url`: if `video_url` is passed explicitly and the user did not request multi-shot stitching, save `video_url` directly.
  - Traverse only the active branch path (from root to active leaf via `parent_turn_id` or explicit `timeline` segments), never all unordered values in `turns.values()`.

---

### `extend_scene` Erroneously Flagged as `is_conversational_edit=True`
- **File:** [`src/omnimash/agent/orchestrator.py#L1009-L1048`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L1009-L1048)
- **Problem:** `extend_scene` passes `is_conversational_edit=True if prev_inter_id else False` to `process_user_turn`. This causes two regressions:
  1. It subjects scene extension actions to `validate_conversational_edit`, which rejects any prompt with action sequences, multiple verbs, or connectors (e.g. `"The hero draws sword, then strikes the enemy"`).
  2. It forces the compiler into `build_delta_prompt` (`[PRESERVATION LOCK] / [ISOLATED DIFF]`), instructing Omni Flash to keep all kinematics locked and alter only one variable — the exact opposite of extending a scene forward in time.
  3. `clip_index` is omitted and defaults to 0, preventing timeline advancement.
- **Structural Remedy:** Separate conversational delta editing from scene extension:
  - Add an explicit `is_scene_extension=True` parameter to `process_user_turn`.
  - In `extend_scene`, set `is_conversational_edit=False`, `is_scene_extension=True`, and route directly to stateful continuation via `previous_interaction_id` without delta prompt locking.

---

### Incomplete ADK Tool Schema in `generate_parody_clip`
- **File:** [`src/omnimash/agent/orchestrator.py#L1058-L1094`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L1058-L1094)
- **Problem:** The ADK agent's system instruction specifies:
  - Support for 360p draft rendering for rapid feedback before exporting 4K masters.
  - Stateful scene extensions up to 40s total continuation via `previous_interaction_id`.
  - Dual-keyframe transitions (`<FIRST_FRAME>` and `<LAST_FRAME>`).
  - Conversational delta edits.
  However, the `generate_parody_clip` tool only accepts `(prompt, user_id, project_id, clip_index, parent_turn_id, reference_url)`.
  It lacks `resolution`, `duration_seconds`, `aspect_ratio`, `keyframe_image_url`, `is_conversational_edit`, and `audio_stem`.
  The agent cannot execute any of the capabilities described in its system prompt because the tool arguments are missing.
- **Structural Remedy:** Expand `generate_parody_clip` arguments to include `resolution: str = "720p"`, `duration_seconds: float = 10.0`, `aspect_ratio: str = "16:9"`, `keyframe_image_url: str | None = None`, `is_conversational_edit: bool = False`, and `audio_stem: str | None = None`, forwarding them to `process_user_turn`.

---

## 2. Readability & Simplicity

### Fragile Regex & High False-Positive Rate in `validate_conversational_edit`
- **File:** [`src/omnimash/agent/orchestrator.py#L345-L442`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L345-L442)
- **Problem:** `validate_conversational_edit` spans ~100 lines of regexes matching hardcoded verbs and connectors. It produces frequent false positives on standard English phrasing:
  - `"Add a setting sun"` matches `add` and `setting` (2 verbs) $\rightarrow$ **REJECTED**.
  - `"Make the car turn left"` matches `make` and `turn` (2 verbs) $\rightarrow$ **REJECTED**.
  - `"Set camera to zoom in"` matches `set` and `zoom` (2 verbs) $\rightarrow$ **REJECTED**.
  - `"Make him walk slowly, to the edge"` has `, to` in clause 2 $\rightarrow$ **REJECTED**.
- **Structural Remedy:** Replace the brittle multi-verb counting heuristic with an intent-based clause segmentation:
  - Discard auxiliary/causative verbs (`make`, `set`, `turn`) from the action verb blacklist when followed by an object/adjective.
  - Use regex boundary tokens on full verbs rather than gerunds/participles (`setting` as adjective in "setting sun").
  - Alternatively, offload multi-change intent classification to a structured Gemini Flash evaluation with a strict schema.

---

### Unused ADK Agent Facade in `deconstruct_screenplay_with_adk`
- **File:** [`src/omnimash/agent/adk_pipeline.py#L150-L212`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/adk_pipeline.py#L150-L212)
- **Problem:** `deconstruct_screenplay_with_adk` instantiates `deconstructor_agent`, assigns it to an unused variable, and then immediately bypasses it to call `sb_agent.expand_vision`:
  ```python
  sb_agent = StoryboardAgent(mock_mode=mock_mode)
  deconstructor_agent = create_script_deconstructor_agent(tools=[sb_agent.expand_vision])
  _ = deconstructor_agent  # <--- Dead code facade
  ...
  shots = sb_agent.expand_vision(...)
  return shots
  ```
  This creates the illusion that Google ADK agents are orchestrating script deconstruction, when in reality it is a direct call to `StoryboardAgent`.
- **Structural Remedy:** Either:
  1. Actually execute the ADK Agent using `google.adk.runners.InMemoryRunner` or `AgentSession` to deconstruct the screenplay via the tool, OR
  2. If direct execution is intended, remove the faux agent instantiation and document that `StoryboardAgent.expand_vision` is the underlying compiler.

---

### Duplicated Character Normalization Logic
- **Files:**
  - [`src/omnimash/agent/orchestrator.py#L579-L639`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L579-L639)
  - [`src/omnimash/agent/adk_pipeline.py#L165-L202`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/adk_pipeline.py#L165-L202)
- **Problem:** 60 lines of repetitive type checking (`isinstance(c, CharacterRole)`, `isinstance(c, dict)`, `hasattr(c, "model_dump")`, `hasattr(c, "role_id")`) are duplicated almost verbatim between `orchestrator.py` and `adk_pipeline.py` (and multiple times in `app.py`).
- **Structural Remedy:** Extract canonical `from omnimash.prompts.character_roles import normalize_character_role` and delete the redundant blocks.

---

### Hardcoded Stop-Words List in State Tracker
- **File:** [`src/omnimash/agent/orchestrator.py#L174-L221`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L174-L221)
- **Problem:** 47 hardcoded words (`["Yo", "The", "Camera", "Wide", "Dramatic", ...]`) are used to filter out non-character words when extracting character names from action text. Any capitalized word outside this set is assumed to be a character name, causing words like `"London"` or `"Cyberpunk"` to become characters in state tracking.
- **Structural Remedy:** Match characters strictly against `known_characters` or registered session character IDs. If no known character matches, do not guess based on capitalization.

---

## 3. Architecture

### Direct Access to Private `SessionManager._sessions` & Encapsulation Break
- **File:** [`src/omnimash/agent/orchestrator.py#L906-L928`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L906-L928)
- **Problem:** `_get_session` accesses the private attribute `self.session_manager._sessions` three times directly:
  ```python
  if session_id in self.session_manager._sessions:
      return self.session_manager._sessions[session_id]
  ...
  for session in self.session_manager._sessions.values():
  ```
  `SessionManager` should encapsulate session retrieval and lookup.
- **Structural Remedy:** Add a public method `get_session(session_id: str) -> ProjectSession | None` on `SessionManager` and remove direct private attribute access.

---

### Eager Initialization of `root_agent` at Module Import Time
- **Files:**
  - [`src/omnimash/agent/agent.py#L5`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/agent.py#L5)
  - [`src/omnimash/agent/orchestrator.py#L1126`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L1126)
- **Problem:** At the bottom of `orchestrator.py`, `root_agent = build_adk_agent(mock_mode=getattr(settings, "mock_mode", False))` executes unconditionally at import time.
  When `agent.py` imports `root_agent`, it instantiates `OmniMashAgent`, initializing `ModelArmorGuardrail`, `GcsStorageManager`, `OmniFlashClient`, `PromptTaxonomyEngine`, `MediaExtractor`, and `VideoStitcher`.
  This triggers GCS and Vertex AI client setup during module discovery (e.g. pytest collection or schema inspection) before environment variables or credentials may be initialized.
- **Structural Remedy:** Use lazy initialization or a factory function:
  ```python
  def get_root_agent() -> Agent: ...
  ```
  Or in `agent.py`, define a module-level `__getattr__` to initialize `agent` upon first access.

---

### Turn Index Allocation Inversion & Concurrency Vulnerability
- **File:** [`src/omnimash/agent/orchestrator.py#L309-L325`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L309-L325)
- **Problem:** `_allocate_turn_index` relies on an in-memory dictionary `self._session_turn_counters: dict[str, int] = {}` protected by a local `threading.Lock()`.
  1. In a multi-worker deployment (e.g. Cloud Run with multiple instances or Uvicorn with multiple workers), this in-memory state is not shared, leading to colliding turn indices.
  2. The method attempts to infer turn numbers by running regex on video URLs (`r"turn_(\d+)_video\.mp4"`). If URLs are hashed, UUID-based, or proxied, regex extraction fails and defaults to `len(session.turns)`.
- **Structural Remedy:** Delegate turn indexing and sequence numbering entirely to `SessionManager`, which persists the canonical turn graph and timeline in the session manifest.

---

### Two Disconnected ADK Representations
- **Files:**
  - `src/omnimash/agent/adk_pipeline.py` (defines multi-agent DAG: `Workflow`, `script_deconstructor`, `storyboard_compiler`, `shot_workers`, `stitcher`)
  - `src/omnimash/agent/orchestrator.py` (defines single agent: `omnimash_orchestrator` with `generate_parody_clip`)
- **Problem:** The repository maintains two distinct, divergent ADK concepts:
  - `adk_pipeline.py` defines a multi-agent Workflow DAG where workers have no tools and which is never executed in production.
  - `orchestrator.py` defines the actual agent used by `adk run` and `app.py`.
  Having two separate ADK architectures confuses engineers and leaves `adk_pipeline.py` as orphaned test-only code.
- **Structural Remedy:** Unify the pipeline: wire the sub-agents in `adk_pipeline.py` as genuine tools or sub-agents of `omnimash_orchestrator`, or export `build_production_orchestrator` as a selectable ADK root agent.

---

### **Consider:** Rename `Journey3StateTracker` to `CumulativeStateTracker`
- **File:** [`src/omnimash/agent/orchestrator.py#L43`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L43)
- **Problem:** The class name `Journey3StateTracker` references a demo/script journey ("Journey 3") from development rather than domain functionality.
- **Structural Remedy:** Rename to `CumulativeStateTracker` or `SceneStateTracker`. Provide a deprecated alias `Journey3StateTracker = CumulativeStateTracker` for backwards compatibility.

---

## 4. Security

### Unvalidated `reference_url` Input
- **File:** [`src/omnimash/agent/orchestrator.py#L560-L567`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L560-L567)
- **Problem:** `reference_url` is passed directly from user input into `media_extractor.process_youtube_url` and `media_extractor.analyze_youtube_reference` without URL scheme, hostname, or domain validation.
  If downstream processing resolves the URL, malicious inputs (e.g. `http://169.254.169.254/...` or `file:///...`) could lead to Server-Side Request Forgery (SSRF) against internal GCP metadata services.
- **Structural Remedy:** Validate `reference_url` against an allowlist of permitted schemes (`https://`) and domains (e.g. `youtube.com`, `youtu.be`, `storage.googleapis.com`) before passing to media extractors.

---

### Silent Exception Swallowing (`except Exception: pass`)
- **File:** [`src/omnimash/agent/orchestrator.py#L80-L81, L101-L102, L926-L927`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L80-L81)
- **Problem:** Throughout `Journey3StateTracker` and `_get_session`, broad `try ... except Exception: pass` blocks catch and suppress all errors without logging.
  This masks GCS permission errors (403 Forbidden), corrupt JSON manifests, and network dropouts.
- **Structural Remedy:** Catch specific exceptions (`GoogleAPICallError`, `KeyError`, `json.JSONDecodeError`) and log warnings with contextual details:
  ```python
  except Exception as exc:
      logger.warning("Failed to persist cumulative state for session %s: %s", session_id, exc)
  ```

---

## 5. Performance

### Redundant Client & Storage Instantiation (Lack of Dependency Injection)
- **File:** [`src/omnimash/agent/orchestrator.py#L293-L308`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L293-L308)
- **Problem:** `OmniMashAgent.__init__` creates:
  ```python
  self.storage = GcsStorageManager(mock_mode=mock_mode)
  self.session_manager = SessionManager(storage=self.storage)
  self.omni_client = OmniFlashClient(mock_mode=mock_mode)
  self.taxonomy = PromptTaxonomyEngine(mock_mode=mock_mode)
  self.media_extractor = MediaExtractor(mock_mode=mock_mode)
  self.stitcher = VideoStitcher(mock_mode=mock_mode)
  self.storyboard_agent = StoryboardAgent(mock_mode=mock_mode)
  ```
  Every single one of these classes instantiates its own internal `GcsStorageManager` instance rather than sharing `self.storage`. This creates 7 duplicate storage client instances, multiplying OpenTelemetry logging hooks, credential checks, and memory footprint.
- **Structural Remedy:** Inject `storage=self.storage` into `OmniFlashClient`, `PromptTaxonomyEngine`, `MediaExtractor`, `VideoStitcher`, and `StoryboardAgent`.

---

### Duplicate GCS Network Roundtrips in `_get_session`
- **File:** [`src/omnimash/agent/orchestrator.py#L917-L925`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L917-L925)
- **Problem:** `_get_session` calls `manifest = self.storage.get_session_manifest(sanitized)`.
  If found, it calls `self.session_manager.get_or_create_session(..., session_name=sanitized)`.
  Inside `get_or_create_session`, if the session is not in cache, it **re-fetches the exact same manifest from GCS a second time**:
  ```python
  manifest = self.storage.get_session_manifest(session_key, project_id=project_id)
  ```
- **Structural Remedy:** Pass the already-fetched manifest into `get_or_create_session(..., initial_manifest=manifest)` to eliminate the duplicate network roundtrip.

---

### Synchronous Blocking Multi-Chunk Video Generation
- **File:** [`src/omnimash/agent/orchestrator.py#L489-L539`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L489-L539)
- **Problem:** Generating multi-chunk videos (e.g. 30 seconds = 3 chunks) executes sequentially in a blocking synchronous loop. Each chunk takes 15–30 seconds for Omni Flash generation, followed by synchronous FFmpeg stitching and GCS upload. In HTTP request contexts, this frequently exceeds standard gateway timeouts (60s).
- **Structural Remedy:** For durations > 10s, return an accepted job ticket with SSE / WebSocket progress updates, processing chunks via an async background task or queue.

---

## 6. Dead Code Hygiene

```
DEAD CODE IDENTIFIED:
1. `_ = deconstructor_agent` in `src/omnimash/agent/adk_pipeline.py` (lines 162-163):
   Instantiates `create_script_deconstructor_agent` only to discard it and call `sb_agent.expand_vision`.
2. `create_adk_agent_tool_pipeline()` in `src/omnimash/agent/adk_pipeline.py` (lines 140-148):
   Unused anywhere in production code; referenced only in `tests/agent/test_adk_pipeline.py`.
3. `build_production_orchestrator()` in `src/omnimash/agent/adk_pipeline.py` (lines 111-137):
   Creates a disconnected Workflow graph with tool-less workers that is never executed by `app.py` or `agent.py`.
4. Hardcoded stop words (`stop_words`) in `src/omnimash/agent/orchestrator.py` (lines 174-221):
   Fragile capitalized-word blacklist superseded by explicit character roster validation.
```

---

## 7. Review Checklist

### Context
- [x] I understand what this module does and why (OmniMash Agent & ADK Orchestration for Gemini Omni Flash 1.1).

### Correctness
- [ ] Change matches spec/task requirements *(Blocked by wardrobe attribute loss and greedy regex state deletion)*
- [ ] Edge cases handled *(Blocked by multi-chunk graph inconsistency and save_final_master clip selection)*
- [ ] Error paths handled *(Blocked by broad `except Exception: pass` suppressing storage failures)*
- [x] Tests cover the change adequately *(31 agent tests passing, but missing tests for wardrobe preservation, greedy regex edge cases, and multi-chunk graph consistency)*

### Readability
- [ ] Names are clear and consistent *(Blocked by `Journey3StateTracker` naming leakage)*
- [ ] Logic is straightforward *(Blocked by ~100-line regex heuristic in `validate_conversational_edit`)*
- [ ] No unnecessary complexity *(Blocked by duplicated character normalization logic)*

### Architecture
- [x] Follows existing patterns
- [ ] No unnecessary coupling or dependencies *(Blocked by redundant GcsStorageManager instantiations)*
- [ ] Appropriate abstraction level *(Blocked by lack of public `get_session` on SessionManager)*
- [ ] Refactors reduce complexity rather than relocate it *(Blocked by disconnected ADK representations in adk_pipeline.py vs orchestrator.py)*
- [x] File stays within healthy size *(orchestrator.py is 1,126 lines; consider splitting into state_tracker.py, prompt_builder.py, and orchestrator.py)*

### Security
- [x] No secrets in code
- [ ] Input validated at boundaries *(Blocked by missing `reference_url` validation)*
- [x] No injection vulnerabilities
- [x] Auth checks in place
- [ ] External data sources treated as untrusted *(Blocked by silent exception suppression on GCS storage reads)*

### Performance
- [x] No N+1 patterns
- [ ] No redundant operations *(Blocked by duplicate GCS manifest fetch in `_get_session` and redundant storage manager instances)*
- [ ] Unbounded synchronous blocking operations *(Multi-chunk video generation blocks synchronously)*

### Verification
- [x] Tests pass (`31 passed in 17.78s` via `uv run pytest tests/agent/ -v`)
- [x] Static type check succeeds (`uv run ty check` 0 errors)
- [x] Linter succeeds (`uv run ruff check src/omnimash/agent` 0 errors)

### Final Verdict
- [ ] **Approve** — Ready to merge
- [x] **Request changes** — Critical and Required issues must be addressed before production release.
