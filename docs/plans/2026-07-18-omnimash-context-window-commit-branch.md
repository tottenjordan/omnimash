# Context Window "Commit & Branch" Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate multimodal context window decay and visual drift in `gemini-omni-flash-preview` by implementing a 5-step "Commit & Branch" checkpointing architecture that flushes conversational history while preserving 720p visual state.

**Architecture:** The Version Tree DAG tracks thread edit depth. When depth reaches $\ge 3$, the orchestrator signals `COMMIT_RECOMMENDED`. On user commit via `POST /api/commit`, the engine extracts the latest 720p output video, closes the cluttered thread, and initializes a fresh Interactions API thread using the committed video as the base visual anchor.

**Tech Stack:** Python 3.12, Google ADK 2.5 (`google.adk.agents.Agent`), Gemini Omni Flash (`google-genai`), FastAPI, Uvicorn, Pydantic, Pytest, Ruff, Ty.

---

### Task 1: State Model Checkpointing & Thread Depth Tracking

**Files:**
- Modify: `src/omnimash/state/session_manager.py`
- Test: `tests/state/test_session_manager.py`

**Step 1: Write the failing test**

```python
def test_commit_turn_and_depth_tracking():
    sm = SessionManager()
    session = sm.get_or_create_session("user_test", "proj_test")
    t1 = sm.add_turn(session.session_id, 0, "Prompt 1", "thread_1", "/clip1.mp4")
    assert t1.edit_depth_in_thread == 0
    assert t1.is_committed is False

    t2 = sm.add_turn(
        session.session_id,
        0,
        "Prompt 2",
        "thread_1",
        "/clip2.mp4",
        parent_turn_id=t1.turn_id,
    )
    assert t2.edit_depth_in_thread == 1

    committed = sm.commit_turn(session.session_id, t2.turn_id)
    assert committed.is_committed is True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/state/test_session_manager.py -v`  
Expected: FAIL with `AttributeError: 'TurnNode' object has no attribute 'edit_depth_in_thread'`

**Step 3: Write minimal implementation**

Modify `src/omnimash/state/session_manager.py`:
```python
from dataclasses import dataclass, field
import uuid

@dataclass
class TurnNode:
    turn_id: str
    clip_index: int
    prompt: str
    interaction_thread_id: str
    video_url: str
    parent_turn_id: str | None = None
    edit_depth_in_thread: int = 0
    is_committed: bool = False
    base_video_anchor_url: str | None = None

@dataclass
class ClipSegment:
    clip_index: int
    active_turn_id: str

@dataclass
class ProjectSession:
    session_id: str
    user_id: str
    project_id: str
    turns: dict[str, TurnNode] = field(default_factory=dict)
    timeline: list[ClipSegment] = field(default_factory=list)

class SessionManager:
    def __init__(self):
        self.sessions: dict[str, ProjectSession] = {}

    def get_or_create_session(self, user_id: str, project_id: str) -> ProjectSession:
        session_id = f"sess_{user_id}_{project_id}"
        if session_id not in self.sessions:
            self.sessions[session_id] = ProjectSession(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id
            )
        return self.sessions[session_id]

    def add_turn(
        self,
        session_id: str,
        clip_index: int,
        prompt: str,
        interaction_thread_id: str,
        video_url: str,
        parent_turn_id: str | None = None,
        is_checkpoint: bool = False
    ) -> TurnNode:
        session = self.sessions[session_id]
        turn_id = f"turn_{uuid.uuid4().hex[:8]}"
        
        depth = 0
        if parent_turn_id and parent_turn_id in session.turns:
            parent = session.turns[parent_turn_id]
            if parent.interaction_thread_id == interaction_thread_id and not is_checkpoint:
                depth = parent.edit_depth_in_thread + 1

        node = TurnNode(
            turn_id=turn_id,
            clip_index=clip_index,
            prompt=prompt,
            interaction_thread_id=interaction_thread_id,
            video_url=video_url,
            parent_turn_id=parent_turn_id,
            edit_depth_in_thread=depth,
            is_committed=is_checkpoint
        )
        session.turns[turn_id] = node

        # Update or append timeline
        updated = False
        for seg in session.timeline:
            if seg.clip_index == clip_index:
                seg.active_turn_id = turn_id
                updated = True
                break
        if not updated:
            session.timeline.append(ClipSegment(clip_index=clip_index, active_turn_id=turn_id))

        return node

    def commit_turn(self, session_id: str, turn_id: str) -> TurnNode:
        session = self.sessions[session_id]
        if turn_id not in session.turns:
            raise KeyError(f"Turn {turn_id} not found in session {session_id}")
        node = session.turns[turn_id]
        node.is_committed = True
        return node
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/state/test_session_manager.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/state/session_manager.py tests/state/test_session_manager.py
git commit -m "feat(state): add thread depth tracking and checkpoint commit support to session DAG"
```

---

### Task 2: Gemini Omni Flash Base Video Re-Anchoring

**Files:**
- Modify: `src/omnimash/engine/omni_client.py`
- Test: `tests/engine/test_omni_client.py`

**Step 1: Write the failing test**

```python
def test_start_thread_from_video_mock():
    client = OmniFlashClient(mock_mode=True)
    res = client.start_thread_from_video(
        base_video_url="/static/rendered/clip1.mp4",
        initial_prompt="Add cyberpunk rain"
    )
    assert res.interaction_thread_id.startswith("reanchored_thread_")
    assert res.video_url.endswith(".mp4")
    assert res.duration_seconds == 10
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/engine/test_omni_client.py -v`  
Expected: FAIL with `AttributeError: 'OmniFlashClient' object has no attribute 'start_thread_from_video'`

**Step 3: Write minimal implementation**

Modify `src/omnimash/engine/omni_client.py`:
```python
import uuid
from dataclasses import dataclass

@dataclass
class GenerationResult:
    interaction_thread_id: str
    video_url: str
    duration_seconds: int = 10
    synth_id_watermark: str = "SYNTHID_C2PA_VERIFIED"

class OmniFlashClient:
    def __init__(self, api_key: str | None = None, mock_mode: bool = True):
        self.api_key = api_key
        self.mock_mode = mock_mode

    def generate_clip(self, prompt: str) -> GenerationResult:
        if self.mock_mode:
            thread_id = f"thread_{uuid.uuid4().hex[:8]}"
            return GenerationResult(
                interaction_thread_id=thread_id,
                video_url=f"/static/rendered/{thread_id}_turn0.mp4"
            )
        raise NotImplementedError("Live API calls require active GCP credentials.")

    def apply_interaction_diff(self, interaction_thread_id: str, diff_prompt: str) -> GenerationResult:
        if self.mock_mode:
            return GenerationResult(
                interaction_thread_id=interaction_thread_id,
                video_url=f"/static/rendered/{interaction_thread_id}_turn_diff.mp4"
            )
        raise NotImplementedError("Live API calls require active GCP credentials.")

    def start_thread_from_video(self, base_video_url: str, initial_prompt: str | None = None) -> GenerationResult:
        if self.mock_mode:
            thread_id = f"reanchored_thread_{uuid.uuid4().hex[:8]}"
            return GenerationResult(
                interaction_thread_id=thread_id,
                video_url=f"/static/rendered/{thread_id}_turn0.mp4"
            )
        raise NotImplementedError("Live API calls require active GCP credentials.")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/engine/test_omni_client.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/engine/omni_client.py tests/engine/test_omni_client.py
git commit -m "feat(engine): add start_thread_from_video to re-anchor Omni Flash interactions"
```

---

### Task 3: ADK Orchestrator Commit & Branch Workflow

**Files:**
- Modify: `src/omnimash/agent/orchestrator.py`
- Test: `tests/agent/test_orchestrator.py`

**Step 1: Write the failing test**

```python
def test_commit_recommended_and_branch_flow():
    agent = OmniMashAgent(mock_mode=True)
    # Turn 1
    r1 = agent.process_user_turn("u1", "p1", "Snape 90s rap", 0)
    assert r1.status_event == "COMPLETED"

    # Turn 2, 3, 4
    r2 = agent.process_user_turn("u1", "p1", "Add gold chains", 0, r1.turn_id)
    r3 = agent.process_user_turn("u1", "p1", "Add neon lights", 0, r2.turn_id)
    r4 = agent.process_user_turn("u1", "p1", "Add fog", 0, r3.turn_id)
    assert r4.status_event == "COMMIT_RECOMMENDED"

    # Commit and branch
    c_res = agent.commit_and_branch("u1", "p1", r4.turn_id, "Add laser eyes")
    assert c_res.success is True
    assert c_res.status_event == "REANCHORED"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/agent/test_orchestrator.py -v`  
Expected: FAIL with `AttributeError: 'OmniMashAgent' object has no attribute 'commit_and_branch'`

**Step 3: Write minimal implementation**

Modify `src/omnimash/agent/orchestrator.py`:
```python
from dataclasses import dataclass
from google.adk.agents import Agent

from omnimash.engine.omni_client import OmniFlashClient
from omnimash.prompts.taxonomy import PromptTaxonomyEngine, StylePreset
from omnimash.security.guardrail import ModelArmorGuardrail
from omnimash.state.session_manager import SessionManager


@dataclass
class AgentTurnResponse:
    success: bool
    status_event: str
    video_url: str | None = None
    error_message: str | None = None
    turn_id: str | None = None
    depth: int = 0


class OmniMashAgent:
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self.guardrail = ModelArmorGuardrail(mock_mode=mock_mode)
        self.session_manager = SessionManager()
        self.omni_client = OmniFlashClient(mock_mode=mock_mode)
        self.taxonomy = PromptTaxonomyEngine()

    def process_user_turn(
        self,
        user_id: str,
        project_id: str,
        prompt: str,
        clip_index: int = 0,
        parent_turn_id: str | None = None,
    ) -> AgentTurnResponse:
        # Step 1: Model Armor Gate
        guard_res = self.guardrail.validate_prompt(prompt)
        if not guard_res.is_approved:
            return AgentTurnResponse(
                success=False,
                status_event="GUARDRAIL_BLOCKED",
                error_message=guard_res.rejection_reason,
            )

        # Step 2: Session Resolution
        session = self.session_manager.get_or_create_session(user_id, project_id)

        # Step 3: Check if initial generation or conversational diff
        if parent_turn_id and parent_turn_id in session.turns:
            parent_turn = session.turns[parent_turn_id]
            delta_prompt = self.taxonomy.build_delta_prompt(
                parent_turn.prompt, guard_res.sanitized_prompt
            )
            gen_res = self.omni_client.apply_interaction_diff(
                parent_turn.interaction_thread_id, delta_prompt
            )
        else:
            meta_prompt = self.taxonomy.build_initial_prompt(
                base_character=guard_res.sanitized_prompt,
                style_preset=StylePreset.NINETIES_RAP_VIDEO,
                custom_instructions="parody skit",
            )
            gen_res = self.omni_client.generate_clip(meta_prompt)

        # Step 4: Persist Turn in Session Version Tree
        turn_node = self.session_manager.add_turn(
            session_id=session.session_id,
            clip_index=clip_index,
            prompt=guard_res.sanitized_prompt,
            interaction_thread_id=gen_res.interaction_thread_id,
            video_url=gen_res.video_url,
            parent_turn_id=parent_turn_id,
        )

        status = "COMMIT_RECOMMENDED" if turn_node.edit_depth_in_thread >= 3 else "COMPLETED"

        return AgentTurnResponse(
            success=True,
            status_event=status,
            video_url=gen_res.video_url,
            turn_id=turn_node.turn_id,
            depth=turn_node.edit_depth_in_thread,
        )

    def commit_and_branch(
        self,
        user_id: str,
        project_id: str,
        turn_id: str,
        prompt: str,
    ) -> AgentTurnResponse:
        guard_res = self.guardrail.validate_prompt(prompt)
        if not guard_res.is_approved:
            return AgentTurnResponse(
                success=False,
                status_event="GUARDRAIL_BLOCKED",
                error_message=guard_res.rejection_reason,
            )

        session = self.session_manager.get_or_create_session(user_id, project_id)
        if turn_id not in session.turns:
            return AgentTurnResponse(
                success=False,
                status_event="ERROR",
                error_message=f"Turn {turn_id} not found",
            )

        # Commit target turn
        committed_turn = self.session_manager.commit_turn(session.session_id, turn_id)

        # Re-anchor Omni Flash thread from committed video
        gen_res = self.omni_client.start_thread_from_video(
            base_video_url=committed_turn.video_url,
            initial_prompt=guard_res.sanitized_prompt,
        )

        # Add new turn marked as checkpoint branch
        new_node = self.session_manager.add_turn(
            session_id=session.session_id,
            clip_index=committed_turn.clip_index,
            prompt=guard_res.sanitized_prompt,
            interaction_thread_id=gen_res.interaction_thread_id,
            video_url=gen_res.video_url,
            parent_turn_id=turn_id,
            is_checkpoint=True,
        )

        return AgentTurnResponse(
            success=True,
            status_event="REANCHORED",
            video_url=gen_res.video_url,
            turn_id=new_node.turn_id,
            depth=0,
        )


def build_adk_agent(mock_mode: bool = True) -> Agent:
    orchestrator = OmniMashAgent(mock_mode=mock_mode)

    def generate_parody_clip(
        user_id: str,
        project_id: str,
        prompt: str,
        clip_index: int = 0,
        parent_turn_id: str | None = None,
    ) -> dict[str, str | bool | None | int]:
        res = orchestrator.process_user_turn(
            user_id=user_id,
            project_id=project_id,
            prompt=prompt,
            clip_index=clip_index,
            parent_turn_id=parent_turn_id,
        )
        return {
            "success": res.success,
            "status": res.status_event,
            "video_url": res.video_url,
            "turn_id": res.turn_id,
            "depth": res.depth,
            "error": res.error_message,
        }

    return Agent(
        name="omnimash_orchestrator",
        model="gemini-omni-flash-preview",
        instruction=(
            "You are OmniMash, an AI parody and mashup video creation agent. "
            "Use generate_parody_clip to validate prompts through Model Armor, "
            "structure style-blended prompts, and generate 720p clips."
        ),
        tools=[generate_parody_clip],
    )


root_agent = build_adk_agent(mock_mode=True)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/agent/test_orchestrator.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/agent/orchestrator.py tests/agent/test_orchestrator.py
git commit -m "feat(agent): implement commit recommendation and commit_and_branch workflow"
```

---

### Task 4: FastAPI Commit Endpoints & SSE Streaming

**Files:**
- Modify: `src/omnimash/api/app.py`
- Test: `tests/api/test_app.py`

**Step 1: Write the failing test**

```python
def test_api_commit_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    gen_res = client.post(
        "/api/generate",
        json={
            "user_id": "usr_c",
            "project_id": "prj_c",
            "prompt": "Snape rap",
            "clip_index": 0,
        },
    )
    turn_id = gen_res.json()["turn_id"]

    commit_res = client.post(
        "/api/commit",
        json={
            "user_id": "usr_c",
            "project_id": "prj_c",
            "turn_id": turn_id,
            "next_prompt": "Continue with lasers",
        },
    )
    assert commit_res.status_code == 200
    data = commit_res.json()
    assert data["success"] is True
    assert data["status"] == "REANCHORED"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_app.py -v`  
Expected: FAIL with `404 Not Found` for `POST /api/commit`

**Step 3: Write minimal implementation**

Modify `src/omnimash/api/app.py`:
```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from omnimash.agent.orchestrator import OmniMashAgent

class GenerateRequest(BaseModel):
    user_id: str
    project_id: str
    prompt: str
    clip_index: int = 0
    parent_turn_id: str | None = None

class CommitRequest(BaseModel):
    user_id: str
    project_id: str
    turn_id: str
    next_prompt: str = ""

def create_app(mock_mode: bool = True) -> FastAPI:
    app = FastAPI(title="OmniMash API", version="0.1.0")
    agent = OmniMashAgent(mock_mode=mock_mode)

    @app.post("/api/generate")
    def generate_video(req: GenerateRequest):
        res = agent.process_user_turn(
            user_id=req.user_id,
            project_id=req.project_id,
            prompt=req.prompt,
            clip_index=req.clip_index,
            parent_turn_id=req.parent_turn_id
        )
        return {
            "success": res.success,
            "status": res.status_event,
            "video_url": res.video_url,
            "turn_id": res.turn_id,
            "depth": res.depth,
            "error": res.error_message
        }

    @app.post("/api/commit")
    def commit_turn_endpoint(req: CommitRequest):
        res = agent.commit_and_branch(
            user_id=req.user_id,
            project_id=req.project_id,
            turn_id=req.turn_id,
            prompt=req.next_prompt
        )
        return {
            "success": res.success,
            "status": res.status_event,
            "video_url": res.video_url,
            "turn_id": res.turn_id,
            "depth": res.depth,
            "error": res.error_message
        }

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(content="<h1>OmniMash Dashboard</h1>")

    return app
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_app.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/api/app.py tests/api/test_app.py
git commit -m "feat(api): add POST /api/commit endpoint for thread re-anchoring"
```

---

### Task 5: Web UI Dashboard "Commit & Re-Anchor" Modal & E2E Integration

**Files:**
- Modify: `src/omnimash/api/app.py`
- Test: `tests/api/test_integration.py`

**Step 1: Write the failing test**

```python
def test_e2e_commit_and_reanchor_pipeline():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    r1 = client.post(
        "/api/generate",
        json={"user_id": "u_e2e", "project_id": "p_e2e", "prompt": "Initial", "clip_index": 0}
    )
    t1 = r1.json()["turn_id"]

    t_prev = t1
    for i in range(3):
        r = client.post(
            "/api/generate",
            json={"user_id": "u_e2e", "project_id": "p_e2e", "prompt": f"Edit {i}", "clip_index": 0, "parent_turn_id": t_prev}
        )
        t_prev = r.json()["turn_id"]
        if i == 2:
            assert r.json()["status"] == "COMMIT_RECOMMENDED"

    rc = client.post(
        "/api/commit",
        json={"user_id": "u_e2e", "project_id": "p_e2e", "turn_id": t_prev, "next_prompt": "Reanchored turn"}
    )
    assert rc.json()["status"] == "REANCHORED"
    assert rc.json()["depth"] == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_integration.py -v`  
Expected: FAIL if endpoint or depth assertions are unmet.

**Step 3: Write minimal implementation**

Enhance the HTML/React template inside `src/omnimash/api/app.py` to:
- Render a **"Commit & Re-Anchor"** warning banner modal when `status === 'COMMIT_RECOMMENDED'`.
- Render a ⚓ green badge on checkpoint nodes in the Version Tree DAG viewer.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_integration.py -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add src/omnimash/api/app.py tests/api/test_integration.py
git commit -m "feat(ui): add commit & re-anchor modal banner and checkpoint DAG badge"
```

---

## 🧪 Global Quality & Verification Commands

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check .
```
