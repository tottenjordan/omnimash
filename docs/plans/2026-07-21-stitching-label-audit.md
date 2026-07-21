# UI Stitching Label Enhancement & Comprehensive Code & Documentation Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update the Act 3 React UI button and modal to explicitly indicate **🎬 Stitch & Save Master (30–60s) to GCS**, add clear subtext describing automatic multi-clip concatenation, and conduct a thorough codebase and documentation audit (`README.md`, integration tests, screenshot scripts, and rendered JPEG artifacts) to eliminate any stale terminology.

**Architecture:**
1. **Act 3 React Studio UI (`src/omnimash/api/app.py`)**:
   - Update Act 3 toolbar button text to `💾 Stitch & Save Master (30–60s) to GCS`.
   - Update Save Master modal header to `Stitch & Save Master (30–60s) to GCS`.
   - Add modal description subtext: *"OmniMash will automatically concatenate all 10-second scene clips and audio stems generated in this session into a single 30–60s master video MP4 file."*
2. **Integration Tests (`tests/api/test_integration.py`)**:
   - Update `test_dashboard_ui_html_features` assertions to check for `Stitch & Save Master` and `/api/save-final`.
3. **Documentation & Architecture (`README.md`)**:
   - Review and update all references to the Act 3 master export button (`Stitch & Save Master (30–60s) to GCS`).
   - Audit all 3 acts in `README.md` to ensure complete consistency with Character Vault, Roster Persistence, and Master Stitching features.
4. **Visual Diagrams & Screenshot Generator (`scratch/render_readme_screenshots.py` & `imgs/`)**:
   - Update Act 3 HTML rendering template in `scratch/render_readme_screenshots.py` to render the updated button label.
   - Run `uv run python3 scratch/render_readme_screenshots.py` to update the 1600x1000 JPG mockups in `imgs/` (`imgs/ui_act1_concept_and_cast.jpg`, `imgs/ui_act2_storyboard_directing.jpg`, and `imgs/ui_act3_screening_room.jpg`).

**Tech Stack:** Python 3.12, FastAPI, React 18, Tailwind CSS, Headless Chrome, PIL, pytest, uv, ruff, ty.

---

## User Review Required

> [!IMPORTANT]
> **UI Text Enhancement**:
> The button in Act 3 changes from `"Save Final Master to GCS"` to `"💾 Stitch & Save Master (30–60s) to GCS"`.
> The modal header changes to `"Stitch & Save Master (30–60s) to GCS"` with explicit subtext explaining multi-scene clip concatenation.

---

## Proposed Changes

### React Studio UI & Integration Tests

#### [MODIFY] `src/omnimash/api/app.py`
- Update button text in Act 3 toolbar:
```html
<button
    type="button"
    onClick={() => setShowSaveModal(true)}
    className="text-xs bg-amber-950/80 hover:bg-amber-900 text-amber-300 border border-amber-700/80 font-bold py-1.5 px-3 rounded-lg shadow flex items-center gap-1.5 transition"
>
    <span>💾</span>
    <span>Stitch &amp; Save Master (30–60s) to GCS</span>
</button>
```
- Update Save Master modal header and description:
```html
<h3 className="font-bold text-base text-amber-200 flex items-center gap-2">
    <span>🎬</span>
    <span>Stitch &amp; Save Master (30–60s) to GCS</span>
</h3>
<p className="text-xs text-gray-400">
    OmniMash will automatically concatenate all 10-second scene clips and audio stems generated in this session into a single 30–60s master MP4 file exported to Google Cloud Storage.
</p>
```

#### [MODIFY] `tests/api/test_integration.py`
- Update string assertion:
```python
assert "Stitch & Save Master" in html
assert "/api/save-final" in html
```

---

### Documentation & Screenshot Generator

#### [MODIFY] `README.md`
- Update Act 3 feature descriptions and step-by-step walkthrough references to reflect **💾 Stitch & Save Master (30–60s) to GCS**.

#### [MODIFY] `scratch/render_readme_screenshots.py`
- Update `act3_content` template in `scratch/render_readme_screenshots.py` to render `<span>💾</span><span>Stitch &amp; Save Master (30–60s) to GCS</span>`.
- Re-render images in `imgs/` via headless Chrome.

---

## Bite-Sized Execution Tasks

### Task 1: Update Act 3 UI Button & Modal in app.py & Integration Tests
- Update `src/omnimash/api/app.py` and `tests/api/test_integration.py`.
- Run `uv run pytest tests/api/test_integration.py`.

### Task 2: Audit & Update README.md and Screenshot Script
- Update `README.md` and `scratch/render_readme_screenshots.py`.
- Run `uv run python3 scratch/render_readme_screenshots.py` to regenerate JPEG screenshots in `imgs/`.

### Task 3: Full Verification & Test Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).

---

## Verification Plan

### Automated Tests
- Integration tests: `uv run pytest tests/api/test_integration.py`
- Full test suite: `uv run pytest`
- Linting & Typing: `uv run ruff check . && uv run ruff format --check . && uv run ty check .`

### Manual Verification
1. Run local dev server (`uv run python -m omnimash.api.app`).
2. Open Act 3 in browser (`http://127.0.0.1:8000/dev-ui/?app-agent.py_folder`).
3. Verify button label displays **💾 Stitch & Save Master (30–60s) to GCS** and modal subtext explains multi-clip concatenation.
