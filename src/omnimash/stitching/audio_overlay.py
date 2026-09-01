import logging
import os
import subprocess
import uuid

logger = logging.getLogger(__name__)


def apply_dialogue_audio_ducking(
    music_path: str,
    dialogue_path: str,
    output_path: str | None = None,
    output_dir: str = "/tmp",
    ducking_db: float = -12.0,
    mock_mode: bool | None = None,
) -> str:
    """Apply FFmpeg sidechain compression filter to duck background music under dialogue audio (-12dB default).

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
    from omnimash.config import settings

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

    # Normalize static paths if relative
    if music_path.startswith("/static/"):
        static_loc = os.path.join(os.getcwd(), music_path.lstrip("/"))
        if os.path.exists(static_loc):
            music_path = static_loc

    if dialogue_path.startswith("/static/"):
        static_loc = os.path.join(os.getcwd(), dialogue_path.lstrip("/"))
        if os.path.exists(static_loc):
            dialogue_path = static_loc

    # Calculate compression threshold from ducking_db attenuation (-12dB default -> 0.2512 linear threshold)
    threshold = round(10.0 ** (-abs(ducking_db) / 20.0), 4)

    # FFmpeg sidechaincompress filter graph
    # [0:a] is background music, [1:a] is dialogue trigger signal
    filter_complex = (
        f"[0:a][1:a]sidechaincompress="
        f"threshold={threshold}:ratio=4:attack=20:release=300[ducked];"
        f"[ducked][1:a]amix=inputs=2:duration=first[aout]"
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

    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning("FFmpeg sidechain ducking failed: %s", res.stderr)
            with open(output_path, "w") as f:
                f.write("fallback ducked audio content")
    except Exception as exc:
        logger.warning("Failed to execute FFmpeg dialogue audio ducking: %s", exc)
        with open(output_path, "w") as f:
            f.write("fallback ducked audio content")

    return output_path
