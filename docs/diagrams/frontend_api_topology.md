# Frontend UI & FastAPI Async API Topology

This document details the Next.js / React 18 single-page application and its connection to FastAPI's async generation endpoints and SSE event streams (`src/omnimash/api/app.py`).

---

## 🌐 Application Architecture

```mermaid
graph TD
    subgraph Browser Client (Next.js / React 18 + Tailwind CSS)
        UI[OmniMash Web UI Dashboard]
        PromptBar[Prompt Input Bar & Style Cards]
        DAGView[Interactive Version Tree DAG Viewer]
        Player[720p Video Player + SynthID Badge]
        
        UI --> PromptBar
        UI --> DAGView
        UI --> Player
    end

    subgraph Backend Services (FastAPI + Uvicorn)
        Gateway[FastAPI Async App (create_app)]
        EndpointGen[POST /api/generate]
        EndpointRoot[GET / (HTML Dashboard)]
        
        Gateway --> EndpointRoot
        Gateway --> EndpointGen
    end

    subgraph Orchestration Engine
        EndpointGen --> Agent[OmniMashAgent]
        Agent --> State[SessionManager (Version DAG)]
        Agent --> OmniClient[OmniFlashClient]
    end

    PromptBar -->|POST /api/generate| EndpointGen
    EndpointGen -->|JSON / SSE Event Stream| DAGView
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
  "error": null
}
```
