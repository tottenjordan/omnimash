# OmniMash Reference Video Analysis & Preset Contribution Inspector

> **Session Note Date:** 2026-07-19  
> **Status:** Implemented & Verified in PR #11  
> **Target Model:** `gemini-omni-flash-preview`  
> **Architectural Focus:** Multimodal Transparency, Acoustic Analysis, Color Palette Extraction, and Preset Vector Inspection.

---

## 🏗️ Architecture Overview

The OmniMash platform provides complete creative transparency by decoupling multimodal inputs into distinct, inspectable layers before synthesizing them into the monolithic prompt payload for `gemini-omni-flash-preview`.

![OmniMash Reference Analysis & Preset Contribution Inspector](file:///usr/local/google/home/jordantotten/omnimash/docs/diagrams/omnimash_reference_analysis_inspector.png)

---

## 🎨 1. Style Preset Contribution Inspector

When a creator selects or switches a Style Preset (e.g. *90s Rap Video*, *Trap Disstrack*, *Cyberpunk Drift*, *VHS Anime*), the dashboard immediately surfaces what aesthetic signifiers are being contributed across 4 distinct vectors:

| Preset Aesthetic Vector | Purpose & Role | Example Signifier (90s Rap Video) |
| :--- | :--- | :--- |
| 👔 **Wardrobe Vector** | Injects character costume, accessories, and stylistic styling. | `wearing an oversized shiny black puffer jacket, thick diamond Cuban link chain, and vintage Cartier glasses` |
| 🎥 **Camera / Lighting Vector** | Defines lens optics, single-shot constraints, and color grading. | `In a single continuous shot, no scene cuts. Shot on a 90s fisheye lens, low-angle tracking shot, MTV rap video lighting` |
| 🏃 **Motion Vector** | Controls subject kinematics, tempo synchronization, and gesture cadence. | `bopping head rhythmically to a 120 BPM beat while gesturing emphatically for a 10-second clip` |
| 🎵 **Sound Design Vector** | Formats pure acoustic directives for native Omni Flash audio generation. | `120 BPM boom-bap hip-hop beat, vinyl scratch intro, punchy kick drum, crisp snare` |

---

## 🖼️ 2. Extracted YouTube Keyframe Gallery & Usage Annotations

When a creator inputs a YouTube reference URL, `MediaExtractor` parses the video and extracts keyframes stored at `sessions/{session_id}/references/`. Each keyframe is displayed in the UI gallery with an explicit usage annotation:

1. **Frame 1 (`00:02` - Close-up):**  
   🏷️ **`🎯 [SUBJECT ANCHOR]`**: Conditions the primary facial geometry, hooked nose, cynical expression, and shoulder-length straight greasy black hair baseline.
2. **Frame 2 (`00:15` - Medium Shot):**  
   🏷️ **`🧥 [AESTHETIC BASELINE]`**: Establishes initial lighting contrast, rim lighting, and character costume baseline.
3. **Frame 3 (`00:30` - Action / Beat Onset):**  
   🏷️ **`🎵 [ACOUSTIC STEM]`**: Extracts acoustic rhythm and beat tempo for 120 BPM audio track synchronization.

---

## 📊 3. Ingested Reference Video Analysis & Color Palette

In addition to keyframe images, `MediaExtractor` runs acoustic and visual analysis, persisting the structured report to GCS at `sessions/{session_id}/references/reference_analysis.json`:

```json
{
  "video_title": "Reference Beat & Character Baseline",
  "duration_seconds": 180,
  "detected_bpm": 120,
  "dominant_colors": [
    "#1B2A4A",
    "#0B6623",
    "#D4AF37"
  ],
  "extracted_keyframes": [
    {
      "timestamp": "00:02",
      "image_url": "/tmp/mock_frame_1.jpg",
      "usage_annotation": "🎯 [SUBJECT ANCHOR]: Conditioning facial likeness, expression, and hair baseline."
    }
  ]
}
```

* 🎵 **Detected BPM Badge:** Surfaced in the UI header to show the analyzed acoustic tempo (e.g. `120 BPM`).
* 🎨 **Dominant Color Swatches:** Hex color chips (e.g. `#1B2A4A`, `#0B6623`, `#D4AF37`) extracted from the reference video, allowing creators to inspect the color palette guiding the environmental lighting.

---

## 📦 4. Raw Compiled Model Payload Container

To eliminate any black-box AI behavior, the dashboard includes an interactive, collapsible **Raw Compiled Model Payload** code container with a **📋 Copy Raw Prompt** button.

Creators can inspect the live, monolithic string assembled by `PromptTaxonomyEngine` in real time:

```text
Generate a 720p 10-second cinematic parody video with native audio using the Anchor & Inject framework: [SUBJECT ANCHOR]: Severus Snape, a gaunt man with a hooked nose, severe cynical expression, and shoulder-length straight greasy black hair | [AESTHETIC INJECTION]: wearing an oversized shiny black puffer jacket, thick diamond Cuban link chain, and vintage Cartier glasses | [ENVIRONMENT]: in a stone Hogwarts dungeon lit by atmospheric fog and ambient glow | [CAMERA/LIGHTING]: In a single continuous shot, no scene cuts. Shot on a 90s fisheye lens, low-angle tracking shot, high-contrast MTV rap video lighting with green and purple neon rim lights | [MOTION]: bopping head rhythmically to a 120 BPM beat while gesturing emphatically for a 10-second clip | [AUDIO TRACK]: 120 BPM boom-bap hip-hop beat, vinyl scratch intro, punchy kick drum, crisp snare, and rhythmic rap cadence | Sound design: 120 BPM boom-bap hip-hop beat, vinyl scratch intro, punchy kick drum, crisp snare, and rhythmic rap cadence. No text, no subtitles, no captions on screen.
```
