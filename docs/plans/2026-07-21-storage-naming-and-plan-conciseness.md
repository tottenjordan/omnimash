# Storage Naming Alignment & Plan Conciseness Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Address 4 key points of feedback regarding GCS/local storage file naming consistency for final masters and intermediate turns, and establish conciseness rules for plan file naming.

---

## 📋 Four-Point Execution Plan

### 1. 🎞️ Final Master Prompt Companion File (`save_final_master`)
- **Requirement**: When saving a video to `final_masters/` (e.g. `official_rap_battle_master.mp4`), automatically save its compiled prompt JSON alongside it using the matching base name (`official_rap_battle_master_prompt.json`).
- **Implementation**:
  - Update `save_final_master` in `src/omnimash/agent/orchestrator.py` and `src/omnimash/storage/gcs.py` to accept optional `raw_compiled_prompt: str | None = None` or `prompt_data: dict | str`.
  - When saving `final_masters/{master_title}.mp4`, write `final_masters/{master_title}_prompt.json` containing the compiled prompt string/dict.

### 2. 🧩 Intermediate Video & Prompt Naming Convention Alignment
- **Requirement**: Ensure intermediate video file names strictly match their prompt naming convention (`turn_0_video.mp4` and `turn_0_prompt.json`).
- **Implementation**:
  - Standardize intermediate video naming in `GcsStorageManager.upload_file` and `OmniMashAgent._execute_turn_generation` to `turn_{turn_index}_video.mp4` (matching `turn_{turn_index}_prompt.json`).

### 3. 📏 Rule for Concise Plan File Titles
- **Requirement**: Create an explicit rule for naming plan files: `YYYY-MM-DD-short-title.md` (keep date, max 3-4 words total after date).
- **Implementation**:
  - Add Rule to `user_rules` and `docs/` naming conventions:
    > "Plan files must follow `YYYY-MM-DD-short-descriptive-title.md` format (date + maximum 3 to 4 words total after the date)."

### 4. 🧹 Rename Existing Long Plan File Titles
- **Requirement**: Simplify existing long plan filenames in `docs/plans/` to short, intuitive titles.
- **Renames to Perform**:
  - `2026-07-21-authenticated-gcs-media-proxy-and-character-preservation.md` $\rightarrow$ `2026-07-21-gcs-media-proxy.md`
  - `2026-07-21-authenticated-gcs-media-proxy-for-ref-images.md` $\rightarrow$ `2026-07-21-ref-image-proxy.md`
  - `2026-07-20-prompt-visibility-character-styles-and-screening-room-workflows.md` $\rightarrow$ `2026-07-20-prompt-visibility.md`
  - `2026-07-20-gemini-omni-prompt-guide-voiceover-and-audio-direction.md` $\rightarrow$ `2026-07-20-voiceover-audio-guide.md`
  - `2026-07-21-screenplay-scripting-and-global-vs-local-context.md` $\rightarrow$ `2026-07-21-screenplay-scripting.md`
  - `2026-07-21-explicit-gcs-session-name-preservation.md` $\rightarrow$ `2026-07-21-gcs-session-preservation.md`
  - `2026-07-21-unique-role-id-allocation-fix.md` $\rightarrow$ `2026-07-21-unique-role-ids.md`

---

## Tech Stack & Tools
Python 3.12, GCS Storage Client, FastAPI, pytest, uv, ruff, ty.

---

## Execution Tasks

### Task 1: Update Storage Manager & Orchestrator for 1:1 Final Master Prompts & Intermediate Turn Naming
- Update `save_final_master` in `src/omnimash/storage/gcs.py` to write `{master_title}_prompt.json` alongside `{master_title}.mp4`.
- Standardize intermediate video naming to `turn_{index}_video.mp4` matching `turn_{index}_prompt.json`.
- Add test assertions in `tests/storage/test_gcs.py` and `tests/agent/test_orchestrator.py`.
- Run `uv run pytest tests/storage/test_gcs.py tests/agent/test_orchestrator.py`.

### Task 2: Simplify Existing Plan Titles & Establish Naming Convention Rule
- Rename oversized plan files in `docs/plans/` via `git mv`.
- Update naming convention guidance in `docs/`.
- Run `uv run pytest`.

### Task 3: Full Verification & Quality Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).
