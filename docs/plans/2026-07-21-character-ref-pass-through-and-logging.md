# Character Reference Image Pass-Through & Robust Multimodal Logging Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure character reference images (`char_objs`) are passed through from `OmniMashAgent.process_user_turn` to `omni_client.generate_clip`, and add robust logging to verify base64 image payload attachment in `gemini-omni-flash-preview` calls.

---

## 📋 Execution Plan

### 1. 👥 Character Reference Pass-Through (`src/omnimash/agent/orchestrator.py`)
- **Requirement**: Pass `characters=char_objs` in `self._execute_turn_generation(...)` so character reference URLs reach `OmniFlashClient`.
- **Implementation**:
  - In `src/omnimash/agent/orchestrator.py`:
    - Update `_execute_turn_generation` signature to accept `characters: list[CharacterRole] | None = None`.
    - Pass `characters=char_objs` when invoking `_execute_turn_generation(...)` inside `process_user_turn`.
    - Forward `characters=characters` to `self.omni_client.generate_clip` and `self.omni_client.apply_interaction_diff`.

### 2. 🪵 Robust Multimodal Reference Logging (`src/omnimash/engine/omni_client.py`)
- **Requirement**: Log explicit diagnostic details when character reference images are loaded, base64-encoded, or failed.
- **Implementation**:
  - In `src/omnimash/engine/omni_client.py`:
    - In `_load_reference_images_as_input`:
      - Log `INFO`: `Loaded N reference image(s) for characters: [Role A (Swagrid), Role B (Ice-Vander)]`.
      - Log `WARNING`: `Character Role X (Name) has reference_url '...' but image bytes could not be loaded.`
    - In `_generate_live_omni_flash_video`:
      - Log `INFO`: `Attaching N multimodal base64 reference image(s) to gemini-omni-flash-preview interaction input payload.`

### 3. 🧪 Unit & Integration Testing
- In `tests/agent/test_orchestrator.py` & `tests/engine/test_omni_client.py`:
  - Add test verifying `process_user_turn` passes `characters` to `omni_client.generate_clip`.
  - Add test verifying `_load_reference_images_as_input` logs warning/info correctly.
- Run `uv run pytest`.

---

## Tech Stack & Tools
Python 3.12, FastAPI, GCS Storage Client, pytest, uv, ruff, ty.

---

## Execution Tasks

### Task 1: Update Orchestrator Character Reference Pass-Through
- Update `_execute_turn_generation` in `src/omnimash/agent/orchestrator.py` to accept and pass `characters` to `omni_client`.
- Add test assertions in `tests/agent/test_orchestrator.py`.
- Run `uv run pytest tests/agent/test_orchestrator.py`.

### Task 2: Add Robust Multimodal Reference Logging in OmniClient
- Update `_load_reference_images_as_input` and `_generate_live_omni_flash_video` in `src/omnimash/engine/omni_client.py` with diagnostic logging.
- Add test assertions in `tests/engine/test_omni_client.py`.
- Run `uv run pytest tests/engine/test_omni_client.py`.

### Task 3: Full Verification & Quality Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).
