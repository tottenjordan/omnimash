# Digital Director's Studio: 3-Act Progressive Linear Workflow

## 📌 Motivation & Architecture
Open-ended text boxes often lead users to vague prompts (e.g., *"make Harry Potter look cool"*), failing to leverage the joint audio-video latent space of `gemini-omni-flash-preview`. 

The **Digital Director's Studio** replaces generic chat interfaces with a structured 3-Act progressive pipeline grounded in the **Anchor & Inject** framework:

---

## 🎭 Act 1: The Clash (The Setup)
* **Goal**: Select two conflicting cultural universes to mash up.
* **Split-Screen Card Grid**:
  * **Left Side (Subject Anchor)**: Recognizable pop-culture & historical archetypes (*Dark Wizard*, *Sci-Fi Bounty Hunter*, *Renaissance Painter*, or *Harry "Gucci" Potter & Draco "Jeezy" Malfoy*).
  * **Right Side (Aesthetic Injection)**: Iconic music video & cultural subcultures (*Atlanta Trap Disstrack*, *90s East Coast Rap*, *Hyperpop/Cyberpunk Drift*, *VHS Anime Lo-Fi*).
* **Reference Asset Extraction**: Dedicated button (`POST /api/extract-reference`) for attached YouTube URLs, extracting keyframe annotations and BPM synchronization before generation.
* **🧠 Gemini 3.5 Flash Parody Research**: 1-click research trigger (`POST /api/research`) that analyzes cultural analogies (e.g. Hogwarts hustle vs. Gucci vs. Jeezy Atlanta rap beef) and auto-populates the fine-tune controls for Act 2.

---

## 🎛️ Act 2: The Fine-Tune (The Directing)
* **Goal**: Dial in specific directorial details before rendering the video cut.
* **Directorial Controls**:
  * **The "Drip" Selector**: Interactive chip tags for iconic wardrobe & jewelry props (*Diamond Lightning Bolt Chain*, *Vintage Gucci Tracksuit*, *Slytherin Snowman Pendant*, *Microphone Wand*, *Shutter Shades*).
  * **Vibe Slider (Lighting & Camera)**: Smooth slider from **Gritty/Underground (0%)** $\leftrightarrow$ **Balanced (50%)** $\leftrightarrow$ **Neon/Glossy (100%)**, dynamically adjusting camera lighting signifiers (e.g. 16mm grain & laser smoke vs. anamorphic neon lens flares).
  * **Audio Beat Loops**: Selectors for 140 BPM Heavy 808 Trap, 120 BPM Boom-Bap, 110 BPM Synthwave, or 85 BPM Lo-Fi.
  * **Voiceover & Multi-Subject Dialogue**: Monologues or turn-by-turn dialogue syntax (`Snape: "Potter, explain." / Harry: "Burrr!"`).
  * **Live Prompt Preview**: 6-part compiled Anchor & Inject prompt card.

---

## 🎬 Act 3: The Director's Chair (The Iteration Loop)
* **Goal**: Review the rendered 10-second video and execute conversational delta edits via Gemini Enterprise Interactions API.
* **Studio Controls**:
  * **Central High-Resolution Player**: Play/pause, loop toggle, and MP4 download.
  * **Chronological Layer-Cake Edit History**: Side timeline displaying turn-by-turn cards with the exact Preservation Lock and Isolated Diff badges.
  * **"Direct the Scene" Chat Bar**: Quick iterative delta prompting (e.g., *"Make his chain bigger"*).
  * **⚡ 1-Click Trap-Warts Preset**: Instantly loads the complete *"Trap-Warts: Harry & The Brick Factory"* concept across all 3 acts.
