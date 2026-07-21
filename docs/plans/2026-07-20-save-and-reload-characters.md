# Save and Reload Characters & Cast Rosters Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable users to persist, manage, and reload individual Character Roles and entire session cast rosters directly from the Act 1 React Studio UI into Google Cloud Storage (`sessions/{session_id}/characters/` and `library/characters/`), and update the playable parody media in Step 4 of `README.md` using the latest GCS master `official_1017_intro.mp4`.

**Architecture:** 
1. Extend `GcsStorageManager` (`src/omnimash/storage/gcs.py`) with hierarchical GCS persistence for individual character JSON files (`library/characters/{slug}.json` and `sessions/{session_id}/characters/{slug}.json`) and session cast rosters (`sessions/{session_id}/characters/roster.json`).
2. Expose REST endpoints in FastAPI (`src/omnimash/api/app.py`): `POST /api/characters/save`, `GET /api/characters`, `POST /api/characters/load`, `POST /api/characters/save-roster`, and `GET /api/characters/roster`.
3. Add a **Character Vault & Saved Cast Manager** in Act 1 of the React Studio (`UI_HTML`) featuring 1-click **"💾 Save to Vault"** per character card, **"📂 Load from Vault"** preset badges, and **"💾 Save Cast / 📂 Restore Cast"** session controls.
4. Download `gs://omnimash-media-hybrid-vertex/sessions/trap_or_die_v3/final_masters/official_1017_intro.mp4` and re-encode high-quality animated media (`imgs/live_parody_cut.gif` and `imgs/live_parody_cut.webp`) to ensure Step 4 of `README.md` perfectly reflects the latest parody output.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Google Cloud Storage (GCS) client library, FFmpeg, React 18, Tailwind CSS, pytest, uv, ruff, ty.

---

### Task 1: Extend GcsStorageManager with Character and Roster Persistence

**Files:**
- Modify: `src/omnimash/storage/gcs.py`
- Test: `tests/storage/test_gcs.py`

**Step 1: Write the failing unit tests**
In `tests/storage/test_gcs.py`:
```python
def test_save_and_load_character_gcs():
    storage = GcsStorageManager(mock_mode=True)
    char_data = {
        "role_id": "Role A",
        "name": "Harry",
        "description": "Young wizard",
        "reference_url": "gs://bucket/harry.jpg",
        "aesthetic_tags": ["Red Gucci Tracksuit"],
        "voice_style": "Atlanta trap flow",
    }
    pub_url, gcs_uri = storage.save_character(char_data, session_id="test_session", is_library=True)
    assert "library/characters/harry.json" in gcs_uri

    loaded = storage.load_character("harry")
    assert loaded is not None
    assert loaded["name"] == "Harry"
    assert loaded["voice_style"] == "Atlanta trap flow"

    chars = storage.list_characters()
    assert any(c["name"] == "Harry" for c in chars)
```

**Step 2: Run test to verify it fails**
```bash
uv run pytest tests/storage/test_gcs.py -k test_save_and_load_character_gcs
```

**Step 3: Implement minimal storage methods in `gcs.py`**
- Add `_mock_characters: dict[str, dict[str, Any]]` and `_mock_rosters: dict[str, list[dict[str, Any]]]` initialized with default presets.
- Implement `save_character(...)`, `list_characters(...)`, `load_character(...)`, `save_session_roster(...)`, `load_session_roster(...)`.

**Step 4: Run test to verify it passes**
```bash
uv run pytest tests/storage/test_gcs.py
```

**Step 5: Commit**
```bash
git add src/omnimash/storage/gcs.py tests/storage/test_gcs.py
git commit -m "feat(storage): add character and roster persistence to GCS manager"
```

---

### Task 2: Implement Character & Roster REST API Endpoints

**Files:**
- Modify: `src/omnimash/api/app.py`
- Create/Test: `tests/api/test_character_api.py`

**Step 1: Write the failing API test**
In `tests/api/test_character_api.py`:
```python
from fastapi.testclient import TestClient
from omnimash.api.app import create_app

def test_character_api_save_list_load():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    # 1. List pre-seeded library characters
    res_list = client.get("/api/characters")
    assert res_list.status_code == 200
    assert len(res_list.json()["characters"]) > 0

    # 2. Save a new custom character
    new_char = {
        "role_id": "Role C",
        "name": "Snoop Dogg Wizard",
        "description": "West Coast rap icon casting smoke spells",
        "reference_url": "https://example.com/snoop.jpg",
        "aesthetic_tags": ["Flannel Robe", "Gold Microphone Wand"],
        "voice_style": "Laid back West Coast drawl",
    }
    res_save = client.post("/api/characters/save", json={"character": new_char, "session_name": "snoop_session"})
    assert res_save.status_code == 200
    assert res_save.json()["success"] is True

    # 3. Load saved character
    res_load = client.post("/api/characters/load", json={"slug": "snoop_dogg_wizard"})
    assert res_load.status_code == 200
    loaded = res_load.json()
    assert loaded["name"] == "Snoop Dogg Wizard"
```

**Step 2: Run test to verify it fails**
```bash
uv run pytest tests/api/test_character_api.py
```

**Step 3: Implement route handlers in `app.py`**
- Define `SaveCharacterRequest`, `SaveRosterRequest`, `CharacterListResponse`, `LoadCharacterRequest`.
- Add routes: `/api/characters/save`, `/api/characters`, `/api/characters/load`, `/api/characters/save-roster`, `/api/characters/roster`.

**Step 4: Run test to verify it passes**
```bash
uv run pytest tests/api/test_character_api.py
```

**Step 5: Commit**
```bash
git add src/omnimash/api/app.py tests/api/test_character_api.py
git commit -m "feat(api): expose REST endpoints for saving and loading characters and rosters"
```

---

### Task 3: Add Character Vault & Saved Cast Controls to React Dashboard UI

**Files:**
- Modify: `src/omnimash/api/app.py` (`UI_HTML`)
- Test: `tests/api/test_integration.py`

**Step 1: Write failing integration test**
In `tests/api/test_integration.py`:
```python
def test_dashboard_ui_html_character_vault():
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "Character Vault" in html
    assert "Save to Vault" in html or "Save Character" in html
    assert "/api/characters" in html
```

**Step 2: Update `UI_HTML` in `app.py`**
- In Act 1:
  - Add state `savedCharacters` and fetch on mount via `GET /api/characters`.
  - Add a **🏛️ Character Vault & Saved Library** bar above Character Roles with clickable badges for quick-loading presets.
  - Add a **💾 Save to Vault** button inside each Character Role card.
  - Add **💾 Save Cast Roster** and **📂 Load Session Cast** buttons in the roster toolbar.

**Step 3: Run tests to verify they pass**
```bash
uv run pytest tests/api/test_integration.py
```

**Step 4: Commit**
```bash
git add src/omnimash/api/app.py tests/api/test_integration.py
git commit -m "feat(ui): add Character Vault and cast save/reload controls to React studio"
```

---

### Task 4: Update Playable Media in README.md from GCS Master (`official_1017_intro.mp4`)

**Files:**
- New/Update: `imgs/live_parody_cut.gif`
- New/Update: `imgs/live_parody_cut.webp`
- Modify: `README.md`

**Step 1: Download GCS Master**
```bash
gcloud storage cp gs://omnimash-media-hybrid-vertex/sessions/trap_or_die_v3/final_masters/official_1017_intro.mp4 /tmp/official_1017_intro.mp4
```

**Step 2: Re-encode animated GIF and WebP loops**
```bash
ffmpeg -y -i /tmp/official_1017_intro.mp4 -vf "fps=12,scale=720:-1:flags=lanczos" -loop 0 imgs/live_parody_cut.gif
ffmpeg -y -i /tmp/official_1017_intro.mp4 -vcodec libwebp -filter:v "fps=fps=15,scale=720:-1" -lossless 0 -compression_level 4 -q:v 70 -loop 0 imgs/live_parody_cut.webp
```

**Step 3: Verify and Commit**
```bash
git add imgs/live_parody_cut.gif imgs/live_parody_cut.webp README.md
git commit -m "docs: update Step 4 playable parody media cut from official 1017 intro master"
```

---

### Task 5: Documentation & Screenshot Verification

**Files:**
- Modify: `README.md`
- Modify: `scratch/render_readme_screenshots.py`
- Update images in `imgs/`

**Step 1: Update documentation and screenshot renderer**
- Add Character Vault instructions to `README.md`.
- Update `scratch/render_readme_screenshots.py` and run `uv run python3 scratch/render_readme_screenshots.py`.

**Step 2: Full verification**
```bash
uv run pytest
uv run ruff check --fix .
uv run ruff format .
uv run ty check .
```

**Step 3: Commit**
```bash
git add README.md scratch/ imgs/
git commit -m "docs: document Character Vault and update UI screenshots"
```
