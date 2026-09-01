"""OpenTelemetry telemetry logger helper for Google Cloud Observability & Gemini Enterprise Agent Platform.

Configures GenAI OpenTelemetry semantic conventions v1.37.0+ for logging multimodal
prompt JSONL exports, Cloud Trace span formatting, and guardrail error guidance.
"""

import logging
import os

from opentelemetry import trace

logger = logging.getLogger("omnimash.engine.telemetry")


class GenAITelemetryLogger:
    """Helper class for logging OpenTelemetry GenAI inference spans and structured telemetry."""

    def __init__(self, bucket_name: str, app_name: str = "omnimash-api") -> None:
        self.bucket_name = bucket_name
        self.app_name = app_name
        self.tracer = trace.get_tracer(app_name)

    def build_telemetry_labels(
        self,
        session_id: str,
        error_code: str | None = None,
        guardrail_type: str | None = None,
        resolution: str | None = None,
        previous_interaction_id: str | None = None,
    ) -> dict[str, str]:
        """Builds structured OpenTelemetry GenAI span labels matching OpenTelemetry GenAI semantic conventions.

        Args:
            session_id: Unique session identifier for input/output GCS references.
            error_code: Optional error code if inference or guardrail failed.
            guardrail_type: Optional guardrail type if safety filter was triggered.
            resolution: Optional generation resolution (e.g. '360p', '720p', '4k').
            previous_interaction_id: Optional previous interaction thread ID for stateful turns.

        Returns:
            Dictionary containing OpenTelemetry GenAI labels.
        """
        labels: dict[str, str] = {
            "gen_ai.system": "vertex_ai",
            "gen_ai.session.id": str(session_id),
            "event.name": "gen_ai.client.inference.operation.details",
            "gen_ai.input.messages_ref": f"gs://{self.bucket_name}/telemetry/{session_id}_input.jsonl",
            "gen_ai.output.messages_ref": f"gs://{self.bucket_name}/telemetry/{session_id}_output.jsonl",
        }

        if resolution is not None:
            labels["gen_ai.request.resolution"] = str(resolution)

        if previous_interaction_id is not None:
            labels["previous_interaction_id"] = str(previous_interaction_id)

        if error_code is not None:
            labels["gen_ai.error.code"] = str(error_code)

        if guardrail_type is not None:
            labels["gen_ai.safety.guardrail_type"] = str(guardrail_type)

        return labels

    def start_inference_span(
        self,
        session_id: str,
        span_name: str = "gen_ai.client.inference",
        error_code: str | None = None,
        guardrail_type: str | None = None,
        resolution: str | None = None,
        previous_interaction_id: str | None = None,
    ) -> trace.Span:
        """Starts an OpenTelemetry span prepopulated with GenAI telemetry labels.

        Args:
            session_id: Session identifier.
            span_name: OpenTelemetry span name.
            error_code: Optional error code.
            guardrail_type: Optional guardrail safety type.
            resolution: Optional generation resolution.
            previous_interaction_id: Optional previous interaction identifier.

        Returns:
            Active OpenTelemetry Span.
        """
        labels = self.build_telemetry_labels(
            session_id=session_id,
            error_code=error_code,
            guardrail_type=guardrail_type,
            resolution=resolution,
            previous_interaction_id=previous_interaction_id,
        )
        return self.tracer.start_span(name=span_name, attributes=labels)



def setup_opentelemetry_genai_logging(
    bucket_name: str, app_name: str = "omnimash-api"
) -> GenAITelemetryLogger:
    """Configures OpenTelemetry telemetry environment variables and initializes GenAITelemetryLogger.

    Configures flags for Google Cloud Observability & Gemini Enterprise Agent Platform best practices:
    - OTEL_SEMCONV_STABILITY_OPT_IN='gen_ai_latest_experimental'
    - OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK='upload'
    - OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT='jsonl'
    - GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY='true'

    Args:
        bucket_name: GCS bucket name used for telemetry message refs.
        app_name: Tracer and application name (defaults to "omnimash-api").

    Returns:
        Configured GenAITelemetryLogger instance.
    """
    os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = "gen_ai_latest_experimental"
    os.environ["OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK"] = "upload"
    os.environ["OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT"] = "jsonl"
    os.environ["GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"] = "true"

    telemetry_logger = GenAITelemetryLogger(bucket_name=bucket_name, app_name=app_name)
    logger.info(
        "OpenTelemetry GenAI logging initialized for app %s with telemetry bucket gs://%s",
        app_name,
        bucket_name,
    )
    return telemetry_logger
