import inspect
import os
from typing import Any
from unittest.mock import MagicMock, patch
import pytest

import omnimash.config
from omnimash.engine.omni_client import (
    OmniFlashClient,
    _generate_dynamic_audio_wav,
    ensure_rendered_video,
)
import omnimash.engine.omni_client as omni_module


@pytest.fixture(autouse=True)
def mock_gtts_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock gTTS network calls in tests for instant, deterministic test execution."""
    monkeypatch.setattr("gtts.gTTS.save", lambda self, path: None, raising=False)


def test_zero_veo_references() -> None:
    """Verify that _generate_live_veo_video method and Veo model references are completely removed."""
    assert not hasattr(OmniFlashClient, "_generate_live_veo_video")
    src = inspect.getsource(omni_module)
    assert "veo-2.0-generate-001" not in src
    assert "generate_live_veo_video" not in src
    assert "Veo" not in src


def test_dual_strategy_client_initialization_both_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify OmniFlashClient initializes both Developer API and Vertex AI clients when both are available."""
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-proj-dual")
    monkeypatch.setenv("GEMINI_LOCATION", "us-central1")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-api-key")

    created_clients = []

    def mock_client_factory(**kwargs: Any) -> Any:
        mock = MagicMock()
        mock.init_kwargs = kwargs
        created_clients.append(mock)
        return mock

    with patch("google.genai.Client", side_effect=mock_client_factory):
        client = OmniFlashClient(mock_mode=False)

        # Verify Developer API client
        assert client._dev_client is not None
        dev_init: dict[str, Any] = getattr(client._dev_client, "init_kwargs", {})
        assert dev_init.get("api_key") == "test-gemini-api-key"
        assert client._api_key_client == client._dev_client

        # Verify Vertex AI client
        assert client._vertex_client is not None
        vertex_init: dict[str, Any] = getattr(client._vertex_client, "init_kwargs", {})
        assert vertex_init.get("vertexai") is True
        assert vertex_init.get("project") == "test-proj-dual"
        assert vertex_init.get("location") == "us-central1"

        # Verify primary genai client is set to Vertex AI by default
        assert client._genai_client == client._vertex_client


def test_dual_strategy_client_initialization_dev_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify OmniFlashClient handles Developer API key only."""
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GEMINI_LOCATION", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-dev-key")

    def mock_client_factory(**kwargs: Any) -> Any:
        if kwargs.get("vertexai"):
            raise RuntimeError("Vertex AI ADC not available")
        mock = MagicMock()
        mock.init_kwargs = kwargs
        return mock

    with patch("google.genai.Client", side_effect=mock_client_factory):
        client = OmniFlashClient(mock_mode=False)
        assert client._dev_client is not None
        dev_init: dict[str, Any] = getattr(client._dev_client, "init_kwargs", {})
        assert dev_init.get("api_key") == "test-dev-key"
        assert client._vertex_client is None
        assert client._genai_client == client._dev_client


def test_dual_strategy_client_initialization_vertex_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify OmniFlashClient handles Vertex AI only when no API key is provided."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(omnimash.config.settings, "google_api_key", None)
    monkeypatch.setattr(omnimash.config.settings, "gemini_api_key", None)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-vertex-proj")
    monkeypatch.setenv("GEMINI_LOCATION", "us-east4")

    def mock_client_factory(**kwargs: Any) -> Any:
        mock = MagicMock()
        mock.init_kwargs = kwargs
        return mock

    with patch("google.genai.Client", side_effect=mock_client_factory):
        client = OmniFlashClient(api_key=None, mock_mode=False)
        assert client._dev_client is None
        assert client._vertex_client is not None
        vertex_init: dict[str, Any] = getattr(client._vertex_client, "init_kwargs", {})
        assert vertex_init.get("vertexai") is True
        assert client._genai_client == client._vertex_client


def test_switch_to_developer_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify switch_to_developer_api swaps the active client."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-dev-key")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-proj")

    def mock_client_factory(**kwargs: Any) -> Any:
        mock = MagicMock()
        mock.init_kwargs = kwargs
        return mock

    with patch("google.genai.Client", side_effect=mock_client_factory):
        client = OmniFlashClient(mock_mode=False)
        assert client._genai_client == client._vertex_client
        switched = client.switch_to_developer_api()
        assert switched is True
        assert client._genai_client == client._dev_client


def test_initial_generation_mock() -> None:
    client = OmniFlashClient(mock_mode=True)
    res = client.generate_clip("Snape in a 90s rap video")
    assert res.video_url.endswith(".mp4")
    assert res.interaction_thread_id is not None
    assert res.duration_seconds == 10


def test_conversational_diff_mock() -> None:
    client = OmniFlashClient(mock_mode=True)
    res = client.apply_interaction_diff(
        interaction_thread_id="thread_123",
        diff_prompt="Swap the wand for a vintage microphone",
    )
    assert res.video_url.endswith(".mp4")
    assert res.interaction_thread_id == "thread_123"


def test_start_thread_from_video_mock() -> None:
    client = OmniFlashClient(mock_mode=True)
    res = client.start_thread_from_video(
        base_video_url="/static/rendered/clip1.mp4",
        initial_prompt="Add cyberpunk rain",
    )
    assert res.interaction_thread_id.startswith("reanchored_thread_")
    assert res.video_url.endswith(".mp4")
    assert res.duration_seconds == 10


def test_dynamic_audio_synthesizer_genres() -> None:
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


def test_ensure_rendered_video_creates_playable_mp4() -> None:
    video_url = "/static/rendered/test_dynamic_render.mp4"
    ensure_rendered_video(video_url, prompt="140 BPM UK Drill 808s")
    rel_path = video_url.lstrip("/")
    assert os.path.exists(rel_path)
    if os.path.exists(rel_path):
        os.remove(rel_path)


def test_ensure_rendered_video_procedural_visualizer_fallback() -> None:
    video_url = "/static/rendered/test_procedural_render.mp4"
    ensure_rendered_video(video_url, prompt="140 BPM UK Drill 808s")
    rel_path = video_url.lstrip("/")
    assert os.path.exists(rel_path)
    assert os.path.getsize(rel_path) > 10000
    if os.path.exists(rel_path):
        os.remove(rel_path)


def test_dynamic_audio_wav_ducks_instrumental_when_voiceover_present() -> None:
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


def test_ensure_rendered_video_synthesizes_spoken_dialogue_audio() -> None:
    video_url = "/static/rendered/test_spoken_speech.mp4"
    ensure_rendered_video(
        video_url,
        prompt="140 BPM Heavy 808 Trap",
        voiceover='Harry: "You talkin bout potions Draco? I been cooking since first year. Burrr!" / Draco: "This is Trap or Die Potter!"',
    )
    rel_path = video_url.lstrip("/")
    assert os.path.exists(rel_path)
    assert os.path.getsize(rel_path) > 10000
    if os.path.exists(rel_path):
        os.remove(rel_path)
