# OmniMash Request Lifecycle & State Management Notes

## 🔄 Core Request Lifecycle (Phase 1 Blueprint)

```mermaid
sequenceDiagram
    autonumber
    actor User as User (Web UI)
    participant API as FastAPI Backend (ADK)
    participant State as Agent Sessions / Memory Bank
    participant Armor as Model Armor (Agent Gateway)
    participant Omni as gemini-omni-flash-preview (Interactions API)
    participant Stitcher as FFmpeg Stitching Engine

    User->>API: Submit Prompt + Optional Reference (Upload / YouTube URL)
    API->>State: Resolve Custom Session ID & Active Interaction Thread
    State-->>API: Return Active Interaction Thread ID & Timeline State
    
    API->>Armor: Validate Text Prompt & Reference Media (Safety/Injection Check)
    alt Policy Violation
        Armor-->>API: Rejection Error (Save Quota)
        API-->>User: Guardrail Error Alert
    else Approved
        Armor-->>API: Sanitized Payload
        API->>Omni: Call Interactions API (Thread ID + Diff Prompt)
        Omni-->>API: Rendered 720p 10s Clip + SynthID/C2PA Metadata
        API->>State: Update Session State (Store Clip ID & Thread Turn ID)
        opt Multi-Clip Timeline
            API->>Stitcher: Re-stitch active timeline segments
            Stitcher-->>API: Output Master .mp4
        end
        API-->>User: Stream Progress / Video .mp4 via SSE/WebSocket
    end
```

---

## 💡 Key Architectural Enhancements

### 1. Version Tree / Branching (Undo & Forking Edits)
- **Challenge:** Users may dislike an iterative edit (e.g. Turn 2) and want to revert to Turn 1 without starting from scratch.
- **Solution:** Maintain a DAG of `interaction_turn_id` snapshots in Agent Sessions so users can undo or branch their edits.

### 2. Multi-Clip Timeline State
- **Challenge:** Interactions API operates per 10s clip. Full parody videos contain multiple clips.
- **Solution:** A Project session contains an ordered list of `ClipSegment` objects, each with its own `interaction_thread_id`. Editing Clip #2 only modifies Thread #2; FFmpeg re-stitches the master timeline without touching Clip #1 or Clip #3.

### 3. Asynchronous Streaming (SSE / WebSockets)
- **Challenge:** Video rendering latency can cause HTTP timeouts.
- **Solution:** FastAPI asynchronous task queue with SSE updates (`[Model Armor: Approved]` -> `[Omni Flash: Rendering]` -> `[SynthID: Verified]` -> `[Done]`).
