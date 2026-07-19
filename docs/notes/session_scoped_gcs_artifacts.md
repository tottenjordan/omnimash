# 🗂️ Hierarchical Session-Scoped GCS Bucket Architecture

## 📌 Motivation & Design
To avoid mixing media artifacts across different user projects or multi-turn sessions, all cloud storage blobs in `gs://omnimash-media-${GOOGLE_CLOUD_PROJECT}/` are organized into **session-scoped subfolders**.

Within each session folder (`sessions/${session_id}/`), assets are strictly categorized into 4 distinct subdirectories.

---

## 🏗️ Storage Layout & Directory Structure

```text
gs://omnimash-media-${GOOGLE_CLOUD_PROJECT}/
└── sessions/
    └── ${session_id}/
        ├── intermediate/
        │   ├── thread_12874fb1_turn0.mp4       # Per-turn 720p 24fps video clips
        │   ├── thread_12874fb1_turn_diff.mp4   # Multi-turn conversational delta diff clips
        │   ├── reanchored_thread_912300d3.mp4  # Checkpoint re-anchored thread clips
        │   └── temp_beat.wav                   # 120 BPM hip-hop audio stems
        ├── finalized/
        │   └── master_5bbcb4e1_stitched.mp4    # Master concatenated/stitched MP4 videos
        ├── prompts/
        │   ├── turn_0_prompt.json              # 5-part Anchor & Inject meta-prompt JSON
        │   └── turn_1_prompt.json              # 2-part Lock & Isolate delta prompt JSON
        └── references/
            ├── character_portrait_anchor.jpg   # Ingested YouTube character portrait keyframes
            └── reference_beat_stem.wav         # Ingested YouTube reference audio stems
```

---

## 🛠️ Code Implementation

- **`GcsStorageManager.build_session_blob_path(session_id, category, filename)`**: Automatically constructs the 3-level GCS URI path (`sessions/{session_id}/{category}/{filename}`).
- **`GcsStorageManager.save_session_prompt(session_id, turn_index, prompt_data)`**: Persists compiled prompt metadata for debugging, lineage tracking, and auditability.
- **`OmniFlashClient` & `VideoStitcher`**: Tag every generated or stitched asset with its active `session_id` and appropriate subfolder category (`intermediate`, `finalized`, `prompts`, `references`).
