import concurrent.futures
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from typing import Any, Literal

from omnimash.config import settings
from omnimash.stitching.audio_overlay import apply_dialogue_audio_ducking
from omnimash.stitching.resolver import resolve_media_source_to_local_path
from omnimash.storage.gcs import GcsStorageManager

AspectRatio = Literal["16:9", "9:16", "1:1", "21:9"]

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont

    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def _get_font(font_name: str, size: int) -> Any:
    """Helper to load a TrueType font with fallbacks to default fonts."""
    if not HAS_PIL:
        return None
    try:
        return ImageFont.truetype(font_name, size)
    except Exception:
        try:
            return ImageFont.load_default(size=size)
        except Exception:
            return ImageFont.load_default()


class VideoStitcher:
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

    def concatenate_clips(
        self,
        clip_paths: list[str],
        output_dir: str = "/tmp",
        session_id: str | None = None,
        master_audio_path: str | None = None,
    ) -> str:
        os.makedirs(output_dir, exist_ok=True)
        master_filename = f"master_{uuid.uuid4().hex[:8]}_stitched.mp4"
        out_path = os.path.join(output_dir, master_filename)

        if not self.mock_mode and not clip_paths:
            raise ValueError("concatenate_clips requires at least one clip path.")

        if self.mock_mode:
            if clip_paths and os.path.exists(clip_paths[0]):
                shutil.copyfile(clip_paths[0], out_path)
            else:
                with open(out_path, "w") as f:
                    f.write("mock mp4 master video content")
        else:
            with tempfile.TemporaryDirectory() as scoped_temp_dir:
                max_workers = min(len(clip_paths), 4) if clip_paths else 1
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [
                        executor.submit(
                            resolve_media_source_to_local_path,
                            clip,
                            temp_dir=scoped_temp_dir,
                            storage=self.storage,
                            mock_mode=self.mock_mode,
                        )
                        for clip in clip_paths
                    ]
                    resolved_clips: list[str] = [
                        res for f in futures if (res := f.result()) is not None
                    ]

                resolved_audio = (
                    resolve_media_source_to_local_path(
                        master_audio_path,
                        temp_dir=scoped_temp_dir,
                        storage=self.storage,
                        mock_mode=self.mock_mode,
                    )
                    if master_audio_path
                    else None
                )

                if resolved_clips:
                    concat_list_path = os.path.join(
                        scoped_temp_dir, f"concat_list_{uuid.uuid4().hex[:8]}.txt"
                    )
                    with open(concat_list_path, "w") as f:
                        for clip_file in resolved_clips:
                            escaped_clip = clip_file.replace("'", "'\\''")
                            f.write(f"file '{escaped_clip}'\n")

                    if resolved_audio and os.path.exists(resolved_audio):
                        try:
                            if os.path.getsize(resolved_audio) < 64:
                                with open(resolved_audio, "rb") as af:
                                    head = af.read(64)
                                if head.startswith(b"fallback ducked audio content"):
                                    logger.warning(
                                        "Ignoring fallback ducked audio placeholder in live stitch: %s",
                                        resolved_audio,
                                    )
                                    resolved_audio = None
                        except OSError:
                            pass

                    if resolved_audio and os.path.exists(resolved_audio):
                        cmd_copy = [
                            "ffmpeg",
                            "-y",
                            "-f",
                            "concat",
                            "-safe",
                            "0",
                            "-i",
                            concat_list_path,
                            "-i",
                            resolved_audio,
                            "-c:v",
                            "copy",
                            "-c:a",
                            "aac",
                            "-map",
                            "0:v:0",
                            "-map",
                            "1:a:0",
                            "-shortest",
                            out_path,
                        ]
                    else:
                        cmd_copy = [
                            "ffmpeg",
                            "-y",
                            "-f",
                            "concat",
                            "-safe",
                            "0",
                            "-i",
                            concat_list_path,
                            "-c",
                            "copy",
                            out_path,
                        ]

                    timeout_secs = float(getattr(settings, "ffmpeg_timeout_seconds", 120.0))
                    try:
                        res = subprocess.run(
                            cmd_copy,
                            capture_output=True,
                            text=True,
                            timeout=timeout_secs,
                        )
                        if res.returncode != 0:
                            if resolved_audio and os.path.exists(resolved_audio):
                                cmd_reencode = [
                                    "ffmpeg",
                                    "-y",
                                    "-f",
                                    "concat",
                                    "-safe",
                                    "0",
                                    "-i",
                                    concat_list_path,
                                    "-i",
                                    resolved_audio,
                                    "-c:v",
                                    "libx264",
                                    "-c:a",
                                    "aac",
                                    "-map",
                                    "0:v:0",
                                    "-map",
                                    "1:a:0",
                                    "-pix_fmt",
                                    "yuv420p",
                                    "-r",
                                    "24",
                                    "-shortest",
                                    out_path,
                                ]
                            else:
                                cmd_reencode = [
                                    "ffmpeg",
                                    "-y",
                                    "-f",
                                    "concat",
                                    "-safe",
                                    "0",
                                    "-i",
                                    concat_list_path,
                                    "-c:v",
                                    "libx264",
                                    "-c:a",
                                    "aac",
                                    "-pix_fmt",
                                    "yuv420p",
                                    "-r",
                                    "24",
                                    out_path,
                                ]
                            res_reencode = subprocess.run(
                                cmd_reencode,
                                capture_output=True,
                                text=True,
                                timeout=timeout_secs,
                            )
                            if res_reencode.returncode != 0:
                                logger.error(
                                    "FFmpeg re-encode fallback failed (exit %s): %s",
                                    res_reencode.returncode,
                                    res_reencode.stderr,
                                )
                                raise RuntimeError(f"FFmpeg re-encode failed: {res_reencode.stderr}")
                    except subprocess.TimeoutExpired as exc:
                        logger.error(
                            "FFmpeg concatenate execution timed out after %s seconds: %s",
                            timeout_secs,
                            exc,
                        )
                        raise RuntimeError(
                            f"FFmpeg execution timed out after {timeout_secs} seconds"
                        ) from exc

        gcs_blob = self.storage.build_session_blob_path(
            session_id=session_id,
            category="final_masters",
            filename=master_filename,
        )
        self.storage.upload_file(out_path, destination_blob_name=gcs_blob)
        return out_path

    def generate_title_card_clip(
        self,
        title_text: str,
        subtitle_text: str = "",
        duration_seconds: float = 3.0,
        style: str = "gothic_gold",
        output_dir: str = "/tmp",
        aspect_ratio: AspectRatio | str = "16:9",
    ) -> str:
        os.makedirs(output_dir, exist_ok=True)
        clip_filename = f"title_card_{uuid.uuid4().hex[:8]}.mp4"
        out_path = os.path.join(output_dir, clip_filename)

        if self.mock_mode:
            with open(out_path, "w") as f:
                f.write("mock title card mp4 clip content")
            return out_path

        if not HAS_PIL:
            logger.warning("Pillow library not available, returning fallback title card clip.")
            with open(out_path, "w") as f:
                f.write("fallback title card video content")
            return out_path

        img_path = os.path.join(output_dir, f"title_card_{uuid.uuid4().hex[:8]}.png")

        aspect_map = {
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "1:1": (1080, 1080),
            "21:9": (1680, 720),
        }
        width, height = aspect_map.get(aspect_ratio, (1280, 720))

        try:
            if style == "neon_cyber":
                bg_color = (10, 10, 20)
                title_color = (0, 255, 240)
                subtitle_color = (255, 0, 200)
            elif style == "gothic_gold":
                bg_color = (15, 10, 25)
                title_color = (255, 215, 0)
                subtitle_color = (200, 180, 220)
            else:
                bg_color = (15, 15, 20)
                title_color = (255, 255, 255)
                subtitle_color = (180, 180, 180)

            img = Image.new("RGB", (width, height), color=bg_color)
            draw = ImageDraw.Draw(img)

            title_font = _get_font("DejaVuSans-Bold.ttf", 60)
            subtitle_font = _get_font("DejaVuSans.ttf", 36)

            t_bbox = draw.textbbox((0, 0), title_text, font=title_font)
            t_w = t_bbox[2] - t_bbox[0]
            t_h = t_bbox[3] - t_bbox[1]

            if subtitle_text:
                s_bbox = draw.textbbox((0, 0), subtitle_text, font=subtitle_font)
                s_w = s_bbox[2] - s_bbox[0]
                s_h = s_bbox[3] - s_bbox[1]
                spacing = 20
                total_h = t_h + spacing + s_h
                t_y = (height - total_h) / 2
                s_y = t_y + t_h + spacing

                draw.text(
                    ((width - t_w) / 2, t_y),
                    title_text,
                    fill=title_color,
                    font=title_font,
                )
                draw.text(
                    ((width - s_w) / 2, s_y),
                    subtitle_text,
                    fill=subtitle_color,
                    font=subtitle_font,
                )
            else:
                t_y = (height - t_h) / 2
                draw.text(
                    ((width - t_w) / 2, t_y),
                    title_text,
                    fill=title_color,
                    font=title_font,
                )

            img.save(img_path)

            cmd = [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                img_path,
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-t",
                str(duration_seconds),
                "-pix_fmt",
                "yuv420p",
                "-vf",
                f"scale={width}:{height}",
                "-r",
                "24",
                "-shortest",
                out_path,
            ]
            timeout_secs = float(getattr(settings, "ffmpeg_timeout_seconds", 120.0))
            try:
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_secs,
                )
                if res.returncode != 0:
                    logger.warning("FFmpeg title card rendering failed: %s", res.stderr)
                    with open(out_path, "w") as f:
                        f.write("fallback title card video content")
            except subprocess.TimeoutExpired as exc:
                logger.warning(
                    "FFmpeg title card rendering timed out after %s seconds: %s",
                    timeout_secs,
                    exc,
                )
                with open(out_path, "w") as f:
                    f.write("fallback title card video content")
        except Exception as exc:
            logger.warning("Failed to generate title card clip: %s", exc)
            with open(out_path, "w") as f:
                f.write("fallback title card video content")
        finally:
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                except OSError:
                    pass

        return out_path

    @staticmethod
    def _is_valid_audio_reference(ref: str) -> bool:
        if not ref or not isinstance(ref, str):
            return False
        s = ref.strip()
        if not s:
            return False
        if s.startswith(("/", "./", "../", "gs://", "http://", "https://")):
            return True
        if s.lower().endswith((".mp3", ".wav", ".aac", ".m4a", ".ogg", ".flac")):
            return True
        return os.path.exists(s)

    def stitch_storyboard_master(
        self,
        shot_clips: list[str],
        title_cards: list[dict[str, Any]] | None = None,
        narrator_audio_paths: list[str] | None = None,
        background_music_path: str | None = None,
        output_dir: str = "/tmp",
        session_id: str | None = None,
        aspect_ratio: AspectRatio | str = "16:9",
    ) -> str:
        ordered_clips = list(shot_clips)
        temp_storyboard_files: list[str] = []

        try:
            def _safe_insert_at(card: dict[str, Any]) -> int:
                raw_idx = card.get("insert_at", 0)
                try:
                    return int(raw_idx)
                except (ValueError, TypeError):
                    return 0

            if title_cards:
                sorted_cards = sorted(
                    title_cards,
                    key=_safe_insert_at,
                    reverse=True,
                )
                for card in sorted_cards:
                    title = card.get("title") or card.get("title_text", "")
                    subtitle = card.get("subtitle") or card.get("subtitle_text", "")
                    duration = card.get("duration") or card.get("duration_seconds", 3.0)
                    style = card.get("style", "gothic_gold")

                    card_clip_path = self.generate_title_card_clip(
                        title_text=title,
                        subtitle_text=subtitle,
                        duration_seconds=float(duration),
                        style=style,
                        output_dir=output_dir,
                        aspect_ratio=aspect_ratio,
                    )
                    temp_storyboard_files.append(card_clip_path)
                    idx = max(0, min(_safe_insert_at(card), len(ordered_clips)))
                    ordered_clips.insert(idx, card_clip_path)

            valid_narrator_paths = [
                p.strip()
                for p in (narrator_audio_paths or [])
                if isinstance(p, str) and self._is_valid_audio_reference(p)
            ]

            master_audio = (
                background_music_path
                if (background_music_path and self._is_valid_audio_reference(background_music_path))
                else None
            )
            if master_audio and valid_narrator_paths:
                ducked_audio = apply_dialogue_audio_ducking(
                    music_path=master_audio,
                    dialogue_path=valid_narrator_paths[0],
                    output_dir=output_dir,
                    mock_mode=self.mock_mode,
                    storage=self.storage,
                )
                temp_storyboard_files.append(ducked_audio)
                master_audio = ducked_audio
            elif not master_audio and valid_narrator_paths:
                master_audio = valid_narrator_paths[0]

            return self.concatenate_clips(
                clip_paths=ordered_clips,
                output_dir=output_dir,
                session_id=session_id,
                master_audio_path=master_audio,
            )
        finally:
            for tmp_p in temp_storyboard_files:
                if os.path.exists(tmp_p):
                    try:
                        os.remove(tmp_p)
                    except OSError:
                        pass
