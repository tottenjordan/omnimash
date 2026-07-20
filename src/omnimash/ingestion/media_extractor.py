from __future__ import annotations

import os
from dataclasses import dataclass, field
from omnimash.storage.gcs import GcsStorageManager

from PIL import Image, ImageDraw


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
class ParodyResearchResult:
    synopsis: str
    suggested_props: list[str]
    suggested_vibe: str
    vibe_intensity: int
    suggested_audio: str
    suggested_dialogue: str


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

    def _generate_keyframe_jpeg(
        self, path: str, label: str, timestamp: str, color_hex: str
    ) -> str:
        """Generates a high-quality annotated 1280x720 JPEG keyframe image file on disk."""
        if dirname := os.path.dirname(path):
            os.makedirs(dirname, exist_ok=True)

        if Image:
            img = Image.new("RGB", (1280, 720), color="#0F172A")
            draw = ImageDraw.Draw(img)
            # Top banner
            draw.rectangle([0, 0, 1280, 80], fill="#1E293B")
            draw.rectangle([0, 75, 1280, 80], fill=color_hex)
            # Main center viewport box
            draw.rectangle([80, 120, 1200, 620], outline=color_hex, width=4)
            # Draw labels
            draw.text((40, 25), "🎬 OMNIMASH REFERENCE FRAME EXTRACTOR", fill="#FFFFFF")
            draw.text((1050, 25), f"⏱️ {timestamp}", fill="#38BDF8")
            draw.text((120, 160), label, fill="#F8FAFC")
            draw.text(
                (120, 220),
                f"Conditioning Vector: {color_hex} • 720p HD Anchor",
                fill="#94A3B8",
            )
            img.save(path, "JPEG", quality=90)
        else:
            # Fallback binary JPEG header
            with open(path, "wb") as f:
                f.write(
                    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00"
                    + b"\x00" * 2000
                )
        return path

    def process_youtube_url(
        self, url: str, session_id: str | None = None
    ) -> ExtractedReference:
        sid = session_id or "default"
        blob_path = self.storage.build_session_blob_path(
            session_id=sid,
            category="references",
            filename="reference_bundle.tar",
        )
        return ExtractedReference(
            is_valid=True,
            source_url=url,
            keyframes=[
                f"/static/sessions/{sid}/references/frame_1.jpg",
                f"/static/sessions/{sid}/references/frame_2.jpg",
            ],
            audio_track_path=f"/static/sessions/{sid}/references/audio_stem.wav",
            description="Extracted 90s hip-hop beat and character portrait keyframes.",
            gcs_uri=self.storage.get_gcs_uri(blob_path),
        )

    def analyze_youtube_reference(
        self, url: str, session_id: str = "default"
    ) -> ReferenceAnalysisReport:
        sid = session_id or "default"

        # Generate actual physical keyframe JPEG files on disk
        local_dir = f"static/sessions/{sid}/references"
        os.makedirs(local_dir, exist_ok=True)

        f1_path = os.path.join(local_dir, "frame_1.jpg")
        f2_path = os.path.join(local_dir, "frame_2.jpg")
        f3_path = os.path.join(local_dir, "frame_3.jpg")

        self._generate_keyframe_jpeg(
            f1_path,
            "🎯 [SUBJECT ANCHOR]: Facial Likeness & Hair Conditioning",
            "00:02",
            "#DE5FE9",
        )
        self._generate_keyframe_jpeg(
            f2_path,
            "🧥 [AESTHETIC BASELINE]: High-Fashion Trap Wardrobe & Lighting",
            "00:15",
            "#38BDF8",
        )
        self._generate_keyframe_jpeg(
            f3_path,
            "🎵 [ACOUSTIC STEM]: Tempo Reference & Spectral Analysis",
            "00:30",
            "#34A853",
        )

        # Also copy to /tmp for backward compatibility
        import shutil

        for src, dst in [
            (f1_path, "/tmp/mock_frame_1.jpg"),
            (f2_path, "/tmp/mock_frame_2.jpg"),
            (f3_path, "/tmp/mock_frame_3.jpg"),
        ]:
            try:
                shutil.copyfile(src, dst)
            except Exception:
                pass

        # Upload all 3 JPEG keyframe files to GCS
        url_1 = self.storage.upload_file(
            f1_path,
            destination_blob_name=f"sessions/{sid}/references/frame_1.jpg",
            session_id=sid,
            category="references",
        )
        url_2 = self.storage.upload_file(
            f2_path,
            destination_blob_name=f"sessions/{sid}/references/frame_2.jpg",
            session_id=sid,
            category="references",
        )
        url_3 = self.storage.upload_file(
            f3_path,
            destination_blob_name=f"sessions/{sid}/references/frame_3.jpg",
            session_id=sid,
            category="references",
        )

        report = ReferenceAnalysisReport(
            video_title="Reference Beat & Character Baseline",
            duration_seconds=180,
            detected_bpm=120,
            dominant_colors=["#1B2A4A", "#0B6623", "#D4AF37"],
            extracted_keyframes=[
                KeyframeAnnotation(
                    timestamp="00:02",
                    image_url=url_1,
                    usage_annotation="🎯 [SUBJECT ANCHOR]: Conditioning facial likeness, expression, and hair baseline.",
                ),
                KeyframeAnnotation(
                    timestamp="00:15",
                    image_url=url_2,
                    usage_annotation="🧥 [AESTHETIC BASELINE]: Reference for lighting contrast and initial character wardrobe.",
                ),
                KeyframeAnnotation(
                    timestamp="00:30",
                    image_url=url_3,
                    usage_annotation="🎵 [ACOUSTIC STEM]: Tempo reference extracted for 120 BPM audio track synchronization.",
                ),
            ],
        )

        self.storage.save_reference_analysis(session_id=sid, report=report)
        return report

    def research_parody_clash(
        self, subject: str, aesthetic: str
    ) -> ParodyResearchResult:
        return ParodyResearchResult(
            synopsis="Dripwarts: Harry & The Brick Factory - A high-fashion parody mashup blending Hogwarts wizard rivalry with 2010s Atlanta trap music beef (Gucci vs. Jeezy).",
            suggested_props=[
                "Diamond Lightning Bolt Chain",
                "Vintage Gucci Tracksuit",
                "Slytherin Snowman Pendant",
                "Microphone Wand",
                "Shutter Shades",
            ],
            suggested_vibe="Dark moody 808 bass lighting, laser smoke, and high-gloss neon reflections",
            vibe_intensity=75,
            suggested_audio="140 BPM Heavy 808 Trap",
            suggested_dialogue='Harry: "I been cooking potions since first year. Burrr!" / Draco: "This is Trap or Die, Potter!"',
        )
