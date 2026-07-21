# Authenticated GCS Media Proxy & Full Character State Preservation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 
1. Enable directors to use convenient `gs://...` URIs (e.g., `gs://omnimash-media-hybrid-vertex/saved_characters/harry_drip.jpeg`) for character reference images while ensuring they render crisp and 100% reliably in browser `<img>` tags via an authenticated backend media proxy (`GET /api/media-proxy?uri=gs://...`) without needing public bucket permissions.
2. Ensure full character state preservation (`name`, `description`, `reference_url`, `voice_style`, `aesthetic_tags`) across both Global Vault presets (`library/characters/<slug>.json`) and Per-Session Cast Rosters (`sessions/{session_name}/characters/roster.json`).

**Architecture:**
1. **Authenticated GCS Media Proxy (`src/omnimash/storage/gcs.py` & `src/omnimash/api/app.py`)**:
   - **GCS Storage Manager**: Add `download_blob_bytes(self, gs_uri: str) -> tuple[bytes, str]` to fetch binary data and content type using authenticated `google.cloud.storage.Client` credentials.
   - **FastAPI Proxy Endpoint**: Add `GET /api/media-proxy?uri=gs://...` to stream image bytes to the client with `Cache-Control: public, max-age=86400` headers.
   - **React Studio UI**: Update `getDisplayableRefUrl(url)` in `UI_HTML` to return `/api/media-proxy?uri=${encodeURIComponent(url)}` for `gs://` links.
2. **Full Character Field Serialization & Restoration (`src/omnimash/storage/gcs.py` & `src/omnimash/api/app.py`)**:
   - Verify that `save_vault_character` and `save_session_roster` persist all 5 character attributes (`name`, `description`, `reference_url`, `voice_style`, `aesthetic_tags`).
   - Update React `handleLoadVaultCharacter` and `handleLoadSessionRoster` to populate all 5 character card state fields when loading presets or restoring cast rosters.
3. **Integration & API Tests (`tests/storage/test_gcs.py`, `tests/api/test_app.py`, `tests/api/test_integration.py`)**:
   - Add test cases verifying proxy streaming for `gs://` URIs and full character attribute persistence.

**Tech Stack:** Python 3.12, FastAPI, React 18, Google Cloud Storage Client SDK, pytest, uv, ruff, ty.

---

## User Review Required

> [!IMPORTANT]
> **Key User Experience Highlights**:
> 1. **Convenient `gs://` URIs**: Type any `gs://bucket/path.jpg` URI. The backend `/api/media-proxy` streams the image directly to the browser using authenticated service account credentials without requiring public bucket ACLs.
> 2. **Complete Character Preservation**: Saving a character card to the Vault or saving a session roster preserves 100% of the character's description, reference image, voice style, and aesthetic signifiers.

---

## Proposed Changes

### Storage Layer

#### [MODIFY] `src/omnimash/storage/gcs.py`
- Add `download_blob_bytes(self, gs_uri: str) -> tuple[bytes, str]`:
```python
def download_blob_bytes(self, gs_uri: str) -> tuple[bytes, str]:
    """Downloads binary blob data and content type for a gs:// URI using authenticated credentials."""
    if not gs_uri or not gs_uri.startswith("gs://"):
        return b"", "image/jpeg"
    clean = gs_uri.replace("gs://", "")
    parts = clean.split("/", 1)
    bucket_name = parts[0]
    blob_name = parts[1] if len(parts) > 1 else ""

    if self.mock_mode or not self._client:
        return b"", "image/jpeg"

    try:
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        content_type = blob.content_type or "image/jpeg"
        if blob_name.endswith(".png"):
            content_type = "image/png"
        elif blob_name.endswith(".jpeg") or blob_name.endswith(".jpg"):
            content_type = "image/jpeg"
        return blob.download_as_bytes(), content_type
    except Exception:
        return b"", "image/jpeg"
```

---

### Backend API & UI

#### [MODIFY] `src/omnimash/api/app.py`
- Add endpoint `/api/media-proxy`:
```python
@app.get("/api/media-proxy")
def media_proxy(uri: str) -> Response:
    if not uri or not uri.startswith("gs://"):
        raise HTTPException(status_code=400, detail="Invalid gs:// URI")
    data, content_type = agent.storage.download_blob_bytes(uri)
    if not data:
        raise HTTPException(status_code=404, detail="Media not found or unreadable")
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
```
- Update `getDisplayableRefUrl` in `UI_HTML`:
```javascript
const getDisplayableRefUrl = (url) => {
    if (!url) return "";
    if (url.startsWith("gs://")) {
        return `/api/media-proxy?uri=${encodeURIComponent(url)}`;
    }
    return url;
};
```
- Update `handleLoadVaultCharacter` in `UI_HTML` to restore all fields:
```javascript
const handleLoadVaultCharacter = (c) => {
    const nextRoleLetter = String.fromCharCode(65 + characters.length);
    const newRole = {
        role_id: `Role ${nextRoleLetter}`,
        name: c.name || `Role ${nextRoleLetter}`,
        description: c.description || "",
        reference_url: c.reference_url || null,
        voice_style: c.voice_style || "",
        aesthetic_tags: c.aesthetic_tags || []
    };
    setCharacters([...characters, newRole]);
};
```

---

## Bite-Sized Execution Tasks

### Task 1: Implement download_blob_bytes in GCS Manager & Storage Tests
- Update `src/omnimash/storage/gcs.py` with `download_blob_bytes`.
- Add test assertions in `tests/storage/test_gcs.py`.
- Run `uv run pytest tests/storage/test_gcs.py`.

### Task 2: Add /api/media-proxy Endpoint & Update UI Loading Handlers in app.py
- Add `/api/media-proxy` endpoint and update `getDisplayableRefUrl` and `handleLoadVaultCharacter` in `src/omnimash/api/app.py`.
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
2. Attach `gs://omnimash-media-hybrid-vertex/saved_characters/harry_drip.jpeg` to a character role in Act 1.
3. Observe image preview thumbnail rendering crisp and clean in the Character Role card and Character Vault chip toolbar.
4. Click **Save to Vault**, clear character cards, click the Vault chip, and verify all description text, reference image, voice style, and aesthetic tags are completely restored!
