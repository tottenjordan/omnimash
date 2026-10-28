"""Omnimash stitching module for concatenating video clips, multi-format conforming, and audio overlays."""

from omnimash.stitching.audio_overlay import apply_dialogue_audio_ducking
from omnimash.stitching.commercial_conformer import (
    CANONICAL_SUBSHOT_IDS,
    MAX_BUMPER_SUBSHOT_DURATION_SEC,
    MIN_SUBSHOT_DURATION_SEC,
    PREFERRED_BUMPER_6S_SUBSHOTS,
    PREFERRED_CUTDOWN_15S_SUBSHOTS,
    CommercialConformer,
    ConformedDeliverables,
    SubShotTrimSpec,
    build_default_subshot_specs,
    normalize_subshot_specs,
)
from omnimash.stitching.resolver import resolve_media_source_to_local_path
from omnimash.stitching.stitcher import AspectRatio, VideoStitcher

__all__ = [
    "CANONICAL_SUBSHOT_IDS",
    "MAX_BUMPER_SUBSHOT_DURATION_SEC",
    "MIN_SUBSHOT_DURATION_SEC",
    "PREFERRED_BUMPER_6S_SUBSHOTS",
    "PREFERRED_CUTDOWN_15S_SUBSHOTS",
    "AspectRatio",
    "CommercialConformer",
    "ConformedDeliverables",
    "SubShotTrimSpec",
    "VideoStitcher",
    "apply_dialogue_audio_ducking",
    "build_default_subshot_specs",
    "normalize_subshot_specs",
    "resolve_media_source_to_local_path",
]
