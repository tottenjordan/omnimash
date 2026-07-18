from omnimash.ingestion.media_extractor import MediaExtractor


def test_extract_reference_mock():
    extractor = MediaExtractor(mock_mode=True)
    ref = extractor.process_youtube_url("https://www.youtube.com/watch?v=mock_video")
    assert ref.is_valid is True
    assert len(ref.keyframes) > 0
    assert ref.audio_track_path is not None
