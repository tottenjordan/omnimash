"""Omnimash stitching module for concatenating video clips and audio overlays."""

from omnimash.stitching.audio_overlay import apply_dialogue_audio_ducking
from omnimash.stitching.resolver import resolve_media_source_to_local_path
from omnimash.stitching.stitcher import AspectRatio, VideoStitcher

__all__ = [
    "AspectRatio",
    "VideoStitcher",
    "apply_dialogue_audio_ducking",
    "resolve_media_source_to_local_path",
]
