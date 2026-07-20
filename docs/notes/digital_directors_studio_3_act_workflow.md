# Digital Director's Studio: 3-Act Progressive Linear Workflow

## 📌 Motivation & Architecture
Open-ended text boxes often lead users to vague prompts (e.g., *"make Harry Potter look cool"*), failing to leverage the joint audio-video latent space of `gemini-omni-flash-preview`. 

The **Digital Director's Studio** replaces generic chat interfaces with a structured 3-Act progressive pipeline grounded in the **Flexible Parody Workflow**, concept deconstruction, and **Gemini Omni Image Roles** ([Gemini Omni Image Roles Documentation](https://ai.google.dev/gemini-api/docs/omni#set-image-roles)):

---

## 🎭 Act 1: The Concept & Cast Manager
* **Goal**: Define the open-ended parody concept and cast characters with explicit Gemini Omni Image Roles.
* **Open-Ended Visual Concept Input**: Free-form natural language input for any parody concept or cultural mashup (e.g., *"Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style"* or *"Gordon Ramsay vs Julia Child in a cyberpunk iron chef battle"*).
* **NLP Concept Deconstruction (`POST /api/deconstruct-concept`)**: 1-click deconstruction engine parses raw user shorthand into structured `MetaPromptTags` including dynamic character roles, aesthetic tags, environment settings, camera/lighting signifiers, and audio beats.
* **Character & Image Role Manager (Gemini Omni Image Roles)**:
  * Dynamic assignment of role identifiers (`Role A`, `Role B`, etc.).
  * Editable character names and detailed physical visual likeness descriptions.
  * Explicit Reference Image URL attachment ([Gemini Omni Image Roles](https://ai.google.dev/gemini-api/docs/omni#set-image-roles)) to anchor character likeness across generated scenes.
* **Editable Meta-Prompt Tags & Audio Beat**: Interactive tag chips for aesthetic styles, background environment, camera/lighting framing, and audio beat tempo (e.g. 140 BPM Heavy 808 Trap).

---

## 🎛️ Act 2: Fine-Tune & Storyboard Directing
* **Goal**: Sequence and direct multi-scene storyboards before rendering the final video cut.
* **Multi-Scene Storyboard Editor**:
  * Sequence individual scenes (Scene 1, Scene 2, Scene 3, etc.) for a cohesive ~1-minute parody narrative.
  * **Active Role Selectors**: Assign specific character roles (`Role A`, `Role B`) to each scene in the storyboard.
  * **Action Directives**: Define specific physical actions and cinematographic movements per scene (e.g. *"Arriving at foggy courtyard rapping into microphone wand"*).
  * **Turn-by-Turn Dialogue**: Direct character dialogue and speech per scene (e.g. *"I been cooking potions since first year. Burrr!"*), supporting neural spoken voice synthesis and subtitles.
* **Live Storyboard Prompt Preview**: Real-time compiled prompt view structured across `[ROLE DEFINITIONS]`, `[AESTHETIC INJECTION]`, and `[STORYBOARD SEQUENCE]`.

---

## 🎬 Act 3: The Screening Room & Branching
* **Goal**: Review the rendered multi-character parody cut, iterate with conversational diffs, and manage version branches.
* **Multi-Character Parody Cut Generation (`POST /api/generate`)**:
  * Dispatches the compiled multi-scene storyboard and character role references to `gemini-omni-flash-preview` via the Gemini Enterprise Interactions API.
  * Generates 720p native video with synchronized audio and multi-character consistency.
* **Central High-Resolution Player**: Play/pause, loop toggle, and SynthID / C2PA provenance indicators.
* **Chronological Layer-Cake Version Tree DAG**:
  * Interactive version timeline displaying turn-by-turn history cards with `Preservation Lock` and `Isolated Diff` badges.
  * Tracks thread edit depth (`depth >= 3`) to signal `COMMIT_RECOMMENDED`.
* **Direct the Scene (Conversational Delta Prompting)**: Quick iterative delta prompting (e.g., *"Make his chain bigger"* or *"Swap microphone for glowing wand"*).
* **Commit & Re-Anchor Checkpoint (`POST /api/commit`)**: Resets edit depth to 0, establishes a fresh keyframe baseline, and flushes token context decay.
