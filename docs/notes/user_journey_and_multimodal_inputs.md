# 🎬 OmniMash Multimodal User Journey & Input Architecture

This guide provides a comprehensive breakdown of the OmniMash input pipeline, prompt compiler lifecycle, and interactive video generation user journey.

---

## 🌟 The 4 Core UI Inputs & How They Are Used

OmniMash accepts 4 modular inputs from the creator, allowing maximum flexibility when composing multimodal parodies:

| Input Field | Type | Function & Purpose | How OmniMash Uses It |
| :--- | :--- | :--- | :--- |
| **1. Raw Character Prompt** | Text | The high-level creative concept (e.g., *"Snape in 90s rap video"* or *"Dumbledore diss track"*). | Fed into `PromptTaxonomyEngine` to resolve character facial lore anchors (`[SUBJECT ANCHOR]`). |
| **2. Reference YouTube URL** | HTTPS URL | A public YouTube video containing character likeness or scenes. | Ingested via `MediaExtractor` (`yt-dlp` + `ffmpeg`) to extract keyframe character portraits (stored in `sessions/${session_id}/references/`). |
| **3. Audio Stem Selector** | Waveform / BPM | Dedicated acoustic tempo and beat parameters (e.g. 120 BPM boom-bap, 140 BPM drill 808s). | Populates the **`[AUDIO TRACK]`** tag so Omni Flash's joint latent transformer binds character head bobs/gestures to acoustic beat onset times. |
| **4. Style Preset Carousel** | Selection | Aesthetic foundation vectors (`90s_rap_video`, `trap_disstrack`, `cyberpunk_drift`, `vhs_anime`). | Multiplier that injects domain-curated signifiers across wardrobe, lens choice, lighting, and acoustic cadence. |

---

## ❓ Addressing Key Architectural Questions

### [1] How is an Audio Track or YouTube Reference Video Used?
- **Reference YouTube URL:** Serves as a **visual & acoustic reference bundle**. `MediaExtractor` extracts high-resolution character keyframes (used for conditioning image anchors) and baseline audio stems.
- **Audio Track:** In `gemini-omni-flash-preview`, audio is **not** a disconnected post-processing layer. Because Omni Flash utilizes a **joint multimodal transformer**, the acoustic stem description (e.g. *120 BPM boom-bap, 808 sub-bass, trap hi-hats*) is encoded directly into the prompt payload alongside kinematic motion. The model's cross-attention layers bind the character's physical micro-movements (head nodding, hand gestures, lip cadence) to the exact beat onset times in the synthesized audio track.

### [2] Should "Reference YouTube URL" and "Audio Stem" be Separate Inputs?
- **Yes, they should remain separate, complementary inputs in the UI/API, while converging in the Prompt Compiler.**
- **Why?** 
  1. A creator may provide a YouTube URL for a visual character reference (e.g., a movie clip of Voldemort), but want to apply a completely different custom audio track (e.g., an aggressive 140 BPM trap beat).
  2. Separating them enables modularity: creators can swap beats without changing character anchors, or test different character portraits against the same rhythm stem.

### [3] After the "Anchor & Inject Preview" is Populated, Can Fields be Editable?
- **Yes! Making them editable enables Power-User Prompt Tuning.**
- **Why Editable Fields are Superior:**
  - When the user selects a preset or types a raw concept, the Prompt Compiler generates default values for `[SUBJECT ANCHOR]`, `[AESTHETIC INJECTION]`, `[ENVIRONMENT]`, `[CAMERA/LIGHTING]`, `[MOTION]`, and `[AUDIO TRACK]`.
  - Allowing the user to click and edit any of these 6 fields gives them granular control (e.g. changing the chain from *Cuban link* to *Spinning Snake Medallion*, or the tempo from *120 BPM* to *135 BPM Drill*) before hitting Generate.
  - During multi-turn edits, editing the **`[ISOLATED DIFF]`** field ensures that only the exact intended visual or audio variable is altered across turns.

### [4] How are the Style Presets Used?
- **Style Presets** act as **Domain Aesthetic Multipliers**.
- Rather than requiring the user to type 100 words of camera specs and lighting jargon, choosing a preset (e.g., `90s_rap_video`) automatically injects:
  - **Wardrobe:** *Oversized shiny black puffer jacket, thick diamond Cuban link chain.*
  - **Camera & Lighting:** *90s fisheye lens, low-angle tracking shot, MTV rap video neon rim lights.*
  - **Kinematics:** *Bopping head rhythmically to a 120 BPM beat.*
  - **Audio Cadence:** *120 BPM boom-bap hip-hop beat, vinyl scratches, punchy kick/snare.*

---

## 🗺️ Step-by-Step User Journey & Lifecycle

1. **Input Composition:** The user inputs their prompt, optional YouTube URL, audio stem parameters, and selects a Style Preset.
2. **Interactive Compiler Preview:** The UI displays the 6-Part Anchor & Inject preview cards. The user can fine-tune or edit any field directly.
3. **Model Armor Pre-Gating:** Upon clicking Generate, the prompt is validated by Vertex AI Model Armor against safety templates.
4. **Joint Multimodal Generation:** `gemini-omni-flash-preview` generates a natively synchronized 720p 24fps MP4 video with joint audio in a single forward pass.
5. **Session-Scoped Storage:** Artifacts are uploaded directly to `gs://omnimash-media-${GOOGLE_CLOUD_PROJECT}/sessions/${session_id}/`.
6. **Version Tree & Conversational Branching:** The output appears in the Interactive Video Player. The user can perform follow-up delta edits (Lock & Isolate) or commit and branch new video threads.
