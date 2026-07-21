# Custom Session Naming & Dynamic Dropdown Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable directors to type or prompt for custom session names (e.g. `dripwarts_battle`, `iron_chef_parody`) when creating a new GCS session, automatically synchronizing custom names into the header dropdown list.

**Why Needed:**
The "+ New Session" button previously auto-generated raw numeric timestamps (`session_1784656400000`) without prompting the user for a human-readable custom name.

**Proposed Changes:**
1. **Custom Session Prompt/Input (`src/omnimash/api/app.py`)**:
   - Update **"+ New Session"** handler:
     ```javascript
     const handleCreateNewSession = () => {
         const userInput = window.prompt("Enter new GCS session folder name:", "");
         if (userInput === null) return; // User cancelled
         const cleanName = userInput.trim().toLowerCase().replace(/[^a-z0-9_-]/g, "_") || `session_${Date.now()}`;
         setSessionName(cleanName);
         setAvailableSessions(prev => prev.includes(cleanName) ? prev : [...prev, cleanName]);
         handleResetStudio();
     };
     ```
2. **Text Field Auto-Sync**:
   - On text input blur or enter key, if the typed session name is not empty, automatically add it to `availableSessions` so it remains selectable in the dropdown.
3. **Integration Tests (`tests/api/test_integration.py`)**:
   - Verify `handleCreateNewSession` and prompt logic in `UI_HTML`.

**Tech Stack:** Python 3.12, FastAPI, React 18, pytest, uv, ruff, ty.

---

## Bite-Sized Execution Tasks

### Task 1: Update UI Session Toolbar in app.py & Integration Tests
- Update `UI_HTML` in `src/omnimash/api/app.py` with custom session creation handler `handleCreateNewSession` and input blur sync.
- Add test assertions in `tests/api/test_integration.py`.
- Run `uv run pytest tests/api/test_integration.py`.

### Task 2: Full Verification & Quality Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).

---

## Verification Plan

### Automated Tests
- Integration tests: `uv run pytest tests/api/test_integration.py`
- Full test suite: `uv run pytest`

### Manual Verification
1. Run local dev server (`uv run python -m omnimash.api.app`).
2. Click **➕ New Session**.
3. Type custom session name `cyberpunk_iron_chef`.
4. Verify `cyberpunk_iron_chef` is set as active session and added to dropdown!
