# OmniMash Session Name Selector & Resilient Video Rendering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow users to select a custom Session Name in the Web UI dashboard mapped directly to GCS cloud storage folders (`sessions/{session_name}/`), install Linux font packages in Cloud Run Docker container for FFmpeg `drawtext` support, implement a resilient animated procedural audio visualizer fallback, and add structured Vertex AI error logging.

**Architecture:** 
1. The Web UI React dashboard exposes a **`🗂️ Session / GCS Folder Name`** selector, passing `session_name` via FastAPI (`GenerateRequest`, `CommitRequest`) to `SessionManager`, which formats the session key and GCS bucket prefix (`gs://omnimash-media-${GOOGLE_CLOUD_PROJECT}/sessions/{session_name}/`).
2. The `Dockerfile` is updated with `fonts-dejavu-core` and `fonts-freefont-ttf` so FFmpeg's `drawtext` HUD filter succeeds in Debian-based Cloud Run containers.
3. `OmniFlashClient` is updated with structured logging (`logging.getLogger("omnimash.engine")`) for Vertex AI API operations and a resilient procedural audio visualizer in `ensure_rendered_video()` that generates vibrant animated sound waves reacting to the beat if text/images are missing, eliminating blank solid screens.

**Tech Stack:** FastAPI, React 18, Tailwind CSS, Google Cloud Storage (GCS), Vertex AI (`gemini-omni-flash-preview`), FFmpeg (`showwaves`, `drawtext`, `zoompan`), Pytest, Ruff, Ty.

---

## User Review Required

> [!IMPORTANT]
> **Session Name Sanitization & GCS Mapping:**
> Custom session names entered by the user in the UI (e.g. `Dripwarts Vol 1!`) will be automatically sanitized to safe alphanumeric GCS folder keys (e.g. `dripwarts_vol_1`). If left blank, it defaults to `dripwarts_vol1`. This ensures 100% cloud storage compatibility across all bucket operations.

---

## Proposed Changes

### Component 1: State Management & GCS Folder Mapping

#### [MODIFY] `src/omnimash/state/session_manager.py`
- Update `SessionManager.get_or_create_session(user_id, project_id, session_name=None)` to sanitize and prioritize `session_name` as the `session_id`.
- When `session_name` is passed, `session.session_id` becomes the sanitized session name, automatically routing all GCS artifacts to `sessions/{session_name}/`.

```python
def get_or_create_session(
    self, user_id: str, project_id: str, session_name: str | None = None
) -> ProjectSession:
    if session_name and session_name.strip():
        clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", session_name.strip())
        session_key = clean_name
    else:
        session_key = f"{user_id}:{project_id}"

    if session_key not in self._sessions:
        self._sessions[session_key] = ProjectSession(
            session_id=session_key, user_id=user_id, project_id=project_id
        )
    return self._sessions[session_key]
```

#### [MODIFY] `src/omnimash/agent/orchestrator.py`
- Accept `session_name: str | None = None` in `process_user_turn()` and `commit_and_branch()`.
- Forward `session_name` to `session_manager.get_or_create_session()`.

---

### Component 2: API & UI Dashboard Session Selector

#### [MODIFY] `src/omnimash/api/app.py`
- Update `GenerateRequest` and `CommitRequest` models to include `session_name: str | None = None`.
- In the React Web UI dashboard:
  - Add state variable `const [sessionName, setSessionName] = useState("dripwarts_vol1");`.
  - Add a **`🗂️ Session / GCS Folder Name`** input field at the top of the Prompt & Multimodal Inputs form.
  - Pass `session_name: sessionName` in `POST /api/generate` and `POST /api/commit`.

```jsx
<div>
    <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider mb-1 flex items-center justify-between">
        <span>🗂️ Session / GCS Folder Name</span>
        <span className="text-[10px] text-teal-400 font-mono">gs://bucket/sessions/{sessionName || "default"}/</span>
    </label>
    <input
        type="text"
        value={sessionName}
        onChange={(e) => setSessionName(e.target.value)}
        placeholder="e.g. dripwarts_vol1, snape_rap_remix..."
        className="w-full bg-gray-950 border border-gray-800 rounded-lg p-2.5 text-xs text-white placeholder-gray-600 focus:border-purple-500 focus:outline-none font-mono"
    />
</div>
```

---

### Component 3: Container Font Dependencies & Resilient Visualizer Rendering

#### [MODIFY] `Dockerfile`
- Add `fonts-dejavu-core` and `fonts-freefont-ttf` to `apt-get install -y`.

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*
```

#### [MODIFY] `src/omnimash/engine/omni_client.py`
- Add structured logger `logger = logging.getLogger("omnimash.engine")`.
- In `_generate_live_omni_flash_video()` and `_generate_live_veo_video()`: log Vertex AI API requests and catch/log exceptions with full details.
- In `ensure_rendered_video()`:
  - Upgrade fallback FFmpeg pipeline to generate an animated procedural audio visualizer with pulsing color gradients and sound waves (`showwaves=s=1280x720:mode=cline:colors=0xDE5FE9|0x34A853`) whenever static banner images or fonts are unavailable, guaranteeing 100% animated visual motion on every clip.

---

## Bite-Sized Implementation Tasks

### Task 1: Session Name Selector in State Manager & Agent Orchestrator
**Files:**
- Modify: `src/omnimash/state/session_manager.py`
- Modify: `src/omnimash/agent/orchestrator.py`
- Test: `tests/state/test_session_manager.py`

**Steps:**
1. Write failing test `test_session_manager_custom_session_name()` in `tests/state/test_session_manager.py`.
2. Run `uv run pytest tests/state/test_session_manager.py` to confirm failure.
3. Update `SessionManager` and `OmniMashAgent` to accept and sanitize `session_name`.
4. Run `uv run pytest tests/state/test_session_manager.py` to verify pass.
5. Commit changes.

---

### Task 2: UI Dashboard Session Selector & API Integration
**Files:**
- Modify: `src/omnimash/api/app.py`
- Test: `tests/api/test_integration.py`

**Steps:**
1. Write failing integration test `test_e2e_custom_session_name_gcs_mapping()` in `tests/api/test_integration.py`.
2. Run `uv run pytest tests/api/test_integration.py` to verify failure.
3. Update `GenerateRequest`, `CommitRequest`, and React Web UI in `src/omnimash/api/app.py` with the Session Name input control and GCS path indicator.
4. Run `uv run pytest tests/api/test_integration.py` to verify pass.
5. Commit changes.

---

### Task 3: Container Font Packages, Explicit Logging & Resilient Video Visualizer
**Files:**
- Modify: `Dockerfile`
- Modify: `src/omnimash/engine/omni_client.py`
- Test: `tests/engine/test_omni_client.py`

**Steps:**
1. Write test `test_ensure_rendered_video_procedural_visualizer_fallback()` in `tests/engine/test_omni_client.py`.
2. Add `fonts-dejavu-core fonts-freefont-ttf` to `Dockerfile`.
3. Add structured logging and animated procedural audio visualizer in `src/omnimash/engine/omni_client.py`.
4. Run `uv run pytest tests/engine/test_omni_client.py` to verify pass.
5. Commit changes.

---

## Verification Plan

### Automated Tests
```bash
# Run full Pytest test suite
uv run pytest

# Run linting and formatting
uv run ruff check --fix .
uv run ruff format .

# Run static typing
uv run ty check .
```

### Manual Verification
1. Start local dev server: `uv run uvicorn src.omnimash.api.app:create_app --factory --reload --port 8000`
2. Open dashboard in browser (`http://localhost:8000`).
3. Type a custom Session Name (`dripwarts_session_test`).
4. Generate a video clip and verify that the GCS path indicator and session state reflect `sessions/dripwarts_session_test/`.
5. Verify that the rendered video displays dynamic animated motion.
