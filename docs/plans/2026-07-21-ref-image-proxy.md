# Authenticated GCS Media Proxy for Character Reference Images Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to specify convenient `gs://` URIs (e.g., `gs://omnimash-media-hybrid-vertex/saved_characters/harry_drip.jpeg`) for character reference images while ensuring they render crisp and 100% reliably in browser `<img>` elements without requiring GCS buckets to be public.

**Why Images Currently Fail to Render:**
1. Browsers cannot interpret `gs://` custom protocol URIs.
2. Converting `gs://` to direct HTTPS gateway URLs (`https://storage.googleapis.com/...`) fails with **403 Forbidden** because GCS buckets/objects are private by default.

**Architecture & Proposed Fix:**
1. **GCS Storage Manager (`src/omnimash/storage/gcs.py`)**:
   - Add method `download_blob_bytes(self, gs_uri: str) -> tuple[bytes, str]` to fetch binary object data and infer content type using the backend's authenticated GCP service credentials.
2. **FastAPI Backend Endpoint (`src/omnimash/api/app.py`)**:
   - Add GET endpoint `/api/media-proxy?uri=gs://...` returning streaming `Response` with image content bytes and headers (`Cache-Control: public, max-age=86400`).
3. **React Studio UI (`src/omnimash/api/app.py`)**:
   - Update `getDisplayableRefUrl(url)` helper:
     ```javascript
     const getDisplayableRefUrl = (url) => {
         if (!url) return "";
         if (url.startsWith("gs://")) {
             return `/api/media-proxy?uri=${encodeURIComponent(url)}`;
         }
         return url;
     };
     ```
4. **Integration & API Tests (`tests/storage/test_gcs.py` & `tests/api/test_app.py`)**:
   - Add test assertions verifying `download_blob_bytes` and `/api/media-proxy` behavior for `gs://` URIs.

**Tech Stack:** Python 3.12, FastAPI, React 18, Google Cloud Storage Client SDK, pytest, uv, ruff, ty.

---

## User Review Required

> [!IMPORTANT]
> **User Convenience**:
> You can keep typing standard `gs://...` URIs (e.g. `gs://omnimash-media-hybrid-vertex/saved_characters/harry_drip.jpeg`). The backend `/api/media-proxy` will authenticate and stream the image bytes directly to the UI without needing public GCS bucket permissions.

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

---

## Bite-Sized Execution Tasks

### Task 1: Add download_blob_bytes to GCS Manager & Tests
- Add `download_blob_bytes` in `src/omnimash/storage/gcs.py`.
- Add test cases in `tests/storage/test_gcs.py`.
- Run `uv run pytest tests/storage/test_gcs.py`.

### Task 2: Add /api/media-proxy Endpoint & Update UI in app.py
- Add `/api/media-proxy` route and update `getDisplayableRefUrl` in `src/omnimash/api/app.py`.
- Add test assertions in `tests/api/test_app.py` and `tests/api/test_integration.py`.
- Run `uv run pytest tests/api/test_app.py tests/api/test_integration.py`.

### Task 3: Full Verification & Quality Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).

---

## Verification Plan

### Automated Tests
- GCS tests: `uv run pytest tests/storage/test_gcs.py`
- API & Integration tests: `uv run pytest tests/api/test_app.py tests/api/test_integration.py`
- Full test suite: `uv run pytest`

### Manual Verification
1. Run local dev server (`uv run python -m omnimash.api.app`).
2. Attach `gs://omnimash-media-hybrid-vertex/saved_characters/harry_drip.jpeg` to a character role in Act 1.
3. Observe image preview thumbnail rendering crisp and clean in the Character Role card and Character Vault chip toolbar!
