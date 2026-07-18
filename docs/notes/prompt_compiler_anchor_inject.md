# Prompt Compiler: The "Anchor & Inject" Framework

This note documents the solution to the **Character Decay and Latent Space Averaging** failure mode when blending distinct IPs (e.g. Harry Potter lore) and subcultural aesthetics (e.g. 90s hip-hop/trap).

---

## 🔬 Problem: Latent Space Averaging

When prompting `gemini-omni-flash-preview` with raw user shorthand like *"Severus Snape in a 90s rap video"*, the model's multimodal latent space averages the two distinct concepts. Instead of maintaining Snape's likeness and sharp hip-hop styling, the output defaults to a generic goth guy in a hoodie.

---

## 💡 Solution: The 5-Part "Anchor & Inject" Taxonomy

The ADK agent must never pass raw user text to the video model. Instead, the **Prompt Compiler** intercepts and expands the user's intent into a rigid 5-part structure:

$$\text{Final Prompt} = [\text{SUBJECT ANCHOR}] + [\text{AESTHETIC INJECTION}] + [\text{ENVIRONMENT}] + [\text{CAMERA/LIGHTING}] + [\text{MOTION}]$$

### 1. [SUBJECT ANCHOR]
Explicitly describe defining physical traits, facial features, hair, and expressions rather than relying on character names alone.
* *Example:* "Severus Snape, a gaunt man with a hooked nose, severe expression, and shoulder-length straight black hair."

### 2. [AESTHETIC INJECTION]
Define wardrobe, jewelry, and props with hyper-specific cultural signifiers.
* *Example:* "wearing an oversized shiny black puffer jacket, thick diamond Cuban link chain, and vintage Cartier buff glasses."

### 3. [ENVIRONMENT]
Ground the scene in a concrete physical location with atmospheric details.
* *Example:* "in a stone Hogwarts dungeon lit by vibrant green neon tubes and smoky haze."

### 4. [CAMERA/LIGHTING]
Use precise directorial and cinematographic terminology.
* *Example:* "captured on a 90s fisheye lens, low-angle tracking shot, high-contrast MTV rap video lighting with purple rim light."

### 5. [MOTION]
Describe physically plausible motion for a 10-second 720p clip.
* *Example:* "nodding rhythmically to a boom-bap beat while gesturing emphatically with a glowing wand."
