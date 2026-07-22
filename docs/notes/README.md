# Project Notes & Session Knowledge Index

This directory documents non-obvious knowledge, session notes, and operational quirks for **omnimash** that are not easily derivable from git history or standard docs.

## 📌 Guiding Principles for Notes
- **Check & Update First:** Always check for an existing note on a topic before creating a new one. Update or prune stale/invalid notes.
- **Verification:** Re-verify referenced filenames, flags, or environment behaviors before acting on them.
- **High-Value & Non-Derivable:** Capture quirks, workarounds, and tricky setup details (e.g., tool/CLI quirks, broken flags, environment gotchas).

---

## 🗂️ Key Project Files
- [CODE_STANDARDS.md](../../CODE_STANDARDS.md) – Mandatory coding standards, tooling rules, and git practices.
- [GEMINI.md](../../GEMINI.md) – Agent context and workflow rules.
- [pyproject.toml](../../pyproject.toml) – Build configuration and dependencies (`uv`).
- [main.py](../../main.py) – Application entrypoint.
- [tests/test_main.py](../../tests/test_main.py) – Pytest test suite.
- [README.md](../../README.md) – Project overview.

---

## 📑 Topic Notes

| Topic | Note File | Description |
| :--- | :--- | :--- |
| Digital Director's Studio (3-Act Flow) | [digital_directors_studio_3_act_workflow.md](digital_directors_studio_3_act_workflow.md) | 3-Act progressive linear studio (The Clash, The Fine-Tune, The Director's Chair) with Gemini Parody Research |
| Guided Mode vs. Screenplay Mode | [screenplay_vs_guided_directing.md](screenplay_vs_guided_directing.md) | Detailed guide and prompt compilation breakdown for Guided Form Mode vs Screenplay Scripting |
| Session Naming & Resilient Rendering | [session_naming_and_resilient_video_rendering.md](session_naming_and_resilient_video_rendering.md) | Custom UI session name mapping to GCS folders, container font packages, and procedural visualizer fallback |
| Audio, Voiceover & Dialogue Prompting | [audio_dialogue_and_voiceover_prompting.md](audio_dialogue_and_voiceover_prompting.md) | Decoupling background sound design, multi-character spoken dialogue, voiceovers, and silent video in Gemini Omni Flash |
| Reference Analysis & Preset Inspector | [reference_analysis_and_preset_inspector.md](reference_analysis_and_preset_inspector.md) | Ingested YouTube reference keyframe annotations, BPM & color palette analysis, and 4-vector preset contribution inspector |
| Centralized Settings & .env | [centralized_settings_and_env.md](centralized_settings_and_env.md) | Centralized pydantic-settings configuration, .env.example templates, and secret leak prevention |
| Hierarchical Session GCS Storage | [session_scoped_gcs_artifacts.md](session_scoped_gcs_artifacts.md) | Session-scoped cloud folders (sessions/{session_id}/[intermediate,finalized,prompts,references]) |
| GCS Artifact Persistence | [gcs_artifact_persistence.md](gcs_artifact_persistence.md) | Persistent cloud media storage (gs://omnimash-media-${GOOGLE_CLOUD_PROJECT}) and .gitignore isolation |
| YouTube & Audio Reference Ingestion | [youtube_reference_ingestion.md](youtube_reference_ingestion.md) | Ingesting public YouTube reference videos, character portraits, and audio stems via MediaExtractor |
| Delta Prompting & Lock/Isolate | [delta_prompting_lock_isolate.md](delta_prompting_lock_isolate.md) | Solving facial shift and over-correction on multi-turn edits via 2-part Lock & Isolate delta prompting |
| User Journey & Multimodal Inputs | [user_journey_and_multimodal_inputs.md](user_journey_and_multimodal_inputs.md) | Comprehensive breakdown of the 4 UI inputs, YouTube references, editable 6-part previews, and style presets |
| Joint Audio-Video Latent Space | [joint_audio_video_latent_prompting.md](joint_audio_video_latent_prompting.md) | Synchronizing character kinematic motion to 120 BPM audio stems via 6-part [AUDIO TRACK] prompting |
| Prompt Compiler & Anchor/Inject | [prompt_compiler_anchor_inject.md](prompt_compiler_anchor_inject.md) | Solving character decay and latent space averaging via 6-part Anchor & Inject meta-prompts |
| Context Decay & Checkpoints | [context_decay_commit_branch.md](context_decay_commit_branch.md) | Solving the 4-turn multimodal context decay via Commit & Branch thread re-anchoring |
| Subagents & Permissions | [subagent_workflow_quirks.md](subagent_workflow_quirks.md) | Insights into subagent permission inheritance and autonomous command execution |
| Architecture & System Design | [architecture_omnimash.md](architecture_omnimash.md) | Reference architecture, component breakdown, and pipeline design for OmniMash |
| PR-First Workflow | [development_workflow_prs.md](development_workflow_prs.md) | Mandatory process for submitting structural changes as unmerged Pull Requests |
| Request Lifecycle & State | [request_lifecycle.md](request_lifecycle.md) | Blueprint for state management, Model Armor gating, and Interactions API lifecycle |
| Session Store Limitations | [session-store-limitations.md](session-store-limitations.md) | Thread-safe LRU-bounded in-memory session store and its single-process (single-worker) limitation |
