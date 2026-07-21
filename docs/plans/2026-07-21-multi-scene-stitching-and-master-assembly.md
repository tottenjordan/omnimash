# Multi-Scene 30–60s Master Video Assembly Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clarify and implement the multi-scene master video assembly architecture in OmniMash to address the 10-second single-turn output limit of video generation models (`gemini-omni-flash-preview` / Veo), enabling seamless 30–60s master video assembly via FFmpeg clip stitching and scene extensions.

**Architecture:** 
1. **Hybrid Two-Stage Orchestration Strategy**:
   - **Stage 1 (Upfront Concept Deconstruction)**: Gemini NLP deconstructs a 30–60s master concept into an ordered multi-scene storyboard sequence (`Scene 1`, `Scene 2`, `Scene 3`...).
   - **Stage 2 (Sequential Generation & Anchor Locking)**: Each 10s scene is generated turn-by-turn. Extending scenes (`POST /api/extend-scene`) preserves character reference image URLs (`gs://...`), character style signifiers, and voice styles to eliminate AI amnesia across clips.
   - **Stage 3 (FFmpeg Multi-Clip Master Concatenation)**: `VideoStitcher` (`src/omnimash/stitching/stitcher.py`) uses FFmpeg (`ffmpeg -f concat`) to stitch all sequential 10s scene clips and their synchronized 140 BPM audio stems into a single 30–60s master video (`sessions/{session_id}/final_masters/{master_title}.mp4`).
2. **FFmpeg Concatenation Engine**:
   - Update `VideoStitcher.concatenate_clips` in `src/omnimash/stitching/stitcher.py` to execute real FFmpeg concatenation (`ffmpeg -f concat -safe 0 -i concat_list.txt -c copy`) for real MP4 files.
3. **Master Video Export API**:
   - Update `POST /api/save-final` in `src/omnimash/api/app.py` to automatically collect all generated scene clip turns in the session DAG, stitch them via `VideoStitcher`, and export the final 30–60s master video to GCS.
4. **README.md Clarification**:
   - Document the exact architectural answer to: *"If video generation models output max 10s per clip, how do we assemble 30–60s master videos?"*

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, FFmpeg, Google Cloud Storage (GCS), React 18, Tailwind CSS, pytest, uv, ruff, ty.

---

## User Review Required

> [!IMPORTANT]
> **Architectural Decision: Upfront Deconstruction vs. Interactive Stitching**:
> We adopt a **Hybrid Approach**:
> 1. **Upfront Deconstruction**: Gemini reads the 30–60s concept and plans the complete multi-scene storyboard sequence.
> 2. **Interactive Generation & Extension**: Each 10s scene is generated individually using Omni Flash, preserving character reference image anchors (`gs://...`).
> 3. **FFmpeg Master Assembly**: When saving the final master (`POST /api/save-final`), OmniMash automatically stitches all sequential 10s scene clips into a unified 30–60s MP4 file with continuous synchronized audio.

---

## Open Questions

> [!WARNING]
> **Audio Re-encoding during FFmpeg Concatenation**:
> Standard stream copy (`-c copy`) works when all clips share identical video/audio codecs (720p H.264 / AAC). If clips differ in sample rate or frame rate, FFmpeg requires re-encoding (`-c:v libx264 -c:a aac`).
> 
> *Our plan implements smart fallback: tries fast `-c copy` first; if FFmpeg returns a code error, falls back to full re-encode.*

---

## Proposed Changes

### Stitching Engine

#### [MODIFY] `src/omnimash/stitching/stitcher.py`
- Implement real FFmpeg concatenation in `VideoStitcher.concatenate_clips`:
  - Creates a temporary `concat_list.txt` referencing all local/downloaded clip filepaths.
  - Runs `ffmpeg -y -f concat -safe 0 -i concat_list.txt -c copy {out_path}`.
  - If `-c copy` fails, retries with `ffmpeg -y -f concat -safe 0 -i concat_file.txt -c:v libx264 -c:a aac -pix_fmt yuv420p {out_path}`.
  - Uploads final stitched master to GCS under `sessions/{session_id}/final_masters/{filename}`.

```python
def concatenate_clips(
    self,
    clip_paths: list[str],
    output_dir: str = "/tmp",
    session_id: str | None = None,
) -> str:
    master_filename = f"master_{uuid.uuid4().hex[:8]}_stitched.mp4"
    out_path = os.path.join(output_dir, master_filename)

    if self.mock_mode or not clip_paths:
        os.makedirs(output_dir, exist_ok=True)
        with open(out_path, "w") as f:
            f.write("mock mp4 master video content")
    else:
        concat_file = os.path.join(output_dir, f"concat_{uuid.uuid4().hex[:6]}.txt")
        with open(concat_file, "w") as f:
            for p in clip_paths:
                f.write(f"file '{os.path.abspath(p)}'\n")

        # Try fast stream copy first
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", out_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            # Fallback to re-encode
            cmd_reencode = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
                "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", out_path
            ]
            subprocess.run(cmd_reencode, check=True)

    gcs_blob = self.storage.build_session_blob_path(
        session_id=session_id,
        category="final_masters",
        filename=master_filename,
    )
    self.storage.upload_file(out_path, destination_blob_name=gcs_blob)
    return out_path
```

---

### Orchestrator & API Layer

#### [MODIFY] `src/omnimash/agent/orchestrator.py`
- Add `stitch_session_master(self, session_name: str, master_title: str) -> tuple[str, str]`:
  - Collects all clip turns in the session DAG order (`turn_init`, `extend_1`, `extend_2`...).
  - Calls `self.stitcher.concatenate_clips(clip_paths, session_id=session_name)`.
  - Saves final master to GCS.

#### [MODIFY] `src/omnimash/api/app.py`
- Update `POST /api/save-final`:
  - Calls `agent.stitch_session_master(session_name, master_title)` when multi-scene clip turns exist, returning the stitched 30–60s master GCS URL.

---

### Documentation Layer

#### [MODIFY] `README.md`
- Add a dedicated section explaining **Multi-Scene 30–60s Master Video Assembly Architecture**:
  - Explains the 10s per-clip model constraint.
  - Explains the 3-stage process (Upfront Deconstruction $\to$ Anchor-Locked Scene Extension $\to$ FFmpeg Concatenation).

---

## Bite-Sized Execution Tasks

### Task 1: Implement Real FFmpeg Concatenation in VideoStitcher
- Modify `src/omnimash/stitching/stitcher.py`
- Test `tests/stitching/test_stitcher.py`

### Task 2: Connect Master Video Stitching in Orchestrator & API
- Modify `src/omnimash/agent/orchestrator.py` & `src/omnimash/api/app.py`
- Test `tests/api/test_app.py` & `tests/agent/test_orchestrator.py`

### Task 3: Update README.md Architecture Documentation
- Update `README.md` with multi-scene 30–60s master assembly workflow.

### Task 4: Verification & Test Suite Pass
- Run full test suite (`uv run pytest`, `ruff`, `ty`).

---

## Verification Plan

### Automated Tests
- Stitcher unit tests: `uv run pytest tests/stitching/test_stitcher.py`
- Full test suite:
```bash
uv run pytest
```

### Manual Verification
1. Run local dev server (`uv run python -m omnimash.api.app`).
2. Create Scene 1 (10s) and extend to Scene 2 (10s).
3. Click **💾 Save Final Master to GCS**. Verify the returned master URL is a concatenated 20s MP4 file!
