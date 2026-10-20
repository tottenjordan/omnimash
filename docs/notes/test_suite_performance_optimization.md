# Test Suite Performance Profiling & Optimization

## Overview
Profiling the 416-test `pytest` suite revealed a baseline execution time of **350.90s (~5m 51s)**. Through targeted bottleneck elimination and multi-worker parallelization (`pytest-xdist`), full-suite execution time was reduced to **~25.2s** (**13.9x speedup** / **92.8% reduction**).

---

## Root Cause Analysis (Baseline: 350.90s)

1. **Unmocked Live ADK LLM Calls in `/api/storyboard/expand` (`60.53s` across 2 tests):**
   - `expand_storyboard` in `src/omnimash/api/app.py` called `deconstruct_screenplay_with_adk(...)` without passing `mock_mode=is_mock`, defaulting to `mock_mode=False` and firing 4 live Gemini network requests to Vertex AI during unit tests.
2. **Heavy 240-Frame `zoompan` FFmpeg Filter in `ensure_rendered_video` (`142.80s` across 4 tests):**
   - `ensure_rendered_video` in `src/omnimash/engine/omni_client.py` synthesized a 10-second (`d=240`) 1280x720 video using FFmpeg's single-threaded `zoompan` filter and `-preset fast`, taking `~35s` per invocation.
3. **Un-cached `google.cloud.storage.Client` & Blocking `lookup_bucket` HTTP Calls (`~95s` across 60+ tests):**
   - Every test instantiating `OmniFlashClient(mock_mode=False)` or `VideoStitcher(mock_mode=False)` created a new `GcsStorageManager(mock_mode=False)`, which initialized Google Cloud ADC credentials (`1.19s`) and executed a live `client.lookup_bucket()` HTTP roundtrip (`0.37s`) in `__init__` (`1.56s` overhead per test).
   - `OmniMashAgent.__init__` also instantiated 4 separate `GcsStorageManager` instances across its subcomponents.
4. **Eager Module-Level `app = create_app()` in `src/omnimash/api/app.py` (`~7.6s` import penalty):**
   - Importing `omnimash.api.app` (even for `UI_HTML` string assertions) eagerly constructed a production `FastAPI` instance with `mock_mode=False` and rendered `/static/rendered/mock.mp4`.
5. **Single-Threaded Test Execution & Concurrent Turn Index Race Condition:**
   - All 416 tests ran sequentially on 1 CPU core.
   - Enabling parallel execution uncovered a latent thread-safety bug in `SessionManager.allocate_turn_index`: concurrent threads in `/api/storyboard/draft-batch` inspected `session.turns` before `add_turn` completed, allocating duplicate `turn_index` values.

---

## Implemented Optimizations

- **Forwarded `mock_mode` & Lazy Module `app` (`src/omnimash/api/app.py`):**
  - Passed `mock_mode=is_mock` to `deconstruct_screenplay_with_adk`.
  - Replaced top-level `app = create_app()` with PEP 562 module `__getattr__("app")` lazy initialization.
- **Fast Procedural Fallback & Atomic File Writes (`src/omnimash/engine/omni_client.py`):**
  - Replaced the 240-frame `zoompan` filter with `scale=1280:720,fps=24,setpts=PTS-STARTPTS`, `duration: int = 1`, and `-preset ultrafast` (`33.7s -> 0.95s`, a **35x speedup** while still producing >700KB valid H.264/AAC MP4s).
  - Added `.tmp.<uuid>` + `os.replace()` atomic file replacement in `ensure_rendered_video` and `_generate_dynamic_audio_wav` to prevent multi-worker file races.
- **Shared GCS Client Cache & Lazy Bucket Handle (`src/omnimash/storage/gcs.py`, `src/omnimash/agent/orchestrator.py`):**
  - Added `_SHARED_CLIENTS` per-project cache on `GcsStorageManager` and replaced blocking `lookup_bucket` in `__init__` with lightweight `self._client.bucket(self.bucket_name)` (`ensure_bucket_exists()` remains available for explicit checks).
  - Shared `self.storage` across `OmniMashAgent`, `OmniFlashClient`, `MediaExtractor`, and `VideoStitcher`.
  - Lazily initialized `_orchestrator` inside `build_adk_agent`.
- **Thread-Safe Monotonic Turn Index Allocation (`src/omnimash/state/session_manager.py`):**
  - Added `threading.RLock()` and `_last_allocated_turn_index` tracking on `ProjectSession` so concurrent `ThreadPoolExecutor` workers in `/api/storyboard/draft-batch` always receive unique, strictly increasing turn indices.
- **Parallel Execution (`pytest-xdist`) & Pytest Markers (`pyproject.toml`, `tests/api/test_app.py`):**
  - Added `pytest-xdist` with `addopts = "-n auto"`.
  - Registered `@pytest.mark.slow` and `@pytest.mark.browser` on `test_ui_html_renders_in_browser_without_syntax_error` (deselectable via `uv run pytest -m "not browser"` for sub-12s inner-loop runs).
