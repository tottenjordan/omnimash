import base64
from unittest.mock import MagicMock, patch

import pytest

from omnimash.engine.omni_client import GenerationResult, OmniFlashClient


def _make_mock_interaction(
    inter_id: str = "inter_123", video_bytes: bytes = b"fake_mp4_bytes"
) -> MagicMock:
    interaction = MagicMock()
    interaction.id = inter_id
    interaction.interaction_id = inter_id
    output_vid = MagicMock()
    output_vid.data = base64.b64encode(video_bytes).decode("utf-8")
    interaction.output_video = output_vid
    return interaction


def test_generation_result_dataclass_defaults() -> None:
    res = GenerationResult(
        interaction_thread_id="thread_1",
        video_url="/static/rendered/test.mp4",
    )
    assert res.error_message is None
    assert res.generation_mode == "LIVE_OMNI_FLASH"


def test_automatic_401_unauthenticated_mitigation_switches_to_dev_client(
    caplog: pytest.LogCaptureFixture,
) -> None:
    vertex_client = MagicMock()
    dev_client = MagicMock()

    # Vertex client raises 401 UNAUTHENTICATED
    vertex_client.interactions.create.side_effect = RuntimeError(
        "401 UNAUTHENTICATED: API keys are not supported for Vertex AI endpoint"
    )
    # Dev client succeeds
    mock_inter = _make_mock_interaction("dev_inter_999")
    dev_client.interactions.create.return_value = mock_inter

    client = OmniFlashClient(mock_mode=True)
    client.mock_mode = False
    client.retry_delay = 0.0
    client._vertex_client = vertex_client
    client._dev_client = dev_client
    client._genai_client = vertex_client

    with patch("builtins.open", MagicMock()), patch("os.makedirs", MagicMock()):
        success, inter_id, error_message = client._generate_live_omni_flash_video(
            prompt="A wizard dancing",
            target_rel_path="static/rendered/test.mp4",
        )

    assert success is True
    assert inter_id == "dev_inter_999"
    assert error_message is None
    assert client._genai_client == dev_client

    # Verify error mitigation event was logged
    assert (
        "401 UNAUTHENTICATED on Vertex AI. Actively switching to Google AI Studio Developer API client."
        in caplog.text
    )


def test_exponential_backoff_retry_on_429_rate_limit_exhausted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    vertex_client = MagicMock()
    vertex_client.interactions.create.side_effect = RuntimeError(
        "429 ResourceExhausted: Rate limit exceeded"
    )

    client = OmniFlashClient(mock_mode=True)
    client.mock_mode = False
    client.retry_delay = 0.0
    client._vertex_client = vertex_client
    client._dev_client = None
    client._genai_client = vertex_client

    success, inter_id, error_message = client._generate_live_omni_flash_video(
        prompt="A wizard dancing",
        target_rel_path="static/rendered/test.mp4",
    )

    assert success is False
    assert inter_id is None
    assert error_message is not None
    assert "429" in error_message or "ResourceExhausted" in error_message
    assert vertex_client.interactions.create.call_count == 3


def test_exponential_backoff_retry_on_429_transient_success() -> None:
    vertex_client = MagicMock()
    mock_inter = _make_mock_interaction("transient_success_inter")
    vertex_client.interactions.create.side_effect = [
        RuntimeError("429 ResourceExhausted: Rate limit exceeded"),
        RuntimeError("429 ResourceExhausted: Rate limit exceeded"),
        mock_inter,
    ]

    client = OmniFlashClient(mock_mode=True)
    client.mock_mode = False
    client.retry_delay = 0.0
    client._vertex_client = vertex_client
    client._dev_client = None
    client._genai_client = vertex_client

    with patch("builtins.open", MagicMock()), patch("os.makedirs", MagicMock()):
        success, inter_id, error_message = client._generate_live_omni_flash_video(
            prompt="A wizard dancing",
            target_rel_path="static/rendered/test.mp4",
        )

    assert success is True
    assert inter_id == "transient_success_inter"
    assert error_message is None
    assert vertex_client.interactions.create.call_count == 3


def test_generation_result_modes_success_and_fallback() -> None:
    client = OmniFlashClient(mock_mode=True)
    client.mock_mode = False
    client.retry_delay = 0.0

    # 1. Success case
    with (
        patch.object(
            client,
            "_generate_live_omni_flash_video",
            return_value=(True, "live_thread_123", None),
        ),
        patch.object(client.storage, "upload_file"),
        patch.object(client.storage, "get_gcs_uri", return_value="gs://bucket/test.mp4"),
    ):
        res = client.generate_clip("Prompt test")
        assert res.generation_mode == "LIVE_OMNI_FLASH"
        assert res.error_message is None
        assert res.interaction_thread_id == "live_thread_123"

        res_diff = client.apply_interaction_diff("live_thread_123", "Diff test")
        assert res_diff.generation_mode == "LIVE_OMNI_FLASH"
        assert res_diff.error_message is None

        res_reanchor = client.start_thread_from_video("/static/test.mp4", "Reanchor test")
        assert res_reanchor.generation_mode == "LIVE_OMNI_FLASH"
        assert res_reanchor.error_message is None

    # 2. Fallback case
    with (
        patch.object(
            client,
            "_generate_live_omni_flash_video",
            return_value=(False, None, "Vertex AI 404 Endpoint Not Found"),
        ),
        patch("omnimash.engine.omni_client.ensure_rendered_video"),
        patch.object(client.storage, "upload_file"),
        patch.object(client.storage, "get_gcs_uri", return_value="gs://bucket/test.mp4"),
    ):
        res_fallback = client.generate_clip("Prompt fallback")
        assert res_fallback.generation_mode == "LOCAL_PROCEDURAL_ANIMATION"
        assert res_fallback.error_message == "Vertex AI 404 Endpoint Not Found"

        res_diff_fallback = client.apply_interaction_diff("live_thread_123", "Diff fallback")
        assert res_diff_fallback.generation_mode == "LOCAL_PROCEDURAL_ANIMATION"
        assert res_diff_fallback.error_message == "Vertex AI 404 Endpoint Not Found"

        res_reanchor_fallback = client.start_thread_from_video(
            "/static/test.mp4", "Reanchor fallback"
        )
        assert res_reanchor_fallback.generation_mode == "LOCAL_PROCEDURAL_ANIMATION"
        assert res_reanchor_fallback.error_message == "Vertex AI 404 Endpoint Not Found"
