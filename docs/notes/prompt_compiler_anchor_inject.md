# Prompt Compiler: The "Anchor & Inject" & Multi-Scene Storyboard Framework

This note documents the prompt engineering architecture that eliminates **Character Decay, Latent Space Averaging, and Multi-Scene Ambiguity** when generating multi-character parody videos with `gemini-omni-flash-preview`.

---

## 🔬 Problem: Latent Space Averaging & Multi-Character Bleed

When prompting `gemini-omni-flash-preview` with raw user shorthand like *"Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style"*, the model's multimodal latent space averages the conflicting concepts. Without explicit character role bindings and structured scene sequencing, characters bleed into generic archetypes, losing facial likeness, reference grounding, and narrative pacing.

---

## 💡 Solution Architecture: Structured Prompt Compilation

The **Prompt Compiler** (`src/omnimash/prompts/compiler.py`) intercepts user intent and transforms raw concepts into structured prompt payloads for the Gemini Omni Flash native video pipeline.

It supports two core compilation paradigms:
1. **Single-Clip Baseline Compilation (`compile()`)**: 5-part Anchor & Inject for standalone clips (`[SUBJECT ANCHOR]`, `[AESTHETIC INJECTION]`, `[ENVIRONMENT]`, `[CAMERA/LIGHTING]`, `[MOTION]`).
2. **Multi-Scene Storyboard & Character Roles Compilation (`compile_storyboard()`)**: Formats multi-character roles, attached Gemini Omni Image Role reference URLs, and sequential storyboard scenes.

---

## 👥 Multi-Character Roles & Storyboard Data Models

### 1. `CharacterRole`
Defines a character's role binding, visual likeness, and attached reference image conforming to the [Gemini Omni Image Roles specification](https://ai.google.dev/gemini-api/docs/omni#set-image-roles):
```python
@dataclass
class CharacterRole:
    role_id: str  # e.g., "Role A", "Role B"
    name: str  # e.g., "Harry", "Draco"
    description: str  # Rich physical likeness and attire
    reference_url: str | None = (
        None  # Attached reference image URL for Image Roles
    )
```

### 2. `SceneDirective`
Defines an individual scene within a multi-scene storyboard:
```python
@dataclass
class SceneDirective:
    scene_number: int  # e.g., 1, 2, 3
    active_roles: list[str]  # e.g., ["Role A"], ["Role B"]
    action: str  # Specific physical action and camera movement
    dialogue: str = ""  # Spoken line for neural voice & subtitles
```

### 3. `MetaPromptTags`
Structured container produced by NLP concept deconstruction (`PromptCompiler.deconstruct_concept()`):
```python
@dataclass
class MetaPromptTags:
    characters: list[CharacterRole] = field(default_factory=list)
    aesthetic_tags: list[str] = field(default_factory=list)
    environment_tag: str = ""
    camera_lighting_tag: str = ""
    audio_beat: str = ""
```

---

## 🎬 Four-Block Omni Flash Prompt Structure & Image Role Tagging

The `PromptCompiler.compile_prompt()` and `OmniFlashClient._build_multimodal_contents()` methods structure prompt payloads into four foundational blocks designed specifically for Gemini Omni Flash native multimodal video generation:

```text
### INPUT ROLES
[Image 1: A photo of a woman with red curly hair] = [Character Reference]
[Image 2: A sketch of an ornate silver key] = [Product Reference]
[Image 3: Starting frame concept art] = [Starting Frame]

### CHARACTER PROFILES
[Character A: "Maya"]
Visual: A woman in her 30s with curly red hair, wearing a yellow raincoat.
Voice: High-pitched, fast-paced, and anxious.

[Character B: "Tom"]
Visual: A man in his 50s with a grey beard, wearing a thick wool sweater.
Voice: Deep, gravelly, calm, and slow.

[Character: "Narrator"]
Visual: Off-screen (Voiceover only). Do not show.
Voice: Deep, warm, authoritative documentary voice. Spoken into studio microphone.

### SCENE INSTRUCTIONS
A wide, continuous shot of a rain-swept wooden dock. Maya and Tom are facing each other. No scene cuts.
Camera & Lighting: Anamorphic lens, rainy reflections, high contrast cinematic lighting.
Environment: Rainy wooden dock at dusk.
Audio: Sound design: Foreground voiceover is dominant. Background beat (instrumental slow mournful jazz saxophone) is subtly ducked beneath dialogue.

### TIMELINE
[0-3s] Maya waves her arms frantically. Maya says with an anxious, fast delivery: "The boat is gone! I told you we should have tied it tighter!"
[3-5s] Tom calmly puts his hands in his pockets. Tom says in his deep, slow voice: "It's not gone, Maya."
[5-8s] Tom points out toward the foggy horizon. Tom continues: "The tide just took it out a bit."
[8-10s] Maya turns her head to look where he is pointing. Maya: [loud sigh] "Oh. Right."
```

### Prompt Block Explanations & Best Practices

1. **`### INPUT ROLES`**:
   - Explicitly tags each attached reference image with its functional job:
     - `[Character Reference]` / `[Subject Reference]`: Preserves character face, likeness, and visual attributes.
     - `[Product Reference]`: Preserves exact product logo, branding, and color materials.
     - `[Starting Frame]`: Animates outward from the exact keyframe starting image.
     - `[Style Reference]`: Preserves artistic medium, color palette, and mood.

2. **`### CHARACTER PROFILES`**:
   - Pairs physical likeness descriptions with vocal profile descriptions.
   - For off-screen narration, explicitly sets `Visual: Off-screen (Voiceover only). Do not show.` so the model does not attempt lip-syncing.

3. **`### SCENE INSTRUCTIONS`**:
   - Enforces continuous camera shot directives (`In a single continuous shot. No scene cuts.`).
   - Declares instrumental background audio (`instrumental`) to prevent AI vocals from overlapping spoken dialogue.

4. **`### TIMELINE`**:
   - Orders narrative progression turn-by-turn in chronological `[X-Ys]` timing blocks.
   - Uses explicit quotation marks (`"..."`) around spoken dialogue to distinguish speech from written on-screen text graphics (`reading "..."`).
   - Long scripts > 10s are automatically split into sequential 10s shot cards (`[0-10s]`, `[10-20s]`, `[20-30s]`) with character continuity locks.

---

## 🔁 Single-Clip Baseline & Conversational Delta Compilation

For standalone clip generation and iterative editing, the compiler provides:

### 5-Part Single Clip (`compile()`)
```text
[SUBJECT ANCHOR] + [AESTHETIC INJECTION] + [ENVIRONMENT] + [CAMERA/LIGHTING] + [MOTION]
```

### 2-Part Conversational Delta (`compile_delta()`)
```text
[PRESERVATION LOCK] + [ISOLATED DIFF]
```
- **`[PRESERVATION LOCK]`**: Freezes character likeness, Role identities, environment, and audio rhythm from the parent turn.
- **`[ISOLATED DIFF]`**: Targets only the user-requested modification, preventing unwanted cascade edits across turns.
