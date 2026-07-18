# Multimodal Reference Ingestion & Multi-Clip Video Stitching

This document outlines the pipeline for ingesting external character lore (YouTube/audio/image uploads) and concatenating 10-second Omni Flash clips into a master 30–60s video.

---

## 🖼️ Reference Architecture Diagram

![Media Ingestion & Stitching](multimodal_ingestion_stitching.png)

---

## 🎬 Media Ingestion & Stitching Pipeline Flow

```mermaid
graph LR
    subgraph 1. Ingestion Phase
        YT[Public YouTube URL] -->|yt-dlp extract| Extractor[MediaExtractor]
        Uploads[User Image / Audio Stems] --> Extractor
        Extractor --> Keyframes[Keyframe Portait Grabs]
        Extractor --> AudioStem[Audio Rhythm Track]
        Extractor --> RefSummary[ExtractedReference Summary]
    end

    subgraph 2. Generation Phase
        RefSummary --> Orchestrator[OmniMashAgent]
        Orchestrator --> Omni[Gemini Omni Flash Client]
        Omni --> Clip0[Clip 0: 10s MP4]
        Omni --> Clip1[Clip 1: 10s MP4]
        Omni --> Clip2[Clip 2: 10s MP4]
    end

    subgraph 3. Stitching Phase
        Clip0 --> Stitcher[VideoStitcher (FFmpeg)]
        Clip1 --> Stitcher
        Clip2 --> Stitcher
        Stitcher --> Master[Master Stitched MP4 Video (30s-60s)]
    end
```

---

## ⚙️ Pipeline Specifications

- **Reference Ingestion (`omnimash.ingestion.media_extractor`):**
  - Extract visual character keyframes for prompt lore anchoring.
  - Separate background instrumental and vocal stems to guide the audio tempo and style cadence.

- **FFmpeg Concatenation Engine (`omnimash.stitching.stitcher`):**
  - Collects active clips from the `ProjectSession` timeline.
  - Applies seamless video crossfades, audio beat-matching, and codec normalization (`libx264` + `aac` in 720p).
