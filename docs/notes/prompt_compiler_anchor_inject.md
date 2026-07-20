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

## 🎬 Storyboard Sequence Prompt Structure

The `PromptCompiler.compile_storyboard()` method structures prompt payloads into three foundational blocks designed specifically for Gemini Omni Flash native video generation:

```text
[ROLE DEFINITIONS]
- Role A (Harry): Harry Potter, a young wizard with round wire-rim glasses and lightning scar (Ref: https://example.com/harry.jpg)
- Role B (Draco): Draco Malfoy, a blonde rival wizard in silver-trimmed robes (Ref: https://example.com/draco.jpg)

[AESTHETIC INJECTION]
Concept: Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style
Aesthetic Tags: 2000s Atlanta Trap Disstrack, Diamond Lightning Bolt Chain, Vintage Streetwear
Environment: Gothic Hogwarts courtyard lit by neon stage lights and smoky haze
Audio Beat: 140 BPM Heavy 808 Trap

[STORYBOARD SEQUENCE]
- Scene 1 [Role A]: Arriving at foggy Hogwarts courtyard rapping into microphone wand | Dialogue: "I been cooking potions since first year. Burrr!"
- Scene 2 [Role B]: Stepping from shadows in high-gloss neon lighting with ice chain | Dialogue: "This is Trap or Die, Potter! Let's get it!"
```

### Prompt Block Explanations

1. **`[ROLE DEFINITIONS]`**:
   - Explicitly establishes role identifiers (`Role A`, `Role B`) and binds them to physical descriptions and reference image URLs.
   - Informs Gemini Omni Flash which visual features and reference image embeddings correspond to each character identity, preventing facial drift and character merging.

2. **`[AESTHETIC INJECTION]`**:
   - Injects the overall cultural mashup aesthetic, environment background, camera/lighting style, and audio beat tempo.
   - Ensures the background atmosphere and music rhythm remain unified across all scenes.

3. **`[STORYBOARD SEQUENCE]`**:
   - Orders the narrative progression turn-by-turn across storyboard scenes.
   - Specifies which `active_roles` appear in each scene, their physical kinematics/actions, and their spoken dialogue.
   - Directs the joint audio-video latent space to synchronize character lip motion to dialogue lines and drop audio beats on visual keyframes.

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
