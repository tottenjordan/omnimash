# Prompt Visibility, Character-Specific Style Signifiers & Screening Room Workflows Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Provide end-to-end prompt visibility in Act 3, support per-character aesthetic tags & reference image bindings in Act 1, disable video autoplay in Act 3, and add final GCS master exporting & scene continuation workflows.

**Architecture:** Extend `CharacterRole` and `PromptCompiler` with per-character aesthetic tags; update `OmniMashAgent` and FastAPI routes to support `POST /api/save-final` and `POST /api/extend-scene`; and update the React 18 single-page dashboard (`UI_HTML`) to display the latest generation prompt, disable video autoplay, render character-specific style signifier widgets in Act 1, and provide master export and scene extension modals in Act 3.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, Google GenAI SDK (`gemini-omni-flash-preview`), Google Cloud Storage (`GcsStorageManager`), React 18, Tailwind CSS, Pytest, UV.

---

## 🔬 Research & Conclusions

### Feedback Item [1]: Prompt Construction & Development Visibility
- **Research:** `PromptCompiler.compile_storyboard(...)` constructs structured prompts with `[ROLE DEFINITIONS]`, `[AESTHETIC INJECTION]`, and `[STORYBOARD SEQUENCE]`. The backend returns `raw_compiled_prompt` in `GenerateResponse`, but the frontend did not display it in Act 3.
- **Conclusion:** We must display `raw_compiled_prompt` in a dedicated, collapsible "Final Generation Prompt" card in Act 3, and update it dynamically whenever the user selects any version/iteration from the Version Tree timeline.

### Feedback Item [2]: Reference Image Formatting in Gemini Omni Prompts
- **Research:** Gemini Omni Image Roles (`ai.google.dev/gemini-api/docs/omni#set-image-roles`) bind character identities using `Role A`, `Role B`, etc., with corresponding reference image URIs (`gs://...` or `https://...`).
- **Conclusion:** Reference images are formatted cleanly in the prompt as `(Ref: gs://bucket/path.jpg)` alongside character descriptions. We ensure that `_abstract_prompt_for_responsible_ai` preserves image role references (`Role A`, `Role B`, `Ref: ...`) without regex distortion.

### Feedback Item [3]: Prompt Display on Act 3 Tab (Screening Room)
- **Research:** Currently, Act 3 displays the video player and version tree, but lacks a prompt inspection pane.
- **Conclusion:** We will add a prominent **"🧠 Final Generation Prompt (Active Version)"** section in Act 3 below the video player. Each turn in the `history` state will store its own `rawCompiledPrompt` so switching between historical turns updates the prompt viewer instantly.

### Feedback Item [4]: Disable Video Autoplay
- **Research:** `<video src={currentVideo} controls autoPlay loop />` in `app.py` automatically plays the video upon render.
- **Conclusion:** Remove `autoPlay` from the `<video>` element, allowing the user to initiate playback manually.

### Feedback Item [5]: Character-Specific Aesthetic Tags & Style Signifiers (Act 1)
- **Research & Recommendation:** **This is an excellent idea.** Global aesthetic tags (e.g., `2000s Atlanta Trap`) apply to the overall scene lighting and genre. However, in multi-character parody videos, each character possesses unique attire, jewelry, and props (e.g., Harry has `Red Gucci Tracksuit` and `Cartier Glasses`; Draco has `Platinum Slicked Hair` and `Diamond Iced-Out Chain`). Adding a dedicated "Aesthetic Tags & Style Signifiers" widget to each Character Role card in Act 1 gives creators granular control over individual character likeness.
- **Conclusion:** Add `aesthetic_tags: list[str]` to `CharacterRole`. Update `PromptCompiler.compile_storyboard` to render character-level tags. In Act 1 UI, render a tag chip manager inside each Character Role card.

### Feedback Item [6]: Screening Room Next Steps (Final GCS Export & Scene Extension)
- **Research & Recommendation:** Once a user likes a generated video in Act 3, they need two clear production actions:
  1. **Save Final Copy to Dedicated GCS Folder (`POST /api/save-final`):** Copies the active video from `intermediate/` to `final_masters/<session_name>_<master_title>.mp4` in Google Cloud Storage.
  2. **Extend Video / Start Next Scene (`POST /api/extend-scene`):** Extends the narrative by appending a new scene to the storyboard in Act 2 while locking the existing characters and keyframe baselines.
- **Conclusion:** Implement both backend endpoints (`/api/save-final`, `/api/extend-scene`) and add corresponding action buttons ("💾 Save Final Master to GCS" and "➕ Extend Video / Next Scene") in Act 3.

---

## 🛠️ Implementation Tasks

### Task 1: Extend CharacterRole & PromptCompiler with Character-Specific Aesthetic Tags

**Files:**
- Modify: `src/omnimash/prompts/compiler.py:76-83, 230-278`
- Test: `tests/prompts/test_compiler.py`

**Step 1: Write the failing test**

```python
def test_character_role_specific_aesthetic_tags():
    from omnimash.prompts.compiler import CharacterRole, PromptCompiler, SceneDirective

    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Harry",
            description="Wizard with round glasses",
            reference_url="gs://bucket/harry.jpg",
            aesthetic_tags=["Red Gucci Tracksuit", "Cartier Glasses"],
        )
    ]
    scenes = [SceneDirective(scene_number=1, active_roles=["Role A"], action="Cooking potions")]
    prompt = compiler.compile_storyboard(
        concept="Harry Trap",
        characters=chars,
        scenes=scenes,
    )
    assert "[Style: Red Gucci Tracksuit, Cartier Glasses]" in prompt
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/prompts/test_compiler.py -k test_character_role_specific_aesthetic_tags`
Expected: FAIL with `unexpected keyword argument 'aesthetic_tags'`

**Step 3: Implement minimal code**

In `src/omnimash/prompts/compiler.py`:
- Update `CharacterRole` dataclass:
  ```python
  @dataclass
  class CharacterRole:
      role_id: str
      name: str
      description: str
      reference_url: str | None = None
      aesthetic_tags: list[str] = field(default_factory=list)
  ```
- In `compile_storyboard`:
  ```python
  for char in characters:
      ref_str = f" (Ref: {char.reference_url})" if char.reference_url else ""
      style_str = f" [Style: {', '.join(char.aesthetic_tags)}]" if char.aesthetic_tags else ""
      role_lines.append(
          f"- {char.role_id} ({char.name}): {char.description}{style_str}{ref_str}"
      )
  ```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/prompts/test_compiler.py`
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/prompts/compiler.py tests/prompts/test_compiler.py
git commit -m "feat(prompts): add character-specific aesthetic tags to CharacterRole and compiler"
```

---

### Task 2: Backend API Endpoints for Final GCS Master Export & Scene Extension

**Files:**
- Modify: `src/omnimash/storage/gcs.py`
- Modify: `src/omnimash/agent/orchestrator.py`
- Modify: `src/omnimash/api/app.py`
- Test: `tests/api/test_app.py`

**Step 1: Write the failing test**

```python
def test_save_final_master_and_extend_scene_endpoints(client):
    res_save = client.post(
        "/api/save-final",
        json={
            "session_name": "trap_or_die_v1",
            "video_url": "/static/rendered/mock.mp4",
            "master_title": "official_rap_battle_master"
        }
    )
    assert res_save.status_code == 200
    data_save = res_save.json()
    assert data_save["success"] is True
    assert "final_masters" in data_save["gcs_uri"]

    res_extend = client.post(
        "/api/extend-scene",
        json={
            "session_name": "trap_or_die_v1",
            "turn_id": "turn_0",
            "next_scene_action": "Harry drops the mic and walks away"
        }
    )
    assert res_extend.status_code == 200
    assert res_extend.json()["success"] is True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_app.py -k test_save_final_master_and_extend_scene_endpoints`
Expected: FAIL with 404 Not Found

**Step 3: Implement minimal code**

1. In `src/omnimash/storage/gcs.py`, add `save_final_master(session_id: str, source_rel_path: str, master_title: str) -> str`.
2. In `src/omnimash/agent/orchestrator.py`, add `save_final_master(...)` and `extend_scene(...)`.
3. In `src/omnimash/api/app.py`, define request models `SaveFinalRequest` and `ExtendSceneRequest`, and register routes:
   - `POST /api/save-final`
   - `POST /api/extend-scene`

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_app.py`
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/storage/gcs.py src/omnimash/agent/orchestrator.py src/omnimash/api/app.py tests/api/test_app.py
git commit -m "feat(api): add /api/save-final and /api/extend-scene endpoints"
```

---

### Task 3: React Dashboard UI Updates (Act 1 Character Styles, Act 3 Prompt Viewer, No-Autoplay, Master Export)

**Files:**
- Modify: `src/omnimash/api/app.py: UI_HTML`
- Test: `tests/api/test_integration.py`

**Step 1: Write integration test verifying UI components**

```python
def test_dashboard_ui_html_features(client):
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    # Autoplay removed
    assert 'autoPlay' not in html or 'autoPlay={false}' in html
    # Act 3 prompt visibility container present
    assert "Final Generation Prompt" in html
    # Act 1 character aesthetic tag widget present
    assert "Character Style Signifiers" in html or "Character Aesthetic Tags" in html
    # Act 3 Save Final Master present
    assert "Save Final Master" in html
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_integration.py -k test_dashboard_ui_html_features`
Expected: FAIL

**Step 3: Update `UI_HTML` in `src/omnimash/api/app.py`**

1. **Disable Video Autoplay:** Remove `autoPlay` from the `<video>` element in Act 3.
2. **Act 1 Character Aesthetic Tags:** Inside each Character Role card in Act 1, add a chip manager for character-specific aesthetic tags (e.g. `char.aesthetic_tags`).
3. **Act 3 Prompt Display:** Add a prominent "🧠 Final Generation Prompt (Active Version)" section below the video player showing `rawCompiledPrompt`. When a user clicks a turn in the Version Tree, update `rawCompiledPrompt` to that turn's prompt.
4. **Act 3 Save Final Master & Extend Scene Modals/Buttons:** Add "💾 Save Final Master to GCS" button with modal input for `master_title`, and "➕ Extend Video / Next Scene" button that transitions to Act 2 with a new scene card appended.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_integration.py`
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/api/app.py tests/api/test_integration.py
git commit -m "feat(ui): update React studio with character styles, prompt viewer, no-autoplay, and export workflows"
```

---

### Task 4: Documentation & Screenshot Verification

**Files:**
- Modify: `README.md`
- Scratch: `scratch/render_readme_screenshots.py`

**Step 1: Update README.md with the new features**
Document character-specific style signifiers in Act 1, prompt inspection in Act 3, and final master exporting to GCS.

**Step 2: Re-render UI screenshots**
Run `uv run python3 scratch/render_readme_screenshots.py` to regenerate `imgs/ui_act1_concept_and_cast.jpg` and `imgs/ui_act3_screening_room.jpg`.

**Step 3: Run full verification suite**
Run: `uv run ruff check --fix . && uv run ruff format . && uv run ty check . && uv run pytest`

**Step 4: Commit**

```bash
git add README.md imgs/*.jpg scratch/render_readme_screenshots.py
git commit -m "docs: update documentation and screenshots for character styles and screening room workflows"
```

---

## 🎯 Plan Summary & Execution Options

Plan complete and saved to `docs/plans/2026-07-20-prompt-visibility-character-styles-and-screening-room-workflows.md`. Two execution options:

1. **Subagent-Driven (this session)** - I dispatch a fresh subagent per task, review between tasks, and iterate quickly.
2. **Parallel Session (separate)** - Open a new session with `executing-plans`, batch execution with checkpoints.
