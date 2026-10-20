import os
from typing import Any
from unittest.mock import MagicMock

from omnimash.engine.telemetry import (
    GenAITelemetryLogger,
    setup_opentelemetry_genai_logging,
)


def test_setup_opentelemetry_genai_logging_sets_env_vars() -> None:
    # Clear env vars if present to test setup
    env_keys = [
        "OTEL_SEMCONV_STABILITY_OPT_IN",
        "OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK",
        "OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT",
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY",
    ]
    for key in env_keys:
        os.environ.pop(key, None)

    logger_instance = setup_opentelemetry_genai_logging(
        bucket_name="test-telemetry-bucket", app_name="omnimash-test-api"
    )

    assert os.environ.get("OTEL_SEMCONV_STABILITY_OPT_IN") == "gen_ai_latest_experimental"
    assert os.environ.get("OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK") == "upload"
    assert os.environ.get("OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT") == "jsonl"
    assert os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY") == "true"

    assert isinstance(logger_instance, GenAITelemetryLogger)
    assert logger_instance.bucket_name == "test-telemetry-bucket"
    assert logger_instance.app_name == "omnimash-test-api"


def test_build_telemetry_labels_standard() -> None:
    telemetry_logger = GenAITelemetryLogger(bucket_name="my-omnimash-bucket")
    labels = telemetry_logger.build_telemetry_labels(session_id="sess_123")

    assert labels["gen_ai.system"] == "vertex_ai"
    assert labels["gen_ai.session.id"] == "sess_123"
    assert labels["event.name"] == "gen_ai.client.inference.operation.details"
    assert (
        labels["gen_ai.input.messages_ref"]
        == "gs://my-omnimash-bucket/telemetry/sess_123_input.jsonl"
    )
    assert (
        labels["gen_ai.output.messages_ref"]
        == "gs://my-omnimash-bucket/telemetry/sess_123_output.jsonl"
    )
    assert "gen_ai.error.code" not in labels
    assert "gen_ai.safety.guardrail_type" not in labels


def test_build_telemetry_labels_with_error_and_guardrail() -> None:
    telemetry_logger = GenAITelemetryLogger(bucket_name="my-omnimash-bucket")
    labels = telemetry_logger.build_telemetry_labels(
        session_id="sess_456",
        error_code="400",
        guardrail_type="REAL_PERSON_LIKENESS",
    )

    assert labels["gen_ai.system"] == "vertex_ai"
    assert labels["gen_ai.session.id"] == "sess_456"
    assert labels["event.name"] == "gen_ai.client.inference.operation.details"
    assert (
        labels["gen_ai.input.messages_ref"]
        == "gs://my-omnimash-bucket/telemetry/sess_456_input.jsonl"
    )
    assert (
        labels["gen_ai.output.messages_ref"]
        == "gs://my-omnimash-bucket/telemetry/sess_456_output.jsonl"
    )
    assert labels["gen_ai.error.code"] == "400"
    assert labels["gen_ai.safety.guardrail_type"] == "REAL_PERSON_LIKENESS"


def test_start_inference_span() -> None:
    telemetry_logger = GenAITelemetryLogger(bucket_name="my-omnimash-bucket")
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_span.return_value = mock_span
    telemetry_logger.tracer = mock_tracer

    span = telemetry_logger.start_inference_span(
        session_id="sess_789",
        span_name="custom.gen_ai.span",
        error_code="429",
        guardrail_type="RATE_LIMIT",
    )

    expected_labels = {
        "gen_ai.system": "vertex_ai",
        "gen_ai.session.id": "sess_789",
        "event.name": "gen_ai.client.inference.operation.details",
        "gen_ai.input.messages_ref": "gs://my-omnimash-bucket/telemetry/sess_789_input.jsonl",
        "gen_ai.output.messages_ref": "gs://my-omnimash-bucket/telemetry/sess_789_output.jsonl",
        "gen_ai.error.code": "429",
        "gen_ai.safety.guardrail_type": "RATE_LIMIT",
    }
    mock_tracer.start_span.assert_called_once_with(
        name="custom.gen_ai.span", attributes=expected_labels
    )
    assert span == mock_span
    mock_span.set_status.assert_called_once()
    status_arg = mock_span.set_status.call_args.args[0]
    from opentelemetry.trace import StatusCode

    assert status_arg.status_code == StatusCode.ERROR
    assert status_arg.description == "429"


def test_telemetry_inference_span_records_resolution_and_tokens() -> None:
    telemetry_logger = GenAITelemetryLogger(bucket_name="my-omnimash-bucket")
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_span.return_value = mock_span
    telemetry_logger.tracer = mock_tracer

    span = telemetry_logger.start_inference_span(
        session_id="sess_resolution_123",
        span_name="gen_ai.client.inference",
        resolution="4k",
        previous_interaction_id="inter_thread_777",
    )

    expected_labels = {
        "gen_ai.system": "vertex_ai",
        "gen_ai.session.id": "sess_resolution_123",
        "event.name": "gen_ai.client.inference.operation.details",
        "gen_ai.input.messages_ref": "gs://my-omnimash-bucket/telemetry/sess_resolution_123_input.jsonl",
        "gen_ai.output.messages_ref": "gs://my-omnimash-bucket/telemetry/sess_resolution_123_output.jsonl",
        "gen_ai.request.resolution": "4k",
        "previous_interaction_id": "inter_thread_777",
    }
    mock_tracer.start_span.assert_called_once_with(
        name="gen_ai.client.inference", attributes=expected_labels
    )
    assert span == mock_span


def test_setup_opentelemetry_genai_logging_preserves_existing_env_vars(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("OTEL_SEMCONV_STABILITY_OPT_IN", "custom_semconv_value")
    monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT", "custom_format")

    setup_opentelemetry_genai_logging(bucket_name="test-bucket")

    assert os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] == "custom_semconv_value"
    assert os.environ["OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT"] == "custom_format"


def test_start_inference_span_with_start_time_and_latency() -> None:
    telemetry_logger = GenAITelemetryLogger(bucket_name="my-omnimash-bucket")
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_span.return_value = mock_span
    telemetry_logger.tracer = mock_tracer

    span = telemetry_logger.start_inference_span(
        session_id="sess_timed",
        start_time_ns=1_700_000_000_000_000_000,
        latency_ms=142.5,
    )

    assert span == mock_span
    call_kwargs = mock_tracer.start_span.call_args.kwargs
    assert call_kwargs["start_time"] == 1_700_000_000_000_000_000
    assert call_kwargs["attributes"]["gen_ai.client.inference.duration_ms"] == "142.50"


def test_extract_telemetry_prompt_and_uris_handles_str_dict_and_list() -> None:
    from omnimash.engine.telemetry import extract_telemetry_prompt_and_uris

    sys_instr, prompt_text, uris = extract_telemetry_prompt_and_uris(
        input_prompt=[
            {
                "type": "user_input",
                "content": [
                    {"type": "image", "uri": "gs://bucket/img1.png"},
                    {"type": "text", "text": "Scene at https://example.com/ref.png"},
                ],
            }
        ],
        characters=[{"name": "Hero", "reference_url": "gs://bucket/hero.png"}],
        keyframe_image_url="gs://bucket/kf.png",
        reference_image_uris=["gs://bucket/extra.png"],
    )
    assert sys_instr == "Omnimash Engine Multimodal Generation"
    assert "Scene at https://example.com/ref.png" in prompt_text
    assert uris == [
        "gs://bucket/extra.png",
        "gs://bucket/hero.png",
        "gs://bucket/img1.png",
        "gs://bucket/kf.png",
        "https://example.com/ref.png",
    ]
