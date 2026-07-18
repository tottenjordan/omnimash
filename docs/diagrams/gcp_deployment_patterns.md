# Google Cloud Deployment Patterns

This document details the **Dual-Target Deployment Architecture** for **OmniMash** on Google Cloud Platform: Serverless Full-Stack Cloud Run vs. Enterprise Vertex AI Agent Engine.

---

## 🖼️ Reference Architecture Diagram

![GCP Deployment Patterns](gcp_deployment_patterns.png)

---

## 🏗️ Deployment Target Comparison

OmniMash supports two production-ready deployment targets on Google Cloud:

```mermaid
graph LR
    subgraph Target1["Target 1: Serverless Full-Stack Cloud Run (Live)"]
        Browser["User Browser"] -->|HTTPS / Port 8080| CloudRun["Google Cloud Run Container"]
        CloudRun --- Components["• FastAPI Async Gateway<br/>• React 18 UI Dashboard<br/>• Model Armor Guardrail<br/>• 5-Part Prompt Compiler<br/>• Version Tree DAG Engine<br/>• FFmpeg Concatenation"]
    end

    subgraph Target2["Target 2: Enterprise Vertex AI Agent Engine"]
        Clients["Client Apps / A2A"] -->|gRPC / A2A Protocol| AgentEngine["Vertex AI Agent Engine Runtime"]
        AgentEngine --- ADKComponents["• AdkApp Wrapper<br/>• Google ADK root_agent<br/>• Managed Sessions Backend<br/>• Auto-scaling vCPUs & Memory"]
    end

    CloudRun -->|Interactions API| OmniFlash["gemini-omni-flash-preview API"]
    AgentEngine -->|Interactions API| OmniFlash
```

---

## 🚀 1. Target A: Serverless Full-Stack Cloud Run (Live)

**Best for:** End-user web applications, interactive dashboards, and standalone multi-clip video studios.

### Architecture & Capabilities:
- **Container Runtime:** Docker container built with `python:3.12-slim`, `uv`, and `ffmpeg`.
- **Embedded Web Dashboard:** Single-page Next.js / React 18 UI served directly on `/` with Tailwind CSS, live 5-Part Preview card, and Version DAG Timeline explorer.
- **REST & SSE Endpoints:** `POST /api/generate` and `POST /api/commit` with Server-Sent Events for streaming render progress.
- **Scaling:** Scales automatically to zero when idle, saving compute costs.

### Live Production Deployment:
- **Service URL:** [https://omnimash-934903580331.us-central1.run.app](https://omnimash-934903580331.us-central1.run.app)
- **Deploy Script:** `scripts/deploy_cloud_run.sh`

```bash
./scripts/deploy_cloud_run.sh
```

---

## 🏛️ 2. Target B: Enterprise Vertex AI Agent Engine

**Best for:** Multi-agent ecosystems, Agent-to-Agent (A2A) protocol communication, and enterprise backend agent workflows.

### Architecture & Capabilities:
- **Managed Agent Runtime:** Source-based deployment directly to Vertex AI Agent Engine (`projects/*/locations/*/reasoningEngines/*`).
- **Google ADK Binding:** Wrapped via `AdkApp(agent=root_agent)` in `scripts/deploy_agent_engine.py`.
- **Session Persistence:** Native `VertexAiSessionService` / Agent Engine sessions backend.
- **Multi-Agent Interop:** Connects with Remote A2A Agents across Google Cloud.

### Deploy Command:

```bash
python scripts/deploy_agent_engine.py
```
