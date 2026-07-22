import os
from unittest.mock import MagicMock, patch

import pytest

from omnimash.engine.media_utils import FfmpegError
from omnimash.stitching.stitcher import VideoStitcher


def _ffmpeg_producing(returncode: int = 0):
    """subprocess.run side_effect that writes the ffmpeg output file (cmd[-1])."""

    def _run(cmd, *args, **kwargs):
        if returncode == 0:
            with open(cmd[-1], "wb") as f:
                f.write(b"stitched master bytes")
        res = MagicMock()
        res.returncode = returncode
        res.stderr = b""
        return res

    return _run


def test_stitch_clips_mock(tmp_path):
    stitcher = VideoStitcher(mock_mode=True)
    clip_urls = ["/static/clip1.mp4", "/static/clip2.mp4", "/static/clip3.mp4"]
    with patch.object(stitcher.storage, "upload_file") as mock_upload:
        mock_upload.return_value = "https://storage.googleapis.com/test/blob"
        output_path = stitcher.concatenate_clips(clip_urls, output_dir=str(tmp_path))
        assert output_path.endswith("_stitched.mp4")
        assert os.path.exists(output_path)
        mock_upload.assert_called_once()
        call_kwargs = mock_upload.call_args.kwargs
        assert call_kwargs.get("category") == "final_masters" or "final_masters" in call_kwargs.get(
            "destination_blob_name", ""
        )


def test_stitch_clips_single_clip_mock(tmp_path):
    clip1 = tmp_path / "clip1.mp4"
    clip1.write_bytes(b"dummy clip content")
    stitcher = VideoStitcher(mock_mode=True)
    with patch.object(stitcher.storage, "upload_file") as mock_upload:
        output_path = stitcher.concatenate_clips([str(clip1)], output_dir=str(tmp_path))
        assert os.path.exists(output_path)
        with open(output_path, "rb") as f:
            content = f.read()
        assert content == b"dummy clip content"
        call_kwargs = mock_upload.call_args.kwargs
        assert call_kwargs.get("category") == "final_masters" or "final_masters" in call_kwargs.get(
            "destination_blob_name", ""
        )


def test_stitch_clips_live_mode_copy_success(tmp_path):
    stitcher = VideoStitcher(mock_mode=False)
    clip1 = str(tmp_path / "clip1.mp4")
    clip2 = str(tmp_path / "clip2.mp4")
    clip_paths = [clip1, clip2]

    # The concat list is unique-named and removed in a finally, so capture its
    # path and contents from inside the mocked ffmpeg call.
    captured = {}

    def _run(cmd, *args, **kwargs):
        concat_path = cmd[cmd.index("-i") + 1]
        captured["concat_path"] = concat_path
        with open(concat_path) as cf:
            captured["lines"] = cf.read().splitlines()
        with open(cmd[-1], "wb") as f:
            f.write(b"stitched master bytes")
        res = MagicMock()
        res.returncode = 0
        res.stderr = b""
        return res

    with (
        patch("subprocess.run", side_effect=_run) as mock_subproc,
        patch.object(stitcher.storage, "upload_file") as mock_upload,
    ):
        out_path = stitcher.concatenate_clips(
            clip_paths, output_dir=str(tmp_path), session_id="test_session"
        )

        # Concat list captured during the call had the expected escaped entries.
        assert captured["lines"] == [
            f"file '{os.path.abspath(clip1)}'",
            f"file '{os.path.abspath(clip2)}'",
        ]
        # It is cleaned up afterwards.
        assert not os.path.exists(captured["concat_path"])

        # Verify subprocess call
        mock_subproc.assert_called_once()
        cmd = mock_subproc.call_args[0][0]
        assert cmd[:10] == [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            captured["concat_path"],
            "-c",
            "copy",
        ]
        assert cmd[10] == out_path

        # Verify GCS upload category final_masters
        mock_upload.assert_called_once()
        call_kwargs = mock_upload.call_args.kwargs
        assert call_kwargs.get("category") == "final_masters" or "final_masters" in call_kwargs.get(
            "destination_blob_name", ""
        )


def test_stitch_clips_escapes_single_quotes_in_paths(tmp_path):
    stitcher = VideoStitcher(mock_mode=False)
    # A clip whose filename contains an apostrophe must be escaped for the
    # ffmpeg concat demuxer ('  ->  '\'' ) so the list is not corrupted.
    weird_dir = tmp_path / "o'brien"
    weird_dir.mkdir()
    clip = str(weird_dir / "clip.mp4")

    captured = {}

    def _run(cmd, *args, **kwargs):
        concat_path = cmd[cmd.index("-i") + 1]
        with open(concat_path) as cf:
            captured["lines"] = cf.read().splitlines()
        with open(cmd[-1], "wb") as f:
            f.write(b"stitched master bytes")
        res = MagicMock()
        res.returncode = 0
        res.stderr = b""
        return res

    with (
        patch("subprocess.run", side_effect=_run),
        patch.object(stitcher.storage, "upload_file"),
    ):
        stitcher.concatenate_clips([clip], output_dir=str(tmp_path))

    escaped = os.path.abspath(clip).replace("'", "'\\''")
    assert captured["lines"] == [f"file '{escaped}'"]


def test_stitch_clips_live_mode_reencode_fallback(tmp_path):
    stitcher = VideoStitcher(mock_mode=False)
    clip1 = str(tmp_path / "clip1.mp4")
    clip_paths = [clip1]

    calls = {"n": 0}

    def _run(cmd, *args, **kwargs):
        calls["n"] += 1
        res = MagicMock()
        res.stderr = b""
        if calls["n"] == 1:
            res.returncode = 1  # stream copy fails
        else:
            res.returncode = 0  # re-encode succeeds and produces the file
            with open(cmd[-1], "wb") as f:
                f.write(b"reencoded master bytes")
        return res

    with (
        patch("subprocess.run", side_effect=_run) as mock_subproc,
        patch.object(stitcher.storage, "upload_file") as mock_upload,
    ):
        out_path = stitcher.concatenate_clips(clip_paths, output_dir=str(tmp_path))
        assert out_path.endswith("_stitched.mp4")

        assert mock_subproc.call_count == 2
        # First call was stream copy
        first_cmd = mock_subproc.call_args_list[0][0][0]
        assert "-c" in first_cmd and "copy" in first_cmd

        # Second call was re-encode
        second_cmd = mock_subproc.call_args_list[1][0][0]
        assert "-c:v" in second_cmd and "libx264" in second_cmd
        assert "-c:a" in second_cmd and "aac" in second_cmd
        assert "-pix_fmt" in second_cmd and "yuv420p" in second_cmd

        mock_upload.assert_called_once()


def test_stitch_clips_raises_when_reencode_fails(tmp_path):
    stitcher = VideoStitcher(mock_mode=False)
    clip_paths = [str(tmp_path / "clip1.mp4")]

    # Both stream-copy and re-encode fail: no master is produced, so the stitch
    # must raise instead of uploading a broken/empty file.
    with (
        patch("subprocess.run", side_effect=_ffmpeg_producing(1)),
        patch.object(stitcher.storage, "upload_file") as mock_upload,
    ):
        with pytest.raises(FfmpegError):
            stitcher.concatenate_clips(clip_paths, output_dir=str(tmp_path))
        mock_upload.assert_not_called()
