from omnimash.engine.omni_client import OmniFlashClient


def test_initial_generation_mock():
    client = OmniFlashClient(mock_mode=True)
    res = client.generate_clip("Snape in a 90s rap video")
    assert res.video_url.endswith(".mp4")
    assert res.interaction_thread_id is not None
    assert res.duration_seconds == 10


def test_conversational_diff_mock():
    client = OmniFlashClient(mock_mode=True)
    res = client.apply_interaction_diff(
        interaction_thread_id="thread_123",
        diff_prompt="Swap the wand for a vintage microphone",
    )
    assert res.video_url.endswith(".mp4")
    assert res.interaction_thread_id == "thread_123"


def test_start_thread_from_video_mock():
    client = OmniFlashClient(mock_mode=True)
    res = client.start_thread_from_video(
        base_video_url="/static/rendered/clip1.mp4",
        initial_prompt="Add cyberpunk rain",
    )
    assert res.interaction_thread_id.startswith("reanchored_thread_")
    assert res.video_url.endswith(".mp4")
    assert res.duration_seconds == 10
