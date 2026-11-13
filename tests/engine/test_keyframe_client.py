from __future__ import annotations

import base64
import io
import logging
from typing import Any
from unittest.mock import MagicMock, patch

from PIL import Image
import pytest

from omnimash.engine.keyframe_client import (
    NO_SAMPLING_IMAGE_MODELS,
    KeyframeClient,
)


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


def _build_mock_genai_image_client(
    payload: bytes = b"fake_png_bytes",
) -> tuple[MagicMock, MagicMock]:
    mock_genai_client = MagicMock()
    mock_models = MagicMock()
    final_part = MagicMock(
        thought=False,
        inline_data=MagicMock(data=base64.b64encode(payload).decode("utf-8")),
    )
    mock_candidate = MagicMock(content=MagicMock(parts=[final_part]))
    mock_models.generate_content.return_value = MagicMock(candidates=[mock_candidate])
    mock_genai_client.models = mock_models
    return mock_genai_client, mock_models


def test_execute_gemini_image_generation_honors_pro_image_2k_and_seed() -> None:
    """Verify gemini-3-pro-image receives ImageConfig(image_size='2K') and seed=4101."""
    # Arrange
    from google.genai import types

    client = KeyframeClient(mock_mode=False)
    mock_storage = MagicMock()
    mock_storage.get_gcs_uri.return_value = "gs://test-bucket/keyframes/pro_2k.png"
    client.storage = mock_storage
    mock_genai_client, mock_models = _build_mock_genai_image_client()

    # Act
    with patch("google.genai.Client", return_value=mock_genai_client):
        result_url = client._execute_gemini_image_generation(
            contents=["Create an image of: a wizard at an iron gate"],
            image_model="gemini-3-pro-image",
            aspect_ratio="16:9",
            blob_prefix="keyframes/keyframe",
            log_context="gate1_test",
            image_size="2K",
            seed=4101,
        )

    # Assert
    assert result_url == "/api/media-proxy?uri=gs%3A%2F%2Ftest-bucket%2Fkeyframes%2Fpro_2k.png"
    gen_kwargs = mock_models.generate_content.call_args.kwargs
    assert gen_kwargs["model"] == "gemini-3-pro-image"
    cfg = gen_kwargs["config"]
    assert isinstance(cfg, types.GenerateContentConfig)
    assert cfg.seed == 4101
    assert isinstance(cfg.image_config, types.ImageConfig)
    assert cfg.image_config.aspect_ratio == "16:9"
    assert cfg.image_config.image_size == "2K"


def test_execute_gemini_image_generation_maps_deprecated_3_1_flash_image_to_nano_banana_and_omits_seed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify shut-down gemini-3.1-flash-image maps to gemini-nano-banana-2.1 with 2K and omits seed."""
    # Arrange
    from google.genai import types

    assert "gemini-nano-banana-2.1" in NO_SAMPLING_IMAGE_MODELS
    client = KeyframeClient(mock_mode=False)
    mock_storage = MagicMock()
    mock_storage.get_gcs_uri.return_value = "gs://test-bucket/keyframes/nano.png"
    client.storage = mock_storage
    mock_genai_client, mock_models = _build_mock_genai_image_client()

    # Act
    with (
        caplog.at_level(logging.WARNING, logger="omnimash.engine.keyframe_client"),
        patch("google.genai.Client", return_value=mock_genai_client),
    ):
        result_url = client._execute_gemini_image_generation(
            contents=["Create an image of: neon alley"],
            image_model="gemini-3.1-flash-image",
            aspect_ratio="16:9",
            blob_prefix="keyframes/keyframe",
            log_context="deprecated_map_test",
            image_size="2k",
            seed=4101,
        )

    # Assert
    assert result_url is not None
    gen_kwargs = mock_models.generate_content.call_args.kwargs
    assert gen_kwargs["model"] == "gemini-nano-banana-2.1"
    cfg = gen_kwargs["config"]
    assert isinstance(cfg, types.GenerateContentConfig)
    assert cfg.seed is None
    assert isinstance(cfg.image_config, types.ImageConfig)
    assert cfg.image_config.image_size == "2K"
    assert any("gemini-3.1-flash-image" in rec.message for rec in caplog.records)


def test_generate_keyframe_image_bans_scene_frame_chaining(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify scene-frame anchor_keyframe_url is rejected, logged, and stripped from prompt."""
    # Arrange
    client = KeyframeClient(mock_mode=True)
    banned_anchor = "/api/media-proxy?uri=gs://b/keyframes/keyframe_1a2b3c4d.png"

    # Act
    with caplog.at_level(logging.WARNING, logger="omnimash.engine.keyframe_client"):
        url, compiled_prompt = client.generate_keyframe_image(
            prompt="Medium close-up of wizard speaking at the gate",
            anchor_keyframe_url=banned_anchor,
            return_compiled_prompt=True,
        )

    # Assert
    assert url.startswith("data:image/svg+xml;base64,")
    assert any("SCENE_KEYFRAME_CHAINING_BANNED" in rec.message for rec in caplog.records)
    assert "<FIRST_FRAME>@KeyframeSeed" not in compiled_prompt
    assert "<FIRST_FRAME>@KeyframeSeed" not in client.last_keyframe_prompt


def test_generate_gate1_candidate_batch_defaults_to_n1_and_supports_n6_contact_sheet() -> None:
    """Verify Gate-1 batching defaults to N=1 and supports N=6 with a 3x2 JPEG contact sheet."""
    # Arrange
    client = KeyframeClient(mock_mode=True)

    # Act: default num_candidates=1 (Q2 Option A)
    single_batch = client.generate_gate1_candidate_batch(
        prompt="Wide establishing shot of Trapwarts gate in rain",
        shot_label="shot_a",
    )

    # Assert: N=1 default
    assert len(single_batch.candidates) == 1
    assert single_batch.candidates[0].model == "gemini-3-pro-image"
    assert single_batch.candidates[0].seed == 4101
    assert single_batch.candidates[0].image_size == "2K"
    assert single_batch.contact_sheet_url is None

    # Act: N=6 batch with storage upload
    mock_storage = MagicMock()
    mock_storage.get_gcs_uri.return_value = "gs://test-bucket/keyframes/gate1_shot_a_sheet.jpg"
    client_with_storage = KeyframeClient(mock_mode=True, storage=mock_storage)
    six_batch = client_with_storage.generate_gate1_candidate_batch(
        prompt="Wide establishing shot of Trapwarts gate in rain",
        shot_label="shot_a",
        base_seed=4101,
        num_candidates=6,
    )

    # Assert: 6 seeded candidates + 3x2 contact sheet JPEG uploaded via storage
    assert len(six_batch.candidates) == 6
    assert [c.seed for c in six_batch.candidates] == [4101, 4102, 4103, 4104, 4105, 4106]
    assert six_batch.contact_sheet_url == (
        "/api/media-proxy?uri=gs%3A%2F%2Ftest-bucket%2Fkeyframes%2Fgate1_shot_a_sheet.jpg"
    )
    upload_calls = [
        call
        for call in mock_storage.upload_bytes.call_args_list
        if call.kwargs.get("content_type") == "image/jpeg"
    ]
    assert len(upload_calls) == 1
    sheet_bytes: bytes = upload_calls[0].args[0]
    with Image.open(io.BytesIO(sheet_bytes)) as sheet_img:
        assert sheet_img.format == "JPEG"
        # 3x2 grid implies wider than tall (3 columns vs 2 rows at 16:9 tiles)
        assert sheet_img.width > sheet_img.height
        assert sheet_img.width >= 1800
        assert sheet_img.height >= 700

    # Act: N=6 batch without storage falls back to JPEG data URI
    six_batch_data_uri: Any = client.generate_gate1_candidate_batch(
        prompt="MCU of wizard at Trapwarts gate",
        shot_label="shot_b",
        base_seed=5101,
        num_candidates=6,
    )
    assert six_batch_data_uri.contact_sheet_url is not None
    assert six_batch_data_uri.contact_sheet_url.startswith("data:image/jpeg;base64,")
