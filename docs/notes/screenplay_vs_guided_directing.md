# Storyboard Directing: Guided Mode vs. Screenplay Mode

## 📌 Overview

OmniMash provides two distinct directing modes in **Act 2: Storyboard & Shot Director** for creating 10-second video clip directives:
1. **🎛️ Guided Mode (Default)**: Structured form inputs for visual action and spoken dialogue.
2. **📜 Screenplay Mode**: Multi-line script editing using natural screenplay formatting (`Character: (Action/Audio) "Dialogue"`).

---

## 📊 Mode Comparison Matrix

| Feature | 🎛️ Guided Mode (Default) | 📜 Screenplay Mode |
| :--- | :--- | :--- |
| **Best For** | Quick, simple 10-second shot setup with explicit form inputs | Complex multi-character action, audio FX stems, and dialogue scripts |
| **Input Interface** | - **Action Textarea**: Character movement & camera framing<br>- **Dialogue Input**: Character spoken voiceover line | - **Multi-line Screenplay Textarea**: Full screenplay format (`Character: (Action description. Audio cue.) "Dialogue"`) |
| **Character Allocation** | Checkboxes (`Role A`, `Role B`) | Speaker prefixes (`Harry:`, `Ollivander:`, `Role A:`) automatically matched to Cast Roster |
| **Audio FX & Visual Parsing** | Actions & dialogues formatted as standard fields | Automatically extracts visual actions `(...)`, audio FX cues `(...)`, and spoken quotes `"..."` |

---

## 🛠️ Prompt Compilation Breakdown

### 1. 🎛️ Guided Mode Compilation

In **Guided Mode**, the inputs are combined into a clean, structured single-line directive:

**User Inputs**:
- **Active Roles**: `Role A (Harry)`, `Role B (Ollivander)`
- **Action**: `Harry inspects the glowing wand while Ollivander nods in approval`
- **Dialogue**: `"Is this the 1017 edition?"`

**Compiled Prompt Block**:
```text
[IMAGE ROLES]
- [IMAGE 1]: Reference image for Role A (Harry).
- [IMAGE 2]: Reference image for Role B (Ollivander).

[ROLE DEFINITIONS]
- Role A (Harry): Harry Potter, a young wizard... [Style: Red Gucci Tracksuit]
- Role B (Ollivander): Garrick Ollivander, an elderly wizard... [Style: Vintage Tweed]

[STORYBOARD SEQUENCE]
- Scene 1 [Role A, Role B]: Harry inspects the glowing wand while Ollivander nods in approval | Dialogue: "Is this the 1017 edition?"
```

---

### 2. 📜 Screenplay Mode Compilation

In **Screenplay Mode**, `ScreenplayParser` parses script lines into visual actions, background audio stems, and character spoken dialogue quotes:

**User Inputs**:
- **Active Roles**: `Role A (Harry)`, `Role B (Ollivander)`
- **Screenplay Script Text**:
  ```text
  Harry: (Takes the wand. Heavy bass drops, subwoofers rumble, and lightning flashes).
  Harry: (Looking at his wrist) "BRRR! Yeah, this the one right here. How many Galleons?"
  Ollivander: "For you, Mr. Potter? Just put 1017 in your bio."
  ```

**Compiled Prompt Block**:
```text
[IMAGE ROLES]
- [IMAGE 1]: Reference image for Role A (Harry).
- [IMAGE 2]: Reference image for Role B (Ollivander).

[ROLE DEFINITIONS]
- Role A (Harry): Harry Potter, a young wizard... [Style: Red Gucci Tracksuit]
- Role B (Ollivander): Garrick Ollivander, an elderly wizard... [Style: Vintage Tweed]

[AUDIO & VOCAL DIRECTION]
Voice Style (Role A): Harry Potter voice
Voice Style (Role B): Ollivander voice
Audio Cues: Heavy bass drops, subwoofers rumble, and lightning flashes

[STORYBOARD SEQUENCE]
- Scene 1 [Role A, Role B] (Screenplay):
  - Role A (Harry): Takes the wand. Heavy bass drops, subwoofers rumble, and lightning flashes.
  - Role A (Harry): (Looking at his wrist) "BRRR! Yeah, this the one right here. How many Galleons?"
  - Role B (Ollivander): "For you, Mr. Potter? Just put 1017 in your bio."
```

---

## 💡 Benefits & Best Practices

1. **Guided Mode**: Best when you want to quickly test a single visual prompt and one line of dialogue.
2. **Screenplay Mode**: Best when directing a dynamic 10-second scene with parenthetical sound effects (`(Heavy sub-bass drops)`), visual stage directions (`(Looking at wrist)`), and multiple back-and-forth dialogue exchanges.

---

## 🎬 Multi-Scene Sequence Behavior vs. 4-Stage Storyboard Studio

### 1. Act-Based Director Mode (`+ Add Scene` & `POST /api/generate`)
In Director Mode (Act 2):
- Clicking **`+ Add Scene`** appends `Scene #N` into a **cumulative `scenes` array**.
- All scenes in the array are sent together in the JSON payload to `POST /api/generate`:
  ```json
  {
      "concept": "Parody rap battle",
      "characters": [...],
      "scenes": [
          { "scene_number": 1, "action": "Harry enters potion dungeon...", "dialogue": "..." },
          { "scene_number": 2, "action": "Draco steps out of shadows...", "dialogue": "..." }
      ],
      "environment_tag": "Dimly lit dungeon",
      "audio_stem": "90s 808 Trap Beat"
  }
  ```
- `PromptCompiler.compile_storyboard()` formats **all scenes** into a single `### TIMELINE` block inside the Four-Block prompt:
  ```text
  ### TIMELINE
  - Scene 1 [Role A]: Harry enters potion dungeon... | Dialogue: "..."
  - Scene 2 [Role B]: Draco steps out of shadows... | Dialogue: "..."
  ```
- **Output**: Generates a single combined video cut for the entire timeline sequence.

---

### 2. 4-Stage Storyboard Studio Mode (`POST /api/generate-shot` & Stitching)
In 4-Stage Storyboard Mode:
- Stage 1 (Vision) expands a concept or screenplay into individual **Shot Cards** (Shot #1, Shot #2, Shot #3).
- Each Shot Card is generated **individually** via `POST /api/generate-shot` using custom `shot_directive` parameters and `parent_turn_id` for character visual continuity.
- In Stage 4 (Stitch & Export), all individual shot videos are concatenated via `POST /api/stitch-clips` into a final 60-second master video.

---

### 📊 Summary Comparison Matrix

| Aspect | Act-Based Director Mode (`scenes`) | 4-Stage Storyboard Studio Mode (`stageShots`) |
| :--- | :--- | :--- |
| **API Endpoint** | `POST /api/generate` | `POST /api/generate-shot` |
| **Scene/Shot Scope** | All `scenes` sent together as one sequence into `### TIMELINE` | Each Shot Card generated individually as an isolated 10s clip |
| **Video Output** | Single combined parody cut for the sequence | Individual 10s video per shot card + final stitched master |
| **Continuity Method** | Model renders continuous sequence | Shot #2 references Shot #1's `turn_id` for character likeness |

