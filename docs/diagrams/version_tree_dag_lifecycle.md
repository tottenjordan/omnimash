# Session Version Tree DAG & State Lifecycle

This document illustrates the non-linear version tree (DAG) structure and Commit & Branch Checkpointing that powers conversational video iteration in **OmniMash** (`src/omnimash/state/session_manager.py`).

---

## 🖼️ Reference Architecture Diagram

![Version Tree DAG Lifecycle](version_tree_dag_lifecycle.png)

---

## 🌳 Version Tree DAG & Thread Depth Lifecycle

To prevent context decay in the multimodal latent space after ~4 sequential edits, OmniMash combines non-linear version branching with **Commit & Branch Checkpointing**:

```mermaid
graph TD
    subgraph Active Thread Main (Depth Escalation)
        Turn1["Turn 1 (Root Clip 0)<br/>Prompt: 'Severus Snape in 90s rap'<br/>Depth: 0 | ID: turn_1<br/>Video: /static/rendered/clip0_t1.mp4"]
        Turn2["Turn 2 (Delta 1)<br/>Prompt: 'Add gold chains'<br/>Depth: 1 | Parent: turn_1<br/>Video: /static/rendered/clip0_t2.mp4"]
        Turn3["Turn 3 (Delta 2)<br/>Prompt: 'Add neon green lighting'<br/>Depth: 2 | Parent: turn_2<br/>Video: /static/rendered/clip0_t3.mp4"]
        Turn4["Turn 4 (Delta 3 ⚓ Checkpoint)<br/>Prompt: 'Add atmospheric fog'<br/>Depth: 3 | Status: COMMIT_RECOMMENDED<br/>Video: /static/rendered/clip0_t4.mp4"]
        
        Turn1 --> Turn2 --> Turn3 --> Turn4
    end

    subgraph Re-Anchored Thread Beta (Context Flushed)
        Turn4 -.->|POST /api/commit| CommitAction[Extract 720p Output Video & Flush Context]
        CommitAction --> TurnBeta1["Turn Beta 1 (Fresh Interactions Thread)<br/>Prompt: 'Add laser wand gestures'<br/>Depth: 0 | Checkpoint: True<br/>Video: /static/rendered/clip0_beta1.mp4"]
    end
```

---

## 💾 State Model Data Structures

1. **`TurnNode`:** Immutable record of a single generation step:
   - `turn_id`: UUID4 string identifier.
   - `parent_turn_id`: UUID4 pointer to the parent turn in the version DAG.
   - `clip_index`: Target position in the multi-clip sequence.
   - `prompt`: Sanitized prompt instruction.
   - `interaction_thread_id`: Gemini Omni Flash session handle.
   - `video_url`: Output 720p `.mp4` artifact URI.
   - `edit_depth_in_thread`: Sequential turn counter within the active thread.
   - `is_committed`: Boolean checkpoint indicator.
   - `base_video_anchor_url`: URI of base video input if re-anchored.

2. **`ClipSegment`:** Timeline reference pointing to the currently active turn node for a given clip index.

3. **`ProjectSession`:** Aggregation of all turn nodes (`dict[str, TurnNode]`) and the active timeline sequence (`list[ClipSegment]`).
