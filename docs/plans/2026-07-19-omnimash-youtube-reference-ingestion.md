# YouTube Reference URLs & Audio Track Ingestion Implementation Plan

## Overview
Enable users to attach public YouTube video links (e.g. `https://www.youtube.com/@Onirostudios` or instrumental tracks) and reference audio stems directly through the API and Web UI dashboard. The backend extracts character portrait visual anchors and audio beat stems via `MediaExtractor` and attaches them to the multimodal prompt.

---

## User Review Required

> [!NOTE]
> All subagent executions inherit full permissions (`Workspace: "inherit"`, `command(*)` execution) and follow strict TDD (`uv run pytest`, `uv run ruff`, `uv run ty`).

---

## Proposed Changes & Tasks

### Subsystem 1: Orchestrator & API Integration

#### [Task 1] Extend `GenerateRequest` and `OmniMashAgent.process_user_turn()`
- Update `GenerateRequest` in `src/omnimash/api/app.py` to include `reference_url: str | None = None`.
- Update `OmniMashAgent.process_user_turn()` in `src/omnimash/agent/orchestrator.py` to accept `reference_url: str | None = None`.
- When `reference_url` is provided, invoke `self.media_extractor.process_youtube_url(reference_url)` and attach audio stem / keyframe metadata to the turn.
- Add tests in `tests/agent/test_orchestrator.py`.

### Subsystem 2: Web UI Dashboard

#### [Task 2] Add YouTube Reference URL & Audio Track Input in `src/omnimash/api/app.py`
- Add a dedicated **"📺 YouTube Reference URL / Audio Track"** input bar in the Web UI dashboard right below the prompt bar.
- When filled, display an active **"🎵 Reference Audio Stem Attached"** badge in the 5-Part Preview Card.
- Update end-to-end integration tests in `tests/api/test_integration.py`.

---

## Verification Plan

### Automated Tests
1. `uv run pytest` - Full test suite pass across all subsystems.
2. `uv run ruff check .` & `uv run ruff format --check .` - Clean formatting.
3. `uv run ty check .` - Static typing pass.

### Live Cloud Verification
- Test `POST /api/generate` with `reference_url` and deploy updated revision to Google Cloud Run.
