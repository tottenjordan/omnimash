# OmniMash (`main`) Comprehensive Code Review & Remediation Plan

**Commit Audited:** `64480e0` (`main`)
**Date:** 2026-10-02
**Skills Applied:**
- `omniflash-producer` (Gemini Omni Flash 1.1 4-block meta-prompts, `<FIRST_FRAME>`/`<LAST_FRAME>` anchors, 360p Draft Room, stateful `previous_interaction_id` chaining)
- `adk` (Google ADK agent configuration, `Runner`/`InMemorySessionService` execution, subagent tools, config-driven models)
- `google-cloud-storage-basics` (GCS object persistence, stateless Cloud Run storage patterns, bucket scoping)
- `modern-python` (`uv sync --frozen`, `pyproject.toml` tool config for `ruff` and `ty`)
- `testing-anti-patterns` (no test-only state/methods in production classes, strict JSX scope validation)
- `web-app-development` & `writing-plans` (modular architecture, TDD remediation roadmap)

---

## Executive Summary

An end-to-end architectural and code audit of the `main` branch uncovered **16 high-impact issues** across three categories:
1. **Logical Bugs & Broken User Flows (7 findings):** Silent failures in multi-chunk (`>10s`) stateful video extension, file overwrites that break Draft Room side-by-side variations, `get_session_manifest()` never reading from GCS, prompt compilation occurring *before* auto-keyframe generation (dropping `<FIRST_FRAME>@KeyframeSeed`), and silent 30fps title cards corrupting 24fps audio stream concatenation.
2. **Architecture & Cloud Run Bottlenecks (5 findings):** Uncleaned `/tmp` media files in `VideoStitcher` exhausting Cloud Run's in-memory `tmpfs` (2Gi limit), race conditions on hardcoded `/tmp/concat_list.txt`, synchronous blocking network/FFmpeg I/O inside `async def` FastAPI routes and request threads, process-local volatile state (`SessionManager`, `Journey3StateTracker`), and a 10,768-line monolith in `src/omnimash/api/app.py`.
3. **Systemic & Skill-Specific Flaws (4 findings):** Disconnected ADK agents with legacy model defaults (`gemini-omni-flash-preview`) and contradictory 6-part vs. 4-block instructions, production classes polluted with `_mock_*` dictionaries (`testing-anti-patterns` Iron Law #2), `1x1` transparent PNG fallback poisoning `<FIRST_FRAME>` video conditioning, and `Dockerfile`/`pyproject.toml` deviations from `modern-python`.

---

## Part 1: Detailed Findings

### A. Logical Bugs & Broken User Flows

#### 1. [CRITICAL] Multi-Chunk (`>10s`) Video Generation Drops `previous_interaction_id` (`omniflash-producer`)
- **Location:** [`src/omnimash/agent/orchestrator.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L352-L385) and [line 593](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L593)
- **Root Cause:**
  - When `duration_seconds > 10.0` (`num_chunks > 1`), `OmniMashAgent.process_user_turn()` recursively calls `self.process_user_turn()` for each 10s chunk, passing `parent_turn_id=curr_parent_turn_id` (`turn_resp.turn_id`) to chain chunks statefully.
  - However, the recursive call does **not** pass `is_conversational_edit=True` (nor does it pass `keyframe_image_url`, `resolution`, `aspect_ratio`, or `motion_reference_clip`), and at line 593:
    ```python
    effective_thread_id = parent_thread_id if is_conversational_edit else None
    ```
  - Because `is_conversational_edit` defaults to `False`, `effective_thread_id` is forced to `None` and `omni_client.generate_clip()` is called instead of `apply_interaction_diff()`.
- **Impact:** Multi-chunk shots (`20s`, `30s`, `40s`) never pass `previous_interaction_id` to Gemini Omni Flash 1.1, generating disconnected 10s clips instead of continuous stateful extensions.

#### 2. [CRITICAL] Filename Collision Overwrites Draft Room Variations & Concurrent Sessions (`omniflash-producer`)
- **Location:** [`src/omnimash/engine/omni_client.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L1664-L1670), [lines 1736–1742](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L1736-L1742), and [`src/omnimash/api/app.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10376-L10408)
- **Root Cause:**
  - In `generate_clip()` and `apply_interaction_diff()`, when `turn_index` is provided, the output filename is hardcoded as:
    ```python
    filename = f"turn_{turn_index}_video.mp4" if turn_index is not None else f"{thread_id}_turn0.mp4"
    ```
  - In `/api/storyboard/draft-batch` (`generate_draft_batch`), the loop over `range(req.variations_per_shot)` calls `agent.process_user_turn(..., clip_index=shot.shot_index)` for every variation of the same shot.
- **Impact:**
  1. Every variation (`var_idx = 0, 1, ...`) of Shot `N` writes to the exact same local path (`static/rendered/turn_{N}_video.mp4`) and uploads to the exact same GCS blob (`sessions/{session}/intermediate/turn_{N}_video.mp4`). All Draft Room cards for a shot display the final variation's video, breaking side-by-side comparison.
  2. Concurrent users/sessions generating Shot `N` overwrite each other's local `static/rendered/turn_{N}_video.mp4` file before GCS upload completes.

#### 3. [HIGH] `GcsStorageManager.get_session_manifest()` Never Reads from Cloud Storage (`google-cloud-storage-basics`)
- **Location:** [`src/omnimash/storage/gcs.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L339-L341)
- **Root Cause:**
  - `save_session_manifest()` writes `projects/{project_id}/sessions/{session_id}/prompts/session_manifest.json` to GCS and caches it in `self._mock_session_manifests`.
  - However, `get_session_manifest()` is implemented as:
    ```python
    def get_session_manifest(self, session_id: str) -> dict[str, Any] | None:
        return self._mock_session_manifests.get(session_id)
    ```
  - It never queries `self._bucket` in live mode.
- **Impact:** Any session manifest saved to GCS cannot be retrieved after a Cloud Run container restart or when a request lands on a different Cloud Run instance.

#### 4. [HIGH] Auto-Keyframe Generation Happens *After* Prompt Compilation, Omitting `<FIRST_FRAME>@KeyframeSeed` (`omniflash-producer`)
- **Location:** [`src/omnimash/api/app.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L9872-L9899) (`generate_shot`) and [lines 10250–10280](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10250-L10280) (`journey3_generate_shot`)
- **Root Cause:**
  - Both `/api/generate-shot` and `/api/journey3/generate-shot` compile the 4-block prompt (`compile_storyboard` / `compile_journey3_shot_prompt`) first while `keyframe_url` is still `None` (`has_keyframe_seed=False`).
  - Immediately *after* compiling the prompt, they check `if not keyframe_url:` and auto-generate `keyframe_url = agent.omni_client.generate_keyframe_image(...)`, then pass `compiled_override=compiled_prompt` alongside the newly generated `keyframe_image_url=keyframe_url` into `agent.process_user_turn()`.
- **Impact:** When a keyframe is auto-generated during shot execution, `compiled_override` lacks `[# Sources <FIRST_FRAME>@KeyframeSeed]` in `### INPUT ROLES & REFERENCES`, violating the `omniflash-producer` 4-Block Meta-Prompt contract.

#### 5. [HIGH] Silent 30fps Title Card Clips Corrupt FFmpeg `-c copy` Concatenation with 24fps Audio-Bearing Shots
- **Location:** [`src/omnimash/stitching/stitcher.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L119-L162) and [lines 300–318](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L300-L318)
- **Root Cause:**
  - `generate_title_card_clip()` generates a title card MP4 using `-framerate 30 ... -r 30` with **no audio stream** (only a single video input `0:v`).
  - Omni Flash 1.1 shot clips are 24fps (`24 FPS`) with an AAC audio track (`0:a`).
  - `stitch_storyboard_master()` prepends the silent 30fps title card clip to `interleaved_clips` and calls `concatenate_clips()`, which runs `ffmpeg -f concat -safe 0 -i concat_list.txt -c copy`.
- **Impact:** FFmpeg's `concat` demuxer with `-c copy` requires identical stream layouts, codecs, timebases, and frame rates across all segments. Starting concatenation with a streamless-audio 30fps title card clip causes FFmpeg stream copy to either drop the audio track from all subsequent 24fps shots or produce severe audio/video desynchronization.

#### 6. [MEDIUM] Silent Fallback to SVG Mock Keyframe Poisons `<FIRST_FRAME>` Conditioning with a 1x1 Pixel
- **Location:** [`src/omnimash/engine/omni_client.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L1872-L1904) and [lines 2272–2280](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L2272-L2280)
- **Root Cause:**
  - In `generate_keyframe_image()`, even when `self.mock_mode is False`, any exception from `image_client.models.generate_content()` is caught and silently replaced with `_get_mock_keyframe()` (a `data:image/svg+xml;base64,...` wireframe SVG).
  - Worse, when that SVG data URI is passed to `_build_multimodal_contents()` -> `_fetch_image_bytes()` (lines 1898–1904), `_fetch_image_bytes()` substitutes a **1x1 transparent PNG pixel** (`raster_png_fallback`) and injects `# Visual Tone & Starting Frame Anchor: Attached Image #1 is the keyframe starting concept art frame...`.
  - Additionally, `generate_keyframe_image()` and `generate_character_reference_sheet()` default to `image_model: str = "gemini-3.1-flash-image"` instead of `settings.image_model_id` (`"gemini-3.1-flash-image-preview"`).
- **Impact:** Transient image generation errors or wrong default model IDs are hidden from the user and poison downstream Omni Flash 1.1 video generation by anchoring `<FIRST_FRAME>` to a 1x1 transparent pixel.

#### 7. [MEDIUM] Hardcoded `/tmp/concat_list.txt` Race Condition in `VideoStitcher`
- **Location:** [`src/omnimash/stitching/stitcher.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L119-L123)
- **Root Cause:**
  - `concatenate_clips()` writes the FFmpeg concat manifest to a fixed path:
    ```python
    concat_list_path = os.path.join(output_dir, "concat_list.txt")
    ```
    where `output_dir` defaults to `"/tmp"`.
- **Impact:** Two concurrent stitch operations on the same Cloud Run instance overwrite `/tmp/concat_list.txt` simultaneously, splicing one user's shots into another user's master cut or failing mid-stitch.

---

### B. Architecture & Cloud Run Bottlenecks

#### 8. [CRITICAL] Unbounded `/tmp` (`tmpfs`) Media Leak Causes Cloud Run Memory Exhaustion (`OOMKilled`)
- **Location:** [`src/omnimash/stitching/stitcher.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L75-L185) and [lines 245–360](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/stitching/stitcher.py#L245-L360), [`src/omnimash/engine/omni_client.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L1669-L1860)
- **Root Cause:**
  - On Cloud Run (2nd Gen execution environment), `/tmp` and container-local directories (`static/rendered/`) are backed by an **in-memory `tmpfs` filesystem** shared with the container's `2Gi` RAM limit.
  - `VideoStitcher.concatenate_clips()` and `stitch_storyboard_master()` create downloaded clips (`tmp_clip_*.mp4`), title cards (`title_card_*.mp4`), narrator audio mixes (`master_voiced_*.mp4`), ducked audio files (`ducked_bgm_*.wav`), and stitched masters (`stitched_*.mp4`) in `/tmp` without a `tempfile.TemporaryDirectory()` context manager or `finally:` cleanup.
  - Similarly, `OmniFlashClient` writes every generated 720p/1080p/4K MP4 clip to `static/rendered/` and never deletes local copies after uploading them to GCS.
- **Impact:** After generating and stitching several 1080p/4K clips, `/tmp` and `static/rendered/` accumulate hundreds of megabytes in `tmpfs`, exhausting the 2Gi Cloud Run memory limit and crashing the container (`OOMKilled`).

#### 9. [HIGH] Synchronous Blocking Network & Subprocess I/O Inside `async def` Routes and Request Threads
- **Location:** [`src/omnimash/api/app.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10693-L10763), [`src/omnimash/engine/omni_client.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L1312-L1339), and [`src/omnimash/api/app.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10376-L10414)
- **Root Cause:**
  - `generate_character_sheet_endpoint` (`@app.post("/api/characters/generate-sheet")`) and `save_character_sheet_endpoint` (`@app.post("/api/characters/save-sheet")`) are declared `async def`, running directly on Uvicorn's main `asyncio` event loop, yet call synchronous blocking GenAI SDK and GCS methods.
  - `/api/storyboard/draft-batch` executes `len(shots) * variations_per_shot` video generations **sequentially** in a nested `for` loop instead of concurrently via `ThreadPoolExecutor` / `asyncio.gather`, multiplying Draft Room latency by $N \times M$.
  - `generate_keyframe_image` and `generate_character_reference_sheet` instantiate a new `genai.Client` on every request instead of reusing the initialized client on `OmniFlashClient`.
- **Impact:** A single character turnaround sheet generation freezes the entire FastAPI event loop for 10–25 seconds; Draft Room batches take $4\times$–$6\times$ longer than necessary.

#### 10. [HIGH] Process-Local In-Memory Session & State Volatility Across Cloud Run Instances
- **Location:** [`src/omnimash/state/session_manager.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/state/session_manager.py#L32-L48), [`src/omnimash/agent/orchestrator.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/orchestrator.py#L40-L54), and tracked binary `src/omnimash/agent/.adk/session.db`
- **Root Cause:**
  - `SessionManager._sessions` (storing the turn DAG, `interaction_thread_id`, `edit_depth_in_thread`, and `timeline`) and `Journey3StateTracker._session_states` (storing cumulative character/scene states across shots) exist solely in Python process RAM.
  - Furthermore, a local SQLite binary file `src/omnimash/agent/.adk/session.db` is committed to git.
- **Impact:** When Cloud Run scales beyond 1 instance or recycles a container, `session_manager.get_turn(parent_turn_id)` raises `KeyError("Parent turn ... not found")`, breaking conversational edits (`/api/diff`), scene extensions (`/api/extend-scene`), and cumulative state tracking.

#### 11. [MEDIUM] Security & SSRF / Path Traversal Exposure in Media Ingestion Endpoints
- **Location:** [`src/omnimash/api/app.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L9564-L9612), [lines 10660–10689](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py#L10660-L10689), and [`src/omnimash/engine/omni_client.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py#L1908-L1926)
- **Root Cause:**
  - `_fetch_image_bytes()` opens arbitrary local file paths (`if os.path.exists(ref_url) and os.path.isfile(ref_url): open(ref_url, "rb")`) and fetches arbitrary `http://` URLs without blocking private/link-local IPs (`169.254.169.254` metadata server SSRF).
  - `/api/motion-reference/upload` accepts any server path in `req.input_video_path`.
  - `/api/media-proxy` downloads from any `gs://` bucket accessible to the service account rather than restricting to `agent.storage.bucket_name`.
  - `/api/upload` calls `await file.read()` with no byte limit or extension allowlist.

#### 12. [MEDIUM] 10,768-Line Monolith in `src/omnimash/api/app.py` (`web-app-development`)
- **Location:** [`src/omnimash/api/app.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py)
- **Root Cause:**
  - `src/omnimash/api/app.py` embeds 8,785 lines of unminified JSX (`UI_HTML`, lines 506–9291) directly inside the same Python module as 500 lines of Pydantic schemas and 1,475 lines of FastAPI route handlers, with 4x duplicated `CharacterRole` dict-to-dataclass conversion blocks (lines 9386, 9790, 9983, 10204).
- **Impact:** High cognitive load, slow IDE indexing, fragile JSX edits, and duplicated request normalization logic.

---

### C. Systemic & Skill-Specific Flaws

#### 13. [HIGH] ADK Pipeline Bypass, Legacy Model Default, and Contradictory Prompt Instructions (`adk` & `omniflash-producer`)
- **Location:** [`src/omnimash/agent/adk_pipeline.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/agent/adk_pipeline.py#L19-L198)
- **Root Cause:**
  1. **Bypassed ADK Agents:** `deconstruct_screenplay_with_adk()` (lines 142–198) never invokes `create_script_deconstructor_agent()` or an ADK `Runner`—it directly calls `StoryboardAgent().expand_vision(...)`.
  2. **Legacy & Mismatched Default Model:** All four ADK agent factories default to `model: str = "gemini-omni-flash-preview"` (the deprecated 1.0 video model ID) instead of `settings.gemini_pro_model` (`gemini-3.1-pro-preview`) for text/JSON agent reasoning (`adk` Config-Driven Pattern).
  3. **Contradictory System Prompt:** `STORYBOARD_COMPILER_DEFAULT_INSTRUCTION` (lines 19–21) instructs the agent to compile a legacy *"6-part video generation prompt (`[SUBJECT ANCHOR] + [AESTHETIC INJECTION] + ...`)"* and immediately appends `GEMINI_OMNI_FLASH_INSTR`, which mandates the **4-Block Meta-Prompt** structure (`### INPUT ROLES & REFERENCES`, `### CHARACTER PROFILES`, `### SCENE INSTRUCTIONS`, `### TIMELINE & DIALOGUE`).

#### 14. [MEDIUM] Test-Only State Polluting Production Classes & Silent Exception Swallowing (`testing-anti-patterns` & `google-cloud-storage-basics`)
- **Location:** [`src/omnimash/storage/gcs.py`](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/storage/gcs.py#L78-L99)
- **Root Cause:**
  - `GcsStorageManager.__init__` initializes 10 in-memory `_mock_*` dictionaries (`_mock_characters`, `_mock_rosters`, `_mock_storyboards`, `_mock_session_manifests`, etc.) on the production class, and almost every GCS method wraps live bucket operations in `except Exception: pass`, silently falling back to `_mock_*` dictionaries when a real GCS error occurs.
- **Impact:** Violates `testing-anti-patterns` Iron Law #2 (*"Never add test-only methods/state to production classes"*) and masks real GCS permission/network failures in production by pretending uploads succeeded in memory.

#### 15. [MEDIUM] Production `Dockerfile` & `pyproject.toml` Deviations from `modern-python`
- **Location:** [`Dockerfile`](file:///usr/local/google/home/jordantotten/omnimash/Dockerfile#L23) and [`pyproject.toml`](file:///usr/local/google/home/jordantotten/omnimash/pyproject.toml)
- **Root Cause:**
  - `Dockerfile` runs `uv pip install --system -r pyproject.toml`, which resolves floating version ranges (`>=`) at image build time and completely ignores `uv.lock`, rather than using `uv sync --frozen --no-dev`.
  - `pyproject.toml` lacks `[tool.ruff]`, `[tool.ruff.lint]`, and `[tool.ty]` sections recommended by `modern-python`.

#### 16. [LOW] Lenient Tag Stack Unwinding in `test_ui_html_syntax_and_tag_balance` (`testing-anti-patterns`)
- **Location:** [`tests/api/test_app.py`](file:///usr/local/google/home/jordantotten/omnimash/tests/api/test_app.py#L960-L964)
- **Root Cause:**
  - While `test_ui_html_renders_in_browser_without_syntax_error` now runs headless Chromium via Playwright to catch JSX/Babel errors, the static regex test `test_ui_html_syntax_and_tag_balance` still contains a lenient `elif stack:` branch that silently unwinds unclosed inner tags if an outer tag name matches, and does not track `{` / `}` expression boundaries.

---

## Part 2: Phased TDD Remediation Plan

> **Note:** Per instructions, **no code changes have been applied yet**. Upon approval, we will execute this plan on a dedicated feature/fix branch (`fix/architecture-and-logical-bugs`) using strict Red-Green-Refactor TDD and open a Pull Request for review.

### Phase 1: Fix Core Video Engine & Prompt Compilation Logical Bugs (`omniflash-producer`)

#### Task 1.1: Fix Multi-Chunk (`>10s`) Stateful Chaining in `OmniMashAgent.process_user_turn()`
- **Files:**
  - Modify: `src/omnimash/agent/orchestrator.py`
  - Test: `tests/agent/test_orchestrator.py`
- **TDD Steps:**
  1. **RED:** Write `test_process_user_turn_multi_chunk_chains_previous_interaction_id()` in `tests/agent/test_orchestrator.py` asserting that a `20.0s` shot executes 2 chunks where Chunk 2 calls `apply_interaction_diff` (or passes `previous_interaction_id` from Chunk 1's `interaction_thread_id`) and preserves `resolution`, `aspect_ratio`, and `motion_reference_clip`.
  2. **GREEN:** Update `OmniMashAgent.process_user_turn()` in `src/omnimash/agent/orchestrator.py` so recursive chunk calls pass `is_conversational_edit=(i > 0 or is_conversational_edit)`, `resolution=resolution`, `aspect_ratio=aspect_ratio`, `motion_reference_clip=motion_reference_clip`, and `keyframe_image_url=keyframe_image_url if i == 0 else None`.
  3. **VERIFY:** `uv run pytest tests/agent/test_orchestrator.py -v`

#### Task 1.2: Fix Output Filename Collisions in `OmniFlashClient` & Parallelize `/api/storyboard/draft-batch`
- **Files:**
  - Modify: `src/omnimash/engine/omni_client.py`
  - Modify: `src/omnimash/api/app.py`
  - Test: `tests/engine/test_omni_client.py`, `tests/api/test_app.py`
- **TDD Steps:**
  1. **RED:** Write `test_draft_batch_generates_unique_video_urls_per_variation()` in `tests/api/test_app.py` verifying that `variations_per_shot=2` for `shot_index=1` produces distinct `video_url` and `gcs_uri` values for Variation 0 and Variation 1.
  2. **GREEN:**
     - Include `thread_id` (or a short UUID suffix / `session_id`) in `filename` inside `OmniFlashClient.generate_clip()` and `apply_interaction_diff()` (e.g., `f"turn_{turn_index}_{thread_id}.mp4"`).
     - Run `/api/storyboard/draft-batch` variations concurrently using `ThreadPoolExecutor(max_workers=4)` while preserving result ordering.
  3. **VERIFY:** `uv run pytest tests/engine/test_omni_client.py tests/api/test_app.py -k "draft_batch" -v`

#### Task 1.3: Auto-Generate Keyframe *Before* Prompt Compilation & Fix Image Model Defaults
- **Files:**
  - Modify: `src/omnimash/api/app.py`
  - Modify: `src/omnimash/engine/omni_client.py`
  - Test: `tests/api/test_app.py`, `tests/engine/test_omni_client.py`
- **TDD Steps:**
  1. **RED:** Write `test_generate_shot_auto_keyframe_includes_first_frame_anchor_in_compiled_prompt()` in `tests/api/test_app.py` asserting that calling `/api/generate-shot` and `/api/journey3/generate-shot` with `keyframe_image_url=None` auto-generates the keyframe *first* and includes `<FIRST_FRAME>@KeyframeSeed` in `raw_compiled_prompt`.
  2. **GREEN:**
     - In `generate_shot()` and `journey3_generate_shot()` (`src/omnimash/api/app.py`), move the `if not keyframe_url:` auto-generation block **above** `compile_storyboard()` / `compile_journey3_shot_prompt()`.
     - Update default `image_model` in `OmniFlashClient.generate_keyframe_image()` and `generate_character_reference_sheet()` to `settings.image_model_id` (`"gemini-3.1-flash-image-preview"`), reuse `self._genai_client`, and ensure SVG mock fallback is only used when `self.mock_mode is True` (raising or logging explicit error details in live mode instead of poisoning `<FIRST_FRAME>` with a 1x1 PNG).
  3. **VERIFY:** `uv run pytest tests/api/test_app.py tests/engine/test_omni_client.py -v`

---

### Phase 2: Fix FFmpeg Stitching Audio/FPS Mismatch, Race Conditions & `/tmp` Memory Leaks

#### Task 2.1: Match Title Card FPS (24fps) + Silent Audio Track & Use Scoped Temp Directories in `VideoStitcher`
- **Files:**
  - Modify: `src/omnimash/stitching/stitcher.py`
  - Test: `tests/stitching/test_stitcher.py`
- **TDD Steps:**
  1. **RED:**
     - Write `test_generate_title_card_clip_uses_24fps_and_silent_audio_track()` in `tests/stitching/test_stitcher.py` asserting that `generate_title_card_clip()` configures 24fps (`-framerate 24`, `-r 24`) and includes an `anullsrc` silent AAC audio stream (`-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -c:a aac -shortest`) so `-c copy` concatenation with 24fps Omni Flash clips never drops audio.
     - Write `test_concatenate_clips_uses_unique_manifest_and_cleans_up_temp_files()` verifying that concurrent stitch calls do not share `/tmp/concat_list.txt` and temporary downloaded clip files are removed in a `finally:` block.
  2. **GREEN:**
     - Update `generate_title_card_clip()` in `src/omnimash/stitching/stitcher.py` to output 24fps video with a silent stereo AAC audio track.
     - Use a per-invocation `tempfile.TemporaryDirectory(dir=output_dir)` for `concat_list.txt` and intermediate downloaded clips (`tmp_clip_*`, `tmp_audio_*`, `card_clip_*`), cleaning them up automatically in `finally:`.
  3. **VERIFY:** `uv run pytest tests/stitching/ -v`

---

### Phase 3: Fix GCS Persistence, Cloud Run State Synchronization & Async/Security Bottlenecks

#### Task 3.1: Implement Live GCS Read in `get_session_manifest()` & Persist `SessionManager` / `Journey3StateTracker` State
- **Files:**
  - Modify: `src/omnimash/storage/gcs.py`
  - Modify: `src/omnimash/state/session_manager.py`
  - Modify: `src/omnimash/agent/orchestrator.py`
  - Remove tracked binary: `src/omnimash/agent/.adk/session.db` (and add `.adk/` to `.gitignore`)
  - Test: `tests/storage/test_gcs.py`, `tests/state/test_session_manager.py`
- **TDD Steps:**
  1. **RED:**
     - Write `test_get_session_manifest_reads_from_gcs_bucket_when_not_cached()` in `tests/storage/test_gcs.py` verifying that a fresh `GcsStorageManager` instance downloads `session_manifest.json` from GCS.
     - Write `test_session_manager_persists_and_reloads_turns_via_storage()` in `tests/state/test_session_manager.py`.
  2. **GREEN:**
     - Update `GcsStorageManager.get_session_manifest(session_id, project_id="default_project")` to download and parse `projects/{project_id}/sessions/{session_id}/prompts/session_manifest.json` (and fallback path) from `self._bucket` when not in mock mode.
     - Add optional GCS-backed state persistence hooks to `SessionManager` and `Journey3StateTracker` so turns and cumulative character states survive across Cloud Run instances.
     - Untrack `src/omnimash/agent/.adk/session.db` (`git rm --cached`) and ignore `.adk/` in `.gitignore`.
  3. **VERIFY:** `uv run pytest tests/storage/ tests/state/ -v`

#### Task 3.2: Fix Blocking `async def` Routes & Harden Media Endpoints Against SSRF / Path Traversal
- **Files:**
  - Modify: `src/omnimash/api/app.py`
  - Modify: `src/omnimash/engine/omni_client.py`
  - Test: `tests/api/test_app.py`
- **TDD Steps:**
  1. **RED:** Write tests in `tests/api/test_app.py` verifying that `/api/media-proxy` rejects `gs://` URIs outside the configured bucket, `_fetch_image_bytes` blocks private/metadata IP addresses (`169.254.169.254`) and paths outside allowed directories (`static/`, `/tmp/`), and character sheet routes do not block the event loop.
  2. **GREEN:**
     - Change `generate_character_sheet_endpoint` and `save_character_sheet_endpoint` from `async def` to standard `def` (so FastAPI executes them in the worker threadpool) and extract a shared `normalize_character_roles()` helper to eliminate the 4x duplicated character conversion loops in `src/omnimash/api/app.py`.
     - Scope `/api/media-proxy` to `agent.storage.bucket_name`, validate local paths in `/api/motion-reference/upload` and `_fetch_image_bytes` using `os.path.realpath()` within allowed roots (`static/`, `/tmp/`), and reject private/link-local hosts in HTTP image fetches.
  3. **VERIFY:** `uv run pytest tests/api/test_app.py -v`

---

### Phase 4: Align ADK Pipeline, Modern Python Tooling & JSX Test Guardrails (`adk`, `modern-python`, `testing-anti-patterns`)

#### Task 4.1: Align `adk_pipeline.py` with Config-Driven Models & 4-Block Meta-Prompt Instructions (`adk` & `omniflash-producer`)
- **Files:**
  - Modify: `src/omnimash/agent/adk_pipeline.py`
  - Test: `tests/agent/test_adk_pipeline.py`
- **TDD Steps:**
  1. **RED:** Write `test_adk_agents_use_configured_models_and_4_block_instructions()` in `tests/agent/test_adk_pipeline.py` verifying that agent factories default to `settings.omni_model_id` (`gemini-omni-1.1-flash-preview`) / `settings.gemini_pro_model` instead of legacy `gemini-omni-flash-preview`, and `STORYBOARD_COMPILER_DEFAULT_INSTRUCTION` specifies the 4-Block Meta-Prompt structure without legacy 6-part prompt instructions.
  2. **GREEN:** Update `src/omnimash/agent/adk_pipeline.py` to pull model defaults from `omnimash.config.settings`, replace the contradictory 6-part instruction prefix in `STORYBOARD_COMPILER_DEFAULT_INSTRUCTION` with the 4-Block Meta-Prompt specification, and wire `create_script_deconstructor_agent()` into `deconstruct_screenplay_with_adk()`.
  3. **VERIFY:** `uv run pytest tests/agent/test_adk_pipeline.py -v`

#### Task 4.2: Modernize `Dockerfile`, `pyproject.toml`, and Strict JSX Scope Balance Test (`modern-python`, `testing-anti-patterns`)
- **Files:**
  - Modify: `Dockerfile`
  - Modify: `pyproject.toml`
  - Modify: `tests/api/test_app.py`
- **TDD Steps:**
  1. **RED:** Add a test in `tests/api/test_app.py` asserting that `test_ui_html_syntax_and_tag_balance` fails immediately on any mismatched closing tag or unclosed tag across `{ ... }` JSX expression scopes (without lenient stack unwinding).
  2. **GREEN:**
     - Tighten `test_ui_html_syntax_and_tag_balance` in `tests/api/test_app.py` so every closing tag must match `stack[-1]` directly.
     - Add `[tool.ruff]`, `[tool.ruff.lint]`, and `[tool.ty]` configuration blocks to `pyproject.toml`.
     - Update `Dockerfile` to copy `uv.lock` and install production dependencies deterministically via `uv sync --frozen --no-dev --no-install-project` (or `uv pip install --system --no-cache -r pyproject.toml` with lockfile export).
  3. **VERIFY:**
     - `uv run pytest`
     - `uv run ruff check .`
     - `uv run ty check`
