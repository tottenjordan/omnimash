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
from omnimash.prompts.compiler import CharacterRole, get_character_identifier
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
        assert os.path.getsize(rel_path) > 0
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
                "master wizard",
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
    """Verify that _generate_live_omni_flash_video passes kwargs to interactions.create with safety_settings."""
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


def test_load_reference_images_as_input_returns_base64_objects() -> None:
    """Verify that _load_reference_images_as_input returns base64 image objects for characters with reference_url."""
    import base64
    from omnimash.prompts.compiler import CharacterRole

    client = OmniFlashClient(mock_mode=True)
    char1 = CharacterRole(
        role_id="Role A",
        name="Harry",
        description="Harry Potter",
        reference_url="gs://test-bucket/harry.png",
    )
    char2 = CharacterRole(
        role_id="Role B",
        name="Draco",
        description="Draco Malfoy",
        reference_url=None,
    )
    char3 = CharacterRole(
        role_id="Role C",
        name="Snape",
        description="Severus Snape",
        reference_url="gs://test-bucket/snape.jpg",
    )

    with patch.object(
        client.storage,
        "download_blob_bytes",
        side_effect=lambda url: (
            (b"fake_png_data", "image/png")
            if "png" in url
            else (b"fake_jpg_data", "image/jpeg")
        ),
    ):
        imgs, char_map = client._load_reference_images_as_input(
            session_id="session_123", characters=[char1, char2, char3]
        )

    assert len(imgs) == 2
    assert imgs[0] == {
        "type": "image",
        "data": base64.b64encode(b"fake_png_data").decode("utf-8"),
        "mime_type": "image/png",
    }
    assert imgs[1] == {
        "type": "image",
        "data": base64.b64encode(b"fake_jpg_data").decode("utf-8"),
        "mime_type": "image/jpeg",
    }


def test_generate_live_omni_flash_video_multimodal_input(tmp_path: Any) -> None:
    """Verify _generate_live_omni_flash_video calls interactions.create with multimodal input array containing image and text objects."""
    import base64
    from omnimash.prompts.compiler import CharacterRole

    client = OmniFlashClient(mock_mode=False)
    mock_interactions = MagicMock()
    fake_video_bytes = base64.b64encode(b"fake_mp4_video_data").decode("utf-8")
    mock_output_video = MagicMock(data=fake_video_bytes)
    mock_interactions.create.return_value = MagicMock(
        id="inter_test_789", output_video=mock_output_video
    )

    mock_genai_client = MagicMock()
    mock_genai_client.interactions = mock_interactions
    client._genai_client = mock_genai_client

    char = CharacterRole(
        role_id="Role A",
        name="Harry",
        description="Harry Potter",
        reference_url="gs://test-bucket/harry.png",
    )

    with patch.object(
        client.storage,
        "download_blob_bytes",
        return_value=(b"fake_image_bytes", "image/png"),
    ):
        target_file = str(tmp_path / "test_multimodal_out.mp4")
        success, inter_id, error = client._generate_live_omni_flash_video(
            prompt="Harry Potter in a rap battle",
            target_rel_path=target_file,
            characters=[char],
            session_id="session_456",
        )

    assert success is True
    assert inter_id == "inter_test_789"
    assert error is None

    assert mock_interactions.create.called
    call_kwargs = mock_interactions.create.call_args.kwargs
    assert call_kwargs["model"] == "gemini-omni-flash-preview"

    input_arg = call_kwargs["input"]
    assert isinstance(input_arg, list)
    assert len(input_arg) == 1
    assert input_arg[0]["type"] == "user_input"
    assert len(input_arg[0]["content"]) == 2
    assert any("Spectacled Wizard Bruv" in str(x) for x in input_arg[0]["content"])


def test_generate_live_omni_flash_video_with_keyframe_starting_image_seed(
    tmp_path: Any,
) -> None:
    """Verify that keyframe_image_url is prepended as the starting image seed and tone anchor in multimodal payload."""
    from omnimash.prompts.compiler import CharacterRole

    client = OmniFlashClient(mock_mode=False)
    mock_interactions = MagicMock()
    mock_interactions.create.return_value = MagicMock(
        id="inter_keyframe_123", output_video=MagicMock(data=b"fake_mp4_video_bytes")
    )
    client._genai_client = MagicMock(interactions=mock_interactions)

    char = CharacterRole(
        role_id="Role A",
        name="Harry",
        description="Harry Potter",
        reference_url="gs://test-bucket/harry.png",
    )

    with patch.object(
        client.storage,
        "download_blob_bytes",
        return_value=(b"fake_image_bytes", "image/png"),
    ):
        target_file = str(tmp_path / "test_keyframe_seed_out.mp4")
        success, inter_id, error = client._generate_live_omni_flash_video(
            prompt="Harry Potter Climax Duel",
            target_rel_path=target_file,
            characters=[char],
            session_id="session_keyframe",
            keyframe_image_url="gs://test-bucket/keyframe_start.png",
        )

    assert success is True
    assert inter_id == "inter_keyframe_123"
    assert error is None

    assert mock_interactions.create.called
    call_kwargs = mock_interactions.create.call_args.kwargs
    input_arg = call_kwargs["input"]
    assert isinstance(input_arg, list)
    assert input_arg[0]["type"] == "user_input"
    content_list = input_arg[0]["content"]
    # Should have 2 image content dicts (keyframe seed + char ref) + 1 text directive dict
    assert len(content_list) == 3
    assert content_list[0]["type"] == "image"
    assert content_list[1]["type"] == "image"
    assert content_list[2]["type"] == "text"
    assert "Visual Tone & Starting Frame Anchor" in content_list[2]["text"]


def test_apply_interaction_diff_with_keyframe_starting_image_seed(
    tmp_path: Any,
) -> None:
    """Verify that apply_interaction_diff passes keyframe_image_url to anchor conversational edits to the existing starting frame."""
    client = OmniFlashClient(mock_mode=False)
    mock_interactions = MagicMock()
    mock_interactions.create.return_value = MagicMock(
        id="inter_diff_999", output_video=MagicMock(data=b"fake_diff_video_bytes")
    )
    client._genai_client = MagicMock(interactions=mock_interactions)

    with patch.object(
        client.storage,
        "download_blob_bytes",
        return_value=(b"fake_keyframe_bytes", "image/png"),
    ), patch.object(client.storage, "upload_file"):
        gen_res = client.apply_interaction_diff(
            interaction_thread_id="inter_parent_111",
            diff_prompt="Change lighting to neon green",
            keyframe_image_url="gs://test-bucket/existing_keyframe.png",
        )

    assert gen_res.interaction_thread_id == "inter_diff_999"
    assert mock_interactions.create.called
    call_kwargs = mock_interactions.create.call_args.kwargs
    input_arg = call_kwargs["input"]
    assert isinstance(input_arg, list)
    content_list = input_arg[0]["content"]
    assert content_list[0]["type"] == "image"
    assert "Visual Tone & Starting Frame Anchor" in content_list[1]["text"]


def test_generate_keyframe_image_with_character_roster() -> None:
    """Verify that generate_keyframe_image formats character roster header and visual consistency instructions for Gemini 3.1 Flash Image."""
    import base64
    from omnimash.prompts.compiler import CharacterRole

    client = OmniFlashClient(mock_mode=False)
    mock_genai_client = MagicMock()
    mock_models = MagicMock()
    mock_candidate = MagicMock(
        content=MagicMock(
            parts=[
                MagicMock(
                    inline_data=MagicMock(data=base64.b64encode(b"fake_png").decode("utf-8"))
                )
            ]
        )
    )
    mock_models.generate_content.return_value = MagicMock(candidates=[mock_candidate])
    mock_genai_client.models = mock_models
    client.storage = MagicMock()
    client.storage.get_gcs_uri.return_value = "gs://test-bucket/keyframes/keyframe_test.png"

    char = CharacterRole(
        role_id="Role A",
        name="Harry",
        description="Young spectacled wizard",
        reference_url="gs://test-bucket/harry_ref.png",
        aesthetic_tags=["Cartier Glasses", "Oversized Tee"],
    )

    with patch("google.genai.Client", return_value=mock_genai_client), patch.object(
        client, "_fetch_image_bytes", return_value=(b"fake_ref_bytes", "image/png")
    ):
        res_url = client.generate_keyframe_image(
            prompt="Harry Potter in potion class",
            style_tone="Gothic Trap",
            characters=[char],
        )

    assert "keyframe" in res_url
    assert mock_models.generate_content.called
    call_kwargs = mock_models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-3.1-flash-image"
    contents = call_kwargs["contents"]
    assert len(contents) == 2  # 1 image part + 1 prompt text
    prompt_str = contents[1]
    assert "# Character Roster & Visual Directives:" in prompt_str
    assert f"- {get_character_identifier(char)}: Young spectacled wizard [Style: Cartier Glasses, Oversized Tee] (Reference Image: @Image1)" in prompt_str


def test_generate_keyframe_image_with_anchor_seed() -> None:
    """Verify generate_keyframe_image attaches anchor_keyframe_url as @Image1 and prepends consistency instructions."""
    import base64
    from omnimash.prompts.compiler import CharacterRole

    client = OmniFlashClient(mock_mode=False)
    mock_genai_client = MagicMock()
    mock_models = MagicMock()
    mock_candidate = MagicMock(
        content=MagicMock(
            parts=[
                MagicMock(
                    inline_data=MagicMock(data=base64.b64encode(b"fake_png").decode("utf-8"))
                )
            ]
        )
    )
    mock_models.generate_content.return_value = MagicMock(candidates=[mock_candidate])
    mock_genai_client.models = mock_models
    client.storage = MagicMock()
    client.storage.get_gcs_uri.return_value = "gs://test-bucket/keyframes/keyframe_shot2.png"

    char = CharacterRole(
        role_id="Role A",
        name="Harry",
        description="Young spectacled wizard",
        reference_url="gs://test-bucket/harry_ref.png",
    )

    def mock_fetch_bytes(url: str):
        if url == "gs://test-bucket/anchor_shot1.png":
            return (b"anchor_bytes", "image/png")
        if url == "gs://test-bucket/harry_ref.png":
            return (b"char_bytes", "image/png")
        return (b"", "image/png")

    with patch("google.genai.Client", return_value=mock_genai_client), patch.object(
        client, "_fetch_image_bytes", side_effect=mock_fetch_bytes
    ):
        res_url = client.generate_keyframe_image(
            prompt="Harry running through hallway",
            style_tone="Gothic Trap",
            characters=[char],
            anchor_keyframe_url="gs://test-bucket/anchor_shot1.png",
        )

    assert "keyframe" in res_url
    assert mock_models.generate_content.called
    call_kwargs = mock_models.generate_content.call_args.kwargs
    contents = call_kwargs["contents"]
    assert len(contents) == 3
    prompt_str = contents[2]
    assert "Maintain exact subject face, character likeness, wardrobe baseline, and environmental lighting from <FIRST_FRAME>@Image1 while rendering the new action/angle." in prompt_str


def test_load_reference_images_logs_diagnostics(
    caplog: pytest.LogCaptureFixture, tmp_path: Any
) -> None:
    """Verify diagnostic logs during reference image loading and payload construction."""
    import base64
    import logging
    from omnimash.prompts.compiler import CharacterRole

    client = OmniFlashClient(mock_mode=False)

    char1 = CharacterRole(
        role_id="Role A",
        name="Harry",
        description="Harry Potter",
        reference_url="gs://test-bucket/harry.png",
    )
    char2 = CharacterRole(
        role_id="Role B",
        name="Draco",
        description="Draco Malfoy",
        reference_url=None,
    )
    char3 = CharacterRole(
        role_id="Role C",
        name="Snape",
        description="Severus Snape",
        reference_url="gs://test-bucket/snape.jpg",
    )

    def mock_download(url: str) -> tuple[bytes, str]:
        if "harry" in url:
            return b"fake_harry_png", "image/png"
        return b"", ""

    with caplog.at_level(logging.INFO, logger="omnimash.engine"):
        with patch.object(
            client.storage, "download_blob_bytes", side_effect=mock_download
        ):
            imgs, char_map = client._load_reference_images_as_input(
                session_id="session_123", characters=[char1, char2, char3]
            )

    assert len(imgs) == 1
    assert char_map.get("Role A") == 1
    assert char_map.get("Harry") == 1

    mock_interactions = MagicMock()
    fake_video_bytes = base64.b64encode(b"fake_mp4_video_data").decode("utf-8")
    mock_output_video = MagicMock(data=fake_video_bytes)
    mock_interactions.create.return_value = MagicMock(
        id="inter_test_999", output_video=mock_output_video
    )
    mock_genai_client = MagicMock()
    mock_genai_client.interactions = mock_interactions
    client._genai_client = mock_genai_client

    target_file = str(tmp_path / "test_diag_out.mp4")
    with caplog.at_level(logging.INFO, logger="omnimash.engine"):
        with patch.object(
            client.storage, "download_blob_bytes", side_effect=mock_download
        ):
            client._generate_live_omni_flash_video(
                prompt="Harry in rap battle",
                target_rel_path=target_file,
                characters=[char1],
            )


def test_generate_live_omni_flash_video_includes_safety_settings(tmp_path: Any) -> None:
    """Verify that _generate_live_omni_flash_video attaches relaxed safety_settings in kwargs."""
    import base64

    client = OmniFlashClient(mock_mode=False)
    mock_interactions = MagicMock()
    fake_video_bytes = base64.b64encode(b"fake_mp4_video_data").decode("utf-8")
    mock_output_video = MagicMock(data=fake_video_bytes)
    mock_interactions.create.return_value = MagicMock(
        id="inter_test_safety", output_video=mock_output_video
    )

    mock_genai_client = MagicMock()
    mock_genai_client.interactions = mock_interactions
    client._genai_client = mock_genai_client

    target_file = str(tmp_path / "test_safety_out.mp4")
    success, inter_id, error = client._generate_live_omni_flash_video(
        prompt="A wizard duel", target_rel_path=target_file
    )

    assert success is True
    assert mock_interactions.create.called
    call_kwargs = mock_interactions.create.call_args.kwargs
    assert "safety_settings" not in call_kwargs


def test_abstract_prompt_handles_parody_names() -> None:
    """Verify abstract prompt for responsible AI replaces parody character names."""
    prompt = "Swagrid and Ollivander talk to Ice-Vander and Ice Vander in the shop."
    res = _abstract_prompt_for_responsible_ai(prompt)
    assert "swagrid" not in res.lower()
    assert "ollivander" not in res.lower()
    assert "ice-vander" not in res.lower()
    assert "ice vander" not in res.lower()
    assert "a towering friendly gamekeeper in a fur coat" in res
    assert "an elderly shopkeeper wandmaker wizard" in res
    assert "an elderly iced-out shopkeeper wandmaker wizard" in res


def test_abstract_prompt_sanitizes_syrup_and_foam_cup_terms() -> None:
    """Verify abstract prompt for responsible AI sanitizes syrup, polystyrene foam cup, cup stacking, and volatile substance parody terms."""
    prompt = (
        "He is holding a white polystyrene foam cup that is sizzling as its glowing toxic-green contents eat through the cup. "
        "Totti, this Basilisk syrup is eating straight through the enchanted thermoses! "
        "Triple stack the cups, blood. We can't drop this tonight, my G, it's too volatile!"
    )
    res = _abstract_prompt_for_responsible_ai(prompt)
    assert "basilisk syrup" not in res.lower()
    assert "polystyrene foam cup" not in res.lower()
    assert "eat through the cup" not in res.lower()
    assert "eating straight through" not in res.lower()
    assert "triple stack the cups" not in res.lower()
    assert "too volatile" not in res.lower()
    assert "magical sparkling elixir" in res
    assert "enchanted crystal chalice" in res
    assert "sparkle inside the goblet" in res
    assert "sparkling brightly inside" in res
    assert "pour the elixir" in res
    assert "too potent for ordinary wizards" in res

    # Also verify general foam/styrofoam cups, standalone syrup, and cube blood
    extra_prompt = "Double foam cups and white styrofoam cups with cube blood and syrup."
    extra_res = _abstract_prompt_for_responsible_ai(extra_prompt)
    assert "golden goblet" in extra_res
    assert "ice cube" in extra_res
    assert "magical sparkling elixir" in extra_res


def test_generate_keyframe_image_mock_mode() -> None:
    """Verify generate_keyframe_image returns a valid base64 SVG data URI in mock mode."""
    client = OmniFlashClient(mock_mode=True)
    uri = client.generate_keyframe_image(
        prompt="A dramatic wizard duel at dusk", style_tone="cinematic"
    )
    assert uri.startswith("data:image/svg+xml;base64,")
    import base64
    decoded = base64.b64decode(uri.split("base64,")[1]).decode("utf-8")
    assert "KEYFRAME PREVIEW DIRECTIVE" in decoded
    assert "dramatic wizard duel" in decoded


def test_generate_keyframe_image_verifies_gemini_flash_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify generate_keyframe_image uses Gemini 2.5 Flash when creating GenAI client."""
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-proj-keyframe")
    monkeypatch.setenv("GEMINI_LOCATION", "us-central1")

    created_clients: list[MagicMock] = []

    def mock_client_factory(**kwargs: Any) -> Any:
        mock = MagicMock()
        mock.init_kwargs = kwargs
        fake_resp = MagicMock()
        fake_resp.candidates = []
        mock.models.generate_content.return_value = fake_resp
        created_clients.append(mock)
        return mock

    with patch("google.genai.Client", side_effect=mock_client_factory):
        client = OmniFlashClient(mock_mode=False)
        created_clients.clear()

        uri = client.generate_keyframe_image(
            prompt="Cyberpunk street keyframe", style_tone="neon"
        )

        assert len(created_clients) == 1
        client_init = created_clients[0].init_kwargs
        assert client_init.get("vertexai") is True
        assert client_init.get("project") == "test-proj-keyframe"

        created_clients[0].models.generate_content.assert_called_once()
        gen_kwargs = created_clients[0].models.generate_content.call_args.kwargs
        assert gen_kwargs.get("model") == "gemini-3.1-flash-image"
        assert any("Cyberpunk street keyframe" in str(c) for c in gen_kwargs.get("contents", []))
        assert uri is not None


def test_generate_keyframe_image_fallback_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify generate_keyframe_image falls back to base64 SVG data URI when client call fails."""
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-proj-fail")

    def mock_client_factory(**kwargs: Any) -> Any:
        mock = MagicMock()
        mock.models.generate_content.side_effect = RuntimeError("Generation failed")
        return mock

    with patch("google.genai.Client", side_effect=mock_client_factory):
        client = OmniFlashClient(mock_mode=False)
        uri = client.generate_keyframe_image("Failing prompt", style_tone="dark")
        assert uri.startswith("data:image/svg+xml;base64,")
        import base64
        decoded = base64.b64decode(uri.split("base64,")[1]).decode("utf-8")
        assert "Failing prompt" in decoded


def test_generate_keyframe_image_with_reference_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify generate_keyframe_image passes reference images to gemini-3.1-flash-image."""
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-proj-ref")

    created_clients: list[MagicMock] = []

    def mock_client_factory(**kwargs: Any) -> Any:
        mock = MagicMock()
        mock.init_kwargs = kwargs
        fake_resp = MagicMock()
        fake_resp.candidates = []
        mock.models.generate_content.return_value = fake_resp
        created_clients.append(mock)
        return mock

    with patch("google.genai.Client", side_effect=mock_client_factory):
        client = OmniFlashClient(mock_mode=False)
        created_clients.clear()

        ref_data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        uri = client.generate_keyframe_image(
            prompt="Character in magical duel",
            style_tone="cinematic",
            reference_image_urls=[ref_data_uri],
        )

        assert len(created_clients) == 1
        gen_kwargs = created_clients[0].models.generate_content.call_args.kwargs
        contents = gen_kwargs.get("contents", [])
        assert len(contents) >= 2
        assert uri is not None


def test_reference_image_multi_key_indexing() -> None:
    """Verify _load_reference_images_as_input indexes char_img_map with role_id, name, combo, and lowercases."""
    from omnimash.prompts.compiler import CharacterRole

    client = OmniFlashClient(mock_mode=True)
    char = CharacterRole(
        role_id="Role A",
        name="Snape Dawg",
        description="Gaunt potion master",
        reference_url="gs://test-bucket/snape.png",
    )

    with patch.object(
        client.storage,
        "download_blob_bytes",
        return_value=(b"fake_image_bytes", "image/png"),
    ):
        imgs, char_map = client._load_reference_images_as_input(
            session_id="session_123", characters=[char]
        )

    assert len(imgs) == 1
    assert char_map.get("Role A") == 1
    assert char_map.get("role a") == 1
    assert char_map.get("Snape Dawg") == 1
    assert char_map.get("snape dawg") == 1
    assert char_map.get("Role A (Snape Dawg)") == 1
    assert char_map.get("role a (snape dawg)") == 1


def test_generate_keyframe_image_includes_wardrobe_aesthetic_tags_and_style_preset() -> None:
    """Verify generate_keyframe_image includes character wardrobe, aesthetic tags, and style preset in prompt formatting."""
    import base64
    from omnimash.prompts.compiler import CharacterRole

    client = OmniFlashClient(mock_mode=False)
    mock_genai_client = MagicMock()
    mock_models = MagicMock()
    mock_candidate = MagicMock(
        content=MagicMock(
            parts=[
                MagicMock(
                    inline_data=MagicMock(data=base64.b64encode(b"fake_png").decode("utf-8"))
                )
            ]
        )
    )
    mock_models.generate_content.return_value = MagicMock(candidates=[mock_candidate])
    mock_genai_client.models = mock_models
    client.storage = MagicMock()
    client.storage.get_gcs_uri.return_value = "gs://test-bucket/keyframes/keyframe_wardrobe_test.png"

    char = CharacterRole(
        role_id="Role A",
        name="Snape",
        description="Gothic Potion Master",
        reference_url="gs://test-bucket/snape_ref.png",
        aesthetic_tags=["Iced Chain", "Dark Robes"],
        wardrobe="Black Velvet Trench Coat with Silver Embroidery",
    )

    with patch("google.genai.Client", return_value=mock_genai_client), patch.object(
        client, "_fetch_image_bytes", return_value=(b"fake_ref_bytes", "image/png")
    ):
        res_url = client.generate_keyframe_image(
            prompt="Snape brewing a potion in a rap video",
            style_tone="90s_rap_video",
            characters=[char],
            style_preset="90s_rap_video",
            wardrobe="Custom Gold Chain and Sunglasses",
        )

    assert "keyframe" in res_url
    assert mock_models.generate_content.called
    call_kwargs = mock_models.generate_content.call_args.kwargs
    contents = call_kwargs["contents"]
    prompt_str = contents[1]

    # Verify character roster contains wardrobe & aesthetic tags
    assert "# Character Roster & Visual Directives:" in prompt_str
    assert f"- {get_character_identifier(char)}: Gothic Potion Master" in prompt_str
    assert "[Wardrobe: Black Velvet Trench Coat with Silver Embroidery]" in prompt_str
    assert "[Style: Iced Chain, Dark Robes]" in prompt_str

    # Verify style preset context header
    assert "# Style Preset (90s_rap_video):" in prompt_str
    assert "Preset Wardrobe Baseline: wearing an oversized shiny black puffer jacket" in prompt_str

    # Verify global wardrobe directives header
    assert "# Wardrobe Directives:\nCustom Gold Chain and Sunglasses" in prompt_str

    # Verify reference image token is bound
    assert "(Reference Image: @Image1)" in prompt_str


def test_generate_keyframe_image_with_dict_characters_wardrobe() -> None:
    """Verify generate_keyframe_image parses dictionary characters containing wardrobe and aesthetic tags."""
    import base64

    client = OmniFlashClient(mock_mode=False)
    mock_genai_client = MagicMock()
    mock_models = MagicMock()
    mock_candidate = MagicMock(
        content=MagicMock(
            parts=[
                MagicMock(
                    inline_data=MagicMock(data=base64.b64encode(b"fake_png").decode("utf-8"))
                )
            ]
        )
    )
    mock_models.generate_content.return_value = MagicMock(candidates=[mock_candidate])
    mock_genai_client.models = mock_models
    client.storage = MagicMock()
    client.storage.get_gcs_uri.return_value = "gs://test-bucket/keyframes/keyframe_dict_test.png"

    char_dict = {
        "role_id": "Role B",
        "name": "Draco",
        "description": "Platinum rival wizard",
        "reference_url": "gs://test-bucket/draco_ref.png",
        "aesthetic_tags": ["Platinum Hair", "Emerald Ring"],
        "wardrobe": "Slytherin Tracksuit and Gucci Slides",
    }

    with patch("google.genai.Client", return_value=mock_genai_client), patch.object(
        client, "_fetch_image_bytes", return_value=(b"fake_ref_bytes", "image/png")
    ):
        res_url = client.generate_keyframe_image(
            prompt="Draco in potion laboratory",
            style_tone="cyberpunk_drift",
            characters=[char_dict],
            style_preset="cyberpunk_drift",
        )

    assert "keyframe" in res_url
    assert mock_models.generate_content.called
    call_kwargs = mock_models.generate_content.call_args.kwargs
    prompt_str = call_kwargs["contents"][1]

    assert f"- {get_character_identifier(char_dict)}: Platinum rival wizard" in prompt_str
    assert "[Wardrobe: Slytherin Tracksuit and Gucci Slides]" in prompt_str
    assert "[Style: Platinum Hair, Emerald Ring]" in prompt_str
    assert "# Style Preset (cyberpunk_drift):" in prompt_str


def test_build_multimodal_contents_omni_flash_native_multimodal() -> None:
    """Verify that _build_multimodal_contents assembles keyframe seed image, character reference images, character roster with Visual Reference bindings, and timecoded prompt without redundant section headers."""
    import base64
    from omnimash.prompts.compiler import CharacterRole

    client = OmniFlashClient(mock_mode=True)
    char1 = CharacterRole(
        role_id="Role A",
        name="Harry",
        description="Spectacled wizard student",
        reference_url="gs://test-bucket/harry.png",
        aesthetic_tags=["Cartier Glasses"],
    )
    char2 = CharacterRole(
        role_id="Role B",
        name="Snape",
        description="Gothic potion master",
        reference_url="gs://test-bucket/snape.jpg",
        aesthetic_tags=["Dark Robes"],
    )

    keyframe_url = "gs://test-bucket/keyframe_seed.png"

    def mock_download_blob(url: str) -> tuple[bytes, str]:
        if "keyframe" in url:
            return b"fake_keyframe_png_bytes", "image/png"
        elif "harry" in url:
            return b"fake_harry_png_bytes", "image/png"
        elif "snape" in url:
            return b"fake_snape_jpg_bytes", "image/jpeg"
        return b"", "image/png"

    timecoded_prompt = (
        "In a single continuous shot. No scene cuts. Shot on low-angle 90s fisheye lens.\n\n"
        "[0-3s] Action: Harry gestures emphatically in potion dungeon. Audio: 120 BPM boom-bap beat.\n"
        "[3-6s] Action: Snape steps into frame with dark robes billowing. Audio: Dialogue: Snape: 'Turn to page 394.'\n"
        "[6-10s] Action: Harry laughs and boos. Audio: Rhythmic beat fades."
    )

    with patch.object(client.storage, "download_blob_bytes", side_effect=mock_download_blob):
        payload = client._build_multimodal_contents(
            prompt=timecoded_prompt,
            session_id="session_test_123",
            characters=[char1, char2],
            keyframe_image_url=keyframe_url,
        )

    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["type"] == "user_input"

    content = payload[0]["content"]
    assert len(content) == 4  # 1 keyframe + 2 char refs + 1 text directive

    # Verify Attached Image #1 (keyframe)
    assert content[0]["type"] == "image"
    assert content[0]["mime_type"] == "image/png"
    assert content[0]["data"] == base64.b64encode(b"fake_keyframe_png_bytes").decode("utf-8")

    # Verify Attached Image #2 (char1)
    assert content[1]["type"] == "image"
    assert content[1]["mime_type"] == "image/png"
    assert content[1]["data"] == base64.b64encode(b"fake_harry_png_bytes").decode("utf-8")

    # Verify Attached Image #3 (char2)
    assert content[2]["type"] == "image"
    assert content[2]["mime_type"] == "image/jpeg"
    assert content[2]["data"] == base64.b64encode(b"fake_snape_jpg_bytes").decode("utf-8")

    # Verify Text Directive
    text_part = content[3]
    assert text_part["type"] == "text"
    text_val = text_part["text"]

    # Check keyframe tone header
    assert "# Visual Tone & Starting Frame Anchor:" in text_val
    assert "Attached Image #1" in text_val

    # Check character roster bindings
    assert "# Character Roster & Visual Directives:" in text_val
    assert f"- {get_character_identifier(char1)} <IMAGE_REF_0>: Spectacled wizard student [Style: Cartier Glasses]" in text_val
    assert f"- {get_character_identifier(char2)} <IMAGE_REF_1>: Gothic potion master [Style: Dark Robes]" in text_val

    # Check timecoded prompt content (with sanitized names and bound image ref tags)
    assert "<IMAGE_REF_0>" in text_val
    assert "<IMAGE_REF_1>" in text_val
    assert "In a single continuous shot. No scene cuts." in text_val
    assert "Harry <IMAGE_REF_0>" in text_val
    assert "Potion Master <IMAGE_REF_1>" in text_val

    # Ensure redundant section headers are NOT present
    assert "# Character Likeness Directives:" not in text_val
    assert "# Audio & Sound Design:" not in text_val


def test_build_multimodal_contents_four_block_omni_flash() -> None:
    """Verify _build_multimodal_contents maps attached reference images under ### INPUT ROLES using explicit tags matching CharacterRole.image_role."""
    from omnimash.prompts.compiler import CharacterRole

    client = OmniFlashClient(mock_mode=True)
    char1 = CharacterRole(
        role_id="Role A",
        name="Hero",
        description="Young wizard with round glasses",
        reference_url="gs://bucket/hero.jpg",
        image_role="Subject Reference",
    )
    char2 = CharacterRole(
        role_id="Role B",
        name="Golden Snitch",
        description="Enchanted golden flying ball",
        reference_url="gs://bucket/snitch.jpg",
        image_role="Product Reference",
    )
    char3 = CharacterRole(
        role_id="Role C",
        name="Dungeon Entrance",
        description="Starting frame of dungeon corridor",
        reference_url="gs://bucket/dungeon.jpg",
        image_role="Starting Frame",
    )
    char4 = CharacterRole(
        role_id="Role D",
        name="Retro Aesthetic",
        description="90s VHS mood reference",
        reference_url="gs://bucket/style.jpg",
        image_role="Style Reference",
    )

    def mock_download_blob(url: str) -> tuple[bytes, str]:
        return b"fake_img_bytes", "image/jpeg"

    with patch.object(client.storage, "download_blob_bytes", side_effect=mock_download_blob):
        payload = client._build_multimodal_contents(
            prompt="Hero catching the snitch",
            characters=[char1, char2, char3, char4],
        )

    assert isinstance(payload, list)
    assert len(payload) == 1
    content = payload[0]["content"]
    text_part = content[-1]
    text_val = text_part["text"]

    # 1. Verify ### INPUT ROLES section header
    assert "### INPUT ROLES" in text_val

    # 2. Verify explicit image role tags matching CharacterRole.image_role
    assert "[# Sources <FIRST_FRAME>@Image3]" in text_val
    assert "[# References <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image2 <IMAGE_REF_2>@Image4]" in text_val


def test_four_block_character_identifier_symmetry() -> None:
    client = OmniFlashClient(mock_mode=True)
    char = CharacterRole(
        role_id="Role A",
        name="Hero",
        description="Young wizard with round glasses",
        reference_url="gs://bucket/hero.jpg",
        image_role="Character Reference",
    )
    expected_id = get_character_identifier(char)

    with patch.object(
        client.storage, "download_blob_bytes", return_value=(b"fake_png", "image/png")
    ):
        payload = client._build_multimodal_contents(
            prompt="Hero catching the snitch",
            characters=[char],
        )

    assert isinstance(payload, list)
    text_part = payload[0]["content"][-1]["text"]

    assert "[# References <IMAGE_REF_0>@Image1]" in text_part
    assert f"- {expected_id} <IMAGE_REF_0>: Young wizard with round glasses" in text_part


def test_four_block_official_image_ref_tags() -> None:
    client = OmniFlashClient(mock_mode=True)
    char1 = CharacterRole(
        role_id="Role A",
        name="Snape Dawg",
        description="Gaunt potion master wizard",
        reference_url="gs://bucket/snape.jpg",
        image_role="Character Reference",
    )
    char2 = CharacterRole(
        role_id="Role B",
        name="Harry Potter",
        description="Young wizard with round glasses",
        reference_url="gs://bucket/harry.jpg",
        image_role="Character Reference",
    )

    with patch.object(
        client.storage, "download_blob_bytes", return_value=(b"fake_png", "image/png")
    ):
        payload = client._build_multimodal_contents(
            prompt="Snape Dawg in potion class",
            characters=[char1, char2],
            keyframe_image_url="gs://bucket/keyframe.png",
        )

    assert isinstance(payload, list)
    text_val = payload[0]["content"][-1]["text"]

    assert "### INPUT ROLES" in text_val
    assert "[# Sources <FIRST_FRAME>@Image1]" in text_val
    assert "[# References <IMAGE_REF_0>@Image2 <IMAGE_REF_1>@Image3]" in text_val
    assert "- Role A - Potion Master Dawg <IMAGE_REF_0>: Gaunt potion master wizard" in text_val
    assert "- Role B - Spectacled Wizard Bruv <IMAGE_REF_1>: Young wizard with round glasses" in text_val


def test_abstract_prompt_preserves_character_tags_and_image_refs() -> None:
    """Verify _abstract_prompt_for_responsible_ai preserves character tags, IMAGE_REF tags, and bracketed section headers intact while replacing character names in descriptions and general text."""
    prompt = (
        "### INPUT ROLES\n"
        "[# References <IMAGE_REF_0>@Image1]\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A - Snape Dawg <IMAGE_REF_0>: Severus Snape brewing potion in dark robes.\n\n"
        "### TIMELINE\n"
        "[0-5s] Role A - Snape Dawg <IMAGE_REF_0> says: Snape brews potion."
    )
    res = _abstract_prompt_for_responsible_ai(prompt)

    # 1. Section header and image reference tag syntax preserved intact
    assert "[# References <IMAGE_REF_0>@Image1]" in res
    assert "<IMAGE_REF_0>" in res

    # 2. Character identifier string / header intact without multi-word description insertion
    assert "Role A - Snape Dawg <IMAGE_REF_0>" in res
    assert "Role A - a stern potion master wizard in dark robes Dawg" not in res

    # 3. Snape / Severus Snape in general description and dialogue text replaced by visual archetype
    assert "Severus Snape" not in res
    assert "Snape brews" not in res
    assert "a stern" in res
    assert "master wizard" in res


def test_build_multimodal_contents_extracts_base_names_and_tokens() -> None:
    client = OmniFlashClient(mock_mode=True)
    char1 = CharacterRole(
        role_id="Role 1",
        name="Yo Totti (Post High Security Fortress)",
        description="Yo Totti after fortress release",
        reference_url="gs://bucket/yototti.png",
    )
    char2 = CharacterRole(
        role_id="Role 2",
        name="Swagrid Tha Plug",
        description="Swagrid the legendary supplier",
        reference_url="gs://bucket/swagrid.png",
    )

    with patch.object(
        client.storage, "download_blob_bytes", return_value=(b"fake_png", "image/png")
    ):
        images, char_img_map = client._load_reference_images_as_input(
            session_id=None,
            characters=[char1, char2],
            starting_index=1,
        )
        assert char_img_map.get("Yo Totti (Post High Security Fortress)") == 1
        assert char_img_map.get("Yo Totti") == 1
        assert char_img_map.get("Totti") == 1

        assert char_img_map.get("Swagrid Tha Plug") == 2
        assert char_img_map.get("Swagrid") == 2
        assert char_img_map.get("Plug") == 2

        payload = client._build_multimodal_contents(
            prompt="Swagrid glides out of the forest",
            characters=[char1, char2],
        )

    assert isinstance(payload, list)
    text_val = payload[0]["content"][-1]["text"]
    assert "Swagrid <IMAGE_REF_1>" in text_val


def test_safety_retry_preserves_multimodal_reference_images(
    tmp_path: Any,
) -> None:
    """Verify that a 400 safety/prohibited content retry preserves multimodal reference images in kwargs['input']."""
    import base64
    from unittest.mock import MagicMock, patch
    from omnimash.engine.omni_client import OmniFlashClient
    from omnimash.prompts.compiler import CharacterRole

    client = OmniFlashClient(mock_mode=False)
    mock_interactions = MagicMock()
    fake_video_bytes = base64.b64encode(b"fake_mp4_video_data").decode("utf-8")
    mock_output_video = MagicMock(data=fake_video_bytes)
    success_interaction = MagicMock(
        id="inter_test_retry_123", output_video=mock_output_video
    )

    mock_interactions.create.side_effect = [
        Exception("400 prohibited content guidelines violated"),
        success_interaction,
    ]

    mock_genai_client = MagicMock()
    mock_genai_client.interactions = mock_interactions
    client._genai_client = mock_genai_client

    char = CharacterRole(
        role_id="Role B",
        name="Yo Totti",
        description="Yo Totti character",
        reference_url="http://example.com/yototti.jpg",
    )

    with patch.object(
        client,
        "_fetch_image_bytes",
        return_value=(b"fake_jpg_bytes", "image/jpeg"),
    ):
        target_file = str(tmp_path / "test_safety_retry_out.mp4")
        success, inter_id, error = client._generate_live_omni_flash_video(
            prompt="Yo Totti in a rap battle",
            target_rel_path=target_file,
            characters=[char],
            session_id="session_test_safety",
        )

    assert success is True
    assert inter_id == "inter_test_retry_123"
    assert error is None
    assert mock_interactions.create.call_count == 2

    second_call_kwargs = mock_interactions.create.call_args_list[1].kwargs
    second_input = second_call_kwargs["input"]
    assert isinstance(second_input, list)
    assert len(second_input) == 1
    assert second_input[0]["type"] == "user_input"

    content = second_input[0]["content"]
    image_parts = [
        p
        for p in content
        if isinstance(p, dict) and p.get("type") == "image"
    ]
    text_parts = [
        p
        for p in content
        if isinstance(p, dict) and p.get("type") == "text"
    ]

    assert (
        len(image_parts) == 1
    ), "Expected reference image part ('type': 'image') in retry payload content"
    assert (
        len(text_parts) == 1
    ), "Expected fallback text part ('type': 'text') in retry payload content"
    assert "parody" in text_parts[0].get("text", "").lower()


def test_omni_client_skips_safety_retry_abstraction_when_disabled(tmp_path):
    client = OmniFlashClient(mock_mode=False)
    client._genai_client = MagicMock()

    mock_interactions = MagicMock()
    client._genai_client.interactions = mock_interactions

    err_resp = MagicMock()
    err_resp.status_code = 400
    err_resp.text = "Prompt violates safety policy or contains real person"

    import base64

    fake_video_bytes = base64.b64encode(b"fake_mp4_video_data").decode("utf-8")
    mock_output_video = MagicMock(data=fake_video_bytes)
    mock_res = MagicMock(
        id="inter_test_no_abstraction", output_video=mock_output_video
    )

    mock_interactions.create.side_effect = [
        Exception(err_resp.text),
        mock_res,
    ]

    target_file = os.path.join(tmp_path, "output.mp4")

    success, inter_id, error = client._generate_live_omni_flash_video(
        prompt="Harry Potter casting spells",
        target_rel_path=target_file,
        enable_safety_sanitization=False,
    )

    assert success is True
    assert mock_interactions.create.call_count == 2

    second_call_kwargs = mock_interactions.create.call_args_list[1].kwargs
    second_input = second_call_kwargs["input"]
    assert second_input == "Harry Potter casting spells"












