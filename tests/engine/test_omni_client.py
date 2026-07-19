import os
from omnimash.engine.omni_client import (
    OmniFlashClient,
    _generate_dynamic_audio_wav,
    ensure_rendered_video,
)


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


def test_dynamic_audio_synthesizer_genres():
    wav_path = "/tmp/test_dynamic_beat.wav"

    # 1. 140 BPM Drill
    bpm_drill = _generate_dynamic_audio_wav(
        wav_path, prompt="140 BPM UK Drill 808s", duration=1
    )
    assert bpm_drill == 140
    assert os.path.exists(wav_path)

    # 2. 85 BPM Anime Lo-Fi
    bpm_anime = _generate_dynamic_audio_wav(
        wav_path, prompt="VHS anime lo-fi city pop", duration=1
    )
    assert bpm_anime == 85

    # 3. 110 BPM Cyberpunk
    bpm_cyber = _generate_dynamic_audio_wav(
        wav_path, prompt="Cyberpunk synthwave arpeggios", duration=1
    )
    assert bpm_cyber == 110

    # 4. 120 BPM Boom-Bap default
    bpm_boom = _generate_dynamic_audio_wav(
        wav_path, prompt="Gaunt wizard in 90s rap video", duration=1
    )
    assert bpm_boom == 120


def test_ensure_rendered_video_creates_playable_mp4():
    video_url = "/static/rendered/test_dynamic_render.mp4"
    ensure_rendered_video(video_url, prompt="140 BPM UK Drill 808s")
    rel_path = video_url.lstrip("/")
    assert os.path.exists(rel_path)
    # Clean up test artifact
    if os.path.exists(rel_path):
        os.remove(rel_path)


def test_ensure_rendered_video_procedural_visualizer_fallback():
    video_url = "/static/rendered/test_procedural_render.mp4"
    ensure_rendered_video(video_url, prompt="140 BPM UK Drill 808s")
    rel_path = video_url.lstrip("/")
    assert os.path.exists(rel_path)
    assert os.path.getsize(rel_path) > 10000
    if os.path.exists(rel_path):
        os.remove(rel_path)


def test_dynamic_audio_wav_ducks_instrumental_when_voiceover_present():
    wav_no_vo = "temp_beat_no_vo.wav"
    wav_vo = "temp_beat_vo.wav"
    _generate_dynamic_audio_wav(
        wav_no_vo, prompt="120 BPM boom-bap", voiceover=None, duration=1
    )
    _generate_dynamic_audio_wav(
        wav_vo, prompt="120 BPM boom-bap", voiceover="Gaunt wizard speaking", duration=1
    )

    assert os.path.exists(wav_no_vo)
    assert os.path.exists(wav_vo)
    for p in [wav_no_vo, wav_vo]:
        if os.path.exists(p):
            os.remove(p)
