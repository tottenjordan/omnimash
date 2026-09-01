import os
from unittest.mock import MagicMock, patch

from omnimash.agent.orchestrator import OmniMashAgent
from omnimash.stitching.stitcher import VideoStitcher


def test_concatenate_clips_without_master_audio(tmp_path):
    stitcher = VideoStitcher(mock_mode=False)
    clip1 = str(tmp_path / "clip1.mp4")
    clip2 = str(tmp_path / "clip2.mp4")

    mock_res = MagicMock()
    mock_res.returncode = 0

    with (
        patch("subprocess.run", return_value=mock_res) as mock_subproc,
        patch.object(stitcher.storage, "upload_file"),
    ):
        out_path = stitcher.concatenate_clips(
            [clip1, clip2], output_dir=str(tmp_path), session_id="test_session"
        )
        assert out_path.endswith("_stitched.mp4")

        mock_subproc.assert_called_once()
        cmd = mock_subproc.call_args[0][0]
        assert "-i" in cmd
        assert "-shortest" not in cmd
        assert "-map" not in cmd


def test_concatenate_clips_with_master_audio_exists(tmp_path):
    stitcher = VideoStitcher(mock_mode=False)
    clip1 = str(tmp_path / "clip1.mp4")
    audio_file = tmp_path / "master_audio.mp3"
    audio_file.write_bytes(b"dummy audio data")

    mock_res = MagicMock()
    mock_res.returncode = 0

    with (
        patch("subprocess.run", return_value=mock_res) as mock_subproc,
        patch.object(stitcher.storage, "upload_file"),
    ):
        out_path = stitcher.concatenate_clips(
            [clip1],
            output_dir=str(tmp_path),
            session_id="test_session",
            master_audio_path=str(audio_file),
        )
        assert out_path.endswith("_stitched.mp4")

        mock_subproc.assert_called_once()
        cmd = mock_subproc.call_args[0][0]
        expected_audio_path = os.path.abspath(str(audio_file))
        assert cmd[:-1] == [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(tmp_path / "concat_list.txt"),
            "-i",
            expected_audio_path,
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
        ]
        assert cmd[-1] == out_path


def test_concatenate_clips_with_master_audio_nonexistent(tmp_path):
    stitcher = VideoStitcher(mock_mode=False)
    clip1 = str(tmp_path / "clip1.mp4")
    nonexistent_audio = str(tmp_path / "nonexistent_audio.mp3")

    mock_res = MagicMock()
    mock_res.returncode = 0

    with (
        patch("subprocess.run", return_value=mock_res) as mock_subproc,
        patch.object(stitcher.storage, "upload_file"),
    ):
        out_path = stitcher.concatenate_clips(
            [clip1],
            output_dir=str(tmp_path),
            session_id="test_session",
            master_audio_path=nonexistent_audio,
        )
        assert out_path.endswith("_stitched.mp4")

        mock_subproc.assert_called_once()
        cmd = mock_subproc.call_args[0][0]
        assert "-shortest" not in cmd
        assert "-map" not in cmd


def test_concatenate_clips_with_master_audio_reencode_fallback(tmp_path):
    stitcher = VideoStitcher(mock_mode=False)
    clip1 = str(tmp_path / "clip1.mp4")
    audio_file = tmp_path / "master_audio.mp3"
    audio_file.write_bytes(b"dummy audio data")

    fail_res = MagicMock()
    fail_res.returncode = 1
    success_res = MagicMock()
    success_res.returncode = 0

    with (
        patch("subprocess.run", side_effect=[fail_res, success_res]) as mock_subproc,
        patch.object(stitcher.storage, "upload_file"),
    ):
        out_path = stitcher.concatenate_clips(
            [clip1],
            output_dir=str(tmp_path),
            session_id="test_session",
            master_audio_path=str(audio_file),
        )
        assert out_path.endswith("_stitched.mp4")

        assert mock_subproc.call_count == 2
        second_cmd = mock_subproc.call_args_list[1][0][0]
        expected_audio_path = os.path.abspath(str(audio_file))
        assert second_cmd[:-1] == [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(tmp_path / "concat_list.txt"),
            "-i",
            expected_audio_path,
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
        ]
        assert second_cmd[-1] == out_path


def test_concatenate_clips_mock_mode_with_audio(tmp_path):
    stitcher = VideoStitcher(mock_mode=True)
    audio_file = tmp_path / "master_audio.mp3"
    audio_file.write_bytes(b"dummy audio data")

    with patch.object(stitcher.storage, "upload_file") as mock_upload:
        mock_upload.return_value = "https://storage.googleapis.com/test/blob"
        out_path = stitcher.concatenate_clips(
            ["/static/clip1.mp4"],
            output_dir=str(tmp_path),
            master_audio_path=str(audio_file),
        )
        assert out_path.endswith("_stitched.mp4")
        assert os.path.exists(out_path)


def test_orchestrator_stitch_session_master_passes_audio_path():
    agent = OmniMashAgent(mock_mode=True)
    master_audio = "/tmp/test_master.mp3"

    with (
        patch.object(agent.stitcher, "concatenate_clips", return_value="/tmp/master_stitched.mp4") as mock_concat,
        patch.object(agent.storage, "save_final_master", return_value=("gs://bucket/master.mp4", "https://master.url")) as mock_save,
    ):
        gcs_uri, url = agent.stitch_session_master(
            session_name="test_session",
            master_title="Test Title",
            master_audio_path=master_audio,
        )

        mock_concat.assert_called_once_with(
            [],
            session_id="test_session",
            master_audio_path=master_audio,
        )
        mock_save.assert_called_once()
        assert gcs_uri == "gs://bucket/master.mp4"


def test_apply_dialogue_audio_ducking_filter(tmp_path):
    from omnimash.stitching.audio_overlay import apply_dialogue_audio_ducking

    music_file = tmp_path / "music.mp3"
    music_file.write_bytes(b"dummy music data")
    dialogue_file = tmp_path / "dialogue.mp3"
    dialogue_file.write_bytes(b"dummy dialogue data")

    mock_res = MagicMock()
    mock_res.returncode = 0

    with patch("subprocess.run", return_value=mock_res) as mock_subproc:
        out_path = apply_dialogue_audio_ducking(
            music_path=str(music_file),
            dialogue_path=str(dialogue_file),
            output_dir=str(tmp_path),
            ducking_db=-12.0,
            mock_mode=False,
        )
        assert out_path.endswith(".aac") or out_path.endswith(".mp3")
        mock_subproc.assert_called_once()
        cmd = mock_subproc.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert str(music_file) in cmd
        assert str(dialogue_file) in cmd
        assert "-filter_complex" in cmd
        filter_idx = cmd.index("-filter_complex")
        filter_str = cmd[filter_idx + 1]
        assert "sidechaincompress" in filter_str
        assert "threshold=0.2512" in filter_str


def test_apply_dialogue_audio_ducking_custom_ducking_db(tmp_path):
    from omnimash.stitching.audio_overlay import apply_dialogue_audio_ducking

    music_file = tmp_path / "music.mp3"
    music_file.write_bytes(b"dummy music data")
    dialogue_file = tmp_path / "dialogue.mp3"
    dialogue_file.write_bytes(b"dummy dialogue data")

    mock_res = MagicMock()
    mock_res.returncode = 0

    with patch("subprocess.run", return_value=mock_res) as mock_subproc:
        apply_dialogue_audio_ducking(
            music_path=str(music_file),
            dialogue_path=str(dialogue_file),
            output_dir=str(tmp_path),
            ducking_db=-18.0,
            mock_mode=False,
        )
        cmd = mock_subproc.call_args[0][0]
        filter_str = cmd[cmd.index("-filter_complex") + 1]
        assert "threshold=0.1259" in filter_str


def test_apply_dialogue_audio_ducking_ffmpeg_failure(tmp_path):
    from omnimash.stitching.audio_overlay import apply_dialogue_audio_ducking

    fail_res = MagicMock()
    fail_res.returncode = 1
    fail_res.stderr = "FFmpeg processing error"

    with patch("subprocess.run", return_value=fail_res):
        out_path = apply_dialogue_audio_ducking(
            music_path="/invalid/music.mp3",
            dialogue_path="/invalid/dialogue.mp3",
            output_dir=str(tmp_path),
            mock_mode=False,
        )
        assert os.path.exists(out_path)
        with open(out_path, "r") as f:
            assert "fallback ducked audio content" in f.read()


def test_apply_dialogue_audio_ducking_mock_mode(tmp_path):
    from omnimash.stitching.audio_overlay import apply_dialogue_audio_ducking

    out_path = apply_dialogue_audio_ducking(
        music_path="/static/music.mp3",
        dialogue_path="/static/voice.mp3",
        output_dir=str(tmp_path),
        mock_mode=True,
    )
    assert os.path.exists(out_path)
    with open(out_path, "r") as f:
        assert "mock ducked audio" in f.read()


def test_stitch_storyboard_master_wires_audio_ducking(tmp_path):
    stitcher = VideoStitcher(mock_mode=True)
    music_file = str(tmp_path / "music.mp3")
    narrator_file = str(tmp_path / "dialogue.mp3")

    with (
        patch(
            "omnimash.stitching.stitcher.apply_dialogue_audio_ducking",
            return_value=str(tmp_path / "ducked.aac"),
        ) as mock_ducking,
        patch.object(stitcher, "concatenate_clips", return_value=str(tmp_path / "master.mp4")) as mock_concat,
    ):
        result = stitcher.stitch_storyboard_master(
            shot_clips=[],
            background_music_path=music_file,
            narrator_audio_paths=[narrator_file],
            output_dir=str(tmp_path),
        )

        mock_ducking.assert_called_once_with(
            music_path=music_file,
            dialogue_path=narrator_file,
            output_dir=str(tmp_path),
            mock_mode=True,
        )
        mock_concat.assert_called_once_with(
            clip_paths=[],
            output_dir=str(tmp_path),
            session_id=None,
            master_audio_path=str(tmp_path / "ducked.aac"),
        )
        assert result == str(tmp_path / "master.mp4")


