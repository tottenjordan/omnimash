# Interactive GCS Session Folder Selector & Listing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable directors to list, select, or create GCS session folders (`gs://<bucket_name>/sessions/{session_id}/`) directly from an interactive header dropdown in OmniMash, replacing the static hardcoded `"parody_session_1"` default.

**Why Needed:**
`sessionName` previously defaulted to `"parody_session_1"`, requiring manual typing to switch sessions. Directors need to select existing session folders from GCS or generate new session folders with 1 click.

**Architecture:**
1. **GCS Storage Manager (`src/omnimash/storage/gcs.py`)**:
   - Add `list_session_ids(self) -> list[str]` to inspect `sessions/` prefixes in GCS or return mock sessions (`["parody_session_1", "session_8492", "dripwarts_battle"]`).
2. **FastAPI Backend Endpoint (`src/omnimash/api/app.py`)**:
   - Add GET endpoint `/api/sessions` returning `{"sessions": list[str]}`.
3. **React Studio UI Header (`src/omnimash/api/app.py`)**:
   - Fetch `/api/sessions` on mount in `useEffect`.
   - Render a **📂 Existing GCS Session Dropdown (`<select>`)** and **➕ New Session Button** in the Act 1 header toolbar.
   - Selecting a session from the dropdown updates `sessionName` and automatically triggers `handleLoadSessionRoster` to restore that session's cast roster.
4. **Integration & API Tests (`tests/storage/test_gcs.py`, `tests/api/test_app.py`, `tests/api/test_integration.py`)**:
   - Add test coverage for `list_session_ids`, `/api/sessions`, and UI session selection dropdown.

**Tech Stack:** Python 3.12, FastAPI, React 18, Google Cloud Storage Client SDK, pytest, uv, ruff, ty.

---

## Bite-Sized Execution Tasks

### Task 1: Add list_session_ids in GcsStorageManager & Storage Unit Tests
- Add `list_session_ids(self) -> list[str]` in `src/omnimash/storage/gcs.py`.
- Add test assertions in `tests/storage/test_gcs.py`.
- Run `uv run pytest tests/storage/test_gcs.py`.

### Task 2: Add GET /api/sessions Endpoint & Update UI Session Selector in app.py
- Add GET endpoint `/api/sessions` in `src/omnimash/api/app.py`.
- Update `UI_HTML` header toolbar with session dropdown selector, new session button, and auto-load roster trigger.
- Add test assertions in `tests/api/test_app.py` and `tests/api/test_integration.py`.
- Run `uv run pytest tests/api/test_app.py tests/api/test_integration.py`.

### Task 3: Full Verification & Quality Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).

---

## Verification Plan

### Automated Tests
- Storage tests: `uv run pytest tests/storage/test_gcs.py`
- API & Integration tests: `uv run pytest tests/api/test_app.py tests/api/test_integration.py`
- Full test suite: `uv run pytest`

### Manual Verification
1. Run local dev server (`uv run python -m omnimash.api.app`).
2. Observe session dropdown in top navigation bar populated with GCS session folders.
3. Select an existing session and verify its cast roster is automatically loaded!
4. Click **➕ New Session** and verify a fresh timestamped session ID is generated!
