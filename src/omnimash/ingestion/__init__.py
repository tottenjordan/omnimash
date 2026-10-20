"""Ingestion module for OmniMash."""

from omnimash.ingestion.media_extractor import MediaExtractor
from omnimash.ingestion.models import (
    DEFAULT_KEYFRAME_SPECS,
    JPEG_QUALITY,
    KEYFRAME_HEIGHT,
    KEYFRAME_WIDTH,
    ExtractedReference,
    KeyframeAnnotation,
    KeyframeSpec,
    ParodyResearchResult,
    ReferenceAnalysisReport,
    build_parody_research_result,
)
from omnimash.ingestion.validators import (
    normalize_and_validate_clip_paths,
    sanitize_clip_timing,
    sanitize_ingestion_session_id,
    validate_youtube_reference_url,
)

__all__ = [
    "DEFAULT_KEYFRAME_SPECS",
    "ExtractedReference",
    "JPEG_QUALITY",
    "KEYFRAME_HEIGHT",
    "KEYFRAME_WIDTH",
    "KeyframeAnnotation",
    "KeyframeSpec",
    "MediaExtractor",
    "ParodyResearchResult",
    "ReferenceAnalysisReport",
    "build_parody_research_result",
    "normalize_and_validate_clip_paths",
    "sanitize_clip_timing",
    "sanitize_ingestion_session_id",
    "validate_youtube_reference_url",
]
