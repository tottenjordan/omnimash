import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass


@dataclass
class GenerationResult:
    interaction_thread_id: str
    video_url: str
    duration_seconds: int = 10
    synth_id_watermark: str = "SYNTHID_C2PA_VERIFIED"


def ensure_rendered_video(video_url: str) -> None:
    """Ensures a valid playable 720p MP4 file exists on disk for the given video URL."""
    if not video_url.startswith("/static/"):
        return
    rel_path = video_url.lstrip("/")
    os.makedirs(os.path.dirname(rel_path), exist_ok=True)
    if os.path.exists(rel_path) and os.path.getsize(rel_path) > 0:
        return

    base_sample = "static/rendered/thread_5bbcb4e1_turn0.mp4"
    if os.path.exists(base_sample) and os.path.getsize(base_sample) > 0:
        shutil.copy(base_sample, rel_path)
        return

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=0x110022:s=1280x720:d=10",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=10",
                "-vf",
                "drawtext=text='🎬 OmniMash - Dripwarts 720p Clip\nSnape Dawg x DumbleDior':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=(h-text_h)/2",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                rel_path,
            ],
            capture_output=True,
            check=False,
        )
    except Exception:
        pass


class OmniFlashClient:
    def __init__(self, api_key: str | None = None, mock_mode: bool = True):
        self.api_key = api_key
        self.mock_mode = mock_mode

    def generate_clip(self, prompt: str) -> GenerationResult:
        if self.mock_mode:
            thread_id = f"thread_{uuid.uuid4().hex[:8]}"
            url = f"/static/rendered/{thread_id}_turn0.mp4"
            ensure_rendered_video(url)
            return GenerationResult(
                interaction_thread_id=thread_id,
                video_url=url,
            )
        raise NotImplementedError("Live API calls require active GCP credentials.")

    def apply_interaction_diff(
        self, interaction_thread_id: str, diff_prompt: str
    ) -> GenerationResult:
        if self.mock_mode:
            url = f"/static/rendered/{interaction_thread_id}_turn_diff.mp4"
            ensure_rendered_video(url)
            return GenerationResult(
                interaction_thread_id=interaction_thread_id,
                video_url=url,
            )
        raise NotImplementedError("Live API calls require active GCP credentials.")

    def start_thread_from_video(
        self, base_video_url: str, initial_prompt: str | None = None
    ) -> GenerationResult:
        if self.mock_mode:
            thread_id = f"reanchored_thread_{uuid.uuid4().hex[:8]}"
            url = f"/static/rendered/{thread_id}_turn0.mp4"
            ensure_rendered_video(url)
            return GenerationResult(
                interaction_thread_id=thread_id,
                video_url=url,
            )
        raise NotImplementedError("Live API calls require active GCP credentials.")
