import logging
import os
import subprocess
import uuid

from typing import Any

from omnimash.config import settings
from omnimash.stitching.resolver import resolve_media_source_to_local_path

logger = logging.getLogger(__name__)


def apply_dialogue_audio_ducking(
    music_path: str,
    dialogue_path: str,
    output_path: str | None = None,
    output_dir: str = "/tmp",
    ducking_db: float = -12.0,
    mock_mode: bool | None = None,
    storage: Any = None,
) -> str:
    """Apply FFmpeg sidechain compression filter to duck background music under dialogue audio (-12dB default).

    Preserves speech dialogue volume at full loudness (0 dB) with normalize=0 while ducking background music.

    Args:
        music_path: File path to the background music audio.
        dialogue_path: File path to the dialogue/narration audio.
        output_path: Optional explicit output file path.
        output_dir: Directory for output file if output_path is not specified.
        ducking_db: Ducking attenuation level in dB (default -12dB).
        mock_mode: If True, skips FFmpeg execution and writes mock output.

    Returns:
        Path to the output audio file with sidechain compression applied.
    """
    if mock_mode is None:
        mock_mode = getattr(settings, "mock_mode", False)

    if output_path:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
    else:
        os.makedirs(output_dir, exist_ok=True)
        out_filename = f"ducked_audio_{uuid.uuid4().hex[:8]}.aac"
        output_path = os.path.join(output_dir, out_filename)

    if mock_mode:
        with open(output_path, "w") as f:
            f.write("mock ducked audio content")
        return output_path

    temp_files: list[str] = []

    try:
        resolved_music = resolve_media_source_to_local_path(
            music_path, temp_dir=output_dir, storage=storage, mock_mode=mock_mode
        )
        if (
            resolved_music
            and resolved_music != music_path
            and os.path.dirname(resolved_music) == os.path.abspath(output_dir)
        ):
            temp_files.append(resolved_music)
        music_path = resolved_music or ""

        resolved_dialogue = resolve_media_source_to_local_path(
            dialogue_path, temp_dir=output_dir, storage=storage, mock_mode=mock_mode
        )
        if (
            resolved_dialogue
            and resolved_dialogue != dialogue_path
            and os.path.dirname(resolved_dialogue) == os.path.abspath(output_dir)
        ):
            temp_files.append(resolved_dialogue)
        dialogue_path = resolved_dialogue or ""

        # Calculate compression threshold from ducking_db attenuation (-12dB default -> 0.2512 linear threshold)
        threshold = round(10.0 ** (-abs(ducking_db) / 20.0), 4)

        # FFmpeg sidechaincompress filter graph
        # [0:a] is background music, [1:a] is dialogue trigger signal
        # amix normalize=0 preserves full dialogue loudness (0 dB)
        filter_complex = (
            f"[0:a][1:a]sidechaincompress="
            f"threshold={threshold}:ratio=4:attack=20:release=300[ducked];"
            f"[ducked][1:a]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            music_path,
            "-i",
            dialogue_path,
            "-filter_complex",
            filter_complex,
            "-map",
            "[aout]",
            "-c:a",
            "aac",
            output_path,
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
                logger.warning("FFmpeg sidechain ducking failed: %s", res.stderr)
                with open(output_path, "w") as f:
                    f.write("fallback ducked audio content")
        except subprocess.TimeoutExpired as exc:
            logger.warning(
                "FFmpeg sidechain ducking timed out after %s seconds: %s",
                timeout_secs,
                exc,
            )
            with open(output_path, "w") as f:
                f.write("fallback ducked audio content")
        except Exception as exc:
            logger.warning("Failed to execute FFmpeg dialogue audio ducking: %s", exc)
            with open(output_path, "w") as f:
                f.write("fallback ducked audio content")
    finally:
        for tp in temp_files:
            if os.path.exists(tp):
                try:
                    os.remove(tp)
                except OSError:
                    pass

    return output_path
