# Relaxed Safety Settings & Parody Name Abstraction Fix Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure `client.interactions.create` includes `safety_settings=_get_relaxed_safety_settings()` (configured with `BLOCK_NONE` across all harm categories), and expand `_abstract_prompt_for_responsible_ai` with parody character names (`Swagrid`, `Ollivander`, `Ice-Vander`) to prevent false-positive `400 Prohibited Content` policy blocks on Cloud Run.

---

## 📋 Execution Plan

### 1. 🛡️ Relaxed Safety Settings & Parody Abstractions (`src/omnimash/engine/omni_client.py`)
- **Requirement**: Pass `safety_settings` in `kwargs` for `interactions.create`, and abstract `Swagrid`, `Ollivander`, `Ice-Vander`.
- **Implementation**:
  - In `src/omnimash/engine/omni_client.py`:
    - In `_abstract_prompt_for_responsible_ai`:
      - Add `r"\bswagrid\b": "a towering friendly gamekeeper in a fur coat"`.
      - Add `r"\bollivander\b": "an elderly shopkeeper wandmaker wizard"`.
      - Add `r"\bice[- ]vander\b": "an elderly iced-out shopkeeper wandmaker wizard"`.
    - In `_generate_live_omni_flash_video`:
      - Pass `safety_settings = _get_relaxed_safety_settings()` in `kwargs` dictionary for `self._genai_client.interactions.create(**kwargs)`.

### 2. 🧪 Unit & Integration Testing
- In `tests/engine/test_omni_client.py`:
  - Add test `test_generate_live_omni_flash_video_includes_safety_settings` verifying `safety_settings` in `kwargs`.
  - Add test `test_abstract_prompt_handles_parody_names` verifying parody character name replacement.
- Run `uv run pytest`.

---

## Tech Stack & Tools
Python 3.12, FastAPI, Google GenAI SDK, pytest, uv, ruff, ty.

---

## Execution Tasks

### Task 1: Update OmniClient Safety Settings and Abstraction Replacements
- Update `_abstract_prompt_for_responsible_ai` and `_generate_live_omni_flash_video` in `src/omnimash/engine/omni_client.py`.
- Add test cases in `tests/engine/test_omni_client.py`.
- Run `uv run pytest tests/engine/test_omni_client.py`.

### Task 2: Full Verification & Quality Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).
