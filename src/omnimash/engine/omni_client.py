import base64
import json
import logging
import os
import re
import subprocess
import time
from typing import Any
import uuid

from omnimash.config import settings
from omnimash.engine.guardrails import (
    _abstract_prompt_for_responsible_ai,
    _get_relaxed_safety_settings as _guardrails_get_relaxed_safety_settings,
    parse_guardrail_error_guidance,
)
from omnimash.engine.media_loader import (
    fetch_media_bytes,
    render_svg_to_png_bytes,
)
from omnimash.engine.keyframe_client import KeyframeClient, _LAST_KEYFRAME_PROMPT_VAR
from omnimash.engine.models import GenerationResult
from omnimash.engine.multimodal import build_multimodal_contents, load_reference_images_as_input
from omnimash.engine.procedural_renderer import (
    _generate_dynamic_audio_wav,
    ensure_rendered_video,
    extract_clean_dialogue_summary,
)
from omnimash.engine.telemetry import (
    extract_telemetry_prompt_and_uris,
    setup_opentelemetry_genai_logging,
)
from omnimash.prompts.compiler import (
    CharacterRole,
    sanitize_real_names,
)
from omnimash.storage.gcs import GcsStorageManager

logger = logging.getLogger("omnimash.engine")

try:
    from google import genai
except ImportError:
    genai: Any = None

_STOP_WORDS = frozenset(
    {"the", "and", "fam", "bruv", "chef", "blood", "star", "queen", "king", "master"}
)


def _get_relaxed_safety_settings() -> list[Any] | None:
    """Configures relaxed BLOCK_NONE safety thresholds across all harm categories for unrestricted Gemini Omni Flash video generation."""
    return _guardrails_get_relaxed_safety_settings(genai_module=genai)


get_relaxed_safety_settings = _get_relaxed_safety_settings


def _is_char_in_prompt(char: CharacterRole, raw_p: str, san_p: str) -> bool:
    """Returns True if a character's role_id, name, or sanitized name tokens appear in the prompt."""
    r_lower = raw_p.lower()
    s_lower = san_p.lower()

    role_id = (char.role_id or "").strip()
    if role_id and (role_id.lower() in r_lower or role_id.lower() in s_lower):
        return True

    name = (char.name or "").strip()
    if not name:
        return False

    if name.lower() in r_lower or name.lower() in s_lower:
        return True

    words = [
        w.lower() for w in re.split(r"\W+", name) if len(w) >= 3 and w.lower() not in _STOP_WORDS
    ]
    if any(w in r_lower or w in s_lower for w in words):
        return True

    san_name = sanitize_real_names(name).strip()
    if san_name:
        if san_name.lower() in r_lower or san_name.lower() in s_lower:
            return True
        san_words = [
            w.lower()
            for w in re.split(r"\W+", san_name)
            if len(w) >= 3 and w.lower() not in _STOP_WORDS
        ]
        if any(w in r_lower or w in s_lower for w in san_words):
            return True

    return False


class OmniFlashClient:
    def __init__(
        self,
        api_key: str | None = None,
        mock_mode: bool | None = None,
        bucket_name: str | None = None,
        retry_delay: float | None = None,
        storage: GcsStorageManager | None = None,
    ):
        self.api_key = api_key
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self.retry_delay = retry_delay if retry_delay is not None else (0.0 if mock_mode else 0.5)
        self.project = os.environ.get(
            "GOOGLE_CLOUD_PROJECT",
            getattr(settings, "google_cloud_project", "hybrid-vertex"),
        )
        self.location = os.environ.get(
            "GEMINI_LOCATION", getattr(settings, "gemini_location", "global")
        )
        self._dev_client: Any = None
        self._vertex_client: Any = None
        self._genai_client: Any = None
        self.last_keyframe_prompt = ""
        self.storage = storage or GcsStorageManager(
            bucket_name=bucket_name,
            project_id=self.project,
            mock_mode=self.mock_mode,
        )
        self.telemetry = setup_opentelemetry_genai_logging(bucket_name=self.storage.bucket_name)

        effective_key = (
            self.api_key
            if self.api_key is not None
            else (
                os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or getattr(settings, "gemini_api_key", None)
                or getattr(settings, "google_api_key", None)
            )
        )
        if not self.mock_mode and genai:
            from google.genai import types

            http_options = types.HttpOptions(timeout=300000)

            if effective_key:
                try:
                    self._dev_client = genai.Client(
                        api_key=effective_key,
                        vertexai=False,
                        http_options=http_options,
                    )
                except Exception as exc:
                    logger.warning("Failed to initialize Developer API client: %s", exc)

            try:
                self._vertex_client = genai.Client(
                    vertexai=True,
                    project=self.project,
                    location=self.location,
                    http_options=http_options,
                )
            except Exception as exc:
                logger.warning("Failed to initialize Vertex AI client: %s", exc)

            self._genai_client = self._dev_client or self._vertex_client

        self._keyframe_client = KeyframeClient(
            mock_mode=self.mock_mode,
            storage=self.storage,
            api_key=self.api_key,
            project=self.project,
            genai_client=self._genai_client,
            log_inference_fn=self._log_multimodal_inference,
            fetch_image_fn=lambda u: self._fetch_image_bytes(u),
            storage_getter=lambda: self.storage,
            api_key_getter=lambda: self.api_key,
            project_getter=lambda: self.project,
        )

    @property
    def last_keyframe_prompt(self) -> str:
        return _LAST_KEYFRAME_PROMPT_VAR.get()

    @last_keyframe_prompt.setter
    def last_keyframe_prompt(self, value: str) -> None:
        _LAST_KEYFRAME_PROMPT_VAR.set(value)

    @property
    def _api_key_client(self) -> Any:
        return self._dev_client

    def switch_to_developer_api(self) -> bool:
        """Switches active client to Developer API client."""
        if self._dev_client:
            self._genai_client = self._dev_client
            if hasattr(self, "_keyframe_client"):
                self._keyframe_client._genai_client = self._dev_client
            return True
        return False

    def _log_multimodal_inference(
        self,
        session_id: str,
        turn_name: str,
        input_prompt: Any,
        output_data: dict[str, Any],
        error_code: str | None = None,
        guardrail_type: str | None = None,
        characters: list[Any] | None = None,
        keyframe_image_url: str | None = None,
        reference_image_uris: list[str] | None = None,
        resolution: str | None = None,
        previous_interaction_id: str | None = None,
        start_time_ns: int | None = None,
        latency_ms: float | None = None,
    ) -> None:
        """Logs multimodal prompt JSONL exports and OpenTelemetry GenAI inference spans to Cloud Storage and Cloud Trace."""
        sid = session_id or "global"
        tname = turn_name or "inference"

        system_instructions, prompt_text, cleaned_uris = extract_telemetry_prompt_and_uris(
            input_prompt=input_prompt,
            characters=characters,
            keyframe_image_url=keyframe_image_url,
            reference_image_uris=reference_image_uris,
        )

        input_record = {
            "system_instructions": system_instructions,
            "prompt_text": prompt_text,
            "reference_image_uris": cleaned_uris,
        }
        input_jsonl = json.dumps(input_record) + "\n"

        output_record = {
            "media_url": output_data.get("media_url") or output_data.get("video_url"),
            "gcs_uri": output_data.get("gcs_uri"),
            "generation_mode": output_data.get("generation_mode", "LIVE_OMNI_FLASH"),
            "error_message": output_data.get("error_message") or error_code,
        }
        output_jsonl = json.dumps(output_record) + "\n"

        input_blob_name = f"telemetry/{sid}_{tname}_input.jsonl"
        output_blob_name = f"telemetry/{sid}_{tname}_output.jsonl"

        try:
            self.storage.upload_bytes(
                input_jsonl.encode("utf-8"),
                input_blob_name,
                content_type="application/x-ndjson",
            )
            self.storage.upload_bytes(
                output_jsonl.encode("utf-8"),
                output_blob_name,
                content_type="application/x-ndjson",
            )
        except Exception as exc:
            logger.warning("Failed to upload telemetry JSONL logs to GCS: %s", exc)

        session_key = f"{sid}_{tname}"
        try:
            span_kwargs: dict[str, Any] = {
                "session_id": session_key,
                "error_code": error_code,
                "guardrail_type": guardrail_type,
                "resolution": resolution,
                "previous_interaction_id": previous_interaction_id,
            }
            if start_time_ns is not None:
                span_kwargs["start_time_ns"] = start_time_ns
            if latency_ms is not None:
                span_kwargs["latency_ms"] = latency_ms
            span = self.telemetry.start_inference_span(**span_kwargs)
            if span:
                span.end()
        except Exception as exc:
            logger.warning("Failed to emit OpenTelemetry span: %s", exc)

    def _load_reference_images_as_input(
        self,
        session_id: str | None,
        characters: list[CharacterRole] | None = None,
        starting_index: int = 1,
    ) -> tuple[list[Any], dict[str, int]]:
        return load_reference_images_as_input(
            session_id=session_id,
            characters=characters,
            fetch_image_fn=self._fetch_image_bytes,
            genai_client=self._genai_client,
            dev_client=self._dev_client,
            starting_index=starting_index,
        )

    def _build_multimodal_contents(
        self,
        prompt: str,
        session_id: str | None = None,
        characters: list[CharacterRole] | None = None,
        keyframe_image_url: str | None = None,
        directors_notes: dict[str, Any] | str | None = None,
        enable_safety_sanitization: bool = True,
        motion_reference_clip: str | None = None,
    ) -> list[dict[str, Any]] | str:
        return build_multimodal_contents(
            prompt=prompt,
            session_id=session_id,
            characters=characters,
            keyframe_image_url=keyframe_image_url,
            directors_notes=directors_notes,
            enable_safety_sanitization=enable_safety_sanitization,
            motion_reference_clip=motion_reference_clip,
            fetch_image_fn=self._fetch_image_bytes,
            genai_client=self._genai_client,
            dev_client=self._dev_client,
        )

    def _poll_and_download_file_uri(
        self,
        file_name: str,
        target_path: str,
        poll_interval: float = 1.0,
        timeout_seconds: float = 60.0,
    ) -> bytes:
        """Polls files.get until state is ACTIVE, then downloads and saves video bytes."""
        if not self._genai_client or not hasattr(self._genai_client, "files"):
            raise RuntimeError("Gemini client files API is not available")

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            file_info = self._genai_client.files.get(name=file_name)
            state = getattr(file_info, "state", None)
            if state == "ACTIVE" or str(state).upper() == "ACTIVE":
                video_bytes = self._genai_client.files.download(file=file_name)
                if target_path:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with open(target_path, "wb") as f:
                        f.write(video_bytes)
                return video_bytes
            if state in ("FAILED", "ERROR") or str(state).upper() in ("FAILED", "ERROR"):
                error_msg = getattr(file_info, "error", None) or "File processing failed"
                raise RuntimeError(f"File URI processing failed: {error_msg}")
            time.sleep(poll_interval)

        raise TimeoutError(
            f"Timed out after {timeout_seconds}s waiting for file URI {file_name} to become ACTIVE"
        )

    def _generate_live_omni_flash_video(
        self,
        prompt: str,
        target_rel_path: str,
        previous_interaction_id: str | None = None,
        characters: list[CharacterRole] | None = None,
        session_id: str | None = None,
        keyframe_image_url: str | None = None,
        directors_notes: dict[str, Any] | str | None = None,
        enable_safety_sanitization: bool = True,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
        duration_seconds: int | float | None = None,
        motion_reference_clip: str | None = None,
    ) -> tuple[bool, str | None, str | None]:
        """Calls Gemini Omni Flash 1.1 Preview via Interactions API for native video+audio generation & conversational editing with 3 retry attempts and active error mitigation."""
        if self.mock_mode:
            ensure_rendered_video(target_rel_path, prompt=prompt)
            self._log_multimodal_inference(
                session_id=session_id or "global",
                turn_name="video_clip",
                input_prompt=prompt,
                output_data={
                    "media_url": target_rel_path,
                    "gcs_uri": self.storage.get_gcs_uri(target_rel_path),
                    "generation_mode": "LIVE_OMNI_FLASH",
                    "error_message": None,
                },
                characters=characters,
                keyframe_image_url=keyframe_image_url,
                resolution=resolution,
                previous_interaction_id=previous_interaction_id,
            )
            return True, previous_interaction_id, None

        if not self._genai_client or not hasattr(self._genai_client, "interactions"):
            msg = "Gemini client or interactions API not available"
            logger.warning("Generation aborted: %s", msg)
            self._log_multimodal_inference(
                session_id=session_id or "global",
                turn_name="video_clip",
                input_prompt=prompt,
                output_data={
                    "media_url": None,
                    "gcs_uri": None,
                    "generation_mode": "LIVE_OMNI_FLASH",
                    "error_message": msg,
                },
                error_code="500",
                characters=characters,
                keyframe_image_url=keyframe_image_url,
                resolution=resolution,
                previous_interaction_id=previous_interaction_id,
            )
            return False, None, msg

        max_attempts = 3
        delay = getattr(self, "retry_delay", 0.0 if self.mock_mode else 0.5)
        last_error: str | None = None
        start_time_ns = time.time_ns()

        input_payload = self._build_multimodal_contents(
            prompt=prompt,
            session_id=session_id,
            characters=characters,
            keyframe_image_url=keyframe_image_url,
            directors_notes=directors_notes,
            enable_safety_sanitization=enable_safety_sanitization,
            motion_reference_clip=motion_reference_clip,
        )

        model_id = getattr(settings, "omni_model_id", "gemini-omni-1.1-flash")
        if (
            self._genai_client is not None
            and self._genai_client is self._dev_client
            and model_id == "gemini-omni-1.1-flash-preview"
        ):
            model_id = "gemini-omni-1.1-flash"
        kwargs: dict[str, Any] = {
            "model": model_id,
            "input": input_payload,
        }
        if previous_interaction_id:
            kwargs["previous_interaction_id"] = previous_interaction_id

        response_format: dict[str, Any] = {
            "type": "video",
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
        }
        if duration_seconds is not None:
            response_format["duration"] = f"{int(duration_seconds)}s"
        if resolution in ("4k", "1080p") and not self.mock_mode:
            response_format["delivery"] = "uri"
        kwargs["response_format"] = response_format

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    "Requesting Gemini Omni Flash video generation (attempt %d/%d) for prompt: %s",
                    attempt,
                    max_attempts,
                    prompt,
                )
                if not self._genai_client or not hasattr(self._genai_client, "interactions"):
                    last_error = "Gemini client or interactions API not available"
                    break

                interaction = self._genai_client.interactions.create(**kwargs)
                inter_id = getattr(interaction, "id", None) or getattr(
                    interaction, "interaction_id", None
                )

                output_vid = getattr(interaction, "output_video", None)
                if not output_vid:
                    outputs = getattr(interaction, "outputs", None)
                    if isinstance(outputs, (list, tuple)) and len(outputs) > 0:
                        output_vid = outputs[0]

                if output_vid:
                    file_uri_name = (
                        getattr(output_vid, "name", None)
                        or getattr(output_vid, "file_uri", None)
                        or getattr(output_vid, "uri", None)
                    )
                    data = (
                        getattr(output_vid, "data", None)
                        or getattr(output_vid, "video_bytes", None)
                        or getattr(output_vid, "bytes", None)
                        or getattr(output_vid, "video", None)
                    )
                    video_bytes = None
                    if data:
                        video_bytes = base64.b64decode(data) if isinstance(data, str) else data
                        os.makedirs(os.path.dirname(target_rel_path), exist_ok=True)
                        with open(target_rel_path, "wb") as f:
                            f.write(video_bytes)
                    elif file_uri_name and hasattr(self._genai_client, "files"):
                        video_bytes = self._poll_and_download_file_uri(
                            file_name=file_uri_name,
                            target_path=target_rel_path,
                        )

                    if video_bytes:
                        logger.info(
                            "Successfully generated native Gemini Omni Flash MP4 to %s (size: %d bytes)",
                            target_rel_path,
                            len(video_bytes),
                        )
                        latency_ms = (time.time_ns() - start_time_ns) / 1_000_000.0
                        self._log_multimodal_inference(
                            session_id=session_id or "global",
                            turn_name="video_clip",
                            input_prompt=prompt,
                            output_data={
                                "media_url": target_rel_path,
                                "gcs_uri": self.storage.get_gcs_uri(target_rel_path),
                                "generation_mode": "LIVE_OMNI_FLASH",
                                "error_message": None,
                            },
                            characters=characters,
                            keyframe_image_url=keyframe_image_url,
                            resolution=resolution,
                            previous_interaction_id=previous_interaction_id,
                            start_time_ns=start_time_ns,
                            latency_ms=latency_ms,
                        )
                        return True, inter_id, None

                last_error = "Gemini Omni Flash returned interaction without video output data"
                logger.warning(last_error)
            except Exception as exc:
                exc_str = str(exc)
                last_error = exc_str

                if (
                    "401" in exc_str
                    or "UNAUTHENTICATED" in exc_str
                    or "API keys are not supported" in exc_str
                ):
                    logger.warning(
                        "401 UNAUTHENTICATED on Vertex AI. Actively switching to Google AI Studio Developer API client."
                    )
                    self.switch_to_developer_api()
                elif "404" in exc_str or "Publisher model" in exc_str:
                    logger.warning(
                        "Vertex AI endpoint unavailable (%s). Actively switching to Google AI Studio Developer API client.",
                        exc_str,
                    )
                    self.switch_to_developer_api()
                    if kwargs.get("model") == "gemini-omni-1.1-flash-preview":
                        kwargs["model"] = "gemini-omni-1.1-flash"
                elif any(
                    k in exc_str.lower()
                    for k in (
                        "input blocked",
                        "real people",
                        "likeness",
                        "safety",
                        "prohibited use",
                        "harmful content",
                        "violated google",
                        "invalid_request",
                        "400",
                    )
                ):
                    raw_text = (
                        input_payload[0]["content"][-1]["text"]
                        if isinstance(input_payload, list)
                        and input_payload
                        and "content" in input_payload[0]
                        else str(input_payload)
                    )
                    if enable_safety_sanitization:
                        fallback_prompt = _abstract_prompt_for_responsible_ai(raw_text)
                        logger.warning(
                            "Gemini Omni Flash safety/likeness guardrail triggered (%s). Abstracting prompt with cartoon parody archetypes for retry: %s",
                            exc_str,
                            fallback_prompt,
                        )
                    else:
                        fallback_prompt = raw_text
                        logger.warning(
                            "Gemini Omni Flash safety/likeness guardrail triggered (%s). Safety sanitization disabled; keeping original prompt for retry.",
                            exc_str,
                        )
                    current_input = kwargs.get("input", input_payload)
                    if (
                        isinstance(current_input, list)
                        and len(current_input) > 0
                        and isinstance(current_input[0], dict)
                        and isinstance(current_input[0].get("content"), list)
                    ):
                        existing_content = current_input[0]["content"]
                        image_parts = [
                            p
                            for p in existing_content
                            if isinstance(p, dict) and p.get("type") != "text"
                        ]
                        text_part = {"type": "text", "text": fallback_prompt}
                        kwargs["input"] = [
                            {"type": "user_input", "content": image_parts + [text_part]}
                        ]
                    else:
                        kwargs["input"] = fallback_prompt
                elif (
                    "safety_settings" in exc_str
                    or "Unmarshaller" in exc_str
                    or "ValidationError" in exc_str
                ):
                    logger.warning(
                        "Interactions API parameter error (%s). Removing unsupported safety_settings kwarg and retrying.",
                        exc_str,
                    )
                    kwargs.pop("safety_settings", None)
                elif "429" in exc_str or "ResourceExhausted" in exc_str:
                    logger.warning(
                        "Retry attempt %d/%d after rate limit error (%s). Backoff delay: %.2fs",
                        attempt,
                        max_attempts,
                        exc_str,
                        delay,
                    )
                else:
                    logger.warning(
                        "Omni Flash generation error on attempt %d/%d: %s",
                        attempt,
                        max_attempts,
                        exc_str,
                    )

                if attempt < max_attempts:
                    if delay > 0 and not (
                        "401" in exc_str
                        or "UNAUTHENTICATED" in exc_str
                        or "API keys are not supported" in exc_str
                    ):
                        time.sleep(delay)
                    delay *= 2

        guardrail_info = (
            parse_guardrail_error_guidance(
                last_error or "", char_objs=characters, prompt_text=prompt
            )
            if last_error
            else {}
        )
        guardrail_type = (
            guardrail_info.get("triggers", [None])[0] if guardrail_info.get("triggers") else None
        )
        latency_ms = (time.time_ns() - start_time_ns) / 1_000_000.0
        self._log_multimodal_inference(
            session_id=session_id or "global",
            turn_name="video_clip",
            input_prompt=prompt,
            output_data={
                "media_url": None,
                "gcs_uri": None,
                "generation_mode": "LIVE_OMNI_FLASH",
                "error_message": last_error,
            },
            error_code=last_error,
            guardrail_type=guardrail_type,
            characters=characters,
            keyframe_image_url=keyframe_image_url,
            resolution=resolution,
            previous_interaction_id=previous_interaction_id,
            start_time_ns=start_time_ns,
            latency_ms=latency_ms,
        )
        return False, None, last_error

    def _finalize_video_clip_result(
        self,
        *,
        success: bool,
        inter_id: str | None,
        fallback_thread_id: str,
        error_message: str | None,
        default_error: str,
        url: str,
        rel_path: str,
        prompt: str,
        session_id: str | None,
        project_id: str | None,
        voiceover: str | None,
        is_silent: bool,
        audio_stem: str | None,
    ) -> GenerationResult:
        """Shared post-processing for video clip generation, procedural fallback, and GCS upload."""
        generation_mode = "LIVE_OMNI_FLASH"
        if not success:
            if self.mock_mode:
                generation_mode = "LOCAL_PROCEDURAL_ANIMATION"
                ensure_rendered_video(
                    url,
                    prompt=prompt,
                    voiceover=voiceover,
                    is_silent=is_silent,
                    audio_stem=audio_stem,
                )
            else:
                return GenerationResult(
                    interaction_thread_id=inter_id or fallback_thread_id,
                    video_url="",
                    gcs_uri=None,
                    error_message=error_message or default_error,
                    generation_mode="LIVE_OMNI_FLASH",
                )

        gcs_blob = self.storage.build_session_blob_path(
            session_id, "intermediate", os.path.basename(rel_path), project_id=project_id
        )
        self.storage.upload_file(rel_path, destination_blob_name=gcs_blob)
        gcs_uri = self.storage.get_gcs_uri(gcs_blob)

        return GenerationResult(
            interaction_thread_id=inter_id or fallback_thread_id,
            video_url=url,
            gcs_uri=gcs_uri,
            error_message=error_message if not success else None,
            generation_mode=generation_mode,
        )

    def generate_clip(
        self,
        prompt: str,
        session_id: str | None = None,
        voiceover: str | None = None,
        is_silent: bool = False,
        audio_stem: str | None = None,
        turn_index: int | None = None,
        characters: list[CharacterRole] | None = None,
        keyframe_image_url: str | None = None,
        enable_safety_sanitization: bool = True,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
        motion_reference_clip: str | None = None,
        project_id: str | None = None,
    ) -> GenerationResult:
        thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        filename = (
            f"turn_{turn_index}_video.mp4" if turn_index is not None else f"{thread_id}_turn0.mp4"
        )
        safe_sess = (
            re.sub(r"[^a-zA-Z0-9_-]", "_", session_id.strip())
            if session_id and session_id.strip()
            else ""
        )
        url = (
            f"/static/rendered/{safe_sess}/{filename}"
            if safe_sess
            else f"/static/rendered/{filename}"
        )
        rel_path = url.lstrip("/")

        success, inter_id, error_message = self._generate_live_omni_flash_video(
            prompt,
            rel_path,
            characters=characters,
            session_id=session_id,
            keyframe_image_url=keyframe_image_url,
            enable_safety_sanitization=enable_safety_sanitization,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            motion_reference_clip=motion_reference_clip,
        )
        return self._finalize_video_clip_result(
            success=success,
            inter_id=inter_id,
            fallback_thread_id=thread_id,
            error_message=error_message,
            default_error="Gemini Omni Flash video generation failed",
            url=url,
            rel_path=rel_path,
            prompt=prompt,
            session_id=session_id,
            project_id=project_id,
            voiceover=voiceover,
            is_silent=is_silent,
            audio_stem=audio_stem,
        )

    def apply_interaction_diff(
        self,
        interaction_thread_id: str,
        diff_prompt: str,
        session_id: str | None = None,
        voiceover: str | None = None,
        is_silent: bool = False,
        audio_stem: str | None = None,
        turn_index: int | None = None,
        characters: list[CharacterRole] | None = None,
        keyframe_image_url: str | None = None,
        enable_safety_sanitization: bool = True,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
        motion_reference_clip: str | None = None,
        project_id: str | None = None,
    ) -> GenerationResult:
        filename = (
            f"turn_{turn_index}_video.mp4"
            if turn_index is not None
            else f"{interaction_thread_id}_turn_diff.mp4"
        )
        safe_sess = (
            re.sub(r"[^a-zA-Z0-9_-]", "_", session_id.strip())
            if session_id and session_id.strip()
            else ""
        )
        url = (
            f"/static/rendered/{safe_sess}/{filename}"
            if safe_sess
            else f"/static/rendered/{filename}"
        )
        rel_path = url.lstrip("/")

        success, inter_id, error_message = self._generate_live_omni_flash_video(
            diff_prompt,
            rel_path,
            previous_interaction_id=interaction_thread_id,
            characters=characters,
            session_id=session_id,
            keyframe_image_url=keyframe_image_url,
            enable_safety_sanitization=enable_safety_sanitization,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            motion_reference_clip=motion_reference_clip,
        )
        return self._finalize_video_clip_result(
            success=success,
            inter_id=inter_id,
            fallback_thread_id=interaction_thread_id,
            error_message=error_message,
            default_error="Gemini Omni Flash interaction diff generation failed",
            url=url,
            rel_path=rel_path,
            prompt=diff_prompt,
            session_id=session_id,
            project_id=project_id,
            voiceover=voiceover,
            is_silent=is_silent,
            audio_stem=audio_stem,
        )

    def start_thread_from_video(
        self,
        base_video_url: str,
        initial_prompt: str | None = None,
        session_id: str | None = None,
        voiceover: str | None = None,
        is_silent: bool = False,
        audio_stem: str | None = None,
        characters: list[CharacterRole] | None = None,
        enable_safety_sanitization: bool = True,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
        regenerate_audio: bool = False,
        project_id: str | None = None,
    ) -> GenerationResult:
        thread_id = f"reanchored_thread_{uuid.uuid4().hex[:8]}"
        url = f"/static/rendered/{thread_id}_turn0.mp4"
        rel_path = url.lstrip("/")

        effective_base_video = base_video_url
        stripped_path: str | None = None
        if regenerate_audio:
            stripped_path = f"static/rendered/{thread_id}_stripped_silent.mp4"
            os.makedirs(os.path.dirname(stripped_path), exist_ok=True)
            ffmpeg_input = (
                base_video_url.lstrip("/")
                if base_video_url.startswith("/static/")
                else base_video_url
            )
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                ffmpeg_input,
                "-c:v",
                "copy",
                "-an",
                stripped_path,
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, check=False)
                if getattr(res, "returncode", 1) == 0:
                    effective_base_video = stripped_path
                else:
                    logger.warning(
                        "FFmpeg audio stripping exited with non-zero code (%s) for %s",
                        getattr(res, "returncode", None),
                        base_video_url,
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to strip audio via FFmpeg from base video %s: %s", base_video_url, exc
                )

        prompt = initial_prompt or "Reanchored video turn"
        try:
            success, inter_id, error_message = self._generate_live_omni_flash_video(
                prompt,
                rel_path,
                characters=characters,
                session_id=session_id,
                keyframe_image_url=effective_base_video,
                enable_safety_sanitization=enable_safety_sanitization,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
            )
        finally:
            if stripped_path and os.path.exists(stripped_path):
                try:
                    os.remove(stripped_path)
                except OSError:
                    pass

        return self._finalize_video_clip_result(
            success=success,
            inter_id=inter_id,
            fallback_thread_id=thread_id,
            error_message=error_message,
            default_error="Gemini Omni Flash video re-anchoring failed",
            url=url,
            rel_path=rel_path,
            prompt=prompt,
            session_id=session_id,
            project_id=project_id,
            voiceover=voiceover,
            is_silent=is_silent,
            audio_stem=audio_stem,
        )

    @staticmethod
    def _render_svg_to_png_bytes(svg_bytes: bytes | None = None) -> bytes:
        return render_svg_to_png_bytes(svg_bytes)

    def _fetch_image_bytes(self, ref_url: str) -> tuple[bytes, str]:
        return fetch_media_bytes(ref_url, storage=self.storage)

    def _append_image_part(self, contents: list[Any], img_bytes: bytes, mime_type: str) -> None:
        self._keyframe_client._append_image_part(contents, img_bytes, mime_type)

    def _execute_gemini_image_generation(self, **kwargs: Any) -> str | None:
        return self._keyframe_client._execute_gemini_image_generation(**kwargs)

    def generate_keyframe_image(
        self,
        prompt: str,
        style_tone: str = "",
        reference_image_urls: list[str] | None = None,
        characters: list[Any] | None = None,
        directors_notes: dict[str, Any] | str | None = None,
        style_preset: str | None = None,
        wardrobe: str | None = None,
        anchor_keyframe_url: str | None = None,
        aspect_ratio: str = "16:9",
        image_model: str = "gemini-nano-banana-2.1",
        return_compiled_prompt: bool = False,
        session_id: str | None = None,
    ) -> Any:
        return self._keyframe_client.generate_keyframe_image(
            prompt=prompt,
            style_tone=style_tone,
            reference_image_urls=reference_image_urls,
            characters=characters,
            directors_notes=directors_notes,
            style_preset=style_preset,
            wardrobe=wardrobe,
            anchor_keyframe_url=anchor_keyframe_url,
            aspect_ratio=aspect_ratio,
            image_model=image_model,
            return_compiled_prompt=return_compiled_prompt,
            session_id=session_id,
        )

    def generate_character_reference_sheet(
        self,
        source_image_url: str | None = None,
        character_name: str = "",
        description: str = "",
        aesthetic_tags: list[str] | None = None,
        custom_prompt_override: str | None = None,
        image_model: str = "gemini-nano-banana-2.1",
        aspect_ratio: str = "16:9",
        return_compiled_prompt: bool = False,
        session_id: str | None = None,
        style_preset: str | None = None,
    ) -> Any:
        return self._keyframe_client.generate_character_reference_sheet(
            source_image_url=source_image_url,
            character_name=character_name,
            description=description,
            aesthetic_tags=aesthetic_tags,
            custom_prompt_override=custom_prompt_override,
            image_model=image_model,
            aspect_ratio=aspect_ratio,
            return_compiled_prompt=return_compiled_prompt,
            session_id=session_id,
            style_preset=style_preset,
        )

    def generate_turnaround_sheet(
        self,
        source_image_url: str | None = None,
        character_name: str = "",
        description: str = "",
        aesthetic_tags: list[str] | None = None,
        custom_prompt_override: str | None = None,
        image_model: str = "gemini-nano-banana-2.1",
        aspect_ratio: str = "16:9",
        return_compiled_prompt: bool = False,
        session_id: str | None = None,
        style_preset: str | None = None,
    ) -> Any:
        return self._keyframe_client.generate_turnaround_sheet(
            source_image_url=source_image_url,
            character_name=character_name,
            description=description,
            aesthetic_tags=aesthetic_tags,
            custom_prompt_override=custom_prompt_override,
            image_model=image_model,
            aspect_ratio=aspect_ratio,
            return_compiled_prompt=return_compiled_prompt,
            session_id=session_id,
            style_preset=style_preset,
        )


OmniClient = OmniFlashClient
OmniEngineClient = OmniFlashClient

__all__ = [
    "GenerationResult",
    "KeyframeClient",
    "OmniClient",
    "OmniEngineClient",
    "OmniFlashClient",
    "_abstract_prompt_for_responsible_ai",
    "_generate_dynamic_audio_wav",
    "_get_relaxed_safety_settings",
    "build_multimodal_contents",
    "ensure_rendered_video",
    "extract_clean_dialogue_summary",
    "get_relaxed_safety_settings",
    "load_reference_images_as_input",
    "parse_guardrail_error_guidance",
]
