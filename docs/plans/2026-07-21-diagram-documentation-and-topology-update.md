# Custom Video Clip Selection & Stitching Engine + Diagram Documentation Update Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 
1. Build an explicit **🎬 Stitch & Combine Selected Clips** UI modal in Act 3 and backend REST API (`POST /api/stitch-clips`), allowing directors to visually select, reorder, and concatenate arbitrary subsets of generated video clips from their session timeline into custom master video MP4s exported to GCS.
2. Update all supplementary architectural documentation and Mermaid sequence diagrams in `docs/diagrams/` (`frontend_api_topology.md`, `multimodal_ingestion_stitching.md`, `omnimash_agent_architecture.md`) to reflect the new feature suite.

**Architecture:**
1. **Backend API (`src/omnimash/api/app.py`)**:
   - Model `StitchClipsRequest`: `session_name: str`, `clip_urls: list[str]`, `master_title: str = "custom_stitched_cut"`.
   - Endpoint `POST /api/stitch-clips`: Calls `agent.stitcher.concatenate_clips(clip_urls, session_id=session_name)` and exports to GCS `sessions/{session_name}/final_masters/{master_title}.mp4`.
2. **React Studio UI (`src/omnimash/api/app.py`)**:
   - Act 3 Action Toolbar: Add button **🎬 Stitch & Combine Selected Clips**.
   - Modal `showStitchModal`: Displays checkboxes for all generated turns in the session history (`[x] Turn #1: Scene 1`, `[x] Turn #2: Scene 2`...), input for custom `masterTitle`, and action button **🎬 Concatenate Selected Videos**.
3. **Integration & API Tests (`tests/api/test_app.py` & `tests/api/test_integration.py`)**:
   - Add API route tests for `POST /api/stitch-clips`.
   - Add UI assertion tests verifying the new button and endpoint in `UI_HTML`.
4. **Documentation & Screenshot Generator (`README.md`, `scratch/render_readme_screenshots.py`, `docs/diagrams/`)**:
   - Update `README.md` and `docs/diagrams/frontend_api_topology.md` with `POST /api/stitch-clips`.
   - Update `scratch/render_readme_screenshots.py` and re-render 1600x1000 JPG mockups in `imgs/`.

**Tech Stack:** Python 3.12, FastAPI, React 18, Tailwind CSS, FFmpeg, Headless Chrome, pytest, uv, ruff, ty.

---

## User Review Required

> [!IMPORTANT]
> **New Custom Stitching Feature**:
> Act 3 gains a dedicated **🎬 Stitch & Combine Selected Clips** button and modal. Directors can select individual video clips from their turn history, check/uncheck specific scenes, give the cut a custom title, and click **Concatenate Selected Videos** (`POST /api/stitch-clips`).

---

## Proposed Changes

### Backend REST API

#### [MODIFY] `src/omnimash/api/app.py`
- Add Pydantic model:
```python
class StitchClipsRequest(BaseModel):
    session_name: str
    clip_urls: list[str]
    master_title: str = "custom_stitched_cut"
```
- Add endpoint:
```python
@app.post("/api/stitch-clips", response_model=SaveFinalResponse)
def stitch_selected_clips(req: StitchClipsRequest) -> SaveFinalResponse:
    stitched_path = agent.stitcher.concatenate_clips(
        req.clip_urls, session_id=req.session_name
    )
    _pub_url, gcs_uri = agent.storage.save_final_master(
        session_id=req.session_name,
        source_rel_path=stitched_path,
        master_title=req.master_title,
    )
    return SaveFinalResponse(
        success=True,
        gcs_uri=gcs_uri,
        message=f"Custom stitched master successfully saved to {gcs_uri}",
    )
```

---

### React Studio UI

#### [MODIFY] `src/omnimash/api/app.py`
- Add state: `const [showStitchModal, setShowStitchModal] = useState(false);`
- Add state: `const [selectedClipUrls, setSelectedClipUrls] = useState([]);`
- Add handler `handleStitchSelectedClips()`: calls `POST /api/stitch-clips` with `selectedClipUrls`.
- Add **🎬 Stitch & Combine Selected Clips** button in Act 3 toolbar.
- Render Stitch Modal displaying checkboxes for all turns in `history`.

---

### Integration & API Tests

#### [MODIFY] `tests/api/test_app.py`
- Add `test_api_stitch_selected_clips` verifying custom clip concatenation and GCS export.

#### [MODIFY] `tests/api/test_integration.py`
- Add UI assertions for `Stitch & Combine Selected Clips` and `/api/stitch-clips`.

---

### Documentation & Diagram Updates

#### [MODIFY] `README.md`
- Update Act 3 feature list and step-by-step walkthrough to include custom clip selection & stitching.

#### [MODIFY] `docs/diagrams/frontend_api_topology.md` & `multimodal_ingestion_stitching.md`
- Update topology diagrams and API specifications with `POST /api/stitch-clips`.

#### [MODIFY] `scratch/render_readme_screenshots.py`
- Update Act 3 HTML rendering template and re-render JPEG mockups in `imgs/`.

---

## Bite-Sized Execution Tasks

### Task 1: Add POST /api/stitch-clips Endpoint & Tests
- Update `src/omnimash/api/app.py` and `tests/api/test_app.py`.
- Run `uv run pytest tests/api/test_app.py`.

### Task 2: Implement Stitch & Combine Selected Clips UI Modal in app.py & Integration Tests
- Add UI state, handler, button, and modal in `src/omnimash/api/app.py`.
- Update `tests/api/test_integration.py`.
- Run `uv run pytest tests/api/test_integration.py`.

### Task 3: Update Architecture Documentation & Screenshots
- Update `README.md`, `docs/diagrams/`, and `scratch/render_readme_screenshots.py`.
- Run `uv run python3 scratch/render_readme_screenshots.py` to regenerate `imgs/`.

### Task 4: Full Verification & Quality Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).

---

## Verification Plan

### Automated Tests
- API tests: `uv run pytest tests/api/test_app.py`
- Integration tests: `uv run pytest tests/api/test_integration.py`
- Full test suite: `uv run pytest`

### Manual Verification
1. Run local dev server (`uv run python -m omnimash.api.app`).
2. Generate Scene 1 and Scene 2 in Act 3.
3. Click **🎬 Stitch & Combine Selected Clips**. Check Scene 1 and Scene 2, enter title `my_custom_mashup`, and click **Concatenate Selected Videos**.
4. Verify custom master video is stitched and exported to `sessions/{session_name}/final_masters/my_custom_mashup.mp4`!
