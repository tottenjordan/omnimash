from __future__ import annotations

from omnimash.engine.keyframe_client import KeyframeClient


def test_keyframe_client_mock_mode():
    """Verify KeyframeClient returns SVG data URI in mock mode."""
    client = KeyframeClient(mock_mode=True)
    res = client.generate_keyframe_image(
        prompt="A neon cyber detective standing under rain",
        style_tone="cyberpunk",
    )
    assert isinstance(res, str)
    assert res.startswith("data:image/svg+xml;base64,")


def test_keyframe_client_turnaround_sheet_mock_mode():
    """Verify KeyframeClient generates character turnaround sheet in mock mode."""
    client = KeyframeClient(mock_mode=True)
    res = client.generate_character_reference_sheet(
        character_name="Neon Samurai",
        description="Samurai with glowing cyber katana",
    )
    assert isinstance(res, str)
    assert res.startswith("data:image/svg+xml;base64,")


def test_keyframe_client_returns_compiled_prompt():
    """Verify return_compiled_prompt=True returns (url, prompt_text) tuple."""
    client = KeyframeClient(mock_mode=True)
    url, prompt_text = client.generate_keyframe_image(
        prompt="A magical wizard standing in a crystal cave",
        return_compiled_prompt=True,
    )
    assert url.startswith("data:image/svg+xml;base64,")
    assert "crystal cave" in prompt_text
