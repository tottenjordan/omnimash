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
