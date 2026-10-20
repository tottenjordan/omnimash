"""OpenTelemetry telemetry logger helper for Google Cloud Observability & Gemini Enterprise Agent Platform.

Configures GenAI OpenTelemetry semantic conventions v1.37.0+ for logging multimodal
prompt JSONL exports, Cloud Trace span formatting, and guardrail error guidance.
"""

import logging
import os
import re
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger("omnimash.engine.telemetry")

_URI_REGEX = re.compile(r"(?:gs://|https?://)[^\s)\]>\"']+")
_CHARACTER_URI_KEYS = (
    "reference_url",
    "reference_image_url",
    "turnaround_url",
    "turnaround_sheet_url",
    "uri",
    "url",
)
_ITEM_URI_KEYS = ("uri", "url", "gcs_uri", "reference_url")


def extract_character_uris(characters: list[Any] | None) -> list[str]:
    """Extracts all reference/turnaround image URIs from a list of CharacterRole objects or dicts."""
    if not characters:
        return []
    uris: list[str] = []
    for c in characters:
        if isinstance(c, dict):
            for uri_key in _CHARACTER_URI_KEYS:
                val = c.get(uri_key)
                if val and isinstance(val, str) and val.strip():
                    uris.append(val.strip())
        else:
            for uri_key in _CHARACTER_URI_KEYS:
                val = getattr(c, uri_key, None)
                if val and isinstance(val, str) and val.strip():
                    uris.append(val.strip())
    return uris


def _extract_item_texts_and_uris(item: Any, texts: list[str], uris: list[str]) -> None:
    """Recursively extracts prompt text and reference image URIs from multimodal content items."""
    if isinstance(item, str):
        texts.append(item)
        uris.extend(_URI_REGEX.findall(item))
    elif isinstance(item, dict):
        item_type = item.get("type")
        if item_type == "text":
            t = str(item.get("text", ""))
            texts.append(t)
            uris.extend(_URI_REGEX.findall(t))
        elif item_type == "image":
            for uri_key in _ITEM_URI_KEYS:
                if uri_key in item and item[uri_key]:
                    uris.append(str(item[uri_key]))
        elif item_type == "user_input" and "content" in item and isinstance(item["content"], list):
            for sub in item["content"]:
                _extract_item_texts_and_uris(sub, texts, uris)


def extract_telemetry_prompt_and_uris(
    input_prompt: Any,
    characters: list[Any] | None = None,
    keyframe_image_url: str | None = None,
    reference_image_uris: list[str] | None = None,
) -> tuple[str, str, list[str]]:
    """Extracts system instructions, normalized prompt text, and deduplicated reference image URIs for telemetry JSONL export."""
    system_instructions = "Omnimash Engine Multimodal Generation"
    prompt_text = ""
    ref_image_uris: list[str] = []

    if reference_image_uris:
        ref_image_uris.extend([str(u) for u in reference_image_uris if u])

    if keyframe_image_url and isinstance(keyframe_image_url, str) and keyframe_image_url.strip():
        ref_image_uris.append(keyframe_image_url.strip())

    ref_image_uris.extend(extract_character_uris(characters))

    if isinstance(input_prompt, str):
        prompt_text = input_prompt
        ref_image_uris.extend(_URI_REGEX.findall(input_prompt))
    elif isinstance(input_prompt, dict):
        prompt_text = str(input_prompt.get("prompt", input_prompt.get("text", str(input_prompt))))
        if "system_instructions" in input_prompt:
            system_instructions = str(input_prompt["system_instructions"])
        if "reference_image_uris" in input_prompt and isinstance(
            input_prompt["reference_image_uris"], list
        ):
            ref_image_uris.extend([str(u) for u in input_prompt["reference_image_uris"] if u])
        elif "reference_urls" in input_prompt and isinstance(input_prompt["reference_urls"], list):
            ref_image_uris.extend([str(u) for u in input_prompt["reference_urls"] if u])
        if "keyframe_image_url" in input_prompt and input_prompt["keyframe_image_url"]:
            ref_image_uris.append(str(input_prompt["keyframe_image_url"]))
        if "characters" in input_prompt and isinstance(input_prompt["characters"], list):
            ref_image_uris.extend(extract_character_uris(input_prompt["characters"]))
    elif isinstance(input_prompt, list):
        texts: list[str] = []
        for item in input_prompt:
            _extract_item_texts_and_uris(item, texts, ref_image_uris)
        prompt_text = "\n".join(texts)
    else:
        prompt_text = str(input_prompt or "")

    cleaned_uris = sorted({u for u in ref_image_uris if u and isinstance(u, str)})
    return system_instructions, prompt_text, cleaned_uris


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
        latency_ms: float | None = None,
    ) -> dict[str, str]:
        """Builds structured OpenTelemetry GenAI span labels matching OpenTelemetry GenAI semantic conventions.

        Args:
            session_id: Unique session identifier for input/output GCS references.
            error_code: Optional error code if inference or guardrail failed.
            guardrail_type: Optional guardrail type if safety filter was triggered.
            resolution: Optional generation resolution (e.g. '360p', '720p', '4k').
            previous_interaction_id: Optional previous interaction thread ID for stateful turns.
            latency_ms: Optional measured inference latency in milliseconds.

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

        if latency_ms is not None:
            labels["gen_ai.client.inference.duration_ms"] = f"{latency_ms:.2f}"

        return labels

    def start_inference_span(
        self,
        session_id: str,
        span_name: str = "gen_ai.client.inference",
        error_code: str | None = None,
        guardrail_type: str | None = None,
        resolution: str | None = None,
        previous_interaction_id: str | None = None,
        start_time_ns: int | None = None,
        latency_ms: float | None = None,
    ) -> trace.Span:
        """Starts an OpenTelemetry span prepopulated with GenAI telemetry labels.

        Args:
            session_id: Session identifier.
            span_name: OpenTelemetry span name.
            error_code: Optional error code.
            guardrail_type: Optional guardrail safety type.
            resolution: Optional generation resolution.
            previous_interaction_id: Optional previous interaction identifier.
            start_time_ns: Optional start timestamp in nanoseconds since epoch.
            latency_ms: Optional measured inference latency in milliseconds.

        Returns:
            Active OpenTelemetry Span.
        """
        labels = self.build_telemetry_labels(
            session_id=session_id,
            error_code=error_code,
            guardrail_type=guardrail_type,
            resolution=resolution,
            previous_interaction_id=previous_interaction_id,
            latency_ms=latency_ms,
        )
        start_kwargs: dict[str, Any] = {"name": span_name, "attributes": labels}
        if start_time_ns is not None:
            start_kwargs["start_time"] = start_time_ns
        span = self.tracer.start_span(**start_kwargs)
        if error_code is not None and span and hasattr(span, "set_status"):
            span.set_status(Status(StatusCode.ERROR, str(error_code)))
        return span


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
    os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest_experimental")
    os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK", "upload")
    os.environ.setdefault("OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT", "jsonl")
    os.environ.setdefault("GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", "true")

    telemetry_logger = GenAITelemetryLogger(bucket_name=bucket_name, app_name=app_name)
    logger.info(
        "OpenTelemetry GenAI logging initialized for app %s with telemetry bucket gs://%s",
        app_name,
        bucket_name,
    )
    return telemetry_logger
