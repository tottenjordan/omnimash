# Screenplay Scripting & Global/Local Context Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement clean separation of **Global Production Context** (Act 1: Cast Roster, Environment, Aesthetic) vs. **Local 10-Second Shot Directing** (Act 2: Screenplay Script Mode supporting `Character: (Action/Audio) "Dialogue"`), allowing directors to direct 10s video clips via natural screenplay formatting.

**Tech Stack:** Python 3.12, FastAPI, React 18, pytest, uv, ruff, ty.

---

## Bite-Sized Execution Tasks

### Task 1: Screenplay Script Parser Engine in Backend & Unit Tests
- Create `ScreenplayParser` in `src/omnimash/prompts/compiler.py`:
  - Parses multi-line screenplay text: `Character: (Action/Audio) "Dialogue"`.
  - Maps character names to role IDs (`Role A`, `Role B`, etc.).
  - Extracts visual actions, audio FX cues, and spoken dialogue lines.
- Add unit tests in `tests/prompts/test_compiler.py`.
- Run `uv run pytest tests/prompts/test_compiler.py`.

### Task 2: Act 1 & Act 2 UI Scope Clarification & Screenplay Mode Toggle in app.py
- Update Act 1 header label: **"🌐 Global Production Context (Applies to All Shots)"**.
- Update Act 2 header label: **"🎬 Storyboard & Shot Director (10-Second Clips)"**.
- Add **Screenplay Mode** toggle to Scene Cards in Act 2:
  - Guided Mode (Default): Action input + Dialogue input.
  - Screenplay Mode: Multi-line screenplay text box supporting `Character: (Action) "Dialogue"`.
- Update prompt compiler logic to compile screenplay text seamlessly into Gemini Omni Flash prompts.
- Add test assertions in `tests/api/test_integration.py`.

### Task 3: Full Verification & Quality Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).
