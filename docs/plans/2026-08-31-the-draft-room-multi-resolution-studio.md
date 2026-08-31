# "The Draft Room" Multi-Resolution Comparison Studio Implementation Plan

> **For Agent:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task.

**Goal:** Build a multi-card draft comparison studio in OmniMash that renders 3-4 prompt concept variations simultaneously in **360p Draft Mode** (~60% faster at 1/3 cost), enabling creators to test variations in lighting, audio beat, or character movement before committing to a 4K Master export.

**Architecture:** Expose batch 360p draft generation endpoint `/api/storyboard/draft-batch` in `src/omnimash/api/app.py`, update `UI_HTML` with a "⚡ The Draft Room" studio workspace panel with side-by-side variation cards, and wire "🏆 Upgrade to 4K Master" resolution triggers.

**Tech Stack:** Python 3.12, FastAPI, React (UI_HTML), Pydantic v2, Pytest, Ruff, Gemini Omni Flash 1.1 API (`gemini-omni-1.1-flash-preview`).

---

## User Review Required

> [!IMPORTANT]
> **Draft Mode Cost & Speed Optimization**:
> Draft Room renders use `resolution="360p"` (`response_format={"resolution": "360p"}`) to produce fast previews in parallel. When a creator selects their favorite variation, clicking **🏆 Upgrade to 4K Master** triggers a high-res re-render at `resolution="4k"`.

> [!NOTE]
> **Git Branching & Pull Request Review Workflow**:
> Per workspace standards, all code changes for this implementation plan will be developed on feature branch `feature/the-draft-room-360p-comparison-studio` and submitted as a GitHub Pull Request for user review before merging.

---

## Bite-Sized Tasks

### Task 1: Add Batch 360p Draft Generation Endpoint (`/api/storyboard/draft-batch`)

**Files:**
- Modify: `src/omnimash/api/app.py:380-420` and `9800-9850`
- Test: `tests/api/test_app.py`

**Step 1: Write the failing test**

Add `test_api_storyboard_draft_batch_endpoint()` in `tests/api/test_app.py`:
```python
def test_api_storyboard_draft_batch_endpoint() -> None:
    """Verify POST /api/storyboard/draft-batch accepts variation directives and returns 360p draft clips."""
    from omnimash.api.app import create_app
    from fastapi.testclient import TestClient

    app = create_app(mock_mode=True)
    client = TestClient(app)

    payload = {
        "concept": "Wizard casting spell in Neon Alleyway",
        "variations": [
            {"label": "Option A: Dark Gothic Embers", "action_directive": "Dark Gothic embers and blue spell", "audio_beat": "Dark Synthwave"},
            {"label": "Option B: Neon Cyberpunk Pulse", "action_directive": "Neon Cyberpunk pulse and red spell", "audio_beat": "Heavy 808 Trap"},
        ],
        "keyframe_image_url": "http://example.com/start_keyframe.png",
    }

    res = client.post("/api/storyboard/draft-batch", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["drafts"]) == 2
    assert data["drafts"][0]["resolution"] == "360p"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_app.py -k test_api_storyboard_draft_batch_endpoint -v`
Expected output: `FAIL (404 Not Found)`

**Step 3: Write minimal implementation in `src/omnimash/api/app.py`**

Define request/response models and route handler:
```python
class DraftVariationItem(BaseModel):
    label: str
    action_directive: str
    audio_beat: str | None = None
    style_lighting: str | None = None


class BatchDraftRequest(BaseModel):
    concept: str
    variations: list[DraftVariationItem]
    keyframe_image_url: str | None = None
    aspect_ratio: str = "16:9"


class BatchDraftResponse(BaseModel):
    success: bool
    drafts: list[dict[str, Any]]


@app.post("/api/storyboard/draft-batch", response_model=BatchDraftResponse)
def generate_draft_batch(req: BatchDraftRequest) -> BatchDraftResponse:
    draft_results: list[dict[str, Any]] = []
    for var in req.variations:
        turn = agent.process_user_turn(
            user_id="usr_default",
            project_id="prj_draft_room",
            prompt=f"{req.concept} - {var.action_directive}",
            keyframe_image_url=req.keyframe_image_url,
            audio_stem=var.audio_beat,
            resolution="360p",
            aspect_ratio=req.aspect_ratio,
        )
        draft_results.append(
            {
                "label": var.label,
                "action_directive": var.action_directive,
                "video_url": turn.media_url,
                "resolution": "360p",
                "turn_id": turn.turn_id,
            }
        )
    return BatchDraftResponse(success=True, drafts=draft_results)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_app.py -k test_api_storyboard_draft_batch_endpoint -v`
Expected output: `PASSED`

**Step 5: Commit**

```bash
git add src/omnimash/api/app.py tests/api/test_app.py
git commit -m "feat(api): add /api/storyboard/draft-batch endpoint for 360p multi-card comparison"
```

---

### Task 2: Build "⚡ The Draft Room" UI Component & Multi-Card Preview Grid in `UI_HTML`

**Files:**
- Modify: `src/omnimash/api/app.py` (`UI_HTML` React application code)
- Test: `tests/api/test_app.py`

**Step 1: Write the failing test**

Add `test_ui_html_contains_draft_room_studio_controls()` in `tests/api/test_app.py`:
```python
def test_ui_html_contains_draft_room_studio_controls() -> None:
    """Verify UI_HTML contains 'The Draft Room' studio controls and 4K Master upscale triggers."""
    from omnimash.api.app import UI_HTML

    assert "⚡ The Draft Room" in UI_HTML
    assert "handleGenerateDrafts" in UI_HTML
    assert "🏆 Upgrade to 4K Master" in UI_HTML
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_app.py -k test_ui_html_contains_draft_room_studio_controls -v`
Expected output: `FAIL`

**Step 3: Update `UI_HTML` in `src/omnimash/api/app.py`**

Add React state and handlers:
- `draftVariations`, `isDrafting`, `handleGenerateDrafts()`, `handleUpscaleDraftTo4K()`.
- Render **⚡ The Draft Room (360p Comparison Studio)** section with side-by-side variation cards, live 360p video players, and **🏆 Upgrade to 4K Master** action buttons.

**Step 4: Run JSX tag balance guardrail and unit test**

Run: `uv run pytest tests/api/test_app.py -k "test_ui_html_syntax_and_tag_balance or test_ui_html_contains_draft_room_studio_controls" -v`
Expected output: `PASSED`

**Step 5: Commit**

```bash
git add src/omnimash/api/app.py tests/api/test_app.py
git commit -m "feat(ui): add The Draft Room multi-resolution preview grid and 4K upscale controls"
```

---

### Task 3: Full Test Suite & Linter Verification

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected output: `All tests passing`

**Step 2: Run ruff check**

Run: `uv run ruff check .`
Expected output: `All checks passed!`

---

## Verification Plan

### Automated Tests
1. **Batch Draft Endpoint Test**:
   - `uv run pytest tests/api/test_app.py -k test_api_storyboard_draft_batch_endpoint -v`
2. **UI Draft Room Controls Test**:
   - `uv run pytest tests/api/test_app.py -k test_ui_html_contains_draft_room_studio_controls -v`
3. **JSX Tag Balance Guardrail**:
   - `uv run pytest tests/api/test_app.py -k test_ui_html_syntax_and_tag_balance -v`
4. **Full Test Suite & Linter**:
   - `uv run pytest tests/ -v` and `uv run ruff check .`

### Manual Verification
1. Open OmniMash in browser (`http://localhost:8080`).
2. Open **⚡ The Draft Room** panel.
3. Submit a concept with 2-3 variations (e.g. *Option A: Dark Gothic Synth*, *Option B: Cyberpunk Trap*).
4. Verify that 360p draft videos render in parallel in the multi-card grid.
5. Click **🏆 Upgrade to 4K Master** on your favorite option to trigger high-res 4K export.
