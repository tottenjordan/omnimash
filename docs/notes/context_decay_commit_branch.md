# Context Window Decay & Commit-and-Branch Checkpointing

This note documents the critical multimodal context constraint discovered during empirical testing with `gemini-omni-flash-preview` and the architectural "Commit & Branch" pattern used to solve it.

---

## 🔬 Empirical Observation & The Constraint

1. **Coherence Decay Threshold:**
   - `gemini-omni-flash-preview` maintains 720p scene and character facial coherence across **~3–4 sequential conversational delta diffs** in a single Interactions API thread.
   - Beyond 4 turns, conversational history clutter and token accumulation in the unified multimodal latent space cause minor visual details, lighting anchors, and background continuity to drift.

2. **The Architectural Fix: "Commit & Branch":**
   - After 3–4 edits on a thread, prompt the user to **"Commit & Re-Anchor"**.
   - The application extracts the latest 720p output video from the active turn.
   - The orchestrator spawns a **brand-new Interactions API thread** (`new_thread_id`) using the committed video as the base visual input.
   - This flushes the accumulated conversational token context while locking in the exact visual state of the video as the new baseline for subsequent edits.

---

## 🌳 Version Tree Integration

- `TurnNode` tracks `edit_depth_in_thread: int` and `is_checkpoint: bool`.
- When `edit_depth_in_thread >= 3`, the API returns a status event recommending a commit (`COMMIT_RECOMMENDED`).
- A `commit_and_branch()` operation resets `edit_depth_in_thread = 0` on the new turn node while pointing `parent_turn_id` to the committed checkpoint.
