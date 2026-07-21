# Authenticated GCS Media Proxy, Character State Preservation & Thread Isolation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 
1. **Fix Saved Character Display Names (`src/omnimash/api/app.py`)**: Remove auto-injected aesthetic tags in quotes from character chip display names.
2. **Authenticated GCS Media Proxy (`GET /api/media-proxy?uri=gs://...`)**: Enable directors to use convenient `gs://...` URIs for character reference images while ensuring they render crisp and 100% reliably in browser `<img>` tags via an authenticated backend media proxy without needing public bucket permissions.
3. **Full Character State Preservation**: Ensure complete character state preservation (`name`, `description`, `reference_url`, `voice_style`, `aesthetic_tags`) across both Global Vault presets (`library/characters/<slug>.json`) and Per-Session Cast Rosters (`sessions/{session_name}/characters/roster.json`).
4. **Thread Isolation & Clean Voiceover Fallback**: Ensure that starting a new concept, deconstructing a concept, or starting a new session resets `parentTurnId = null` so Gemini Omni Flash starts a fresh, isolated interaction thread instead of continuing prior video threads. Also remove legacy hardcoded voiceover fallbacks in `ensure_rendered_video`.

**Architecture:**
1. **Clean Character Display Name Formatting (`src/omnimash/api/app.py`)**:
   - Update character vault chip text generation: `const chipText = c.name || c.role_id || Preset ${vIdx + 1};`.
2. **Authenticated GCS Media Proxy (`src/omnimash/storage/gcs.py` & `src/omnimash/api/app.py`)**:
   - Add `download_blob_bytes` to `GcsStorageManager`.
   - Add `GET /api/media-proxy?uri=gs://...` endpoint returning binary image bytes with `Cache-Control: public, max-age=86400`.
   - Update `getDisplayableRefUrl(url)` in `UI_HTML` to route `gs://` links through `/api/media-proxy`.
3. **Full Character Field Serialization & Restoration (`src/omnimash/storage/gcs.py` & `src/omnimash/api/app.py`)**:
   - Ensure all 5 character attributes are persisted and restored when loading vault presets or session rosters.
4. **Thread Isolation & Voiceover Fallback Fix (`src/omnimash/api/app.py` & `src/omnimash/engine/omni_client.py`)**:
   - In `UI_HTML`: Reset `parentTurnId = null` and `rawCompiledPrompt = ""` when `deconstruct_concept` runs or when resetting studio workspace.
   - In `omni_client.py`: Remove legacy hardcoded `"Trapwarts / Draco"` default voiceover fallback in `ensure_rendered_video`.

**Tech Stack:** Python 3.12, FastAPI, React 18, Google Cloud Storage Client SDK, pytest, uv, ruff, ty.

---

## User Review Required

> [!IMPORTANT]
> **Key Fixes & Enhancements**:
> 1. **Clean Display Names**: Character preset chips show strictly the character's clean `name`.
> 2. **Convenient `gs://` URIs**: Type any `gs://bucket/path.jpg` URI. The backend `/api/media-proxy` streams the image directly to the browser using authenticated service account credentials.
> 3. **Complete Character Preservation**: Saving a character card to the Vault or saving a session roster preserves 100% of the character's description, reference image, voice style, and aesthetic signifiers.
> 4. **Thread Isolation**: Starting a new concept or resetting the studio clears `parentTurnId` so new videos start fresh unlinked threads.

---

## Bite-Sized Execution Tasks

### Task 1: Fix Display Name Chip Logic & Implement download_blob_bytes in GCS Manager
- Update `chipText` formatting in `src/omnimash/api/app.py`.
- Add `download_blob_bytes` in `src/omnimash/storage/gcs.py`.
- Add test cases in `tests/storage/test_gcs.py`.
- Run `uv run pytest tests/storage/test_gcs.py`.

### Task 2: Add /api/media-proxy Endpoint & Update UI Loading Handlers in app.py
- Add `/api/media-proxy` route and update `getDisplayableRefUrl` and `handleLoadVaultCharacter` in `src/omnimash/api/app.py`.
- Add test assertions in `tests/api/test_app.py` and `tests/api/test_integration.py`.
- Run `uv run pytest tests/api/test_app.py tests/api/test_integration.py`.

### Task 3: Implement Thread Isolation & Clean Voiceover Fallback
- Reset `parentTurnId` and `rawCompiledPrompt` on concept deconstruction and studio reset in `src/omnimash/api/app.py`.
- Update fallback voiceover handling in `src/omnimash/engine/omni_client.py`.
- Add test assertions in `tests/api/test_app.py` and `tests/engine/test_omni_client.py`.
- Run `uv run pytest`.

### Task 4: Full Verification & Quality Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).

---

## Verification Plan

### Automated Tests
- Storage tests: `uv run pytest tests/storage/test_gcs.py`
- Engine tests: `uv run pytest tests/engine/test_omni_client.py`
- API & Integration tests: `uv run pytest tests/api/test_app.py tests/api/test_integration.py`
- Full test suite: `uv run pytest`

### Manual Verification
1. Run local dev server (`uv run python -m omnimash.api.app`).
2. Verify `parentTurnId` is reset to null when clicking **✨ Deconstruct Concept**.
3. Generate a video for a new concept (e.g. *Gordon Ramsay vs Julia Child*) and confirm no dialogue or characters from earlier videos are reused!
