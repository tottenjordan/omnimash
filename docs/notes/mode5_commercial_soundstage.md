# Mode 5: Commercial Soundstage — Backend Engine & Production Physics

This note documents the architecture, non-obvious multimodal safety/physics invariants, and multi-format post-production design of **Mode 5: Commercial Soundstage** (`src/omnimash/prompts/`, `src/omnimash/stitching/`, `src/omnimash/agent/`, and `src/omnimash/api/routers/soundstage.py`).

---

## 1. Dual-Layer Brand & Cast Safety Abstraction

Gemini Omni Flash (`gemini-omni-1.1-flash`, `location="global"`) enforces strict server-side HTTP `400` blocks on protected trademarks, two-word real human names, and photorealistic human portrait uploads. Mode 5 resolves this via **`DualLayerIdentityAbstractor`** (`src/omnimash/prompts/soundstage_discovery.py`):

- **Display Layer (`display_subject`, `display_offering`, `display_tagline`, `emblem_url`):** Preserves verbatim brand spelling, accents/diacritics, and marks for the UI and Pillow/FFmpeg vector end-card lockups (`src/omnimash/stitching/end_card_renderer.py`).
- **Omni-Safe Layer (`omni_safe_offering_descriptor`, `omni_safe_cast_description`, `cast_handle`):**
  - Scrubs Unicode-aware trademark tokens (`extract_brand_scrub_tokens` / `scrub_offering_trademarks` in `src/omnimash/prompts/offering_physics.py`) while protecting `#RRGGBB` hex literals and `@ImageN` multimodal reference tokens.
  - Resolves a single-word `cast_handle` verified not to collide with any extracted brand token (preventing accidental self-scrubbing in Block 1/2/4 when a brand name overlaps a role noun such as `"Vanguard"`).
  - Enforces `"No text, no subtitles on screen."` across all Omni prompts (`CLEAN_FRAME_NO_TEXT` in Pass 6) so typography is rendered cleanly at vector sharpness on the end-card rather than hallucinated in-frame.

---

## 2. First-Principles Offering Physics & 3-Act (`3 × 10s`) Causality

`OfferingPhysicsAnalyzer` (`src/omnimash/prompts/offering_physics.py`) classifies offerings across 9 physical archetypes (1:1 human scale, ergonomic role, surface branding mode, thermal state `ambient` / `chilled` / `hot`, and forbidden hallucinations) and governs the 9 storyboard plates (`1.1`–`3.3`) compiled by `SoundstageThreeActPlanner` (`src/omnimash/prompts/commercial_planner.py`):

- **Act I (`0:00–0:10`, Tiles `1.1–1.3`):** Protagonist (`@Image3`) arrives empty-handed in environmental anticipation; `1.3` is a strictly human-free (`has_person=False`) sensory environment macro.
- **Act II (`0:10–0:20`, Tiles `2.1–2.3`):** `2.1` tactile first contact with the hero offering (`@Image4`); `2.2` strictly human-free (`has_person=False`) 100mm zero-hand craft macro; `2.3` 85mm intimate sensory reaction.
- **Act III (`0:20–0:30`, Tiles `3.1–3.3`):** `3.1–3.2` post-experience lifestyle glow without repeated consumption; `3.3` strictly human-free (`has_person=False`) motionless solo hero packshot.

### Key Multimodal Reference Isolation Invariants
1. **Human-Free Plate Isolation (`1.3`, `2.2`, `3.3`):** During `KeyframeClient` storyboard plate synthesis (`src/omnimash/agent/soundstage_store.py`), tiles with `has_person=False` attach **only** `packshot_url` and pass `characters=None` (never `lead_cast_url`), preventing human likeness bleed into optical macro and packshot plates.
2. **Dual-Keyframe Slot Offsets:** Each 10s act attaches `<FIRST_FRAME>@KeyframeSeed` (Board `N.1`) and `<LAST_FRAME>@EndKeyframe` (Board `N.3`), shifting character and hero offering references to `<IMAGE_REF_0>@Image3` and `<IMAGE_REF_1>@Image4` so `PreFlightGatekeeper` Pass 2 (`repair_keyframe_offsets`) and Pass 6 (`soundstage_preflight.py`) are 100% idempotent.

---

## 3. Multi-Format Conforming (`1 Film → 3 Cuts`) & Native Omni Audio Ducking

`CommercialConformer` (`src/omnimash/stitching/commercial_conformer.py`) slices the 3 × 10s act clips across 9 addressable sub-shots (`SubShotTrimSpec`, clamped `>= 0.5s`) and assembles:
- **`30s_16x9_master.mp4` (`1280×720`):** All active non-bypassed sub-shots + `16:9` WCAG luminance-contrasted Pillow/FFmpeg brand end-card.
- **`15s_9x16_cutdown.mp4` (`720×1280`):** Aspect-safe vertical center-crop (`scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280`) of preferred beats `1.1, 2.1, 2.2, 2.3, 3.2` (with active fallback) + `9:16` end-card.
- **`6s_9x16_bumper.mp4` (`720×1280`):** Vertical center-crop of signature beats `2.2, 2.3` (capped `<= 2.4s`/beat with active fallback) + `1.2s` `9:16` end-card.

**Native Omni Audio Sidechain Ducking Gotcha:** Because Gemini Omni Flash embeds joint spoken VO and foley directly into each act MP4's audio stream (`0:a:0`), `narrator_audio_path` is typically `None`. When an external `background_music_path` is supplied without `narrator_audio_path`, `CommercialConformer` concatenates the unscored master segments first and passes that MP4's native audio stream as `dialogue_path` into `apply_dialogue_audio_ducking(..., ducking_db=-18.0)` (`-af apad -shortest`), preserving native Omni VO/foley at `0 dB` instead of overwriting `0:a:0`.

---

## 4. ADK 2.11+ Workflow & `/api/soundstage/*` Surface

- **ADK Workflow (`build_soundstage_commercial_workflow` in `src/omnimash/agent/adk_pipeline.py`):**
  `START -> soundstage_physics_and_dna -> soundstage_three_act_planner -> kit_and_boards_worker -> [soundstage_act_worker_1..3] -> acts_execution_join -> commercial_conformer -> doma_commercial_critic`
- **API Endpoints (`src/omnimash/api/routers/soundstage.py` & `src/omnimash/agent/soundstage_runner.py`):**
  - `POST /api/soundstage/discover`, `POST /api/soundstage/plan`, `POST /api/soundstage/cast`, `POST /api/soundstage/boards`, `POST /api/soundstage/run`
  - `GET /api/soundstage/{run_id}/events` (non-blocking `asyncio.to_thread` SSE stream) & `GET /api/soundstage/{run_id}/status`
  - `POST /api/soundstage/{run_id}/revise` (Lock & Isolate single-act `PromptRefiner` re-cut), `POST /api/soundstage/{run_id}/reconform` (0-call FFmpeg NLE trim/bypass), `POST /api/soundstage/{run_id}/variations` (`fork_session` across `"place" | "cast" | "offering"`), and `GET /api/soundstage/{run_id}/package.zip`.
