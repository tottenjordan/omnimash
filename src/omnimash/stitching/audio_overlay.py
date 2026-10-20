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

    temp_files: list[str] = []

    def _resolve_audio_input(raw_path: str) -> str:
        from urllib.parse import parse_qs, unquote, urlparse

        norm = raw_path.strip()
        if "/api/media-proxy" in norm and "uri=" in norm:
            try:
                parsed = urlparse(norm)
                qs = parse_qs(parsed.query)
                if "uri" in qs and qs["uri"]:
                    norm = unquote(qs["uri"][0])
            except Exception:
                pass
        if norm.startswith("/static/"):
            from omnimash.engine.media_loader import validate_local_media_path

            static_loc = validate_local_media_path(norm)
            if static_loc and os.path.exists(static_loc):
                return static_loc
            return ""
        if os.path.exists(norm):
            from omnimash.engine.media_loader import validate_local_media_path

            confined_path = validate_local_media_path(norm)
            if confined_path and os.path.exists(confined_path):
                return os.path.abspath(confined_path)
            return ""
        if norm.startswith(("gs://", "https://storage.googleapis.com/")):
            try:
                from omnimash.storage.gcs import GcsStorageManager

                storage_mgr = GcsStorageManager(mock_mode=mock_mode)
                data, _ = storage_mgr.download_blob_bytes(norm)
                if data:
                    ext = os.path.splitext(norm)[1] or ".mp3"
                    tmp_p = os.path.join(output_dir, f"duck_in_{uuid.uuid4().hex[:8]}{ext}")
                    with open(tmp_p, "wb") as tf:
                        tf.write(data)
                    temp_files.append(tmp_p)
                    return tmp_p
            except Exception:
                pass
        return norm

    try:
        music_path = _resolve_audio_input(music_path)
        dialogue_path = _resolve_audio_input(dialogue_path)

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
