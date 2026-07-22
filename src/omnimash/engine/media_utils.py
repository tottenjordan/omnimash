"""Bounded ffmpeg execution helpers.

Every ffmpeg invocation in the codebase should go through these helpers so that
calls are time-bounded (a stalled ffmpeg can otherwise hang a worker forever)
and their success is inspectable instead of silently ignored.
"""

from __future__ import annotations

import logging
import subprocess

from omnimash.config import settings

log = logging.getLogger(__name__)

# Default wall-clock budget for a single ffmpeg call. Renders/stitches are short
# (10s clips), so a couple of minutes is a generous ceiling that still fails fast
# on a hung process. Sourced from settings (env: FFMPEG_TIMEOUT).
DEFAULT_FFMPEG_TIMEOUT = settings.ffmpeg_timeout


class FfmpegError(RuntimeError):
    """Raised when an ffmpeg invocation fails or times out."""

    def __init__(
        self,
        message: str,
        *,
        returncode: int | None = None,
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


def _stderr_tail(stderr: bytes | str | None, *, limit: int = 2000) -> str:
    """Return the trailing portion of ffmpeg stderr as text for diagnostics."""
    if not stderr:
        return ""
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    return stderr[-limit:]


def run_ffmpeg(
    cmd: list[str],
    *,
    timeout: float = DEFAULT_FFMPEG_TIMEOUT,
) -> subprocess.CompletedProcess:
    """Run an ffmpeg command, bounded by ``timeout``.

    Raises :class:`FfmpegError` on timeout or a non-zero exit code, with the
    stderr tail attached. Returns the completed process on success.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        tail = _stderr_tail(exc.stderr)
        log.warning("ffmpeg timed out after %ss: %s", timeout, tail)
        raise FfmpegError(f"ffmpeg timed out after {timeout}s", stderr=tail) from exc

    if result.returncode != 0:
        tail = _stderr_tail(result.stderr)
        log.warning("ffmpeg exited with %s: %s", result.returncode, tail)
        raise FfmpegError(
            f"ffmpeg exited with code {result.returncode}",
            returncode=result.returncode,
            stderr=tail,
        )
    return result


def ffmpeg_ok(
    cmd: list[str],
    *,
    timeout: float = DEFAULT_FFMPEG_TIMEOUT,
) -> bool:
    """Run an ffmpeg command and return whether it succeeded (never raises).

    Use for best-effort primary/fallback flows where the caller retries with a
    different command on failure rather than aborting.
    """
    try:
        run_ffmpeg(cmd, timeout=timeout)
        return True
    except FfmpegError:
        return False
