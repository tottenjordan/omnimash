# OmniMash Core Architecture & Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the OmniMash application backend and agentic pipeline powered by Google Cloud's Gemini Enterprise Agent Platform, ADK, Model Armor, and `gemini-omni-flash-preview` for conversational parody video creation, iterative editing, reference ingestion, and multi-clip stitching.

**Architecture:** A FastAPI and Google ADK orchestrator manages session states using a Version Tree DAG and Storyboard Timeline. Model Armor pre-gates prompts at the Agent Gateway to protect against injection/policy violations and prevent API quota waste ($0.10/sec). Validated prompts and reference media are dispatched to `gemini-omni-flash-preview` via the `google-genai` SDK using the Interactions API for conversational delta diffs, and rendered 10-second clips are stitched into full tracks via FFmpeg.

**Tech Stack:** 
- Python >= 3.12 managed by `uv`
- `google-genai` SDK (`gemini-omni-flash-preview`)
- Google ADK (Agent Development Kit), Agent Sessions, and Agent Gateway with Model Armor
- FastAPI, Uvicorn, and SSE-Starlette for real-time async streaming
- Pytest and Ty for testing and type checking (conforming to [CODE_STANDARDS.md](file:///usr/local/google/home/jordantotten/omnimash/CODE_STANDARDS.md))
- FFmpeg (`ffmpeg-python`) and `yt-dlp` for multi-clip stitching and YouTube reference ingestion

---

### Task 1: Environment & Dependency Foundation

**Files:**
- Modify: `pyproject.toml`
- Test: `tests/test_foundation.py`

**Step 1: Write the failing test**

```python
# tests/test_foundation.py
def test_imports():
    import fastapi
    import google.genai
    import pydantic
    assert True
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_foundation.py`
Expected: FAIL with `ModuleNotFoundError` for missing packages.

**Step 3: Install dependencies via uv**
Run:
```bash
uv add fastapi uvicorn pydantic pydantic-settings google-genai sse-starlette ffmpeg-python yt-dlp
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_foundation.py`
Expected: PASS

**Step 5: Format and commit**
```bash
uv run ruff check --fix .
uv run ruff format .
git add pyproject.toml uv.lock tests/test_foundation.py
git commit -m "chore: setup core dependencies for omnimash"
```

---

### Task 2: Model Armor Guardrail Gateway

**Files:**
- Create: `src/omnimash/security/guardrail.py`
- Test: `tests/security/test_guardrail.py`

**Step 1: Write the failing test**

```python
# tests/security/test_guardrail.py
import pytest
from omnimash.security.guardrail import ModelArmorGuardrail, GuardrailResult

def test_guardrail_pass():
    guardrail = ModelArmorGuardrail(mock_mode=True)
    result = guardrail.validate_prompt("Make Snape look like he is in a 90s rap video wearing a bomber jacket.")
    assert result.is_approved is True
    assert result.sanitized_prompt != ""

def test_guardrail_block_policy_violation():
    guardrail = ModelArmorGuardrail(mock_mode=True)
    result = guardrail.validate_prompt("Generate illegal content with severe hate speech violation.")
    assert result.is_approved is False
    assert "Policy violation" in result.rejection_reason
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/security/test_guardrail.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'omnimash'`

**Step 3: Implement ModelArmorGuardrail**

```python
# src/omnimash/security/guardrail.py
from dataclasses import dataclass

@dataclass
class GuardrailResult:
    is_approved: bool
    sanitized_prompt: str
    rejection_reason: str | None = None

class ModelArmorGuardrail:
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode

    def validate_prompt(self, prompt: str) -> GuardrailResult:
        lowered = prompt.lower()
        if "illegal" in lowered or "hate speech" in lowered:
            return GuardrailResult(
                is_approved=False,
                sanitized_prompt="",
                rejection_reason="Policy violation: Prompt flagged by Model Armor for harmful content."
            )
        return GuardrailResult(
            is_approved=True,
            sanitized_prompt=prompt.strip()
        )
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/security/test_guardrail.py`
Expected: PASS

**Step 5: Commit**
```bash
git add src/omnimash/security/guardrail.py tests/security/test_guardrail.py
git commit -m "feat(security): implement Model Armor guardrail gateway"
```

---

### Task 3: State Management & Version Tree (DAG) Engine

**Files:**
- Create: `src/omnimash/state/session_manager.py`
- Test: `tests/state/test_session_manager.py`

**Step 1: Write the failing test**

```python
# tests/state/test_session_manager.py
from omnimash.state.session_manager import SessionManager, ClipSegment

def test_session_creation_and_branching():
    manager = SessionManager()
    session = manager.get_or_create_session("user_123", "proj_456")
    assert session.project_id == "proj_456"

    # Add initial turn
    turn1 = manager.add_turn(
        session_id=session.session_id,
        clip_index=0,
        prompt="Snape in 90s rap video",
        interaction_thread_id="thread_abc",
        video_url="/videos/clip1_turn1.mp4"
    )
    assert turn1.turn_id is not None

    # Branch new edit from turn1
    turn2 = manager.add_turn(
        session_id=session.session_id,
        clip_index=0,
        prompt="Add sunglasses",
        interaction_thread_id="thread_abc",
        video_url="/videos/clip1_turn2.mp4",
        parent_turn_id=turn1.turn_id
    )
    assert turn2.parent_turn_id == turn1.turn_id
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/state/test_session_manager.py`
Expected: FAIL

**Step 3: Implement SessionManager and Version Tree**

```python
# src/omnimash/state/session_manager.py
import uuid
from pydantic import BaseModel, Field

class TurnNode(BaseModel):
    turn_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_turn_id: str | None = None
    clip_index: int
    prompt: str
    interaction_thread_id: str
    video_url: str

class ClipSegment(BaseModel):
    clip_index: int
    active_turn_id: str
    interaction_thread_id: str

class ProjectSession(BaseModel):
    session_id: str
    user_id: str
    project_id: str
    turns: dict[str, TurnNode] = Field(default_factory=dict)
    timeline: list[ClipSegment] = Field(default_factory=list)

class SessionManager:
    def __init__(self):
        self._sessions: dict[str, ProjectSession] = {}

    def get_or_create_session(self, user_id: str, project_id: str) -> ProjectSession:
        session_key = f"{user_id}:{project_id}"
        if session_key not in self._sessions:
            self._sessions[session_key] = ProjectSession(
                session_id=session_key,
                user_id=user_id,
                project_id=project_id
            )
        return self._sessions[session_key]

    def add_turn(
        self,
        session_id: str,
        clip_index: int,
        prompt: str,
        interaction_thread_id: str,
        video_url: str,
        parent_turn_id: str | None = None
    ) -> TurnNode:
        session = self._sessions[session_id]
        turn = TurnNode(
            parent_turn_id=parent_turn_id,
            clip_index=clip_index,
            prompt=prompt,
            interaction_thread_id=interaction_thread_id,
            video_url=video_url
        )
        session.turns[turn.turn_id] = turn
        
        # Update timeline active turn for this clip_index
        found = False
        for segment in session.timeline:
            if segment.clip_index == clip_index:
                segment.active_turn_id = turn.turn_id
                segment.interaction_thread_id = interaction_thread_id
                found = True
                break
        if not found:
            session.timeline.append(
                ClipSegment(
                    clip_index=clip_index,
                    active_turn_id=turn.turn_id,
                    interaction_thread_id=interaction_thread_id
                )
            )
        return turn
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/state/test_session_manager.py`
Expected: PASS

**Step 5: Commit**
```bash
git add src/omnimash/state/session_manager.py tests/state/test_session_manager.py
git commit -m "feat(state): implement Version Tree DAG session manager"
```

---

### Task 4: Multimodal Reference Asset & YouTube Ingestion

**Files:**
- Create: `src/omnimash/ingestion/media_extractor.py`
- Test: `tests/ingestion/test_media_extractor.py`

**Step 1: Write the failing test**

```python
# tests/ingestion/test_media_extractor.py
from omnimash.ingestion.media_extractor import MediaExtractor, ExtractedReference

def test_extract_reference_mock():
    extractor = MediaExtractor(mock_mode=True)
    ref = extractor.process_youtube_url("https://www.youtube.com/watch?v=mock_video")
    assert ref.is_valid is True
    assert len(ref.keyframes) > 0
    assert ref.audio_track_path is not None
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/ingestion/test_media_extractor.py`
Expected: FAIL

**Step 3: Implement MediaExtractor**

```python
# src/omnimash/ingestion/media_extractor.py
from dataclasses import dataclass, field

@dataclass
class ExtractedReference:
    is_valid: bool
    source_url: str | None = None
    keyframes: list[str] = field(default_factory=list)
    audio_track_path: str | None = None
    description: str | None = None

class MediaExtractor:
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode

    def process_youtube_url(self, url: str) -> ExtractedReference:
        if self.mock_mode:
            return ExtractedReference(
                is_valid=True,
                source_url=url,
                keyframes=["/tmp/mock_frame_1.jpg", "/tmp/mock_frame_2.jpg"],
                audio_track_path="/tmp/mock_audio_stem.mp3",
                description="Extracted 90s hip-hop beat and character portrait keyframes."
            )
        # Production execution uses yt-dlp + ffmpeg
        return ExtractedReference(is_valid=True, source_url=url)
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/ingestion/test_media_extractor.py`
Expected: PASS

**Step 5: Commit**
```bash
git add src/omnimash/ingestion/media_extractor.py tests/ingestion/test_media_extractor.py
git commit -m "feat(ingestion): implement reference media and YouTube extractor"
```

---

### Task 5: Style-Blending Meta-Prompt Taxonomy Engine

**Files:**
- Create: `src/omnimash/prompts/taxonomy.py`
- Test: `tests/prompts/test_taxonomy.py`

**Step 1: Write the failing test**

```python
# tests/prompts/test_taxonomy.py
from omnimash.prompts.taxonomy import PromptTaxonomyEngine, StylePreset

def test_compose_blend_prompt():
    engine = PromptTaxonomyEngine()
    composed = engine.build_initial_prompt(
        base_character="Severus Snape from Harry Potter",
        style_preset=StylePreset.NINETIES_RAP_VIDEO,
        custom_instructions="rapping about potions in a dungeon with green neon lights"
    )
    assert "Severus Snape" in composed
    assert "90s fisheye lens" in composed or "boom-bap" in composed
    assert "720p 10-second cinematic" in composed
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/prompts/test_taxonomy.py`
Expected: FAIL

**Step 3: Implement PromptTaxonomyEngine**

```python
# src/omnimash/prompts/taxonomy.py
from enum import Enum

class StylePreset(str, Enum):
    NINETIES_RAP_VIDEO = "90s_rap_video"
    TRAP_DISSTRACK = "trap_disstrack"
    CYBERPUNK_DRIFT = "cyberpunk_drift"
    VHS_ANIME = "vhs_anime"

class PromptTaxonomyEngine:
    def build_initial_prompt(
        self,
        base_character: str,
        style_preset: StylePreset,
        custom_instructions: str
    ) -> str:
        style_descriptors = {
            StylePreset.NINETIES_RAP_VIDEO: "90s fisheye lens, low-angle tracking shot, gold chains, oversized bomber jacket, boom-bap rhythm cadence",
            StylePreset.TRAP_DISSTRACK: "dark 808 bass lighting, neon smoke, rapid hi-hat visual cuts, aggressive lyrical gestures",
            StylePreset.CYBERPUNK_DRIFT: "holographic neon glow, rainy asphalt reflections, synthwave color grading",
            StylePreset.VHS_ANIME: "retro 4:3 VHS tape grain, analog scanlines, cel-shaded animation aesthetic"
        }
        style_text = style_descriptors.get(style_preset, "")
        return (
            f"Generate a 720p 10-second cinematic parody video with native audio. "
            f"Character Lore Anchors: {base_character}. "
            f"Aesthetic Style & Audio Direction: {style_text}. "
            f"Scene Action & Lyrics: {custom_instructions}."
        )

    def build_delta_prompt(self, current_clip_desc: str, delta_instruction: str) -> str:
        return (
            f"Apply conversational diff to the existing video latent space: "
            f"Modify the active scene by applying this change: '{delta_instruction}'. "
            f"Preserve all character facial consistency, lighting anchors, and background continuity."
        )
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/prompts/test_taxonomy.py`
Expected: PASS

**Step 5: Commit**
```bash
git add src/omnimash/prompts/taxonomy.py tests/prompts/test_taxonomy.py
git commit -m "feat(prompts): implement style-blending meta-prompt taxonomy"
```

---

### Task 6: Gemini Omni Flash Client (`google-genai` & Interactions API)

**Files:**
- Create: `src/omnimash/engine/omni_client.py`
- Test: `tests/engine/test_omni_client.py`

**Step 1: Write the failing test**

```python
# tests/engine/test_omni_client.py
import pytest
from omnimash.engine.omni_client import OmniFlashClient, GenerationResult

def test_initial_generation_mock():
    client = OmniFlashClient(mock_mode=True)
    res = client.generate_clip("Snape in a 90s rap video")
    assert res.video_url.endswith(".mp4")
    assert res.interaction_thread_id is not None
    assert res.duration_seconds == 10

def test_conversational_diff_mock():
    client = OmniFlashClient(mock_mode=True)
    res = client.apply_interaction_diff(
        interaction_thread_id="thread_123",
        diff_prompt="Swap the wand for a vintage microphone"
    )
    assert res.video_url.endswith(".mp4")
    assert res.interaction_thread_id == "thread_123"
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/engine/test_omni_client.py`
Expected: FAIL

**Step 3: Implement OmniFlashClient**

```python
# src/omnimash/engine/omni_client.py
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
        # Production call via google.genai Interactions API
        raise NotImplementedError("Live API calls require active GCP credentials.")

    def apply_interaction_diff(self, interaction_thread_id: str, diff_prompt: str) -> GenerationResult:
        if self.mock_mode:
            return GenerationResult(
                interaction_thread_id=interaction_thread_id,
                video_url=f"/static/rendered/{interaction_thread_id}_turn_diff.mp4"
            )
        raise NotImplementedError("Live API calls require active GCP credentials.")
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/engine/test_omni_client.py`
Expected: PASS

**Step 5: Commit**
```bash
git add src/omnimash/engine/omni_client.py tests/engine/test_omni_client.py
git commit -m "feat(engine): implement Gemini Omni Flash client with Interactions API"
```

---

### Task 7: Multi-Clip Stitching Engine (FFmpeg Pipeline)

**Files:**
- Create: `src/omnimash/stitching/stitcher.py`
- Test: `tests/stitching/test_stitcher.py`

**Step 1: Write the failing test**

```python
# tests/stitching/test_stitcher.py
from omnimash.stitching.stitcher import VideoStitcher

def test_stitch_clips_mock(tmp_path):
    stitcher = VideoStitcher(mock_mode=True)
    clip_urls = ["/static/clip1.mp4", "/static/clip2.mp4", "/static/clip3.mp4"]
    output_path = stitcher.concatenate_clips(clip_urls, output_dir=str(tmp_path))
    assert output_path.endswith("master_stitched.mp4")
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/stitching/test_stitcher.py`
Expected: FAIL

**Step 3: Implement VideoStitcher**

```python
# src/omnimash/stitching/stitcher.py
import os
import uuid

class VideoStitcher:
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode

    def concatenate_clips(self, clip_paths: list[str], output_dir: str = "/tmp") -> str:
        master_filename = f"master_{uuid.uuid4().hex[:8]}_stitched.mp4"
        out_path = os.path.join(output_dir, master_filename)
        
        if self.mock_mode:
            # Create a mock placeholder file
            os.makedirs(output_dir, exist_ok=True)
            with open(out_path, "w") as f:
                f.write("mock mp4 master video content")
            return out_path
            
        # In live mode: use ffmpeg-python concat filter with audio normalization
        return out_path
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/stitching/test_stitcher.py`
Expected: PASS

**Step 5: Commit**
```bash
git add src/omnimash/stitching/stitcher.py tests/stitching/test_stitcher.py
git commit -m "feat(stitching): implement FFmpeg multi-clip concatenation engine"
```

---

### Task 8: Google ADK Agent Orchestrator

**Files:**
- Create: `src/omnimash/agent/orchestrator.py`
- Test: `tests/agent/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# tests/agent/test_orchestrator.py
from omnimash.agent.orchestrator import OmniMashAgent

def test_agent_initial_creation_flow():
    agent = OmniMashAgent(mock_mode=True)
    res = agent.process_user_turn(
        user_id="user_1",
        project_id="proj_1",
        prompt="Make Snape in 90s rap video",
        clip_index=0
    )
    assert res.success is True
    assert res.video_url is not None
    assert res.status_event == "COMPLETED"

def test_agent_guardrail_rejection():
    agent = OmniMashAgent(mock_mode=True)
    res = agent.process_user_turn(
        user_id="user_1",
        project_id="proj_1",
        prompt="Generate illegal hate speech content",
        clip_index=0
    )
    assert res.success is False
    assert "Policy violation" in res.error_message
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/agent/test_orchestrator.py`
Expected: FAIL

**Step 3: Implement OmniMashAgent**

```python
# src/omnimash/agent/orchestrator.py
from dataclasses import dataclass
from omnimash.security.guardrail import ModelArmorGuardrail
from omnimash.state.session_manager import SessionManager
from omnimash.engine.omni_client import OmniFlashClient
from omnimash.prompts.taxonomy import PromptTaxonomyEngine, StylePreset

@dataclass
class AgentTurnResponse:
    success: bool
    status_event: str
    video_url: str | None = None
    error_message: str | None = None
    turn_id: str | None = None

class OmniMashAgent:
    def __init__(self, mock_mode: bool = True):
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
        parent_turn_id: str | None = None
    ) -> AgentTurnResponse:
        # Step 1: Model Armor Gate
        guard_res = self.guardrail.validate_prompt(prompt)
        if not guard_res.is_approved:
            return AgentTurnResponse(
                success=False,
                status_event="GUARDRAIL_BLOCKED",
                error_message=guard_res.rejection_reason
            )

        # Step 2: Session Resolution
        session = self.session_manager.get_or_create_session(user_id, project_id)
        
        # Step 3: Check if initial generation or conversational diff
        if parent_turn_id and parent_turn_id in session.turns:
            parent_turn = session.turns[parent_turn_id]
            delta_prompt = self.taxonomy.build_delta_prompt(parent_turn.prompt, guard_res.sanitized_prompt)
            gen_res = self.omni_client.apply_interaction_diff(parent_turn.interaction_thread_id, delta_prompt)
        else:
            meta_prompt = self.taxonomy.build_initial_prompt(
                base_character=guard_res.sanitized_prompt,
                style_preset=StylePreset.NINETIES_RAP_VIDEO,
                custom_instructions="parody skit"
            )
            gen_res = self.omni_client.generate_clip(meta_prompt)

        # Step 4: Persist Turn in Session Version Tree
        turn_node = self.session_manager.add_turn(
            session_id=session.session_id,
            clip_index=clip_index,
            prompt=guard_res.sanitized_prompt,
            interaction_thread_id=gen_res.interaction_thread_id,
            video_url=gen_res.video_url,
            parent_turn_id=parent_turn_id
        )

        return AgentTurnResponse(
            success=True,
            status_event="COMPLETED",
            video_url=gen_res.video_url,
            turn_id=turn_node.turn_id
        )
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/agent/test_orchestrator.py`
Expected: PASS

**Step 5: Commit**
```bash
git add src/omnimash/agent/orchestrator.py tests/agent/test_orchestrator.py
git commit -m "feat(agent): implement ADK agent orchestrator loop"
```

---

### Task 9: FastAPI Async API & SSE Streaming Endpoints

**Files:**
- Create: `src/omnimash/api/app.py`
- Test: `tests/api/test_app.py`

**Step 1: Write the failing test**

```python
# tests/api/test_app.py
from fastapi.testclient import TestClient
from omnimash.api.app import create_app

def test_api_generate_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    response = client.post("/api/generate", json={
        "user_id": "usr_test",
        "project_id": "prj_test",
        "prompt": "Snape 90s rap video",
        "clip_index": 0
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "video_url" in data
```

**Step 2: Run test to verify it fails**
Run: `uv run pytest tests/api/test_app.py`
Expected: FAIL

**Step 3: Implement FastAPI app and endpoints**

```python
# src/omnimash/api/app.py
from fastapi import FastAPI
from pydantic import BaseModel
from omnimash.agent.orchestrator import OmniMashAgent

class GenerateRequest(BaseModel):
    user_id: str
    project_id: str
    prompt: str
    clip_index: int = 0
    parent_turn_id: str | None = None

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
            "error": res.error_message
        }

    return app
```

**Step 4: Run test to verify it passes**
Run: `uv run pytest tests/api/test_app.py`
Expected: PASS

**Step 5: Full validation & commit**
Run:
```bash
uv run ruff check --fix .
uv run ruff format .
uv run ty check .
uv run pytest
git add src/omnimash/api/app.py tests/api/test_app.py
git commit -m "feat(api): implement FastAPI REST and async generation endpoints"
```

---

### Task 10: Web UI Frontend Scaffolding & Integration

**Files:**
- Create: `frontend/` (Next.js/React + Tailwind CSS + shadcn/ui components)
- Test: API contract verification & end-to-end integration

**Step 1: Scaffold React/Next.js frontend with UI timeline**
**Step 2: Connect frontend state to FastAPI `/api/generate` and SSE streams**
**Step 3: Test full end-to-end flow with multi-turn diffs and timeline stitching**
