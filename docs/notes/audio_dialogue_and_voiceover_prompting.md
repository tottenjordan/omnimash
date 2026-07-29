# 🎙️ Audio Modalities in OmniMash: Sound Design, Voiceover, Multi-Subject Dialogue & Silent Video

## 📌 Context & Motivation
When generating parody videos using multimodal AI models like **Gemini Omni Flash (`gemini-omni-flash-preview`)**, acoustic direction must be strictly decoupled from visual text overlays and separated into distinct acoustic channels. 

In video production, **Background Music/Sound Design** (BPM, 808 sub-bass, synths), **Character Voice Styles & Accents** (character-specific flow, accent, and timbre), and **Global Vocal Delivery** (scene-wide delivery style and energy) are structured into a dedicated acoustic prompt block. Furthermore, creators often require **Silent Video** generation for clean B-roll footage.

---

## 🎧 The Independent Acoustic & Visual Channels

```mermaid
flowchart TD
    subgraph UI_Inputs [🎛️ OmniMash UI Controls]
        A["🎵 1. Audio Beat / Sound Design<br>(e.g. 140 BPM UK Drill, Synthwave, or 🔇 Mute)"]
        B["🎙️ 2. Character Voice Style & Accent<br>(e.g. Fast-paced Atlanta rap flow / Pompous British drawl)"]
        C["🎙️ 3. Vocal Delivery / Voiceover Style<br>(e.g. High-energy rap battle delivery with synchronized lip-sync)"]
        D["📝 4. On-Screen Text / Subtitles<br>(e.g. SNAPE 1994, or empty for clean)"]
    end

    subgraph Compiler [🪄 Prompt Compiler & Taxonomy Engine]
        E["Structured Audio Directive<br>[AUDIO & VOCAL DIRECTION]<br>Background Beat: {beat}<br>Voice Style (Role A): {style_a}<br>Voice Style (Role B): {style_b}<br>Vocal Delivery: {delivery}"]
        F["Negative / Visual Text Constraint<br>On-screen text: '{text}' OR No text, no subtitles on screen."]
    end

    subgraph Model_Execution [⚡ Multimodal Generation]
        G1["🧠 Gemini Omni Flash API<br>(gemini-omni-flash-preview)"]
        G2["🎬 Container Fallback Renderer<br>(FFmpeg + Dynamic PCM Synthesizer)"]
    end

    A --> E
    B --> E
    C --> E
    D --> F

    E --> G1
    F --> G1

    E --> G2
    F --> G2
```

---

## 🎙️ 1. Character Voice Styles & Global Vocal Delivery Controls

OmniMash provides dedicated UI controls to direct acoustic vocal characteristics at both the granular character level and the scene-wide global level:

### 🎙️ Dedicated Voice Style & Accent Inputs per Character Role Card
Located inside each **Character Role** card in **Act 1: The Concept & Cast Manager**:
* **Purpose:** Sets character-specific vocal timbre, accents, flow, and cadence.
* **Examples:**
  * **Role A (Harry):** `Fast-paced confident Atlanta rap flow with autotune`
  * **Role B (Draco):** `Pompous, cynical British drawl with aggressive rap cadence`
* **Compilation:** Mapped directly to `Voice Style (Role A): ...` and `Voice Style (Role B): ...` in the prompt payload.

### 🎙️ Global Vocal Delivery / Voiceover Style Control
Located inside the **Environment & Audio Direction** card in **Act 1**:
* **Purpose:** Dictates overarching acoustic delivery, energy level, narrative tone, and lip-sync synchronization style across all active subjects.
* **Examples:** `High-energy back-and-forth rap battle delivery with synchronized lip-sync`, `Dramatic whispered narration`, or `Deadpan comedic banter`.
* **Compilation:** Mapped directly to `Vocal Delivery: ...` in the prompt payload.

---

## 📋 2. Gemini Omni Flash Timecode Syntax (`[0-3s]`)

Following official **Gemini API Omni documentation**, `PromptCompiler.compile_prompt()` organizes acoustic, visual, and vocal directives directly into chronological `[X-Ys]` timing blocks.

### Official Gemini Omni Flash Timecode Template:
```text
In a single continuous shot. No scene cuts.

# Character Roster & Visual Directives:
- Role A (Harry "Gucci"): Harry "Gucci", young wizard with round gold wire-rim Cartier glasses, red Gucci tracksuit [Style: Red Gucci Tracksuit, Cartier Glasses] [Visual Reference: Attached Image #2]
- Role B (Young Draco "Jeezy"): Young Draco "Jeezy", pale blonde rival wizard with slicked-back platinum hair, green velvet blazer [Style: Platinum Slicked Hair, Diamond Iced-Out Chain] [Visual Reference: Attached Image #3]

[0-3s] Harry "Gucci" steps up to the microphone under glowing neon stage lights. Background audio: 140 BPM Heavy 808 Trap with ambient crowd cheers. He says cheerfully, "Welcome to Dripwarts, turn the beat up!"
[3-6s] Young Draco "Jeezy" drops a heavy 808 trap beat and flashes his diamond chain. Background audio: crisp snare trills and sub-bass drop. He says arrogantly, "Potions class is in session, no cap!"
[6-10s] Both wizards perform a synchronized rap battle climax amidst stage smoke. Background audio: climax 808 beat drop. Both say: "Trap or Die!"
```

### Why Timecode Syntax Matters for Gemini Omni Flash:
1. **Integrated Multimodal Execution:** Chronological `[0-3s]` timing blocks instruct Gemini Omni Flash to process visual movement, background audio effects, and spoken dialogue in a single pass.
2. **Synchronized Dialogue Placement:** Timing blocks prevent the audio engine from firing dialogue lines prematurely before character actions occur.
3. **Continuous Shot Camera Control:** Prepending `"In a single continuous shot. No scene cuts."` prevents Gemini Omni Flash from inserting unwanted scene cuts.

---

## 🎭 3. Multi-Subject Spoken Dialogue vs. Voiceover Narration

### How `gemini-omni-flash-preview` Processes Speech:
Gemini Omni Flash accepts natural language speaker turns. By structuring vocal lines into explicit character turns, the model handles both acoustic vocal synthesis and visual lip-sync:

1. **Single-Subject Voiceover Narration:**
   * **Input:** `Gaunt cynical wizard speaking in a deep British drawl: 'Clearly, fame isn't everything.'`
   * **Compiled Directive:** `Voiceover: Gaunt cynical wizard speaking in a deep British drawl: 'Clearly, fame isn't everything.'`
   * **Model Behavior:** Synthesizes a deep monologue over the background beat while the main character speaks to the camera.

2. **Multi-Subject Conversational Dialogue:**
   * **Input:**
     ```text
     Snape (in a cold, sarcastic sneer): "You think you can out-rap the Half-Blood Prince, Potter?"
     Harry (grinning with confidence): "Expecto Patronum on the 808s, professor!"
     ```
   * **Compiled Directive:**
     `Dialogue between subjects: Snape (in a cold sneer): '...' / Harry (with confidence): '...'.`
   * **Model Behavior:**
     * **Acoustic Vocal Generation:** Synthesizes two distinct voices (deep British drawl for Snape vs. energetic tone for Harry) conditioned by their respective `Voice Style` entries.
     * **Kinematics & Lip-Sync:** Vision generation heads automatically alternate character camera focus and mouth movements to match who is speaking at each second of the 10-second clip!

---

## 🎚️ 4. Automatic Audio Ducking & Text-to-Speech Spoken Voice Synthesis

### Real Spoken Voiceover & Character Dialogue Generation:
When dialogue or voiceover narration is present alongside background music, OmniMash uses a multi-layer acoustic pipeline to synthesize and balance audio levels so spoken words are crystal-clear:

* **Spoken Speech Synthesis (TTS Engine):** Spoken character dialogue turns and voiceover monologues are synthesized into real audible spoken words using FFmpeg's built-in `libflite` TTS engine at 44.1kHz.
* **Foreground Speech Amplification (180% Volume):** Spoken dialogue is mixed in the foreground at high volume (`volume=1.8`) to ensure complete intelligibility.
* **Ducked Background Beat (12%–15% Volume):** When voiceover or character dialogue is detected, the instrumental background beat (808 sub-bass, hi-hats, synthwave arpeggios, or boom-bap drums) is dynamically ducked down to **12%–15% background volume** (`volume=0.12`).
* **Result:** Spoken words from the characters dominate the mix cleanly in the foreground, while the background beat provides a subtle, quiet rhythmic groove beneath their voices.

---

## 🔇 5. Silent Video / Mute Mode

### When & How to Use:
Creators often want pristine 720p 24fps video clips without any audio track for external editing or background video loops.

* **Triggering Silent Video:**
  * Checking the **`🔇 Mute (Silent Video)`** toggle in the UI dashboard.
  * Or typing `"mute"`, `"none"`, or `"silent"` into the Audio Stem / Beat field.
* **Compiled Model Directive:**
  `Background Beat: Silent video. No background music, no audio, no sound effects.`
* **Container Fallback Behavior:**
  Synthesizes a 0-amplitude waveform and generates a clean, silent MP4 container via FFmpeg.

---

## 🎹 6. Summary of Audio Combinations

| Combination | 🎵 Audio Beat Input | 🎙️ Voice Style & Vocal Delivery | 💬 Character Dialogue Input | Resulting Video Audio |
| :--- | :--- | :--- | :--- | :--- |
| **1. Full Mashup (Default)** | `140 BPM UK Drill 808s` | Fast Atlanta flow / Pompous British drawl | `Harry: "Potter..." / Draco: "..."` | 140 BPM Drill beat ducked under synchronized rap battle dialogue exchange. |
| **2. Music / Beat Only** | `Synthwave arpeggios` | *(Leave empty)* | *(Leave empty)* | Pure background instrumentals without vocals. |
| **3. Spoken Dialogue Only** | `🔇 Mute / Silent Video` | Pompous British drawl | `Snape: "Turn to page 394"` | Spoken dialogue without background music. |
| **4. Silent Video** | `🔇 Mute / Silent Video` | *(Leave empty)* | *(Leave empty)* | 100% silent video. |

---

## 🛠️ Key Implementation Files
* [src/omnimash/prompts/compiler.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/prompts/compiler.py) – Formats `[AUDIO & VOCAL DIRECTION]`, character `voice_style`, global `vocal_delivery`, and ducked background beats.
* [src/omnimash/engine/omni_client.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/engine/omni_client.py) – Implements `_generate_dynamic_audio_wav()` to synthesize multi-genre PCM audio waveforms, speech-band formants, or complete silence.
* [src/omnimash/api/app.py](file:///usr/local/google/home/jordantotten/omnimash/src/omnimash/api/app.py) – Exposes the dedicated UI input controls for `🎙️ Voice Style & Accent` and `🎙️ Vocal Delivery / Voiceover Style`, along with live editable prompt preview cards.
