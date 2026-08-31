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


