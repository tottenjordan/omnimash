# 🎨 Roadmap: Character Consistency & Reference Image Enhancements

## 📌 Context & Motivation
In generative multimodal video pipelines using **Gemini Omni Flash** and **Gemini Omni Image Roles**, maintaining visual fidelity (facial structure, wardrobe styling, and lighting aesthetics) across iterative delta edits and multi-scene narrative sequences is critical. 

Currently, OmniMash persists extracted session keyframes and reference analysis in GCS (`sessions/<session_id>/references/`) and attaches reference URLs (`(Ref: gs://... | https://...)`) alongside character style signifiers (`[Style: ...]`) in the compiled prompt's `[ROLE DEFINITIONS]` block.

This document records two planned high-value enhancements to revisit in the near future.

---

## 🚀 Planned Enhancements

### 1. Automatic External URL-to-GCS Mirroring
- **Target Workflows:** `POST /api/deconstruct-concept`, Act 1 Character Roles Manager, `POST /api/generate`.
- **Mechanism:**
  - When a user inputs an external image reference URL (e.g., `https://example.com/character.jpg`), the backend media extractor asynchronously downloads the asset.
  - The image is sanitized, converted/verified as a JPEG/PNG, and uploaded to the session's persistent GCS bucket path:
    `gs://<bucket>/sessions/<session_id>/references/<role_id>_source.jpg`
  - The `CharacterRole.reference_url` is automatically replaced with the canonical GCS URI before prompt compilation.
- **Benefits:**
  - Eliminates external link rot, HTTP 403/429 rate-limiting, and slow fetching during generation passes.
  - Guarantees immutable, low-latency image conditioning embeddings for the Gemini Omni Flash Interactions API.

---

### 2. Keyframe-to-Reference Anchoring on Scene Extensions
- **Target Workflows:** `POST /api/extend-scene`, Act 3 Storyboard Extension.
- **Mechanism:**
  - When a director completes a scene in Act 3 and triggers **➕ Extend Video / Next Scene**, OmniMash parses the approved 720p 24fps MP4 master cut.
  - The engine extracts the highest-quality keyframe from the final seconds of the rendered video and uploads it to:
    `gs://<bucket>/sessions/<session_id>/references/scene_<N>_anchor_keyframe.jpg`
  - This rendered keyframe is automatically attached or offered as a secondary reference anchor for the subsequent scene (`Scene N+1`).
- **Benefits:**
  - Seamlessly bridges visual continuity (e.g., matching lighting conditions, micro-expressions, dynamic props like iced-out chains) across multi-scene storytelling.
  - Minimizes visual drift when transitioning from Scene 1 to Scene 2 and beyond.
