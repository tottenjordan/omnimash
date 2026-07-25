# Storyboard Workflow UI Screenshots & Documentation Plan

## 📌 Context
The 4-Stage Storyboard Journey UI workflow is now fully integrated and deployed on Cloud Run with live concept art keyframe image generation via `gemini-3.1-flash-image` and live video + audio generation via `gemini-omni-flash-preview`.

## 📷 Screenshots & README Update Requirement
When video generation testing is finalized, update the main top-level [README.md](../../README.md) with visual screenshots/embeds of the **4-Stage Storyboard Journey** UI using the exact real-world inputs from the live session:

1. **Stage 1 (Vision & Style)**:
   - 60s Vision prompt input + timecoded screenplay script (`[0-3s]`, `[3-6s]`, `[6-10s]`).
   - Character Roster cards (e.g. `Role A: Harry "Gucci"`, `Role B: Young Draco "Jeezy"`).
   - Style & Tone pill selector (`Cinematic Trap Parody`, `Gritty 90s Rap Video`, `Gothic Trap Parody`).

2. **Stage 2 (5-Part Storyboard Grid)**:
   - Interactive grid of 16:9 keyframe preview image cards generated live via `gemini-3.1-flash-image`.
   - 5-part directive fields (`Action/Subject`, `Location`, `Style & Lighting`, `Framing & Motion`, `Audio`).
   - `🎬 Generate Video for Shot #N` per-shot video triggers.

3. **Stage 3 (The Dailies & Diff)**:
   - Side-by-side video clip player comparing Baseline vs Current turn.
   - Shot Selector tabs (`Shot #1`, `Shot #2`, `Shot #3`).
   - Conversational diff bar with single-change enforcement badge.

4. **Stage 4 (The Final Cut)**:
   - Full master video player with master audio track overlay.
   - GCS Cloud Storage export controls.
