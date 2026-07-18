# Multimodal Reference Ingestion & Multi-Clip Video Stitching

This document outlines the 4-phase pipeline for ingesting external character lore, compiling 5-part Anchor & Inject meta-prompts, re-anchoring Omni Flash clips, and concatenating segments into a master 30–60s video.

---

## 🖼️ Reference Architecture Diagram

![Media Ingestion & Stitching](multimodal_ingestion_stitching.png)

---

## 🎬 4-Phase Processing Pipeline Flow

```mermaid
graph LR
    subgraph IngestionPhase["1. Ingestion Phase"]
        YT["Public YouTube URL"] -->|yt-dlp extract| Extractor["MediaExtractor"]
        Uploads["User Image / Audio Stems"] --> Extractor
        Extractor --> Keyframes["Keyframe Portraits"]
        Extractor --> AudioStem["Audio Rhythm Stems"]
    end

    subgraph PromptCompilation["2. Prompt Compilation Phase"]
        Keyframes --> Compiler["PromptCompiler Engine"]
        AudioStem --> Compiler
        Compiler --> FiveParts["5-Part Meta-Prompt<br/>[SUBJECT ANCHOR]<br/>[AESTHETIC INJECTION]<br/>[ENVIRONMENT]<br/>[CAMERA/LIGHTING]<br/>[MOTION]"]
    end

    subgraph GenerationReAnchoring["3. Generation & Re-Anchoring Phase"]
        FiveParts --> Omni["Gemini Omni Flash Client"]
        Omni --> Clip0["Clip 0: 10s MP4"]
        Clip0 -->|"Depth >= 3"| Checkpoint["Commit Checkpoint"]
        Checkpoint -->|Re-Anchor| Omni
    end

    subgraph StitchingPhase["4. Stitching Phase"]
        Clip0 --> Stitcher["VideoStitcher (FFmpeg)"]
        Stitcher --> Master["Master Stitched MP4 Video (30s-60s)"]
    end
```

---

## ⚙️ Pipeline Specifications

- **Reference Ingestion (`omnimash.ingestion.media_extractor`):**
  - Extract visual character keyframes for prompt lore anchoring.
  - Separate background instrumental and vocal stems to guide the audio tempo and style cadence.

- **Prompt Compiler (`omnimash.prompts.compiler`):**
  - Translates character lore into physical descriptors preventing latent space averaging.

- **FFmpeg Concatenation Engine (`omnimash.stitching.stitcher`):**
  - Collects active clips from the `ProjectSession` timeline.
  - Applies seamless video crossfades, audio beat-matching, and codec normalization (`libx264` + `aac` in 720p).
