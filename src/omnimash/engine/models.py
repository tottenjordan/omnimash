"""Data models for OmniMash video generation engines."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GenerationResult:
    interaction_thread_id: str
    video_url: str
    gcs_uri: str | None = None
    duration_seconds: int = 10
    synth_id_watermark: str = "SYNTHID_C2PA_VERIFIED"
    error_message: str | None = None
    generation_mode: str = "LIVE_OMNI_FLASH"


__all__ = ["GenerationResult"]
