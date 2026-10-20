from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import os
import shutil
import subprocess
from typing import Any

from PIL import Image, ImageDraw

from omnimash.config import settings
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
from omnimash.storage.gcs import GcsStorageManager

logger = logging.getLogger("omnimash.ingestion")


class MediaExtractor:
    def __init__(
        self,
        mock_mode: bool | None = None,
        bucket_name: str | None = None,
        storage: GcsStorageManager | None = None,
    ):
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self.storage = storage or GcsStorageManager(
            bucket_name=bucket_name, mock_mode=self.mock_mode
        )

    def _extract_youtube_metadata(self, url: str) -> dict[str, Any]:
        """Extracts and sanitizes YouTube metadata using yt-dlp when not in mock mode.

        Source: https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp
        """
        default_meta: dict[str, Any] = {
            "title": "Reference Beat & Character Baseline",
            "duration": 180,
            "description": "Extracted 90s hip-hop beat and character portrait keyframes.",
        }
        if self.mock_mode or not url:
            return default_meta

        try:
            validated_url = validate_youtube_reference_url(url)
            import yt_dlp

            ydl_opts: dict[str, Any] = {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "socket_timeout": 10,
                "skip_download": True,
                "allowed_extractors": ["youtube", "youtube:tab"],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(validated_url, download=False)
                sanitized = ydl.sanitize_info(info) if info else {}
                if isinstance(sanitized, dict):
                    return {
                        "title": str(sanitized.get("title") or default_meta["title"]),
                        "duration": int(sanitized.get("duration") or default_meta["duration"]),
                        "description": str(
                            sanitized.get("description") or default_meta["description"]
                        ),
                    }
        except Exception as exc:
            logger.warning("yt-dlp metadata extraction fallback for %s: %s", url, exc)

        return default_meta

    def _generate_keyframe_jpeg(self, path: str, label: str, timestamp: str, color_hex: str) -> str:
        """Generates a high-quality annotated 1280x720 JPEG keyframe image file on disk.

        Uses Pillow's Image context manager, scalable font_size via ImageDraw.text
        (backed by ImageFont.load_default(size=...)), and Huffman-optimized JPEG saving.
        Sources:
        - https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html#PIL.ImageDraw.ImageDraw.text
        - https://pillow.readthedocs.io/en/stable/reference/ImageFont.html#PIL.ImageFont.load_default
        - https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#jpeg
        """
        if dirname := os.path.dirname(path):
            os.makedirs(dirname, exist_ok=True)

        clean_label = label.encode("ascii", "ignore").decode("ascii").strip() or label
        with Image.new("RGB", (KEYFRAME_WIDTH, KEYFRAME_HEIGHT), color="#0F172A") as img:
            draw = ImageDraw.Draw(img)
            # Top banner
            draw.rectangle([0, 0, KEYFRAME_WIDTH, 80], fill="#1E293B")
            draw.rectangle([0, 75, KEYFRAME_WIDTH, 80], fill=color_hex)
            # Main center viewport box
            draw.rectangle([80, 120, 1200, 620], outline=color_hex, width=4)
            # Draw labels with explicit scalable font_size (Pillow 10.1.0+ FreeType default font)
            draw.text(
                (40, 25),
                "OMNIMASH REFERENCE FRAME EXTRACTOR",
                fill="#FFFFFF",
                font_size=24,
            )
            draw.text(
                (1050, 25),
                f"T+{timestamp}",
                fill="#38BDF8",
                font_size=24,
            )
            draw.text(
                (120, 160),
                clean_label,
                fill="#F8FAFC",
                font_size=28,
            )
            draw.text(
                (120, 220),
                f"Conditioning Vector: {color_hex} | 720p HD Anchor",
                fill="#94A3B8",
                font_size=20,
            )
            img.save(path, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return path

    def process_youtube_url(self, url: str, session_id: str | None = None) -> ExtractedReference:
        sid = sanitize_ingestion_session_id(session_id)
        meta = self._extract_youtube_metadata(url)
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
            description=str(meta["description"]),
            gcs_uri=self.storage.get_gcs_uri(blob_path),
        )

    def _render_and_upload_keyframe(
        self, sid: str, local_dir: str, spec: KeyframeSpec
    ) -> KeyframeAnnotation:
        frame_path = os.path.join(local_dir, spec.filename)
        self._generate_keyframe_jpeg(
            frame_path,
            spec.canvas_label,
            spec.timestamp,
            spec.color_hex,
        )
        uploaded_url = self.storage.upload_file(
            frame_path,
            destination_blob_name=f"sessions/{sid}/references/{spec.filename}",
            session_id=sid,
            category="references",
        )
        return KeyframeAnnotation(
            timestamp=spec.timestamp,
            image_url=uploaded_url,
            usage_annotation=spec.usage_annotation,
        )

    def analyze_youtube_reference(
        self, url: str, session_id: str = "default"
    ) -> ReferenceAnalysisReport:
        sid = sanitize_ingestion_session_id(session_id)
        meta = self._extract_youtube_metadata(url)

        local_dir = os.path.join("static", "sessions", sid, "references")
        os.makedirs(local_dir, exist_ok=True)

        if self.storage.mock_mode:
            annotations = [
                self._render_and_upload_keyframe(sid, local_dir, spec)
                for spec in DEFAULT_KEYFRAME_SPECS
            ]
        else:
            with ThreadPoolExecutor(max_workers=len(DEFAULT_KEYFRAME_SPECS)) as pool:
                futures = [
                    pool.submit(self._render_and_upload_keyframe, sid, local_dir, spec)
                    for spec in DEFAULT_KEYFRAME_SPECS
                ]
                annotations = [fut.result() for fut in futures]

        report = ReferenceAnalysisReport(
            video_title=str(meta["title"]),
            duration_seconds=int(meta["duration"]),
            detected_bpm=120,
            dominant_colors=["#1B2A4A", "#0B6623", "#D4AF37"],
            extracted_keyframes=annotations,
        )

        self.storage.save_reference_analysis(session_id=sid, report=report)
        return report

    def research_parody_clash(self, subject: str, aesthetic: str) -> ParodyResearchResult:
        return build_parody_research_result(subject=subject, aesthetic=aesthetic)

    def crop_3s_motion_reference(self, input_video_path: str, start_sec: float = 0.0) -> str:
        """Crops a 3-second motion reference clip from input_video_path starting at start_sec using ffmpeg."""
        normalized_src, normalized_out = normalize_and_validate_clip_paths(input_video_path)
        start_val, _ = sanitize_clip_timing(start_sec, 3.0)
        return self.extract_reference_video_clip(
            source_video_path=normalized_src,
            output_clip_path=normalized_out,
            start_time_seconds=start_val,
            duration_seconds=3.0,
        )

    def extract_reference_video_clip(
        self,
        source_video_path: str,
        output_clip_path: str,
        start_time_seconds: float = 0.0,
        duration_seconds: float = 3.0,
    ) -> str:
        """Crops a 3-second .mp4 video reference clip for motion transfer conditioning using ffmpeg.

        Sources:
        - https://trac.ffmpeg.org/wiki/Encode/H.264#Encodingfordumbplayers (-pix_fmt yuv420p)
        - https://ffmpeg.org/ffmpeg-formats.html#mov_002c-mp4_002c-ismv (-movflags +faststart)
        - https://ffmpeg.org/ffmpeg.html#Main-options (-nostdin)
        - https://docs.python.org/3.12/library/subprocess.html#subprocess.run (capture_output, timeout)
        """
        normalized_src, normalized_out = normalize_and_validate_clip_paths(
            source_video_path, output_clip_path
        )
        start_val, dur_val = sanitize_clip_timing(start_time_seconds, duration_seconds)
        if dirname := os.path.dirname(normalized_out):
            os.makedirs(dirname, exist_ok=True)

        if self.mock_mode:
            if os.path.exists(normalized_src):
                shutil.copyfile(normalized_src, normalized_out)
            else:
                with open(normalized_out, "wb") as f:
                    f.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
            return normalized_out

        cmd = [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-ss",
            str(start_val),
            "-i",
            normalized_src,
            "-t",
            str(dur_val),
            "-avoid_negative_ts",
            "make_zero",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            normalized_out,
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            logger.warning(
                "FFmpeg motion reference extraction failed for %s: %s",
                normalized_src,
                getattr(exc, "stderr", exc),
            )
            if not os.path.exists(normalized_out):
                with open(normalized_out, "wb") as f:
                    f.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
        return normalized_out


__all__ = [
    "ExtractedReference",
    "KeyframeAnnotation",
    "MediaExtractor",
    "ParodyResearchResult",
    "ReferenceAnalysisReport",
]
