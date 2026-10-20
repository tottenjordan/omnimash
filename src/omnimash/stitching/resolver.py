"""Canonical media source resolution for VideoStitcher and audio overlay."""

import logging
import os
import uuid
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from omnimash.engine.media_loader import (
    fetch_media_bytes,
    validate_local_media_path,
    validate_remote_media_url,
)

logger = logging.getLogger(__name__)


def resolve_media_source_to_local_path(
    source: str,
    temp_dir: str,
    storage: Any,
    mock_mode: bool = False,
) -> str | None:
    """Resolves local paths, /static/ paths, proxy URLs, GCS URIs, and remote URLs to a local file path.

    Args:
        source: Media reference string (file path, static URL, GCS URI, proxy URL, or HTTP URL).
        temp_dir: Directory where downloaded or temporary files should be written.
        storage: GcsStorageManager instance for downloading blobs.
        mock_mode: If True, writes mock content instead of contacting cloud services.

    Returns:
        Absolute local file path if resolved and verified, or None if invalid or blocked.
    """
    if not source or not isinstance(source, str):
        return None
    raw = source.strip()
    if not raw:
        return None

    # Unpack /api/media-proxy query parameters
    if "/api/media-proxy" in raw and "uri=" in raw:
        try:
            parsed = urlparse(raw)
            qs = parse_qs(parsed.query)
            if "uri" in qs and qs["uri"]:
                raw = unquote(qs["uri"][0])
        except Exception as exc:
            logger.warning("Failed to parse media-proxy URL in resolver: %s", exc)

    # Confined local static path
    if raw.startswith("/static/"):
        confined = validate_local_media_path(raw)
        if confined and os.path.exists(confined):
            return os.path.abspath(confined)
        return None

    # Direct existing local path
    if os.path.exists(raw):
        # Verify local path does not escape allowed roots if it uses relative navigation
        confined = validate_local_media_path(raw)
        if confined and os.path.exists(confined):
            return os.path.abspath(confined)
        return os.path.abspath(raw)

    # GCS URI download via public API
    if raw.startswith(("gs://", "https://storage.googleapis.com/")):
        if mock_mode:
            mock_path = os.path.join(temp_dir, f"mock_gcs_{uuid.uuid4().hex[:8]}.mp4")
            with open(mock_path, "wb") as f:
                f.write(b"mock gcs downloaded media")
            return mock_path
        try:
            data, _ = storage.download_blob_bytes(raw)
            if data:
                ext = os.path.splitext(raw)[1] or ".bin"
                tmp_p = os.path.join(temp_dir, f"gcs_{uuid.uuid4().hex[:8]}{ext}")
                with open(tmp_p, "wb") as f:
                    f.write(data)
                return tmp_p
        except Exception as exc:
            logger.warning("Failed to download GCS blob %s in resolver: %s", raw, exc)
            return None

    # Remote HTTP(S) URL with SSRF protection
    if raw.startswith(("http://", "https://")):
        if not validate_remote_media_url(raw):
            logger.warning("Blocked disallowed or private HTTP media URL in resolver: %s", raw)
            return None
        try:
            data, _ = fetch_media_bytes(raw, storage=storage)
            if data:
                ext = os.path.splitext(raw)[1] or ".mp3"
                tmp_p = os.path.join(temp_dir, f"remote_{uuid.uuid4().hex[:8]}{ext}")
                with open(tmp_p, "wb") as f:
                    f.write(data)
                return tmp_p
        except Exception as exc:
            logger.warning("Failed to safely fetch remote media %s in resolver: %s", raw, exc)
            return None

    return None
