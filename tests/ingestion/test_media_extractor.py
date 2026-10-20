import os

from omnimash.ingestion.media_extractor import (
    MediaExtractor,
    ParodyResearchResult,
    ReferenceAnalysisReport,
)


def test_extract_reference_mock():
    extractor = MediaExtractor(mock_mode=True)
    ref = extractor.process_youtube_url("https://www.youtube.com/watch?v=mock_video")
    assert ref.is_valid is True
    assert len(ref.keyframes) > 0
    assert ref.audio_track_path is not None


def test_media_extractor_generates_analysis_report():
    extractor = MediaExtractor(mock_mode=True)
    report = extractor.analyze_youtube_reference(
        "https://www.youtube.com/watch?v=sample_beat", session_id="sess_123"
    )
    assert isinstance(report, ReferenceAnalysisReport)
    assert report.detected_bpm == 120
    assert len(report.extracted_keyframes) >= 3
    assert "[SUBJECT ANCHOR]" in report.extracted_keyframes[0].usage_annotation
    assert len(report.dominant_colors) > 0


def test_media_extractor_parody_research():
    extractor = MediaExtractor(mock_mode=True)
    res = extractor.research_parody_clash(
        subject="Harry Potter and Draco Malfoy", aesthetic="Atlanta Trap Disstrack"
    )
    assert isinstance(res, ParodyResearchResult)
    assert len(res.suggested_props) > 0
    assert res.vibe_intensity >= 0
    assert "Trap" in res.suggested_audio or "808" in res.suggested_audio


def test_crop_3s_motion_reference_clip(tmp_path):
    extractor = MediaExtractor(mock_mode=True)
    input_video = str(tmp_path / "test_input.mp4")
    with open(input_video, "wb") as f:
        f.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")

    output_clip = extractor.crop_3s_motion_reference(input_video, start_sec=1.5)
    assert output_clip.endswith("_motion_3s.mp4")
    assert os.path.exists(output_clip)

    # Test negative start_sec is clamped gracefully
    output_clip_neg = extractor.crop_3s_motion_reference(input_video, start_sec=-5.0)
    assert output_clip_neg.endswith("_motion_3s.mp4")
    assert os.path.exists(output_clip_neg)


def test_crop_3s_motion_reference_clip_non_mock_fallback(tmp_path):
    extractor = MediaExtractor(mock_mode=False)
    input_video = str(tmp_path / "non_existent_input.mp4")
    output_clip = extractor.crop_3s_motion_reference(input_video, start_sec=0.0)
    assert output_clip.endswith("_motion_3s.mp4")
    assert os.path.exists(output_clip)
    assert os.path.getsize(output_clip) > 0


def test_generate_keyframe_jpeg_uses_scalable_font_size_and_optimized_jpeg(tmp_path, monkeypatch):
    from PIL import Image, ImageDraw

    extractor = MediaExtractor(mock_mode=True)
    out_path = str(tmp_path / "test_frame.jpg")

    recorded_text_kwargs: list[dict] = []
    recorded_save_kwargs: list[dict] = []

    orig_text = ImageDraw.ImageDraw.text
    orig_save = Image.Image.save

    def spy_text(self, xy, text, *args, **kwargs):
        recorded_text_kwargs.append(dict(kwargs))
        return orig_text(self, xy, text, *args, **kwargs)

    def spy_save(self, fp, format=None, **params):
        recorded_save_kwargs.append({"format": format, **params})
        return orig_save(self, fp, format=format, **params)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", spy_text)
    monkeypatch.setattr(Image.Image, "save", spy_save)

    res_path = extractor._generate_keyframe_jpeg(
        out_path,
        "🎯 [SUBJECT ANCHOR]: Facial Likeness & Hair Conditioning",
        "00:02",
        "#DE5FE9",
    )
    assert res_path == out_path
    assert os.path.exists(out_path)
    assert len(recorded_text_kwargs) >= 4
    assert all(
        kw.get("font_size", 0) >= 18 or kw.get("font") is not None for kw in recorded_text_kwargs
    )
    assert len(recorded_save_kwargs) == 1
    assert recorded_save_kwargs[0].get("format") == "JPEG"
    assert recorded_save_kwargs[0].get("quality") == 90
    assert recorded_save_kwargs[0].get("optimize") is True


def test_extract_reference_video_clip_ffmpeg_flags_and_subprocess_options(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    import subprocess

    extractor = MediaExtractor(mock_mode=False)
    input_video = str(tmp_path / "source.mp4")
    output_clip = str(tmp_path / "output_clip.mp4")
    with open(input_video, "wb") as f:
        f.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")

    captured_calls: list[tuple[list[str], dict]] = []

    def fake_run(cmd, **kwargs):
        captured_calls.append((list(cmd), dict(kwargs)))
        with open(output_clip, "wb") as f:
            f.write(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    res = extractor.extract_reference_video_clip(
        source_video_path=input_video,
        output_clip_path=output_clip,
        start_time_seconds=2.5,
        duration_seconds=3.0,
    )
    assert res == output_clip
    assert len(captured_calls) == 1
    cmd, kwargs = captured_calls[0]
    assert "-nostdin" in cmd
    assert "-pix_fmt" in cmd and cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert "-movflags" in cmd and cmd[cmd.index("-movflags") + 1] == "+faststart"
    assert kwargs.get("capture_output") is True
    assert kwargs.get("text") is True
    assert kwargs.get("check") is True
    assert kwargs.get("timeout") == 30


def test_analyze_youtube_reference_uses_yt_dlp_sanitize_info_when_live(monkeypatch):
    import yt_dlp

    called_ops: list[str] = []

    class DummyYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            called_ops.append("enter")
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            called_ops.append("exit")
            return False

        def extract_info(self, url, download=False):
            assert download is False
            called_ops.append(f"extract_info:{url}")
            return {"title": "Live Trap Reference Beat", "duration": 215, "description": "808 bass"}

        def sanitize_info(self, info_dict):
            called_ops.append("sanitize_info")
            return dict(info_dict)

    monkeypatch.setattr(yt_dlp, "YoutubeDL", DummyYDL)

    extractor = MediaExtractor(mock_mode=False)
    # Keep storage in mock_mode so GCS calls don't hit network
    extractor.storage.mock_mode = True

    report = extractor.analyze_youtube_reference(
        "https://www.youtube.com/watch?v=live_test", session_id="sess_yt_live"
    )
    assert "enter" in called_ops
    assert "extract_info:https://www.youtube.com/watch?v=live_test" in called_ops
    assert "sanitize_info" in called_ops
    assert "exit" in called_ops
    assert report.video_title == "Live Trap Reference Beat"
    assert report.duration_seconds == 215
