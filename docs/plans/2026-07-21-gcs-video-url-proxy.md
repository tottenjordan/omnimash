# GCS Video URL Media Proxy Routing Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure turn video URLs returned by `OmniMashAgent` use persistent GCS Media Proxy endpoints (`/api/media-proxy?uri=gs://...`), preventing 404 static file errors on Cloud Run.

---

## 📋 Execution Plan

### 1. 🎥 Media Proxy Video URL Formatting (`OmniMashAgent`)
- **Requirement**: When generating or extending a scene turn (`generate_initial_video_turn`, `extend_scene`, `commit_and_branch`), return the media proxy URL `/api/media-proxy?uri={gcs_uri}` instead of the local ephemeral `/static/rendered/turn_N_video.mp4` path.
- **Implementation**:
  - In `src/omnimash/agent/orchestrator.py`:
    - After `gen_res` completes and intermediate video is uploaded to GCS (`sessions/{session_id}/intermediate/turn_{turn_index}_video.mp4`), construct the GCS URI `gs://{bucket_name}/sessions/{session_id}/intermediate/turn_{turn_index}_video.mp4`.
    - Format `proxy_video_url = f"/api/media-proxy?uri={urllib.parse.quote(gcs_uri, safe='')}"`.
    - Store `proxy_video_url` on the turn node and return it in `AgentTurnResponse.video_url`.

### 2. 🧪 Unit & Integration Testing
- In `tests/agent/test_orchestrator.py` & `tests/api/test_integration.py`:
  - Add test verifying `generate_initial_video_turn` returns a video URL starting with `/api/media-proxy?uri=gs://`.
- Run `uv run pytest`.

---

## Tech Stack & Tools
Python 3.12, FastAPI, GCS Storage Client, pytest, uv, ruff, ty.

---

## Execution Tasks

### Task 1: Update Orchestrator to Return Media Proxy Video URLs
- Update `generate_initial_video_turn` and `extend_scene` in `src/omnimash/agent/orchestrator.py` to construct GCS URIs and format `/api/media-proxy?uri=...` video URLs.
- Add test assertions in `tests/agent/test_orchestrator.py`.
- Run `uv run pytest tests/agent/test_orchestrator.py`.

### Task 2: Full Verification & Quality Suite Pass
- Run full test suite (`uv run pytest`, `ruff check`, `ruff format`, `ty check`).
