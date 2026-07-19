# OmniMash Preset Transparency & Reference Analysis Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Provide full creative transparency in OmniMash by adding a Style Preset Contribution Inspector, live Raw API Payload Viewer, Extracted Reference Keyframe Gallery with usage annotations, and automated YouTube Video Analysis (BPM & Color Palette).

**Architecture:** Extend `MediaExtractor` to produce structured `ReferenceAnalysisReport` metadata saved to session GCS storage. Expose preset contribution vectors and analysis metadata via FastAPI endpoints, and render interactive preset inspection badges, raw payload code boxes, annotated keyframe cards, and color palette swatches in the Next.js/React dashboard.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, FFmpeg, Google ADK, Next.js / React 18, Tailwind CSS, Pytest.

---

### Task 1: Reference Video Acoustic & Visual Analysis Data Model (`MediaExtractor`)

**Files:**
- Modify: `src/omnimash/ingestion/media_extractor.py`
- Modify: `src/omnimash/storage/gcs.py`
- Test: `tests/ingestion/test_media_extractor.py`

**Step 1: Write the failing test**

```python
from omnimash.ingestion.media_extractor import MediaExtractor, ReferenceAnalysisReport

def test_media_extractor_generates_analysis_report():
    extractor = MediaExtractor(mock_mode=True)
    report = extractor.analyze_youtube_reference("https://www.youtube.com/watch?v=sample_beat", session_id="sess_123")
    assert isinstance(report, ReferenceAnalysisReport)
    assert report.detected_bpm == 120
    assert len(report.extracted_keyframes) >= 3
    assert "[SUBJECT ANCHOR]" in report.extracted_keyframes[0].usage_annotation
    assert len(report.dominant_colors) > 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ingestion/test_media_extractor.py -v`  
Expected: FAIL with `ReferenceAnalysisReport not defined` or `analyze_youtube_reference missing`.

**Step 3: Write minimal implementation**

In `src/omnimash/ingestion/media_extractor.py`:
- Define `KeyframeAnnotation` dataclass: `timestamp: str`, `image_url: str`, `usage_annotation: str`.
- Define `ReferenceAnalysisReport` dataclass: `video_title: str`, `duration_seconds: int`, `detected_bpm: int`, `dominant_colors: list[str]`, `extracted_keyframes: list[KeyframeAnnotation]`.
- Implement `analyze_youtube_reference(self, url: str, session_id: str) -> ReferenceAnalysisReport`.
- In `GcsStorageManager`, implement `save_reference_analysis(session_id, report)` and `get_reference_analysis(session_id)`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ingestion/test_media_extractor.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/ingestion/media_extractor.py src/omnimash/storage/gcs.py tests/ingestion/test_media_extractor.py
git commit -m "feat(ingestion): add ReferenceAnalysisReport data model and analysis extraction"
```

---

### Task 2: Style Preset Contribution Inspector Data Model

**Files:**
- Modify: `src/omnimash/prompts/taxonomy.py`
- Test: `tests/prompts/test_taxonomy.py`

**Step 1: Write the failing test**

```python
from omnimash.prompts.taxonomy import PromptTaxonomyEngine, StylePreset, PresetContribution

def test_taxonomy_engine_provides_preset_contributions():
    engine = PromptTaxonomyEngine()
    contrib = engine.get_preset_contribution(StylePreset.NINETIES_RAP_VIDEO)
    assert isinstance(contrib, PresetContribution)
    assert "puffer jacket" in contrib.wardrobe
    assert "fisheye lens" in contrib.camera_lighting
    assert "bopping" in contrib.motion
    assert "boom-bap" in contrib.sound_design
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/prompts/test_taxonomy.py -v`  
Expected: FAIL with `PresetContribution not defined`.

**Step 3: Write minimal implementation**

In `src/omnimash/prompts/taxonomy.py`:
- Define `PresetContribution` dataclass: `wardrobe: str`, `camera_lighting: str`, `motion: str`, `sound_design: str`.
- Add method `get_preset_contribution(self, preset: StylePreset | str) -> PresetContribution` to `PromptTaxonomyEngine`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/prompts/test_taxonomy.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/prompts/taxonomy.py tests/prompts/test_taxonomy.py
git commit -m "feat(prompts): add get_preset_contribution to PromptTaxonomyEngine"
```

---

### Task 3: Full-Stack Web UI Dashboard Enhancements

**Files:**
- Modify: `src/omnimash/api/app.py`
- Modify: `src/omnimash/agent/orchestrator.py`
- Test: `tests/api/test_integration.py`

**Step 1: Write the failing test**

```python
def test_e2e_generate_includes_reference_analysis_and_raw_prompt():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/generate",
        json={
            "user_id": "u_diag",
            "project_id": "p_diag",
            "prompt": "Snape 90s rap",
            "clip_index": 0,
            "reference_url": "https://www.youtube.com/watch?v=sample",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "reference_analysis" in data
    assert "raw_compiled_prompt" in data
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_integration.py -v`  
Expected: FAIL with missing response fields.

**Step 3: Write minimal implementation**

1. Update `GenerateResponse` in `src/omnimash/api/app.py`:
   - `raw_compiled_prompt: str | None = None`
   - `reference_analysis: dict | None = None`
2. Update `OmniMashAgent.process_user_turn` to return analysis report & raw compiled prompt.
3. Update HTML/React Web UI Dashboard in `src/omnimash/api/app.py`:
   - **Preset Contribution Inspector**: Show chips for Wardrobe, Camera, Motion, and Sound Design under selected preset.
   - **Raw Model Payload Container**: Render collapsible code block showing exact monolithic prompt string + Copy button.
   - **Extracted Reference Keyframe Gallery**: Render thumbnail cards for Frame 1 (Subject Anchor), Frame 2 (Lighting Baseline), Frame 3 (Acoustic Rhythm) with usage annotations.
   - **Ingested Analysis Card**: Render BPM badge and dominant hex color palette swatches.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_integration.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/api/app.py src/omnimash/agent/orchestrator.py tests/api/test_integration.py
git commit -m "feat(ui): add preset contribution inspector, raw payload box, and annotated keyframe gallery"
```

---

### Task 4: PaperBanana Diagram & Architectural Documentation

**Files:**
- Create: `docs/diagrams/omnimash_reference_analysis_inspector.png`
- Create: `docs/notes/reference_analysis_and_preset_inspector.md`
- Modify: `README.md`
- Modify: `docs/notes/README.md`

**Step 1: Generate PaperBanana Diagram**
- Call `generate_image` for PaperBanana diagram illustrating the Preset Contribution Inspector, Raw Payload Container, and Extracted Reference Keyframes with usage annotations.
- Copy to `docs/diagrams/omnimash_reference_analysis_inspector.png`.

**Step 2: Write documentation note**
- Write `docs/notes/reference_analysis_and_preset_inspector.md` explaining the acoustic analysis, color palette extraction, keyframe annotations, and preset vector contributions.
- Index in `docs/notes/README.md` and `README.md`.

**Step 3: Verification & Commit**
- Run `uv run pytest`, `uv run ruff check --fix .`, `uv run ruff format .`, `uv run ty check .`.
- Commit (no `Co-Authored-By` trailer).

```bash
git add docs/ README.md
git commit -m "docs: add PaperBanana diagram and notes for reference analysis and preset inspector"
```
