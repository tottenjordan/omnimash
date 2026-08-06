import logging
import os
import shutil
import subprocess
import uuid
from typing import Any

from omnimash.storage.gcs import GcsStorageManager

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont

    HAS_PIL = True
except ImportError:
    HAS_PIL = False



class VideoStitcher:
    def __init__(self, mock_mode: bool | None = None, bucket_name: str | None = None):
        from omnimash.config import settings

        self.mock_mode = mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        self.storage = GcsStorageManager(
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

        if self.mock_mode:
            if clip_paths and os.path.exists(clip_paths[0]):
                shutil.copyfile(clip_paths[0], out_path)
            else:
                with open(out_path, "w") as f:
                    f.write("mock mp4 master video content")
        else:
            resolved_clips: list[str] = []
            for clip in clip_paths:
                norm_clip = self.storage._normalize_media_source_path(clip)
                if os.path.exists(norm_clip):
                    resolved_clips.append(os.path.abspath(norm_clip))
                elif norm_clip.startswith("/static/"):
                    loc = os.path.join(os.getcwd(), norm_clip.lstrip("/"))
                    if os.path.exists(loc):
                        resolved_clips.append(loc)
                elif (
                    not self.mock_mode
                    and self.storage._bucket
                    and norm_clip.startswith("gs://")
                ):
                    try:
                        blob_name = norm_clip.replace(
                            f"gs://{self.storage.bucket_name}/", ""
                        ).lstrip("/")
                        tmp_clip_path = os.path.join(
                            output_dir, f"clip_{uuid.uuid4().hex[:6]}.mp4"
                        )
                        blob = self.storage._bucket.blob(blob_name)
                        blob.download_to_filename(tmp_clip_path)
                        resolved_clips.append(tmp_clip_path)
                    except Exception:
                        resolved_clips.append(norm_clip)
                else:
                    resolved_clips.append(norm_clip)

            resolved_audio: str | None = None
            if master_audio_path:
                norm_audio = self.storage._normalize_media_source_path(master_audio_path)
                if os.path.exists(norm_audio):
                    resolved_audio = os.path.abspath(norm_audio)
                elif norm_audio.startswith("/static/"):
                    loc = os.path.join(os.getcwd(), norm_audio.lstrip("/"))
                    if os.path.exists(loc):
                        resolved_audio = loc
                elif (
                    not self.mock_mode
                    and self.storage._bucket
                    and norm_audio.startswith("gs://")
                ):
                    try:
                        blob_name = norm_audio.replace(
                            f"gs://{self.storage.bucket_name}/", ""
                        ).lstrip("/")
                        tmp_audio_path = os.path.join(
                            output_dir, f"audio_{uuid.uuid4().hex[:6]}.mp3"
                        )
                        blob = self.storage._bucket.blob(blob_name)
                        blob.download_to_filename(tmp_audio_path)
                        resolved_audio = tmp_audio_path
                    except Exception:
                        resolved_audio = norm_audio
                elif norm_audio.startswith(("http://", "https://")):
                    try:
                        import urllib.request
                        tmp_audio_path = os.path.join(
                            output_dir, f"audio_{uuid.uuid4().hex[:6]}.mp3"
                        )
                        urllib.request.urlretrieve(norm_audio, tmp_audio_path)
                        resolved_audio = tmp_audio_path
                    except Exception as exc:
                        logger.warning("Failed to download HTTP master audio URL: %s", exc)
                        resolved_audio = norm_audio
                else:
                    resolved_audio = norm_audio

            if resolved_clips:
                concat_list_path = os.path.join(output_dir, "concat_list.txt")
                with open(concat_list_path, "w") as f:
                    for clip_file in resolved_clips:
                        f.write(f"file '{clip_file}'\n")

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

                res = subprocess.run(cmd_copy, capture_output=True, text=True)
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
                            out_path,
                        ]
                    subprocess.run(cmd_reencode, capture_output=True, text=True)

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

            img = Image.new("RGB", (1280, 720), color=bg_color)
            draw = ImageDraw.Draw(img)

            try:
                title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 60)
                subtitle_font = ImageFont.truetype("DejaVuSans.ttf", 36)
            except Exception:
                try:
                    title_font = ImageFont.load_default(size=60)
                    subtitle_font = ImageFont.load_default(size=36)
                except Exception:
                    title_font = ImageFont.load_default()
                    subtitle_font = ImageFont.load_default()

            t_bbox = draw.textbbox((0, 0), title_text, font=title_font)
            t_w = t_bbox[2] - t_bbox[0]
            t_h = t_bbox[3] - t_bbox[1]

            if subtitle_text:
                s_bbox = draw.textbbox((0, 0), subtitle_text, font=subtitle_font)
                s_w = s_bbox[2] - s_bbox[0]
                s_h = s_bbox[3] - s_bbox[1]
                spacing = 20
                total_h = t_h + spacing + s_h
                t_y = (720 - total_h) / 2
                s_y = t_y + t_h + spacing

                draw.text(((1280 - t_w) / 2, t_y), title_text, fill=title_color, font=title_font)
                draw.text(((1280 - s_w) / 2, s_y), subtitle_text, fill=subtitle_color, font=subtitle_font)
            else:
                t_y = (720 - t_h) / 2
                draw.text(((1280 - t_w) / 2, t_y), title_text, fill=title_color, font=title_font)

            img.save(img_path)

            cmd = [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                img_path,
                "-c:v",
                "libx264",
                "-t",
                str(duration_seconds),
                "-pix_fmt",
                "yuv420p",
                "-vf",
                "scale=1280:720",
                "-r",
                "30",
                out_path,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                logger.warning("FFmpeg title card rendering failed: %s", res.stderr)
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

    def stitch_storyboard_master(
        self,
        shot_clips: list[str],
        title_cards: list[dict[str, Any]] | None = None,
        narrator_audio_paths: list[str] | None = None,
        background_music_path: str | None = None,
        output_dir: str = "/tmp",
        session_id: str | None = None,
    ) -> str:
        ordered_clips = list(shot_clips)

        if title_cards:
            sorted_cards = sorted(
                title_cards,
                key=lambda c: c.get("insert_at", 0),
                reverse=True,
            )
            for card in sorted_cards:
                title = card.get("title") or card.get("title_text", "")
                subtitle = card.get("subtitle") or card.get("subtitle_text", "")
                duration = card.get("duration") or card.get("duration_seconds", 3.0)
                style = card.get("style", "gothic_gold")
                insert_at = card.get("insert_at", 0)

                card_clip_path = self.generate_title_card_clip(
                    title_text=title,
                    subtitle_text=subtitle,
                    duration_seconds=float(duration),
                    style=style,
                    output_dir=output_dir,
                )
                idx = max(0, min(int(insert_at), len(ordered_clips)))
                ordered_clips.insert(idx, card_clip_path)

        master_audio = background_music_path
        if not master_audio and narrator_audio_paths and len(narrator_audio_paths) > 0:
            master_audio = narrator_audio_paths[0]

        return self.concatenate_clips(
            clip_paths=ordered_clips,
            output_dir=output_dir,
            session_id=session_id,
            master_audio_path=master_audio,
        )

