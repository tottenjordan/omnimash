import pytest
from omnimash.config import settings
from omnimash.engine.omni_client import OmniFlashClient
from omnimash.ingestion.media_extractor import MediaExtractor
from omnimash.prompts.compiler import (
    CharacterRole,
    build_character_image_ref_tags,
    compile_journey3_shot_prompt,
    validate_compiled_prompt,
)


def test_omni_flash_1_1_config_defaults():
    assert settings.omni_model_id == "gemini-omni-1.1-flash-preview"
    assert settings.default_resolution == "720p"
    assert settings.draft_resolution == "360p"
    assert settings.master_resolution == "4k"


def test_build_character_image_ref_tags_with_last_frame():
    chars = [
        CharacterRole(
            name="First Anchor",
            role_id="Role A",
            description="First anchor desc",
            image_role="Starting Frame",
            reference_url="http://example.com/first.png",
        ),
        CharacterRole(
            name="Last Anchor",
            role_id="Role B",
            description="Last anchor desc",
            image_role="Ending Frame",
            reference_url="http://example.com/last.png",
        ),
    ]

    sources_items, references_items, char_tag_map = build_character_image_ref_tags(
        characters=chars, starting_index=1
    )

    assert "<FIRST_FRAME>@Image1" in sources_items
    assert "<LAST_FRAME>@Image2" in sources_items


def test_last_frame_without_first_frame_raises_value_error():
    chars = [
        CharacterRole(
            name="Last Anchor",
            role_id="Role B",
            description="Last anchor desc",
            image_role="Ending Frame",
            reference_url="http://example.com/last.png",
        ),
    ]

    with pytest.raises(ValueError, match="<LAST_FRAME> anchor requires a corresponding <FIRST_FRAME> anchor"):
        build_character_image_ref_tags(characters=chars, starting_index=1)


def test_validate_compiled_prompt_pairing_rule():
    valid_prompt = (
        "### INPUT ROLES\n<FIRST_FRAME>@Image1\n<LAST_FRAME>@Image2\n\n"
        "### CHARACTER PROFILES\nNone.\n\n"
        "### SCENE INSTRUCTIONS\nEnvironment: Studio\n\n"
        "### TIMELINE\n[0-3s] Action: Transition."
    )
    validate_compiled_prompt(valid_prompt)

    invalid_prompt = (
        "### INPUT ROLES\n<LAST_FRAME>@Image2\n\n"
        "### CHARACTER PROFILES\nNone.\n\n"
        "### SCENE INSTRUCTIONS\nEnvironment: Studio\n\n"
        "### TIMELINE\n[0-3s] Action: Transition."
    )
    with pytest.raises(ValueError, match="<LAST_FRAME> anchor requires a corresponding <FIRST_FRAME> anchor"):
        validate_compiled_prompt(invalid_prompt)


def test_compile_journey3_shot_prompt_with_last_frame_url():
    prompt = compile_journey3_shot_prompt(
        shot_number=1,
        action_directive="Hero transforms into dragon",
        characters=[
            {
                "name": "Hero",
                "role_id": "Role A",
                "image_role": "Starting Frame",
                "reference_url": "http://example.com/hero.png",
            }
        ],
        last_frame_image_url="http://example.com/dragon.png",
    )
    assert "<FIRST_FRAME>@Image1" in prompt
    assert "<LAST_FRAME>@Image2" in prompt


def test_omni_client_generate_live_omni_flash_video_kwargs(tmp_path):
    client = OmniFlashClient(mock_mode=True)
    out_file = str(tmp_path / "test.mp4")

    success, inter_id, err = client._generate_live_omni_flash_video(
        prompt="Test prompt",
        target_rel_path=out_file,
        previous_interaction_id="inter_12345",
        resolution="360p",
    )
    assert success is True
    assert inter_id == "inter_12345"
    assert err is None


def test_extract_reference_video_clip(tmp_path):
    extractor = MediaExtractor(mock_mode=True)
    src_file = str(tmp_path / "src.mp4")
    dst_file = str(tmp_path / "clip.mp4")
    with open(src_file, "wb") as f:
        f.write(b"dummy mp4 data")

    res_path = extractor.extract_reference_video_clip(
        source_video_path=src_file,
        output_clip_path=dst_file,
        start_time_seconds=0.0,
        duration_seconds=3.0,
    )
    assert res_path == dst_file


def test_resolution_propagation_in_omni_client_and_orchestrator(monkeypatch):
    from omnimash.agent.orchestrator import OmniMashAgent

    agent = OmniMashAgent(mock_mode=True)
    captured_kwargs = {}

    def mock_generate_live(prompt, target_rel_path, **kwargs):
        captured_kwargs.update(kwargs)
        return True, kwargs.get("previous_interaction_id") or "mock_inter_123", None

    monkeypatch.setattr(agent.omni_client, "_generate_live_omni_flash_video", mock_generate_live)

    # Test generate_clip with 360p draft resolution
    res_clip = agent.omni_client.generate_clip("Draft shot", resolution="360p")
    assert res_clip.error_message is None
    assert captured_kwargs.get("resolution") == "360p"

    # Test apply_interaction_diff with 4k master resolution
    captured_kwargs.clear()
    res_diff = agent.omni_client.apply_interaction_diff("inter_001", "Diff shot", resolution="4k")
    assert res_diff.error_message is None
    assert captured_kwargs.get("resolution") == "4k"
    assert captured_kwargs.get("previous_interaction_id") == "inter_001"

    # Test process_user_turn forwarding resolution
    captured_kwargs.clear()
    turn_res = agent.process_user_turn(
        user_id="u1",
        project_id="p1",
        prompt="Turn prompt",
        resolution="360p",
    )
    assert turn_res.success is True
    assert captured_kwargs.get("resolution") == "360p"

    # Test extend_scene forwarding resolution and previous_interaction_id
    captured_kwargs.clear()
    ext_res = agent.extend_scene(
        session_name="s1",
        turn_id="inter_555",
        next_scene_action="Action continuation",
        resolution="360p",
    )
    assert ext_res.success is True
    assert captured_kwargs.get("resolution") == "360p"
    assert captured_kwargs.get("previous_interaction_id") == "inter_555"


def test_compile_storyboard_with_last_frame_url():
    from omnimash.prompts.compiler import PromptCompiler, CharacterRole, SceneDirective

    compiler = PromptCompiler(mock_mode=True)
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Hero",
            description="Hero start",
            image_role="Starting Frame",
            reference_url="http://example.com/hero.png",
        )
    ]
    scenes = [SceneDirective(scene_number=1, active_roles=["Role A"], action="Start transformation")]

    prompt = compiler.compile_storyboard(
        concept="Hero transforms",
        characters=chars,
        scenes=scenes,
        last_frame_image_url="http://example.com/ending.png",
    )

    assert "<FIRST_FRAME>@Image1" in prompt
    assert "<LAST_FRAME>@Image2" in prompt

