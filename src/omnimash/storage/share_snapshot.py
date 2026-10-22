"""Privacy-allowlisted share snapshot builder aligned with tottenjordan/adk_pipe."""

from __future__ import annotations

from datetime import UTC, datetime
import re
import secrets
from typing import Any, Literal

SNAPSHOT_VERSION = 1
TOKEN_BYTES = 16
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")

ShareScope = Literal["video", "slate"]


def new_share_token() -> str:
    """Generates a 128-bit URL-safe unguessable token."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def is_valid_share_token(token: str | None) -> bool:
    """Validates that a share token conforms strictly to TOKEN_RE."""
    if not token or not isinstance(token, str):
        return False
    return bool(TOKEN_RE.match(token.strip()))


def build_share_snapshot(
    *,
    token: str,
    scope: ShareScope = "video",
    title: str = "Shared OmniMash Video",
    aspect_ratio: str = "16:9",
    duration_seconds: float | int = 10,
    clips: list[dict[str, Any]] | None = None,
    created_at: str | None = None,
    **_ignored_private_fields: Any,
) -> dict[str, Any]:
    """Builds a strictly allowlisted public snapshot dictionary.

    Never includes internal prompts, raw_compiled_prompt, session_id, user_id,
    user_email, gcs_uri, or director notes.
    """
    clean_scope: ShareScope = "slate" if scope == "slate" else "video"
    clean_title = (title or "Shared OmniMash Video").strip() or "Shared OmniMash Video"
    clean_aspect = (aspect_ratio or "16:9").strip() or "16:9"
    clean_created = created_at or datetime.now(UTC).isoformat()

    allowlisted_clips: list[dict[str, Any]] = []
    if clips:
        for idx, raw_clip in enumerate(clips):
            if not isinstance(raw_clip, dict):
                continue
            allowlisted_clips.append(
                {
                    "index": int(raw_clip.get("index", idx)),
                    "title": str(raw_clip.get("title") or f"Clip {idx + 1}").strip(),
                    "summary": str(raw_clip.get("summary") or "").strip(),
                    "video": str(raw_clip.get("video") or "video.mp4").strip(),
                    "poster": raw_clip.get("poster"),
                    "duration_seconds": float(
                        raw_clip.get("duration_seconds") or duration_seconds or 10
                    ),
                }
            )
    else:
        allowlisted_clips.append(
            {
                "index": 0,
                "title": clean_title,
                "summary": "",
                "video": "video.mp4",
                "poster": None,
                "duration_seconds": float(duration_seconds or 10),
            }
        )

    return {
        "version": SNAPSHOT_VERSION,
        "token": token,
        "created_at": clean_created,
        "scope": clean_scope,
        "title": clean_title,
        "aspect_ratio": clean_aspect,
        "duration_seconds": float(duration_seconds or 10),
        "clips": allowlisted_clips,
    }
