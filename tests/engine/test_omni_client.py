import inspect
import os
from typing import Any
from unittest.mock import MagicMock, patch
import pytest

import omnimash.config
from omnimash.engine.omni_client import (
    OmniFlashClient,
    _abstract_prompt_for_responsible_ai,
    _generate_dynamic_audio_wav,
    _get_relaxed_safety_settings,
    ensure_rendered_video,
)
import omnimash.engine.omni_client as omni_module


def test_zero_veo_or_tts_references() -> None:
    """Verify that Veo and external TTS references are completely removed."""
    assert not hasattr(OmniFlashClient, "_generate_live_veo_video")
    src = inspect.getsource(omni_module)
    assert "veo-2.0-generate-001" not in src
    assert "generate_live_veo_video" not in src
    assert "gtts" not in src
    assert "gTTS" not in src
    assert "flite" not in src


def test_dual_strategy_client_initialization_both_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify OmniFlashClient initializes both Developer API and Vertex AI clients and prefers Developer API when API key is present."""
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

        # Verify primary genai client is set to Developer API by default when API key is provided
        assert client._genai_client == client._dev_client


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
        # Set active client to vertex to test manual or error-triggered switch
        client._genai_client = client._vertex_client
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


def test_ensure_rendered_video_clean_voiceover_fallback() -> None:
    video_url = "/static/rendered/test_clean_fallback.mp4"
    rel_path = video_url.lstrip("/")
    if os.path.exists(rel_path):
        os.remove(rel_path)
    try:
        ensure_rendered_video(
            video_url,
            prompt='Dialogue: "I been cooking potions since first year."',
            voiceover=None,
        )
        assert os.path.exists(rel_path)
        assert os.path.getsize(rel_path) > 10000
    finally:
        if os.path.exists(rel_path):
            os.remove(rel_path)


@pytest.mark.parametrize(
    ("prompt", "restricted_keywords", "expected_snippets"),
    [
        (
            "Harry Potter and Severus Snape meet Hermione Granger, Ron Weasley, Draco Malfoy, Voldemort, Dumbledore, Hagrid, and McGonagall at Hogwarts and Dripwarts.",
            [
                "Harry Potter",
                "Harry",
                "Severus Snape",
                "Snape",
                "Hermione Granger",
                "Hermione",
                "Ron Weasley",
                "Ron",
                "Draco Malfoy",
                "Draco",
                "Voldemort",
                "Dumbledore",
                "Hagrid",
                "McGonagall",
                "Hogwarts",
                "Dripwarts",
            ],
            [
                "young wizard student",
                "potion master wizard",
                "witch student",
                "red-haired wizard student",
                "blonde rival wizard student",
                "dark sorcerer",
                "elderly headmaster wizard",
                "giant gamekeeper",
                "distinguished witch professor",
                "magical stone castle academy",
                "hip-hop magical castle academy",
            ],
        ),
        (
            "Darth Vader and Luke Skywalker battle Yoda, Obi-Wan Kenobi, Kenobi, Han Solo, Chewbacca, Kylo Ren, and a Stormtrooper in space.",
            [
                "Darth Vader",
                "Luke Skywalker",
                "Yoda",
                "Obi-Wan Kenobi",
                "Kenobi",
                "Han Solo",
                "Chewbacca",
                "Kylo Ren",
                "Stormtrooper",
            ],
            [
                "dark armored galactic villain",
                "galactic farmboy knight",
                "grand master alien",
                "galactic mentor knight",
                "interstellar smuggler pilot",
                "furry bipedal alien warrior",
                "conflicted masked dark galactic warrior",
                "futuristic galactic soldier",
            ],
        ),
        (
            "Batman, Bruce Wayne, Joker, Superman, Spider-Man, Spiderman, Iron Man, Tony Stark, Thanos, Thor, Wolverine, Captain America, and Hulk team up.",
            [
                "Batman",
                "Bruce Wayne",
                "Joker",
                "Superman",
                "Spider-Man",
                "Spiderman",
                "Iron Man",
                "Tony Stark",
                "Thanos",
                "Thor",
                "Wolverine",
                "Captain America",
                "Hulk",
            ],
            [
                "masked superhero detective",
                "billionaire philanthropist vigilante",
                "flamboyant villain",
                "powerful superhero in a red cape",
                "agile superhero in a red and blue webbed suit",
                "high-tech armored superhero",
                "charismatic billionaire genius inventor",
                "purple galactic titan warrior",
                "mighty thunder warrior god",
                "fierce mutant brawler",
                "patriotic super-soldier hero",
                "giant muscular green powerhouse behemoth",
            ],
        ),
        (
            "Gandalf, Frodo, Sauron, Gollum, Legolas, and Aragorn embark on a quest.",
            [
                "Gandalf",
                "Frodo",
                "Sauron",
                "Gollum",
                "Legolas",
                "Aragorn",
            ],
            [
                "wise gray-bearded wizard",
                "halfling adventurer",
                "menacing dark lord",
                "cave-dwelling creature",
                "elven archer",
                "weathered ranger king warrior",
            ],
        ),
        (
            "Goku, Naruto, Mario, Luigi, Bowser, Sonic, Master Chief, and Pikachu in a crossover game.",
            [
                "Goku",
                "Naruto",
                "Mario",
                "Luigi",
                "Bowser",
                "Sonic",
                "Master Chief",
                "Pikachu",
            ],
            [
                "martial arts warrior",
                "energetic ninja",
                "cheerful plumber hero",
                "tall cheerful plumber hero",
                "spiked turtle dragon king",
                "speedy blue anthropomorphic hedgehog hero",
                "green powered combat armor",
                "yellow electric rodent creature",
            ],
        ),
        (
            "Gordon Ramsay, Julia Child, Snoop Dogg, Eminem, Drake, Kendrick Lamar, Kanye West, Ye, Beyonce, Taylor Swift, Elon Musk, Donald Trump, Kamala Harris, Joe Biden, Barack Obama, Gucci Mane, and Jeezy perform together.",
            [
                "Gordon Ramsay",
                "Julia Child",
                "Snoop Dogg",
                "Eminem",
                "Drake",
                "Kendrick Lamar",
                "Kanye West",
                "Ye",
                "Beyonce",
                "Taylor Swift",
                "Elon Musk",
                "Donald Trump",
                "Kamala Harris",
                "Joe Biden",
                "Barack Obama",
                "Gucci Mane",
                "Jeezy",
            ],
            [
                "celebrity master chef",
                "television chef",
                "laid-back hip-hop legend",
                "fast-rhyming hip-hop superstar",
                "melodic hip-hop star",
                "visionary poetic hip-hop artist",
                "music producer and fashion designer",
                "avant-garde hip-hop artist",
                "glamorous global pop queen superstar",
                "famous pop superstar singer",
                "tech entrepreneur",
                "charismatic business executive",
                "prominent political leader",
                "senior statesman political leader",
                "eloquent former statesman leader",
                "trap music pioneer",
                "southern trap hip-hop icon",
            ],
        ),
    ],
)
def test_abstract_prompt_for_responsible_ai_expanded(
    prompt: str, restricted_keywords: list[str], expected_snippets: list[str]
) -> None:
    abstracted = _abstract_prompt_for_responsible_ai(prompt)
    import re

    for kw in restricted_keywords:
        pattern = rf"\b{re.escape(kw)}\b"
        assert not re.search(pattern, abstracted, re.IGNORECASE), (
            f"Restricted keyword '{kw}' found in abstracted prompt: {abstracted}"
        )

    for snippet in expected_snippets:
        assert snippet.lower() in abstracted.lower(), (
            f"Expected archetype snippet '{snippet}' not found in abstracted prompt: {abstracted}"
        )


def test_get_relaxed_safety_settings_sdk() -> None:
    """Verify _get_relaxed_safety_settings returns 5 types.SafetySetting objects with BLOCK_NONE thresholds when genai SDK is available."""
    settings = _get_relaxed_safety_settings()
    assert settings is not None
    assert len(settings) == 5

    from google.genai import types

    expected_categories = {
        types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
    }

    found_categories = set()
    for setting in settings:
        assert isinstance(setting, types.SafetySetting)
        assert setting.threshold == types.HarmBlockThreshold.BLOCK_NONE
        found_categories.add(setting.category)

    assert found_categories == expected_categories


def test_get_relaxed_safety_settings_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _get_relaxed_safety_settings fallback when genai is not available."""
    monkeypatch.setattr(omni_module, "genai", None)
    settings = _get_relaxed_safety_settings()
    assert settings is not None
    assert len(settings) == 5

    expected_categories = {
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
        "HARM_CATEGORY_CIVIC_INTEGRITY",
    }

    found_categories = set()
    for setting in settings:
        assert isinstance(setting, dict)
        assert setting.get("threshold") == "BLOCK_NONE"
        found_categories.add(setting.get("category"))

    assert found_categories == expected_categories


def test_generate_live_omni_flash_video_kwargs(tmp_path: Any) -> None:
    """Verify that _generate_live_omni_flash_video passes clean kwargs to interactions.create without unsupported safety_settings."""
    import base64

    client = OmniFlashClient(mock_mode=False)
    mock_interactions = MagicMock()
    fake_video_bytes = base64.b64encode(b"fake_mp4_video_data").decode("utf-8")
    mock_output_video = MagicMock(data=fake_video_bytes)
    mock_interactions.create.return_value = MagicMock(
        id="inter_test_456", output_video=mock_output_video
    )

    mock_genai_client = MagicMock()
    mock_genai_client.interactions = mock_interactions
    client._genai_client = mock_genai_client

    target_file = str(tmp_path / "test_out.mp4")
    success, inter_id, error = client._generate_live_omni_flash_video(
        prompt="A magical wizard rap duel", target_rel_path=target_file
    )

    assert success is True
    assert inter_id == "inter_test_456"
    assert error is None

    assert mock_interactions.create.called
    call_kwargs = mock_interactions.create.call_args.kwargs
    assert call_kwargs["model"] == "gemini-omni-flash-preview"
    assert "safety_settings" not in call_kwargs
