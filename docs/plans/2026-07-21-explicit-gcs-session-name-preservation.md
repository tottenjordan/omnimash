# Explicit GCS Session Name Preservation & Character Reference Image Rendering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 
1. Ensure that the GCS folder name and session ID (`session_name` / `session_id`) remain strictly fixed and preserved across all studio operations and ONLY change when explicitly edited by the user.
2. Render visual reference image preview thumbnails for saved Character Roles in the Character Vault chip toolbar and inside each Character Role card whenever a valid `reference_url` is present.

**Architecture:**
1. **Saved Character Reference Image Rendering (`src/omnimash/api/app.py`)**:
   - **Character Role Card Preview**: On each Character Role card in Act 1, render a visual thumbnail preview container (`<img src="..." />`) for any attached `reference_url` (handling `https://`, `http://`, and mapping `gs://` URIs to public GCS gateway URLs `https://storage.googleapis.com/...`).
   - **Character Vault Preset Chips**: Inside the **🏛️ Character Vault & Saved Library** toolbar, render a miniature rounded avatar image thumbnail next to each saved character preset chip when a reference image exists.
2. **React Studio Session State (`src/omnimash/api/app.py`)**:
   - Update `handleResetStudio` to preserve the user's explicit `sessionName` state across resets so starting over clears concept/scenes/history while retaining the user's explicit GCS session folder binding.
   - Format the GCS Session input field in the top header toolbar (`🗂️ GCS Session Folder: <input />`) with explicit path feedback.
3. **Session Manager & Storage Layer (`src/omnimash/state/session_manager.py` & `src/omnimash/storage/gcs.py`)**:
   - Verify path idempotency for session blob paths.
4. **Integration Tests (`tests/api/test_integration.py`)**:
   - Add test assertions for reference image rendering in vault chips and character cards, and verify session name immutability.

**Tech Stack:** Python 3.12, FastAPI, React 18, Tailwind CSS, pytest, uv, ruff, ty.

---

## User Review Required

> [!IMPORTANT]
> **Key Enhancements**:
> 1. **Saved Character Image Thumbnails**: Character cards and Character Vault chip badges in Act 1 will visually render thumbnail images for any saved `reference_url`.
> 2. **Session Name Preservation Rule**: Clicking **🔄 New Project / Start Over** clears prompt state but **KEEPS** the user's explicit GCS session folder name intact.

---

## Proposed Changes

### React Studio UI & Image Rendering

#### [MODIFY] `src/omnimash/api/app.py`
- Helper function for displayable reference URLs:
```javascript
const getDisplayableRefUrl = (url) => {
    if (!url) return null;
    if (url.startsWith("gs://")) {
        // Map gs://bucket/path to public storage gateway URL for browser rendering
        const parts = url.replace("gs://", "").split("/");
        const bucket = parts.shift();
        return `https://storage.googleapis.com/${bucket}/${parts.join("/")}`;
    }
    return url;
};
```
- Render avatar thumbnails in Character Vault chip toolbar:
```html
<button
    key={vIdx}
    type="button"
    onClick={() => handleLoadVaultCharacter(c)}
    className="bg-purple-950/70 hover:bg-purple-900 text-purple-200 border border-purple-800/80 hover:border-purple-500 text-xs px-2.5 py-1.5 rounded-lg flex items-center gap-2 transition shadow-sm"
>
    {getDisplayableRefUrl(c.reference_url) && (
        <img
            src={getDisplayableRefUrl(c.reference_url)}
            alt={c.name}
            className="w-4 h-4 rounded-full object-cover border border-purple-400/60"
            onError={(e) => e.target.style.display = "none"}
        />
    )}
    <span>+</span>
    <span>{chipText}</span>
</button>
```
- Render reference image preview thumbnail inside Character Role card:
```html
{char.reference_url && (
    <div className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-lg p-2 mt-1">
        <img
            src={getDisplayableRefUrl(char.reference_url)}
            alt={char.name || char.role_id}
            className="w-10 h-10 rounded-lg object-cover border border-purple-500/50 bg-black flex-shrink-0"
            onError={(e) => e.target.style.display = "none"}
        />
        <div className="text-[10px] font-mono text-gray-400 overflow-hidden text-ellipsis">
            <span className="text-purple-300 font-bold block">Linked Image Role:</span>
            <span className="text-gray-300 break-all">{char.reference_url}</span>
        </div>
    </div>
)}
```
- Preserve `sessionName` in `handleResetStudio`:
```javascript
const handleResetStudio = () => {
    // Keep sessionName intact across resets
    setConcept("");
    setCharacters([]);
    setAestheticTags([]);
    setEnvironmentTag("");
    setCameraLightingTag("");
    setAudioBeat("");
    setVocalDelivery("");
    setScenes([]);
    setHistory([]);
    setParentTurnId("");
    setDeltaPrompt("");
    setRawCompiledPrompt("Ready for new concept deconstruction.");
    setActiveAct(1);
};
```

---

### Integration Tests

#### [MODIFY] `tests/api/test_integration.py`
- Add test assertions in `test_dashboard_ui_html_features` verifying:
  - Reference image thumbnail rendering helper and `Linked Image Role` containers in `UI_HTML`.
  - Session name preservation behavior.

---

## Bite-Sized Execution Tasks

### Task 1: Implement Reference Image Thumbnail Rendering & Session Name Preservation in app.py
- Update `UI_HTML` in `src/omnimash/api/app.py` with `getDisplayableRefUrl`, card thumbnails, vault chip avatars, and updated `handleResetStudio`.
- Update `tests/api/test_integration.py` with image rendering assertions.
- Run `uv run pytest tests/api/test_integration.py`.

### Task 2: Update Screenshot Generator Script & README.md
- Update `scratch/render_readme_screenshots.py` to render reference image thumbnails in Act 1 mockups.
- Run `uv run python3 scratch/render_readme_screenshots.py` to update `imgs/`.

### Task 3: Full Verification & Test Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).

---

## Verification Plan

### Automated Tests
- Integration tests: `uv run pytest tests/api/test_integration.py`
- Full test suite: `uv run pytest`

### Manual Verification
1. Run local dev server (`uv run python -m omnimash.api.app`).
2. Open Act 1: observe character preset chips (*Harry "Gucci"*, *Young Draco "Jeezy"*, etc.) rendering circular image avatar thumbnails.
3. Observe Character Role cards displaying a crisp 10x10 image preview box for attached reference URLs.
4. Type custom session name `my_explicit_folder_v1`, click **New Project / Start Over**, and verify session name remains fixed.
