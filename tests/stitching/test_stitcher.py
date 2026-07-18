from omnimash.stitching.stitcher import VideoStitcher


def test_stitch_clips_mock(tmp_path):
    stitcher = VideoStitcher(mock_mode=True)
    clip_urls = ["/static/clip1.mp4", "/static/clip2.mp4", "/static/clip3.mp4"]
    output_path = stitcher.concatenate_clips(clip_urls, output_dir=str(tmp_path))
    assert output_path.endswith("_stitched.mp4")
