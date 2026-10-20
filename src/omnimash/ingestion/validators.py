from __future__ import annotations

import math
import os
import re
import tempfile
import urllib.parse

from omnimash.engine.media_loader import validate_remote_media_url

_SAFE_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")
_ALLOWED_YOUTUBE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtu.be",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
    }
)


def validate_youtube_reference_url(url: str) -> str:
    """Validates that a reference URL is a safe HTTP(S) YouTube URL and resolves to a public IP."""
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("Missing YouTube reference URL")
    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Unsupported URL scheme '{parsed.scheme}': only http and https are allowed"
        )
    hostname = (parsed.hostname or "").strip().lower()
    if hostname not in _ALLOWED_YOUTUBE_HOSTS:
        raise ValueError(
            f"Disallowed reference host '{hostname}': only YouTube domains are permitted"
        )
    validate_remote_media_url(cleaned)
    return cleaned


def sanitize_ingestion_session_id(session_id: str | None) -> str:
    """Validates session_id to prevent path traversal outside static/sessions/."""
    cleaned = (session_id or "").strip() or "default"
    if "\x00" in cleaned or ".." in cleaned or not _SAFE_SESSION_ID_RE.match(cleaned):
        raise ValueError(
            f"Invalid session_id '{session_id}': only alphanumeric, underscore, and hyphen characters are permitted"
        )
    base_root = os.path.realpath("static/sessions")
    target_dir = os.path.realpath(os.path.join("static", "sessions", cleaned, "references"))
    if not (target_dir == base_root or target_dir.startswith(base_root + os.sep)):
        raise ValueError(f"Invalid session_id '{session_id}': path escapes static/sessions/")
    return cleaned


def normalize_and_validate_clip_paths(
    source_video_path: str,
    output_clip_path: str | None = None,
) -> tuple[str, str]:
    """Normalizes leading /static/ paths and enforces confinement within static/ or /tmp/."""
    raw_src = (source_video_path or "").strip()
    if not raw_src or raw_src.startswith("-"):
        raise ValueError(f"Invalid source_video_path: {source_video_path!r}")

    normalized_src = raw_src.lstrip("/") if raw_src.startswith("/static/") else raw_src
    if output_clip_path is None:
        base_name, _ext = os.path.splitext(normalized_src)
        normalized_out = f"{base_name}_motion_3s.mp4"
    else:
        raw_out = output_clip_path.strip()
        if not raw_out or raw_out.startswith("-"):
            raise ValueError(f"Invalid output_clip_path: {output_clip_path!r}")
        normalized_out = raw_out.lstrip("/") if raw_out.startswith("/static/") else raw_out

    allowed_roots = (
        os.path.realpath("static"),
        os.path.realpath("/tmp"),
        os.path.realpath(tempfile.gettempdir()),
    )
    for candidate in (normalized_src, normalized_out):
        real_candidate = os.path.realpath(candidate)
        if not any(
            real_candidate == root or real_candidate.startswith(root + os.sep)
            for root in allowed_roots
        ):
            raise ValueError(f"Path '{candidate}' must reside within static/ or /tmp/ directories")

    return normalized_src, normalized_out


def sanitize_clip_timing(
    start_time_seconds: float = 0.0,
    duration_seconds: float = 3.0,
) -> tuple[float, float]:
    """Clamps start_time_seconds and duration_seconds to finite, safe ranges for FFmpeg."""
    try:
        start_val = float(start_time_seconds)
    except (TypeError, ValueError):
        start_val = 0.0
    if not math.isfinite(start_val) or start_val < 0.0:
        start_val = 0.0

    try:
        dur_val = float(duration_seconds)
    except (TypeError, ValueError):
        dur_val = 3.0
    if not math.isfinite(dur_val) or dur_val <= 0.0:
        dur_val = 3.0
    else:
        dur_val = min(max(dur_val, 0.1), 60.0)

    return start_val, dur_val
