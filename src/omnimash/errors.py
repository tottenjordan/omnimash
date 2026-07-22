"""Shared domain errors and sanitization for external-dependency failures.

External calls (video generation, GCS, ffmpeg) can fail in many ways. Rather
than letting raw exceptions bubble up as 500s — leaking bucket names, URIs, and
stack traces — callers translate them into typed responses (orchestrator) or
sanitized HTTP errors (API) using the helpers here.
"""

from __future__ import annotations

from omnimash.engine.media_utils import FfmpegError

try:
    from google.api_core.exceptions import GoogleAPIError
except ImportError:  # google-api-core is optional in some environments
    GoogleAPIError = None  # type: ignore[assignment,misc]


class OmniMashError(RuntimeError):
    """Base class for expected OmniMash service failures surfaced to callers."""


# The concrete external-dependency exception types we expect and translate into
# typed responses instead of leaking raw internals. Built dynamically so an
# absent optional dependency (google-api-core) doesn't break the tuple.
_EXTERNAL_ERROR_TYPES: tuple[type[BaseException], ...] = tuple(
    t for t in (OmniMashError, FfmpegError, GoogleAPIError) if isinstance(t, type)
)


def is_external_service_error(exc: BaseException) -> bool:
    """True if ``exc`` is a known external-dependency failure we can sanitize."""
    return isinstance(exc, _EXTERNAL_ERROR_TYPES)


def sanitized_error_message(exc: BaseException) -> str:
    """A user-safe message that never leaks bucket names, URIs, or paths.

    Keyed on error type so the client learns *what* broke (rendering vs storage)
    without exposing internal identifiers or stack detail.
    """
    if isinstance(exc, FfmpegError):
        return "Video processing failed while rendering or stitching clips."
    if GoogleAPIError is not None and isinstance(exc, GoogleAPIError):
        return "A storage backend error occurred while saving or loading media."
    if isinstance(exc, OmniMashError):
        return str(exc) or "The request could not be completed."
    return "An unexpected error occurred while processing the request."
