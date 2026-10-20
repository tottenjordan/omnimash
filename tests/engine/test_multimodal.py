from __future__ import annotations

from omnimash.engine.multimodal import build_multimodal_contents, load_reference_images_as_input


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
