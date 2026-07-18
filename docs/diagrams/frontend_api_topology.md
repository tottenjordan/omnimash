# Frontend UI & FastAPI Async API Topology

This document details the Next.js / React 18 single-page application and its connection to FastAPI's async generation endpoints, commit endpoints, and SSE event streams (`src/omnimash/api/app.py`).

---

## 🖼️ Reference Architecture Diagram

![Frontend API Topology](frontend_api_topology.png)

---

## 🌐 Application Architecture

```mermaid
graph TD
    subgraph BrowserClient["Browser Client (Next.js / React 18 + Tailwind CSS)"]
        UI["OmniMash Web UI Dashboard"]
        PromptBar["Prompt Input Bar & Style Cards"]
        PreviewCard["🪄 5-Part Anchor & Inject Preview Card"]
        DAGView["Interactive Version DAG with Checkpoint ⚓ Badges"]
        ModalBanner["Commit & Re-Anchor Warning Banner Modal"]
        Player["720p Video Player + SynthID Badge"]
        
        UI --> PromptBar
        UI --> PreviewCard
        UI --> DAGView
        UI --> ModalBanner
        UI --> Player
    end

    subgraph BackendServices["Backend Services (FastAPI + Uvicorn)"]
        Gateway["FastAPI Async App (create_app)"]
        EndpointGen["POST /api/generate"]
        EndpointCommit["POST /api/commit"]
        EndpointRoot["GET / (HTML Dashboard)"]
        
        Gateway --> EndpointRoot
        Gateway --> EndpointGen
        Gateway --> EndpointCommit
    end

    subgraph OrchestrationEngine["Orchestration Engine"]
        EndpointGen --> Agent["OmniMashAgent"]
        EndpointCommit --> Agent
        Agent --> State["SessionManager (Version DAG & Depth)"]
        Agent --> OmniClient["OmniFlashClient"]
    end

    PromptBar -->|POST /api/generate| EndpointGen
    ModalBanner -->|POST /api/commit| EndpointCommit
    EndpointGen -->|JSON / SSE Event Stream| DAGView
    EndpointCommit -->|Re-Anchored Status / Depth 0| DAGView
    EndpointGen -->|720p Video URL| Player
```

---

## 🔌 API Contracts

### `POST /api/generate`
**Request Payload:**
```json
{
  "user_id": "usr_prod",
  "project_id": "prj_mashup",
  "prompt": "Severus Snape in 90s rap video wearing gold chains",
  "clip_index": 0,
  "parent_turn_id": "optional-turn-id-for-diffs"
}
```

**Response Payload (`GenerateResponse`):**
```json
{
  "success": true,
  "status": "COMPLETED",
  "video_url": "/static/rendered/thread_123_turn0.mp4",
  "turn_id": "turn_abc456",
  "depth": 1,
  "error": null
}
```

### `POST /api/commit`
**Request Payload (`CommitRequest`):**
```json
{
  "user_id": "usr_prod",
  "project_id": "prj_mashup",
  "turn_id": "turn_abc456",
  "next_prompt": "Continue with glowing wand gestures"
}
```

**Response Payload (`GenerateResponse`):**
```json
{
  "success": true,
  "status": "REANCHORED",
  "video_url": "/static/rendered/reanchored_thread_789_turn0.mp4",
  "turn_id": "turn_xyz999",
  "depth": 0,
  "error": null
}
```
