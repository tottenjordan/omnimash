import subprocess
from unittest.mock import patch

import pytest

from omnimash.engine.media_utils import FfmpegError, ffmpeg_ok, run_ffmpeg


def _completed(returncode: int, stderr: bytes = b"") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["ffmpeg"], returncode=returncode, stdout=b"", stderr=stderr
    )


def test_run_ffmpeg_success_returns_completed_process():
    with patch("subprocess.run", return_value=_completed(0)) as mock_run:
        result = run_ffmpeg(["ffmpeg", "-version"], timeout=5)
    assert result.returncode == 0
    # Timeout is forwarded to subprocess.run.
    assert mock_run.call_args.kwargs["timeout"] == 5
    assert mock_run.call_args.kwargs["check"] is False


def test_run_ffmpeg_raises_on_nonzero():
    with (
        patch("subprocess.run", return_value=_completed(1, b"boom stderr")),
        pytest.raises(FfmpegError) as exc,
    ):
        run_ffmpeg(["ffmpeg"], timeout=5)
    assert exc.value.returncode == 1
    assert "boom stderr" in exc.value.stderr


def test_run_ffmpeg_raises_on_timeout():
    with (
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=5, stderr=b"stalled"),
        ),
        pytest.raises(FfmpegError) as exc,
    ):
        run_ffmpeg(["ffmpeg"], timeout=5)
    assert "timed out" in str(exc.value)
    assert "stalled" in exc.value.stderr


def test_ffmpeg_ok_returns_bool():
    with patch("subprocess.run", return_value=_completed(0)):
        assert ffmpeg_ok(["ffmpeg"]) is True
    with patch("subprocess.run", return_value=_completed(1, b"nope")):
        assert ffmpeg_ok(["ffmpeg"]) is False
