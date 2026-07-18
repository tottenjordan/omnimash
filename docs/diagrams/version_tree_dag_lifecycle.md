# Session Version Tree DAG & State Lifecycle

This document illustrates the non-linear version tree (DAG) structure that powers conversational video iteration in **OmniMash** (`src/omnimash/state/session_manager.py`).

---

## 🌳 Version Tree DAG Branching

Unlike traditional linear chat agents, OmniMash represents media edits as a directed acyclic graph (DAG). Users can fork new prompt iterations from any prior turn node without overwriting previous generations.

```mermaid
graph TD
    subgraph Clip Index 0 Timeline
        Root[Turn 1: Root Clip 0<br/>'Severus Snape in 90s rap video'<br/>ID: turn_abc1<br/>Video: /static/rendered/clip0_t1.mp4]
        
        BranchA[Turn 2: Branch A<br/>'Add gold chains and neon green lights'<br/>Parent: turn_abc1<br/>Video: /static/rendered/clip0_t2a.mp4]
        
        BranchB[Turn 3: Branch B<br/>'Change background to cyberpunk rainy alley'<br/>Parent: turn_abc1<br/>Video: /static/rendered/clip0_t2b.mp4]
        
        LeafA2[Turn 4: Branch A.1<br/>'Swap microphone for glowing wand'<br/>Parent: turn_2a<br/>Video: /static/rendered/clip0_t3a.mp4]
        
        Root --> BranchA
        Root --> BranchB
        BranchA --> LeafA2
    end

    subgraph Timeline Active Selection
        Segment0[Clip Segment 0<br/>Active Turn: Turn 4 (Leaf A.1)]
        Segment1[Clip Segment 1<br/>Active Turn: Turn 5 (Dumbledore Chorus)]
        Segment2[Clip Segment 2<br/>Active Turn: Turn 6 (Voldemort Beat drop)]
        
        Segment0 --> Segment1 --> Segment2
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

2. **`ClipSegment`:** Timeline reference pointing to the currently active turn node for a given clip index.

3. **`ProjectSession`:** Aggregation of all turn nodes (`dict[str, TurnNode]`) and the active timeline sequence (`list[ClipSegment]`).
