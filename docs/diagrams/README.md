# Agent Architecture & Reference Diagrams

Publication-quality architecture and system diagrams for **OmniMash** (`gemini-3-pro-image-preview` / PaperBanana style), in the visual standard of official Google Cloud Platform documentation.

Each diagram details the multi-agent orchestration loop, state version tree branching, multimodal media extraction, FFmpeg video stitching, and FastAPI/Next.js full-stack topology.

---

## 🏛️ Reference Architecture Suite

| Diagram | Component / Scope | Highlights |
| :--- | :--- | :--- |
| ![omnimash agent architecture](omnimash_agent_architecture.png) | **`omnimash.agent` & `security`** | **ADK Agent Orchestration & Security:** FastAPI Web Gateway $\rightarrow$ OmniMash ADK Agent Orchestrator $\rightarrow$ Model Armor Guardrail Gateway pre-gating $\rightarrow$ Session Version DAG $\rightarrow$ Prompt Taxonomy Engine $\rightarrow$ Gemini Omni Flash Interactions API Client $\rightarrow$ 720p Video with SynthID / C2PA watermark. |
| ![version tree dag](version_tree_dag_lifecycle.png) | **`omnimash.state`** | **Non-Linear Version Tree (DAG):** Non-linear conversational diff branching with `SessionManager`, `TurnNode`, and `ProjectSession`. Displays root turn forking into Turn 2 Branch A and Turn 3 Branch B, alongside active multi-clip timeline segments. |
| ![media ingestion & stitching](multimodal_ingestion_stitching.png) | **`omnimash.ingestion` & `stitching`** | **Multimodal Ingestion & FFmpeg Stitching:** 3-phase media pipeline: 1. Ingestion Phase (YouTube URL via `yt-dlp` & user audio/images extracted into Keyframe Portraits and Audio Rhythm Stems), 2. Generation Phase (Gemini Omni Flash 10s clips), 3. Stitching Phase (FFmpeg Multi-Clip Concatenation Engine $\rightarrow$ Master 30s–60s MP4). |
| ![frontend api topology](frontend_api_topology.png) | **`omnimash.api` & Web UI** | **Full-Stack Topology & SSE Streams:** Next.js / React 18 single-page Web UI (Prompt Input Bar, Style Selector Cards, Version DAG Viewer, 720p Video Player) communicating via `POST /api/generate` and Server-Sent Events (SSE) stream to FastAPI / Uvicorn backend gateway. |

---

## 📑 Detailed Architecture Documents

- [🛡️ Agent Orchestration Architecture Document](omnimash_agent_architecture.md)
- [🌳 Version Tree DAG & State Lifecycle Document](version_tree_dag_lifecycle.md)
- [🎬 Multimodal Ingestion & Video Stitching Document](multimodal_ingestion_stitching.md)
- [🌐 Frontend API & SSE Streaming Topology Document](frontend_api_topology.md)
