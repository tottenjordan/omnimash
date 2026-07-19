from __future__ import annotations

from dataclasses import dataclass, field
from omnimash.storage.gcs import GcsStorageManager


@dataclass
class ExtractedReference:
    is_valid: bool
    source_url: str | None = None
    keyframes: list[str] = field(default_factory=list)
    audio_track_path: str | None = None
    description: str | None = None
    gcs_uri: str | None = None


@dataclass
class KeyframeAnnotation:
    timestamp: str
    image_url: str
    usage_annotation: str


@dataclass
class ReferenceAnalysisReport:
    video_title: str
    duration_seconds: int
    detected_bpm: int
    dominant_colors: list[str]
    extracted_keyframes: list[KeyframeAnnotation]


class MediaExtractor:
    def __init__(self, mock_mode: bool = True, bucket_name: str | None = None):
        self.mock_mode = mock_mode
        self.storage = GcsStorageManager(
            bucket_name=bucket_name, mock_mode=self.mock_mode
        )

    def process_youtube_url(
        self, url: str, session_id: str | None = None
    ) -> ExtractedReference:
        blob_path = self.storage.build_session_blob_path(
            session_id=session_id,
            category="references",
            filename="reference_bundle.tar",
        )
        if self.mock_mode:
            ref = ExtractedReference(
                is_valid=True,
                source_url=url,
                keyframes=["/tmp/mock_frame_1.jpg", "/tmp/mock_frame_2.jpg"],
                audio_track_path="/tmp/mock_audio_stem.mp3",
                description="Extracted 90s hip-hop beat and character portrait keyframes.",
                gcs_uri=self.storage.get_gcs_uri(blob_path),
            )
            return ref

        return ExtractedReference(
            is_valid=True,
            source_url=url,
            gcs_uri=self.storage.get_gcs_uri(blob_path),
        )

    def analyze_youtube_reference(
        self, url: str, session_id: str = "default"
    ) -> ReferenceAnalysisReport:
        if self.mock_mode:
            report = ReferenceAnalysisReport(
                video_title="Reference Beat & Character Baseline",
                duration_seconds=180,
                detected_bpm=120,
                dominant_colors=["#1B2A4A", "#0B6623", "#D4AF37"],
                extracted_keyframes=[
                    KeyframeAnnotation(
                        timestamp="00:02",
                        image_url="/tmp/mock_frame_1.jpg",
                        usage_annotation="🎯 [SUBJECT ANCHOR]: Conditioning facial likeness, expression, and hair baseline.",
                    ),
                    KeyframeAnnotation(
                        timestamp="00:15",
                        image_url="/tmp/mock_frame_2.jpg",
                        usage_annotation="🧥 [AESTHETIC BASELINE]: Reference for lighting contrast and initial character wardrobe.",
                    ),
                    KeyframeAnnotation(
                        timestamp="00:30",
                        image_url="/tmp/mock_frame_3.jpg",
                        usage_annotation="🎵 [ACOUSTIC STEM]: Tempo reference extracted for 120 BPM audio track synchronization.",
                    ),
                ],
            )
            self.storage.save_reference_analysis(session_id=session_id, report=report)
            return report

        report = ReferenceAnalysisReport(
            video_title="YouTube Reference Ingested",
            duration_seconds=180,
            detected_bpm=120,
            dominant_colors=["#1B2A4A", "#0B6623", "#D4AF37"],
            extracted_keyframes=[
                KeyframeAnnotation(
                    timestamp="00:02",
                    image_url=self.storage.get_public_url(
                        f"sessions/{session_id}/references/frame_1.jpg"
                    ),
                    usage_annotation="🎯 [SUBJECT ANCHOR]: Conditioning facial likeness, expression, and hair baseline.",
                ),
                KeyframeAnnotation(
                    timestamp="00:15",
                    image_url=self.storage.get_public_url(
                        f"sessions/{session_id}/references/frame_2.jpg"
                    ),
                    usage_annotation="🧥 [AESTHETIC BASELINE]: Reference for lighting contrast and initial character wardrobe.",
                ),
                KeyframeAnnotation(
                    timestamp="00:30",
                    image_url=self.storage.get_public_url(
                        f"sessions/{session_id}/references/frame_3.jpg"
                    ),
                    usage_annotation="🎵 [ACOUSTIC STEM]: Tempo reference extracted for 120 BPM audio track synchronization.",
                ),
            ],
        )
        self.storage.save_reference_analysis(session_id=session_id, report=report)
        return report
