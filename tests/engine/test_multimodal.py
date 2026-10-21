from __future__ import annotations

from omnimash.engine.multimodal import build_multimodal_contents, load_reference_images_as_input
from omnimash.prompts.compiler import CharacterRole


def test_build_multimodal_contents_plain_text():
    """Verify build_multimodal_contents returns sanitized string when no images are provided."""
    prompt = "A dramatic tracking shot across a cyberpunk skyline."
    res = build_multimodal_contents(prompt=prompt)
    assert isinstance(res, str)
    assert "cyberpunk skyline" in res


def test_build_multimodal_contents_with_mock_fetcher():
    """Verify build_multimodal_contents builds multimodal parts payload when keyframe or characters are provided."""
    dummy_bytes = b"fake-png-data"

    def mock_fetch(url: str):
        return dummy_bytes, "image/png"

    res = build_multimodal_contents(
        prompt="Lead subject enters tavern.",
        keyframe_image_url="http://example.com/kf.png",
        fetch_image_fn=mock_fetch,
    )
    assert isinstance(res, list)
    assert len(res) == 1
    assert res[0]["type"] == "user_input"
    content = res[0]["content"]
    assert any(part.get("type") == "image" for part in content)
    assert any(part.get("type") == "text" for part in content)


def test_load_reference_images_empty():
    """Verify load_reference_images_as_input returns empty when no characters provided."""
    objs, char_map = load_reference_images_as_input(
        session_id="test", characters=None, fetch_image_fn=lambda u: (b"", "")
    )
    assert objs == []
    assert char_map == {}


def test_build_multimodal_contents_preserves_input_roles_header():
    """Verify regex preserves ### INPUT ROLES & REFERENCES without wiping out sources/references."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "None.\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Hero\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Cinematic walk\n\n"
        "### TIMELINE\n"
        "[0-5s] Walks."
    )
    chars = [
        CharacterRole(
            name="Hero",
            role_id="Role A",
            description="Cyber hero",
            reference_url="http://example.com/hero.png",
        )
    ]
    res = build_multimodal_contents(
        prompt=prompt,
        keyframe_image_url="http://example.com/kf.png",
        characters=chars,
    )
    assert isinstance(res, str)
    assert "### INPUT ROLES & REFERENCES\n" in res
    assert "[# Sources <FIRST_FRAME>@KeyframeSeed]" in res
    assert "[# References <IMAGE_REF_0>@Image1]" in res
    assert "### CHARACTER PROFILES" in res


def test_build_multimodal_contents_starting_frame_guiding_instruction():
    """Verify starting frame only appends official Gemini Omni instruction."""
    res = build_multimodal_contents(
        prompt="A car driving down a deserted highway at sunset.",
        keyframe_image_url="http://example.com/start.png",
    )
    assert isinstance(res, str)
    assert "Use this image as the starting frame." in res
    assert "Use this image as the first frame and the last frame." not in res
    assert (
        "Use the first image as the starting frame and the second image as the ending frame."
        not in res
    )


def test_build_multimodal_contents_seamless_loop_guiding_instruction():
    """Verify seamless loop appends official Gemini Omni first/last frame instruction."""
    res = build_multimodal_contents(
        prompt="A campfire crackling under the starry night sky.",
        keyframe_image_url="http://example.com/loop.png",
        is_seamless_loop=True,
    )
    assert isinstance(res, str)
    assert "Use this image as the first frame and the last frame." in res
    assert "Use this image as the starting frame." not in res
    assert (
        "Use the first image as the starting frame and the second image as the ending frame."
        not in res
    )


def test_build_multimodal_contents_dual_keyframe_guiding_instruction():
    """Verify dual keyframe appends official Gemini Omni first/second image instruction."""
    res = build_multimodal_contents(
        prompt="Transition between winter and spring in a mountain valley.",
        keyframe_image_url="http://example.com/winter.png",
        last_frame_image_url="http://example.com/spring.png",
    )
    assert isinstance(res, str)
    assert (
        "Use the first image as the starting frame and the second image as the ending frame." in res
    )
    assert "Use this image as the first frame and the last frame." not in res
    assert "Use this image as the starting frame." not in res


def test_build_multimodal_contents_reference_images_guiding_instruction():
    """Verify reference images append official Gemini Omni reference instruction."""
    chars = [
        CharacterRole(
            name="Dragon",
            role_id="Role A",
            description="Cyber dragon",
            reference_url="http://example.com/dragon.png",
        )
    ]
    res = build_multimodal_contents(
        prompt="Hero battles a cybernetic dragon in a neon colosseum.",
        characters=chars,
    )
    assert isinstance(res, str)
    assert (
        "Use the given image(s) as references for video generation. "
        "The images should not be used as literal initial frames." in res
    )


def test_build_multimodal_contents_reference_videos_guiding_instruction():
    """Verify reference videos append official Gemini Omni video reference instruction."""
    res = build_multimodal_contents(
        prompt="Dancer executing a breakdance power move.",
        motion_reference_clip="http://example.com/dance_routine.mp4",
    )
    assert isinstance(res, str)
    assert (
        "Use the given video(s) as references. "
        "Do not use them as a source for video editing." in res
    )


def test_build_multimodal_contents_avoids_duplicate_guiding_instructions():
    """Verify terminal guiding instructions are not duplicated if already present in prompt."""
    prompt = "A car on a highway.\n\nUse this image as the starting frame."
    res = build_multimodal_contents(
        prompt=prompt,
        keyframe_image_url="http://example.com/car.png",
    )
    assert isinstance(res, str)
    assert res.count("Use this image as the starting frame.") == 1


def test_build_multimodal_contents_seamless_loop_from_matching_prompt_tags():
    """Verify matching <FIRST_FRAME> and <LAST_FRAME> image tags trigger seamless loop instruction, not dual keyframes."""
    prompt = "[# Sources <FIRST_FRAME>@Image1 <LAST_FRAME>@Image1] A cat is sleeping on a rug."
    res = build_multimodal_contents(prompt=prompt)
    assert isinstance(res, str)
    assert "Use this image as the first frame and the last frame." in res
    assert (
        "Use the first image as the starting frame and the second image as the ending frame."
        not in res
    )
    assert "Use this image as the starting frame." not in res


def test_build_multimodal_contents_video_keyframe_does_not_add_image_guiding_instructions():
    """Verify video input in keyframe_image_url does not trigger image starting frame or false reference video editing instructions."""

    def mock_fetch(url: str):
        return b"fake-video-bytes", "video/mp4"

    res = build_multimodal_contents(
        prompt="Extend the scene as the camera moves past the building.",
        keyframe_image_url="http://example.com/scene.mp4",
        fetch_image_fn=mock_fetch,
    )
    assert isinstance(res, list)
    assert len(res) == 1
    content = res[0]["content"]
    assert any(part.get("type") == "video" for part in content)
    text_part = next(part["text"] for part in content if part.get("type") == "text")
    assert "Use this image as the starting frame." not in text_part
    assert "Attached Image #1" not in text_part
    assert "Do not use them as a source for video editing." not in text_part


def test_build_multimodal_contents_character_matching_first_and_last_frame_tags():
    """Verify CharacterRole with Starting Frame and Ending Frame sharing same tag trigger loop instruction."""
    chars = [
        CharacterRole(
            name="Loop Anchor",
            role_id="Role A",
            description="Loop frame anchor",
            reference_url="http://example.com/frame.png",
            image_role="Starting Frame",
        ),
        CharacterRole(
            name="Loop Anchor",
            role_id="Role B",
            description="Loop frame anchor",
            reference_url="http://example.com/frame.png",
            image_role="Ending Frame",
        ),
    ]
    res = build_multimodal_contents(
        prompt="A looping hypnotic geometric animation.",
        characters=chars,
    )
    assert isinstance(res, str)
    assert "Use this image as the first frame and the last frame." in res
    assert (
        "Use the first image as the starting frame and the second image as the ending frame."
        not in res
    )

