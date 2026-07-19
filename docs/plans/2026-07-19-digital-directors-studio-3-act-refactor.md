# Digital Director's Studio: 3-Act Progressive Linear User Journey Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the OmniMash interface from an open-ended single prompt box into a 3-Act Digital Director's Studio (Act 1: The Clash, Act 2: The Fine-Tune, Act 3: The Director's Chair) powered by the Anchor & Inject framework, automated Gemini 3.5 Flash parody research, explicit YouTube reference asset extraction, a Vibe slider, and a chronological layer-cake editing timeline.

**Architecture:** 
1. **Act 1 (The Clash - The Setup):** A split-screen card grid pairing the *Subject Anchor* (e.g. Dark Wizard, Sci-Fi Hunter, Harry & Draco) with the *Aesthetic Injection* (e.g. 90s East Coast Rap, Atlanta Trap Beef, Cyberpunk Drift). Supports YouTube URL reference extraction with an explicit "Extract Reference Assets" button and an optional "🧠 Research Parody with Gemini 3.5" trigger that analyzes character lore and cultural analogies.
2. **Act 2 (The Fine-Tune - The Directing):** Expands the Clash into specific directorial controls: Drip prop selector (e.g. Diamond Lightning Bolt Chain, Vintage Gucci Tracksuit), Vibe slider (Gritty/Underground 0% $\leftrightarrow$ Neon/Glossy 100%), Audio Beat loops (140 BPM Trap, 120 BPM Boom-Bap), and Voiceover/Dialogue turn overrides.
3. **Act 3 (The Director's Chair - The Iteration Loop):** Central high-res video player accompanied by a chronological "Layer Cake" edit history showing the preservation lock and isolated diff for every turn, plus a "Direct the Scene" delta chat input and a 1-click **"⚡ Load Trap-Warts Concept"** preset loader.

**Tech Stack:** FastAPI, React 18, Tailwind CSS, Google GenAI SDK (`gemini-2.5-flash` / `gemini-3.5-flash` for research, `gemini-omni-flash-preview` for video), FFmpeg, Pytest, Ruff, Ty.

---

## User Review Required

> [!IMPORTANT]
> **Linear Progressive Flow with Non-Destructive Navigation:**
> The UI guides users linearly through Act 1 $\rightarrow$ Act 2 $\rightarrow$ Act 3, but allows clicking backwards or forwards at any time via an Act status bar at the top of the Studio.

> [!TIP]
> **Built-in "Trap-Warts" Concept Preset:**
> A 1-click loader button for "Trap-Warts: Harry & The Brick Factory (Gucci vs. Jeezy)" will instantly populate all 3 acts with character analogies, diamond chains, 140 BPM Atlanta trap beats, and dialogue turns for immediate testing.

---

## Proposed Changes

### Component 1: Ingestion & Parody Research Engine

#### [MODIFY] `src/omnimash/ingestion/media_extractor.py`
- Define `ParodyResearchResult` dataclass:
  - `synopsis: str`
  - `suggested_props: list[str]`
  - `suggested_vibe: str`
  - `vibe_intensity: int` (0 to 100)
  - `suggested_audio: str`
  - `suggested_dialogue: str`
- Add method `research_parody_clash(subject: str, aesthetic: str) -> ParodyResearchResult` to `MediaExtractor`:
  - In mock mode (or via Gemini Flash in live mode), returns rich cultural mashup research (e.g. Harry Potter + Atlanta Trap = Gucci Tracksuits over Hogwarts Robes, Lightning Bolt Cuban Chains, and 140 BPM 808 Trap beats).

#### [MODIFY] `src/omnimash/api/app.py`
- Add API endpoints:
  - `POST /api/extract-reference`: extracts keyframes and BPM from YouTube reference before generating.
  - `POST /api/research`: executes Gemini Flash parody research on the selected clash.

---

### Component 2: Directorial Prompt Taxonomy & Compiler Refactor

#### [MODIFY] `src/omnimash/prompts/compiler.py`
- Update `CompiledPromptParts` and `PromptCompiler.compile()` to accept:
  - `drip_props: list[str] | str | None = None`
  - `vibe_intensity: int = 50` (0=Gritty/Underground, 50=Balanced, 100=Neon/Glossy)
- Translate `vibe_intensity` into dynamic lighting/camera directives:
  - $\le 30$: *"Dark moody underground lighting, heavy laser smoke, high-contrast shadows, raw 16mm grain"*
  - $31 - 70$: *"Cinematic high-contrast MTV lighting with balanced ambient color grading"*
  - $\ge 71$: *"High-gloss neon lighting, vibrant anamorphic lens flare, holographic bloom, polished commercial aesthetic"*
- Append selected `drip_props` directly into the `[AESTHETIC INJECTION]` and wardrobe layers.

---

### Component 3: 3-Act "Digital Director's Studio" React Frontend

#### [MODIFY] `src/omnimash/api/app.py`
- Refactor the React Web UI into the 3-Act Director's Studio layout:
  - **Top Navigation Bar:** Studio title, Session Name input (`gs://...` path indicator), and 3-Act progress stepper (`[🎭 Act 1: The Clash] ➔ [🎛️ Act 2: The Fine-Tune] ➔ [🎬 Act 3: The Director's Chair]`).
  - **Act 1: The Clash Screen**:
    - Subject Anchor card grid (Dark Wizard, Sci-Fi Bounty Hunter, Renaissance Painter, Harry "Gucci" Potter & Draco "Jeezy" Malfoy, or Custom Upload/Prompt).
    - Aesthetic Injection card grid (90s East Coast Rap, Atlanta Trap Disstrack, Cyberpunk Drift, VHS Anime Lo-Fi, 00s Nu-Metal).
    - Reference YouTube input + explicit **"🔍 Extract Reference Assets"** button showing instant keyframe annotations.
    - **"🧠 Research Parody Clash with Gemini"** button to auto-generate creative concepts.
  - **Act 2: The Fine-Tune Screen**:
    - **The "Drip" Selector:** Interactive tag cloud / checkboxes for props (Diamond Lightning Bolt Chain, Vintage Gucci Tracksuit, Shutter Shades, Microphone Wand).
    - **Vibe Slider:** Interactive slider from 0% (Gritty/Underground) to 100% (Neon/Glossy).
    - **Audio Beat Selector:** 140 BPM Trap, 120 BPM Boom-Bap, 110 BPM Synthwave, 85 BPM Lo-Fi, or Silent.
    - **Voiceover & Dialogue Editor:** Monologue or multi-subject dialogue turns.
    - Live 6-Part Anchor & Inject Prompt Preview.
    - Big **"🚀 Generate Directorial Cut"** button transitioning to Act 3.
  - **Act 3: The Director's Chair Screen**:
    - High-resolution video player with play/pause, loop, and download.
    - **Chronological Layer-Cake Edit History:** Turn-by-turn cards next to the video player displaying the active Preservation Lock and Isolated Diff.
    - **"Direct the Scene" Chat Bar:** Quick iterative delta prompting (e.g. *"Make his chain bigger"*).
    - **⚡ "Load Trap-Warts Concept"** one-click preset button.

---

## Bite-Sized Implementation Tasks

### Task 1: Parody Research Engine & Reference Extraction API
**Files:**
- Modify: `src/omnimash/ingestion/media_extractor.py`
- Modify: `src/omnimash/api/app.py`
- Test: `tests/ingestion/test_media_extractor.py`
- Test: `tests/api/test_integration.py`

**Steps:**
1. Write failing unit test `test_media_extractor_parody_research()` in `tests/ingestion/test_media_extractor.py`.
2. Implement `ParodyResearchResult` and `research_parody_clash()` in `src/omnimash/ingestion/media_extractor.py`.
3. Add `POST /api/research` and `POST /api/extract-reference` in `src/omnimash/api/app.py`.
4. Run `uv run pytest` to verify pass.
5. Run `uv run ruff check --fix .`, `uv run ruff format .`, `uv run ty check .`.
6. Commit changes on current branch with message: `feat(research): add parody research engine and reference extraction endpoints`.

---

### Task 2: Drip Props & Vibe Slider in Prompt Compiler
**Files:**
- Modify: `src/omnimash/prompts/compiler.py`
- Test: `tests/prompts/test_compiler.py`

**Steps:**
1. Write failing test `test_compiler_vibe_slider_and_drip_props()` in `tests/prompts/test_compiler.py`.
2. Update `CompiledPromptParts` and `PromptCompiler.compile()` in `src/omnimash/prompts/compiler.py` to translate `vibe_intensity` and `drip_props` into compiled prompts.
3. Run `uv run pytest tests/prompts/test_compiler.py` to verify pass.
4. Run `uv run ruff check --fix .`, `uv run ruff format .`, `uv run ty check .`.
5. Commit changes on current branch with message: `feat(prompts): add vibe slider intensity and drip prop compilation`.

---

### Task 3: 3-Act "Digital Director's Studio" React Frontend Refactor
**Files:**
- Modify: `src/omnimash/api/app.py`
- Test: `tests/api/test_integration.py`

**Steps:**
1. Write integration test `test_e2e_directors_studio_3_act_flow()` in `tests/api/test_integration.py`.
2. Update React Web UI HTML template in `src/omnimash/api/app.py`:
   - Implement 3-Act tab navigation (`activeAct: 1 | 2 | 3`).
   - Render Act 1 (The Clash card grids, YouTube extractor button, Gemini Research button).
   - Render Act 2 (Drip props picker, Vibe slider, Audio beat selector, Voiceover editor).
   - Render Act 3 (Video player, Chronological Layer-Cake history timeline, "Direct the Scene" chat bar, and Trap-Warts preset loader).
3. Run `uv run pytest` to ensure all tests pass.
4. Run `uv run ruff check --fix .`, `uv run ruff format .`, `uv run ty check .`.
5. Commit changes on current branch with message: `feat(ui): refactor frontend into 3-act digital directors studio with progressive linear flow`.

---

## Verification Plan

### Automated Tests
```bash
# Run full Pytest test suite
uv run pytest

# Run linting and formatting
uv run ruff check --fix .
uv run ruff format .

# Run static typing
uv run ty check .
```

### Manual Verification
1. Start local dev server: `uv run uvicorn src.omnimash.api.app:create_app --factory --reload --port 8000`
2. Open dashboard in browser (`http://localhost:8000`).
3. Verify Act 1: Click "Harry 'Gucci' Potter" + "Atlanta Trap Disstrack". Click "🧠 Research Parody Clash with Gemini".
4. Verify Act 2: Observe auto-populated Drip props ("Diamond Lightning Bolt Chain"), adjust Vibe slider to 90% (Glossy), select 140 BPM Trap beat. Click "🚀 Generate Directorial Cut".
5. Verify Act 3: Video plays with animated visualizer and ducked audio. Observe Chronological Layer Cake timeline. Type "Make his sunglasses darker" in the "Direct the Scene" chat bar and verify delta iteration.
