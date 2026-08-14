import os
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

    assert (
        os.environ.get("OTEL_SEMCONV_STABILITY_OPT_IN") == "gen_ai_latest_experimental"
    )
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
