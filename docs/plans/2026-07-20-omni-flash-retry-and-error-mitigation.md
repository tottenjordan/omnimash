# Gemini Omni Flash Retry Loop, Error Mitigation, and Zero-Veo Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate all Veo model fallbacks, implement a robust multi-strategy authentication and exponential backoff retry loop for Gemini Omni Flash (`gemini-omni-flash-preview`), actively mitigate API generation errors (401 unauthenticated, 404 endpoint mismatch, 429 rate limit), and surface all generation errors to API responses and the frontend UI.

**Architecture:** 
1. Remove all references to `veo-2.0-generate-001` and `_generate_live_veo_video`.
2. Implement dual-client multi-strategy initialization in `OmniFlashClient` (Google AI Studio Developer API key vs Vertex AI ADC token).
3. Add a 3-attempt exponential backoff retry loop with automatic authentication & endpoint error mitigation in `_generate_live_omni_flash_video`.
4. Capture and surface exact error messages in `GenerationResult`, `AgentTurnResponse`, `GenerateResponse`, and the React 18 UI error banner.

**Tech Stack:** Python 3.12, Google GenAI SDK (`google.genai`), FastAPI, Pydantic, React 18 / Tailwind CSS, Pytest, Ruff, Ty.

---

### Task 1: Remove Veo Fallback & Overhaul Gemini Omni Flash Multi-Strategy Auth

**Files:**
- Modify: `src/omnimash/engine/omni_client.py`
- Test: `tests/engine/test_omni_client.py`

**Step 1: Write the failing test**
In `tests/engine/test_omni_client.py`, add tests verifying:
1. `OmniFlashClient` has no `_generate_live_veo_video` method or Veo references.
2. `OmniFlashClient` initializes with both Developer API key mode and Vertex AI mode support.

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/engine/test_omni_client.py -v`

**Step 3: Implement minimal code**
In `src/omnimash/engine/omni_client.py`:
- Remove `_generate_live_veo_video` completely.
- Update `OmniFlashClient.__init__` to store and configure clients for both Google AI Studio (API Key) and Vertex AI (ADC token).

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/engine/test_omni_client.py -v`

**Step 5: Commit**
```bash
git add src/omnimash/engine/omni_client.py tests/engine/test_omni_client.py
git commit -m "feat(engine): remove veo fallback and implement dual-strategy gemini omni flash auth"
```

---

### Task 2: Implement Exponential Backoff Retries, Error Mitigation, and Error Capture

**Files:**
- Modify: `src/omnimash/engine/omni_client.py`
- Test: `tests/engine/test_omni_client.py`

**Step 1: Write the failing test**
In `tests/engine/test_omni_client.py`, add tests for:
1. Exponential backoff retry loop executing 3 attempts on transient errors.
2. Error mitigation switching from Vertex AI to Developer API on 401 UNAUTHENTICATED.
3. `GenerationResult` capturing `error_message` and `generation_mode` ("LIVE_OMNI_FLASH" or "LOCAL_FALLBACK").

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/engine/test_omni_client.py -v`

**Step 3: Implement minimal code**
In `src/omnimash/engine/omni_client.py`:
- Add exponential backoff retry loop in `_generate_live_omni_flash_video`.
- Implement active error mitigation (handling 401, 404, 429).
- Update `generate_clip`, `apply_interaction_diff`, and `start_thread_from_video` to populate `GenerationResult.error_message` and `GenerationResult.generation_mode`.

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/engine/test_omni_client.py -v`

**Step 5: Commit**
```bash
git add src/omnimash/engine/omni_client.py tests/engine/test_omni_client.py
git commit -m "feat(engine): add exponential backoff retries and error mitigation for omni flash"
```

---

### Task 3: Surface Generation Errors in Agent Orchestrator & FastAPI Endpoints

**Files:**
- Modify: `src/omnimash/agent/orchestrator.py`
- Modify: `src/omnimash/api/app.py`
- Test: `tests/api/test_concept_api.py`
- Test: `tests/agent/test_orchestrator.py`

**Step 1: Write the failing test**
In `tests/api/test_concept_api.py`, verify `POST /api/generate` response payload includes `error` (when present) and `generation_mode`.

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/api/test_concept_api.py -v`

**Step 3: Implement minimal code**
- In `src/omnimash/agent/orchestrator.py`, update `AgentTurnResponse` to include `error_message` and `generation_mode`.
- In `src/omnimash/api/app.py`, update `GenerateResponse` to include `error` and `generation_mode`.

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/api/test_concept_api.py tests/agent/test_orchestrator.py -v`

**Step 5: Commit**
```bash
git add src/omnimash/agent/orchestrator.py src/omnimash/api/app.py tests/api/test_concept_api.py tests/agent/test_orchestrator.py
git commit -m "feat(api): surface omni flash generation errors and mode in turn responses"
```

---

### Task 4: Update UI Error Banner & Generation Mode Indicator in React Frontend

**Files:**
- Modify: `src/omnimash/api/app.py`

**Step 1: Write/Update frontend rendering code**
In `src/omnimash/api/app.py` (`UI_HTML`):
- Add a Generation Status banner in Act 3 ("The Screening Room").
- If `generation_mode == "LOCAL_FALLBACK"` or `error` is present, render an alert banner detailing the exact Gemini Omni Flash error and mitigation steps.

**Step 2: Verification**
Run: `uv run ruff check --fix . && uv run ruff format . && uv run ty check . && uv run pytest`

**Step 3: Commit**
```bash
git add src/omnimash/api/app.py
git commit -m "feat(ui): add live gemini omni flash status badge and error mitigation banner"
```

---

### Task 5: Refresh Documentation & Architecture Notes

**Files:**
- Modify: `docs/notes/request_lifecycle.md`
- Modify: `docs/notes/architecture_omnimash.md`
- Modify: `README.md`

**Step 1: Update documentation**
- Remove Veo fallback references.
- Document exponential backoff retries, dual-strategy auth (Developer API key vs Vertex AI ADC), and error surfacing.

**Step 2: Verification**
Run: `uv run ruff check --fix . && uv run ruff format . && uv run ty check . && uv run pytest`

**Step 3: Commit**
```bash
git add docs/ README.md
git commit -m "docs: document zero-veo policy, exponential retries, and omni flash error mitigation"
```
