import os
from unittest.mock import patch, MagicMock
from omnimash.stitching.stitcher import VideoStitcher


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
        assert call_kwargs.get(
            "category"
        ) == "final_masters" or "final_masters" in call_kwargs.get(
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
        assert call_kwargs.get(
            "category"
        ) == "final_masters" or "final_masters" in call_kwargs.get(
            "destination_blob_name", ""
        )


def test_stitch_clips_live_mode_copy_success(tmp_path):
    stitcher = VideoStitcher(mock_mode=False)
    clip1 = str(tmp_path / "clip1.mp4")
    clip2 = str(tmp_path / "clip2.mp4")
    clip_paths = [clip1, clip2]

    mock_res = MagicMock()
    mock_res.returncode = 0

    with (
        patch("subprocess.run", return_value=mock_res) as mock_subproc,
        patch.object(stitcher.storage, "upload_file") as mock_upload,
    ):
        out_path = stitcher.concatenate_clips(
            clip_paths, output_dir=str(tmp_path), session_id="test_session"
        )

        # Verify concat_list.txt was created
        concat_file = tmp_path / "concat_list.txt"
        assert concat_file.exists()
        lines = concat_file.read_text().splitlines()
        assert lines == [
            f"file '{os.path.abspath(clip1)}'",
            f"file '{os.path.abspath(clip2)}'",
        ]

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
            str(concat_file),
            "-c",
            "copy",
        ]
        assert cmd[10] == out_path

        # Verify GCS upload category final_masters
        mock_upload.assert_called_once()
        call_kwargs = mock_upload.call_args.kwargs
        assert call_kwargs.get(
            "category"
        ) == "final_masters" or "final_masters" in call_kwargs.get(
            "destination_blob_name", ""
        )


def test_stitch_clips_live_mode_reencode_fallback(tmp_path):
    stitcher = VideoStitcher(mock_mode=False)
    clip1 = str(tmp_path / "clip1.mp4")
    clip_paths = [clip1]

    fail_res = MagicMock()
    fail_res.returncode = 1
    success_res = MagicMock()
    success_res.returncode = 0

    with (
        patch("subprocess.run", side_effect=[fail_res, success_res]) as mock_subproc,
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
        mock_upload.assert_called_once()


def test_generate_title_card_clip_mock(tmp_path):
    stitcher = VideoStitcher(mock_mode=True)
    out_path = stitcher.generate_title_card_clip(
        title_text="Trapwarts",
        subtitle_text="Premium Specs",
        duration_seconds=2.0,
        style="gothic_gold",
        output_dir=str(tmp_path),
    )
    assert os.path.exists(out_path)
    assert out_path.endswith(".mp4")
    with open(out_path, "r") as f:
        content = f.read()
    assert "mock title card" in content


def test_generate_title_card_clip_live(tmp_path):
    stitcher = VideoStitcher(mock_mode=False)
    mock_res = MagicMock()
    mock_res.returncode = 0

    with patch("subprocess.run", return_value=mock_res) as mock_subproc:
        out_path = stitcher.generate_title_card_clip(
            title_text="Live Test",
            subtitle_text="Subtitle",
            duration_seconds=3.0,
            style="neon_cyber",
            output_dir=str(tmp_path),
        )
        assert out_path.endswith(".mp4")
        mock_subproc.assert_called_once()
        cmd = mock_subproc.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert "-loop" in cmd
        assert "-c:v" in cmd and "libx264" in cmd
        assert "-pix_fmt" in cmd and "yuv420p" in cmd


def test_stitch_storyboard_master_mock(tmp_path):
    stitcher = VideoStitcher(mock_mode=True)
    shot_clips = ["/static/shot1.mp4", "/static/shot2.mp4"]
    title_cards = [
        {"insert_at": 0, "title": "Trapwarts", "subtitle": "Premium Specs"},
        {"insert_at": 2, "title": "The End", "subtitle": "Goodbye"},
    ]

    with patch.object(stitcher.storage, "upload_file") as mock_upload:
        mock_upload.return_value = "https://storage.googleapis.com/test/master.mp4"
        out_path = stitcher.stitch_storyboard_master(
            shot_clips=shot_clips,
            title_cards=title_cards,
            background_music_path="/static/bgm.mp3",
            output_dir=str(tmp_path),
            session_id="session_123",
        )
        assert os.path.exists(out_path)
        assert out_path.endswith("_stitched.mp4")
        mock_upload.assert_called_once()


def test_stitch_storyboard_master_live(tmp_path):
    stitcher = VideoStitcher(mock_mode=False)
    shot_clips = [str(tmp_path / "shot1.mp4"), str(tmp_path / "shot2.mp4")]
    title_cards = [
        {"insert_at": 0, "title": "Intro", "subtitle": "Start"},
    ]

    fake_card_clip = str(tmp_path / "title_card_0.mp4")

    with (
        patch.object(stitcher, "generate_title_card_clip", return_value=fake_card_clip) as mock_gen_card,
        patch.object(stitcher, "concatenate_clips", return_value=str(tmp_path / "master_stitched.mp4")) as mock_concat,
    ):
        result = stitcher.stitch_storyboard_master(
            shot_clips=shot_clips,
            title_cards=title_cards,
            narrator_audio_paths=["/static/voiceover.mp3"],
            output_dir=str(tmp_path),
            session_id="session_456",
        )

        assert result.endswith("master_stitched.mp4")
        mock_gen_card.assert_called_once_with(
            title_text="Intro",
            subtitle_text="Start",
            duration_seconds=3.0,
            style="gothic_gold",
            output_dir=str(tmp_path),
        )
        mock_concat.assert_called_once_with(
            clip_paths=[fake_card_clip, shot_clips[0], shot_clips[1]],
            output_dir=str(tmp_path),
            session_id="session_456",
            master_audio_path="/static/voiceover.mp3",
        )

