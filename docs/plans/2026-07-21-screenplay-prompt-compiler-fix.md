# Screenplay Mode Prompt Compiler Fix Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update `PromptCompiler.compile_multi_role_prompt` to process `scene.screenplay_text` when present, formatting screenplay scripts into `[STORYBOARD SEQUENCE]` and extracting audio cues into `[AUDIO & VOCAL DIRECTION]`.

---

## 📋 Execution Plan

### 1. 📜 Screenplay Prompt Compilation (`src/omnimash/prompts/compiler.py`)
- **Requirement**: Support `scene.screenplay_text` inside `compile_multi_role_prompt`.
- **Implementation**:
  - In `src/omnimash/prompts/compiler.py`:
    - In `compile_multi_role_prompt(...)`:
      - Iterate through `scenes`.
      - If `scene.screenplay_text` is set:
        - Parse screenplay text via `parse_screenplay_script(scene.screenplay_text, characters=characters)`.
        - Extract parenthetical audio cues and add to `audio_parts`.
        - Format scene sequence line as:
          `- Scene N [Roles] (Screenplay):\n  script_line_1\n  script_line_2...`
      - Else: format standard `scene.action` and `scene.dialogue`.

### 2. 🧪 Unit & Integration Testing
- In `tests/prompts/test_compiler.py`:
  - Add test `test_compile_multi_role_prompt_with_screenplay_text` verifying `compile_multi_role_prompt` includes screenplay script text and extracted audio cues.
- Run `uv run pytest`.

---

## Tech Stack & Tools
Python 3.12, FastAPI, pytest, uv, ruff, ty.

---

## Execution Tasks

### Task 1: Update PromptCompiler compile_multi_role_prompt
- Update `compile_multi_role_prompt` in `src/omnimash/prompts/compiler.py` to handle `scene.screenplay_text`.
- Add test in `tests/prompts/test_compiler.py`.
- Run `uv run pytest tests/prompts/test_compiler.py`.

### Task 2: Full Verification & Quality Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).
