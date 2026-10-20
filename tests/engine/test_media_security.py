import base64
import socket
from typing import Any
from unittest.mock import MagicMock, patch
import urllib.error
import xml.etree.ElementTree as ET
import pytest

from omnimash.engine.media_loader import (
    MAX_MEDIA_FETCH_BYTES,
    _SafeRedirectHandler,
    build_mock_keyframe_svg_data_uri,
    build_mock_ref_sheet_svg_data_uri,
    coerce_character_roles,
    fetch_media_bytes,
    render_svg_to_png_bytes,
)
from omnimash.prompts.compiler import CharacterRole


def test_fetch_media_bytes_blocks_svg_path_traversal(tmp_path: Any) -> None:
    secret_svg = tmp_path / "secret_outside.svg"
    secret_svg.write_text("<svg><text>TOP_SECRET_SVG_DATA</text></svg>")

    # Attempt path traversal with .svg extension outside static/ and /tmp
    data, mime = fetch_media_bytes(
        ref_url=f"../../../../{secret_svg}",
        storage=MagicMock(),
        allowed_roots=(str(tmp_path / "static"),),
    )
    assert data == b""
    assert mime == "image/png"


def test_fetch_media_bytes_allows_valid_local_svg_within_allowed_roots(tmp_path: Any) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    valid_svg = static_dir / "valid_icon.svg"
    valid_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>Allowed SVG</text></svg>')

    data, mime = fetch_media_bytes(
        ref_url=str(valid_svg),
        storage=MagicMock(),
        allowed_roots=(str(static_dir),),
    )
    assert data.startswith(b"\x89PNG")
    assert mime == "image/png"


def test_fetch_media_bytes_blocks_dns_rebinding_to_private_and_loopback_ips() -> None:
    with patch(
        "socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))],
    ):
        data, _ = fetch_media_bytes("http://evil-rebind.example.com/latest/meta-data/", MagicMock())
        assert data == b""

    with patch(
        "socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 8080))],
    ):
        data2, _ = fetch_media_bytes("http://localhost-alias.example.com/admin", MagicMock())
        assert data2 == b""


def test_fetch_media_bytes_blocks_redirect_to_internal_host() -> None:
    handler = _SafeRedirectHandler()
    req = MagicMock(full_url="https://example.com/start")
    with pytest.raises(urllib.error.URLError, match="Disallowed redirect target"):
        handler.redirect_request(req, None, 302, "Found", {}, "http://127.0.0.1:8080/admin")


def test_fetch_media_bytes_enforces_max_byte_limit() -> None:
    oversized_stream = MagicMock()
    oversized_stream.headers = {"Content-Type": "image/png"}
    oversized_stream.read.return_value = b"x" * (MAX_MEDIA_FETCH_BYTES + 1)
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = oversized_stream

    with (
        patch(
            "socket.getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
        ),
        patch("urllib.request.OpenerDirector.open", return_value=mock_cm),
    ):
        data, _ = fetch_media_bytes("https://example.com/huge.png", MagicMock())
        assert data == b""


def test_svg_generators_escape_ampersands_and_produce_valid_xml() -> None:
    kf_uri = build_mock_keyframe_svg_data_uri(
        prompt="R&B & Hip-Hop <battle> \"quote\" 'single'",
        style_preset="Tom & Jerry <90s>",
        style_tone="Dark & Moody",
        aspect_ratio="16:9 & <wide>",
    )
    kf_svg = base64.b64decode(kf_uri.split("base64,")[1]).decode("utf-8")
    ET.fromstring(kf_svg)
    assert "&amp;" in kf_svg

    sheet_uri = build_mock_ref_sheet_svg_data_uri(
        character_name="Dr. Jekyll & Mr. Hyde <Jr>",
        description="A & B 'test' \"quote\"",
        aspect_ratio="16:9 & <custom>",
    )
    sheet_svg = base64.b64decode(sheet_uri.split("base64,")[1]).decode("utf-8")
    ET.fromstring(sheet_svg)
    assert "&amp;" in sheet_svg


def test_coerce_character_roles_handles_dicts_objects_and_dataclasses() -> None:
    class CustomCharObj:
        role_id = "Role C"
        name = "Custom"
        description = "Custom desc"
        reference_url = "gs://bucket/c.png"
        aesthetic_tags = ("Tag1", "Tag2")
        wardrobe = "Cloak"

    roles = coerce_character_roles(
        [
            CharacterRole(role_id="Role A", name="Hero", description="Hero desc"),
            {
                "role_id": "Role B",
                "name": "Villain",
                "description": "Villain desc",
                "wardrobe": "Armor",
            },
            CustomCharObj(),
        ]
    )
    assert len(roles) == 3
    assert all(isinstance(r, CharacterRole) for r in roles)
    assert roles[1].wardrobe == "Armor"
    assert roles[2].aesthetic_tags == ["Tag1", "Tag2"]
    assert render_svg_to_png_bytes(b"<svg><text>Test</text></svg>").startswith(b"\x89PNG")
