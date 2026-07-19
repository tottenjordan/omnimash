from omnimash.ingestion.media_extractor import MediaExtractor, ReferenceAnalysisReport


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
