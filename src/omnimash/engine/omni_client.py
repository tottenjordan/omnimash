import base64
from contextvars import ContextVar
from dataclasses import dataclass
import json
import logging
import os
import re
import subprocess
import tempfile
import time
from typing import Any
from urllib.parse import quote
import uuid

from omnimash.config import settings
from omnimash.engine.guardrails import (
    _abstract_prompt_for_responsible_ai,
    _get_relaxed_safety_settings as _guardrails_get_relaxed_safety_settings,
    parse_guardrail_error_guidance,
)
from omnimash.engine.media_loader import (
    build_mock_keyframe_svg_data_uri,
    build_mock_ref_sheet_svg_data_uri,
    coerce_character_roles,
    fetch_media_bytes,
    render_svg_to_png_bytes,
)
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
    AESTHETIC_SIGNIFIERS,
    CharacterRole,
    build_character_image_ref_tags,
    get_character_identifier,
    replace_character_in_text_image_tags,
    sanitize_real_names,
    sort_characters_by_role_id,
)
from omnimash.storage.gcs import GcsStorageManager

logger = logging.getLogger("omnimash.engine")

try:
    from google import genai
except ImportError:
    genai: Any = None

_LAST_KEYFRAME_PROMPT_VAR: ContextVar[str] = ContextVar("_last_keyframe_prompt", default="")
_STOP_WORDS = frozenset(
    {"the", "and", "fam", "bruv", "chef", "blood", "star", "queen", "king", "master"}
)


@dataclass
class GenerationResult:
    interaction_thread_id: str
    video_url: str
    gcs_uri: str | None = None
    duration_seconds: int = 10
    synth_id_watermark: str = "SYNTHID_C2PA_VERIFIED"
    error_message: str | None = None
    generation_mode: str = "LIVE_OMNI_FLASH"


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
        """Loads reference images for characters, base64-encoding them into Gemini multimodal input dicts with ordinal payload index mapping."""
        if not characters:
            return [], {}

        image_objects: list[Any] = []
        char_img_map: dict[str, int] = {}
        curr_idx = starting_index

        sorted_chars = sort_characters_by_role_id(characters)

        for char in sorted_chars:
            role_id = (
                getattr(char, "role_id", "")
                if not isinstance(char, dict)
                else char.get("role_id", "")
            )
            name = getattr(char, "name", "") if not isinstance(char, dict) else char.get("name", "")
            ref_url = (
                getattr(char, "reference_url", None)
                if not isinstance(char, dict)
                else char.get("reference_url")
            )
            if not ref_url or not isinstance(ref_url, str):
                continue

            img_bytes, mime_type = self._fetch_image_bytes(ref_url)

            if img_bytes:
                lower_ref = ref_url.lower()
                if lower_ref.endswith(".mp4"):
                    mime_type = "video/mp4"
                elif lower_ref.endswith(".png"):
                    mime_type = "image/png"
                elif lower_ref.endswith(".jpg") or lower_ref.endswith(".jpeg"):
                    mime_type = "image/jpeg"

                upload_client = (
                    self._genai_client
                    if (
                        self._genai_client
                        and getattr(self._genai_client, "vertexai", False) is not True
                    )
                    else self._dev_client
                )
                if (
                    len(img_bytes) > 25 * 1024 * 1024
                    and upload_client
                    and hasattr(upload_client, "files")
                ):
                    suffix = ".mp4" if mime_type == "video/mp4" else ".png"
                    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_f:
                        tmp_f.write(img_bytes)
                        tmp_path = tmp_f.name
                    try:
                        upload_config: Any = {"mime_type": mime_type}
                        if (
                            genai
                            and hasattr(genai, "types")
                            and hasattr(genai.types, "UploadFileConfig")
                        ):
                            upload_config = genai.types.UploadFileConfig(mime_type=mime_type)
                        file_obj = upload_client.files.upload(file=tmp_path, config=upload_config)
                        image_objects.append(file_obj)
                    finally:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                else:
                    b64_str = base64.b64encode(img_bytes).decode("utf-8")
                    type_key = "video" if mime_type.startswith("video/") else "image"
                    image_objects.append(
                        {
                            "type": type_key,
                            "data": b64_str,
                            "mime_type": mime_type,
                        }
                    )
                char_id = get_character_identifier(char)
                r_id = str(role_id or "").strip()
                n_str = str(name or "").strip()
                n_clean = sanitize_real_names(n_str) if n_str else ""
                base_n = re.sub(r"\s*\(.*?\)", "", n_str).strip() if n_str else ""
                base_n_clean = sanitize_real_names(base_n) if base_n else ""

                candidate_keys: set[str] = set()
                for k in (char_id, r_id, n_str, n_clean, base_n, base_n_clean):
                    if k and k.strip():
                        candidate_keys.add(k.strip())

                if r_id and n_str:
                    candidate_keys.add(f"{r_id} ({n_str})")

                for source_n in (base_n, n_str):
                    if source_n:
                        for token in source_n.split():
                            tok = token.strip()
                            if tok:
                                candidate_keys.add(tok)
                                tok_clean = sanitize_real_names(tok)
                                if tok_clean and tok_clean.strip():
                                    candidate_keys.add(tok_clean.strip())

                for key in candidate_keys:
                    if key and key.strip():
                        k_str = key.strip()
                        char_img_map[k_str] = curr_idx
                        char_img_map[k_str.lower()] = curr_idx
                curr_idx += 1
            else:
                char_id = get_character_identifier(char)
                logger.warning(
                    "Character %s has reference_url '%s' but image bytes could not be loaded!",
                    char_id,
                    ref_url,
                )

        return image_objects, char_img_map

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
        """Assembles keyframe seed image, motion reference video clip, character reference images, character roster header with visual reference bindings, and timecoded prompt text cleanly into Omni Flash multimodal payload."""
        keyframe_image_parts: list[dict[str, Any]] = []
        if keyframe_image_url:
            img_bytes, mime_type = self._fetch_image_bytes(keyframe_image_url)
            if img_bytes:
                b64_str = base64.b64encode(img_bytes).decode("utf-8")
                type_key = (
                    "video"
                    if (
                        mime_type.startswith("video/")
                        or keyframe_image_url.lower().endswith(".mp4")
                    )
                    else "image"
                )
                keyframe_image_parts.append(
                    {
                        "type": type_key,
                        "data": b64_str,
                        "mime_type": mime_type,
                    }
                )

        motion_ref_parts: list[dict[str, Any]] = []
        has_motion_ref = False
        if motion_reference_clip:
            m_bytes, _ = self._fetch_image_bytes(motion_reference_clip)
            if m_bytes:
                b64_str = base64.b64encode(m_bytes).decode("utf-8")
                motion_ref_parts.append(
                    {
                        "type": "video",
                        "data": b64_str,
                        "mime_type": "video/mp4",
                    }
                )
                has_motion_ref = True

        has_kf_seed = bool(keyframe_image_parts)
        start_ref_idx = 1
        ref_image_parts, _ = self._load_reference_images_as_input(
            session_id, characters, starting_index=start_ref_idx
        )
        all_image_parts = keyframe_image_parts + motion_ref_parts + ref_image_parts

        sources_items, references_items, char_tag_map = build_character_image_ref_tags(
            characters=characters,
            starting_index=start_ref_idx,
            has_keyframe_seed=has_kf_seed,
            enable_sanitization=enable_safety_sanitization,
        )

        if has_motion_ref:
            references_items.append("<VIDEO_REF_0>@VideoReference1")

        input_roles_lines: list[str] = []
        if sources_items:
            input_roles_lines.append(f"[# Sources {' '.join(sources_items)}]")
        if references_items:
            input_roles_lines.append(f"[# References {' '.join(references_items)}]")

        input_roles_header = (
            "### INPUT ROLES\n" + "\n".join(input_roles_lines) + "\n\n" if input_roles_lines else ""
        )

        tone_header = ""
        if keyframe_image_parts and "# Visual Tone & Starting Frame Anchor" not in prompt:
            tone_header = (
                "# Visual Tone & Starting Frame Anchor:\n"
                "Attached Image #1 is the keyframe starting concept art frame for this shot. "
                "Begin the video clip from Attached Image #1 and match its exact color palette, "
                "lighting scheme, camera angle, and aesthetic tone.\n\n"
            )

        motion_ref_header = ""
        if has_motion_ref and "# Motion Reference Conditioning:" not in prompt:
            motion_ref_header = (
                "# Motion Reference Conditioning:\n"
                "Condition motion choreography, pacing, camera movement, and kinetic timing "
                "on the attached motion reference video clip (<VIDEO_REF_0>@VideoReference1).\n\n"
            )

        notes_header = ""
        if directors_notes:
            if isinstance(directors_notes, dict):
                lines_n = ["# Director's Notes & Relational Dynamics:"]
                for k, v in directors_notes.items():
                    if k != "raw_notes" and v:
                        lines_n.append(f"- {k.replace('_', ' ').title()}: {v}")
                if len(lines_n) > 1:
                    notes_header = "\n".join(lines_n) + "\n\n"
            elif isinstance(directors_notes, str) and directors_notes.strip():
                notes_header = (
                    f"# Director's Notes & Relational Dynamics:\n{directors_notes.strip()}\n\n"
                )

        character_roster_header = ""
        if characters:
            char_lines: list[str] = ["# Character Roster & Visual Directives:"]
            for c in coerce_character_roles(characters):
                char_id = get_character_identifier(c)
                tag_str = f" [Style: {', '.join(c.aesthetic_tags)}]" if c.aesthetic_tags else ""
                tag = char_tag_map.get(char_id)
                tag_ref_str = f" {tag}" if tag else ""
                char_lines.append(f"- {char_id}{tag_ref_str}: {c.description}{tag_str}")
            character_roster_header = "\n".join(char_lines) + "\n\n"

        clean_prompt = (
            sanitize_real_names(prompt)
            if (prompt and enable_safety_sanitization)
            else (prompt or "")
        )
        if char_tag_map and clean_prompt:
            for c_id in sorted(char_tag_map.keys(), key=len, reverse=True):
                tag = char_tag_map[c_id]
                if tag not in clean_prompt and c_id in clean_prompt:
                    clean_prompt = clean_prompt.replace(c_id, f"{c_id} {tag}")

        if "### INPUT ROLES" in clean_prompt and input_roles_header:
            clean_prompt = re.sub(
                r"### INPUT ROLES\n.*?\n\n",
                input_roles_header,
                clean_prompt,
                flags=re.DOTALL,
            )
            input_roles_header = ""

        if (
            "# Character Roster & Visual Directives:" in clean_prompt
            or "### CHARACTER PROFILES" in clean_prompt
        ):
            character_roster_header = ""

        sanitized_input = (
            input_roles_header
            + tone_header
            + motion_ref_header
            + notes_header
            + character_roster_header
            + clean_prompt
        )

        if all_image_parts:
            text_part = {"type": "text", "text": sanitized_input}
            return [{"type": "user_input", "content": all_image_parts + [text_part]}]
        return sanitized_input

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

        model_id = getattr(settings, "omni_model_id", "gemini-omni-1.1-flash-preview")
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
        if genai and hasattr(genai, "types") and hasattr(genai.types, "Part"):
            contents.append(genai.types.Part.from_bytes(data=img_bytes, mime_type=mime_type))
        else:
            contents.append(
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64.b64encode(img_bytes).decode("utf-8"),
                    }
                }
            )

    def _execute_gemini_image_generation(
        self,
        *,
        contents: list[Any],
        image_model: str,
        aspect_ratio: str,
        blob_prefix: str,
        log_context: str,
    ) -> str | None:
        """Shared execution helper for Gemini image generation (keyframe & reference sheet) with thought-part filtering and client cleanup."""
        effective_key = (
            self.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        )
        if effective_key:
            image_client = genai.Client(api_key=effective_key, vertexai=False)
        else:
            image_client = genai.Client(
                vertexai=True,
                project=self.project,
                location="global",
            )
        try:
            config = None
            if hasattr(genai, "types") and hasattr(genai.types, "GenerateContentConfig"):
                image_cfg = (
                    genai.types.ImageConfig(aspect_ratio=aspect_ratio)
                    if hasattr(genai.types, "ImageConfig") and aspect_ratio
                    else None
                )
                config = genai.types.GenerateContentConfig(
                    safety_settings=_get_relaxed_safety_settings(),
                    image_config=image_cfg,
                )

            clean_model = image_model.strip() if image_model else ""
            target_model = (
                "gemini-nano-banana-2.1"
                if not clean_model or clean_model.startswith("gemini-3.1-flash-image")
                else clean_model
            )
            response = image_client.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            if response and hasattr(response, "candidates") and response.candidates:
                for candidate in response.candidates:
                    content = getattr(candidate, "content", None)
                    parts = getattr(content, "parts", []) if content else []
                    for part in parts:
                        if getattr(part, "thought", False) is True:
                            continue
                        inline_data = getattr(part, "inline_data", None)
                        if inline_data and getattr(inline_data, "data", None):
                            data = inline_data.data
                            img_bytes = base64.b64decode(data) if isinstance(data, str) else data
                            blob_name = f"{blob_prefix}_{uuid.uuid4().hex[:8]}.png"
                            self.storage.upload_bytes(
                                img_bytes, blob_name, content_type="image/png"
                            )
                            gcs_uri = self.storage.get_gcs_uri(blob_name)
                            return f"/api/media-proxy?uri={quote(gcs_uri, safe='')}"
        except Exception as e:
            logger.warning("gemini-nano-banana-2.1 generation failed for %s: %s", log_context, e)
        finally:
            if hasattr(image_client, "close"):
                try:
                    image_client.close()
                except Exception:
                    pass
        return None

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
        """Generates a visual keyframe image directive using Gemini Nano Banana 2.1 (or Gemini 3 Pro Image)."""
        sanitized_prompt = sanitize_real_names(prompt)
        full_prompt = f"{sanitized_prompt}, style: {style_tone}" if style_tone else sanitized_prompt

        all_char_objs = coerce_character_roles(characters)
        if all_char_objs:
            char_objs = [
                c for c in all_char_objs if _is_char_in_prompt(c, prompt, sanitized_prompt)
            ]
            if not char_objs:
                char_objs = list(all_char_objs)
        else:
            char_objs = []

        ordered_ref_urls: list[str] = []
        for c in char_objs:
            if c.reference_url and c.reference_url.strip():
                u = c.reference_url.strip()
                if u not in ordered_ref_urls and u != anchor_keyframe_url:
                    ordered_ref_urls.append(u)

        if reference_image_urls:
            for u in reference_image_urls:
                if (
                    u
                    and u.strip()
                    and u.strip() not in ordered_ref_urls
                    and u.strip() != anchor_keyframe_url
                ):
                    ordered_ref_urls.append(u.strip())

        reference_image_urls = ordered_ref_urls

        style_preset_header = ""
        if style_preset and style_preset.strip():
            preset_key = style_preset.lower().strip()
            if preset_key in AESTHETIC_SIGNIFIERS:
                signifiers = AESTHETIC_SIGNIFIERS[preset_key]
                preset_wardrobe = signifiers.get("wardrobe", "")
                preset_camera = signifiers.get("camera", "")
                style_preset_header = (
                    f"# Style Preset ({style_preset}):\n"
                    f"- Preset Wardrobe Baseline: {preset_wardrobe}\n"
                    f"- Camera & Visual Style: {preset_camera}\n\n"
                )
            else:
                style_preset_header = f"# Style Preset Context:\nStyle: {style_preset}\n\n"

        global_wardrobe_header = f"# Wardrobe Directives:\n{wardrobe}\n\n" if wardrobe else ""

        ref_url_to_token: dict[str, str] = {}
        if anchor_keyframe_url:
            ref_url_to_token[anchor_keyframe_url] = "@KeyframeSeed"

        token_counter = 1
        if reference_image_urls:
            for ref_url in reference_image_urls:
                if ref_url not in ref_url_to_token:
                    ref_url_to_token[ref_url] = f"@Image{token_counter}"
                    token_counter += 1
        elif char_objs:
            for c in char_objs:
                if c.reference_url and c.reference_url not in ref_url_to_token:
                    ref_url_to_token[c.reference_url] = f"@Image{token_counter}"
                    token_counter += 1

        character_roster_header = ""
        name_to_img_tag: dict[str, str] = {}
        if char_objs:
            char_lines: list[str] = ["# Character Roster & Visual Directives:"]
            for c in char_objs:
                char_id = get_character_identifier(c)
                wardrobe_str = f" [Wardrobe: {c.wardrobe}]" if c.wardrobe else ""
                tag_str = f" [Style: {', '.join(c.aesthetic_tags)}]" if c.aesthetic_tags else ""
                if c.reference_url and c.reference_url.strip():
                    token = ref_url_to_token.get(c.reference_url, c.reference_url)
                    name_to_img_tag[char_id] = token
                    if c.name:
                        name_to_img_tag[c.name] = token
                        san_name = sanitize_real_names(c.name).strip()
                        if san_name:
                            name_to_img_tag[san_name] = token
                        base_name = re.sub(r"\s*\(.*?\)", "", c.name).strip()
                        if base_name:
                            name_to_img_tag[base_name] = token
                            san_base = sanitize_real_names(base_name).strip()
                            if san_base:
                                name_to_img_tag[san_base] = token
                    desc_part = f" {c.description}" if c.description else ""
                    char_lines.append(
                        f"- {char_id}: (Reference Image: {token}){desc_part}{wardrobe_str}{tag_str}"
                    )
                else:
                    desc_part = f"{c.description}" if c.description else ""
                    line_body = f"{desc_part}{wardrobe_str}{tag_str}".strip()
                    char_lines.append(f"- {char_id}: {line_body}")
            character_roster_header = "\n".join(char_lines) + "\n\n"

        if name_to_img_tag and full_prompt:
            full_prompt = replace_character_in_text_image_tags(full_prompt, name_to_img_tag)

        anchor_instruction = (
            "Maintain exact subject face, character likeness, wardrobe baseline, and environmental lighting from <FIRST_FRAME>@KeyframeSeed while rendering the new action/angle.\n\n"
            if anchor_keyframe_url
            else ""
        )

        prompt_text = (
            f"{anchor_instruction}"
            f"{character_roster_header}"
            f"{style_preset_header}"
            f"{global_wardrobe_header}"
            f"# Scene Action & Lighting:\n{full_prompt}"
        )
        self.last_keyframe_prompt = prompt_text

        def _get_mock_keyframe() -> str:
            return build_mock_keyframe_svg_data_uri(
                prompt=prompt,
                style_preset=style_preset,
                style_tone=style_tone,
                aspect_ratio=aspect_ratio,
            )

        def _return(
            url: str,
            start_ns: int | None = None,
            lat_ms: float | None = None,
        ) -> Any:
            url_str = (
                url
                if isinstance(url, str)
                else (url[0] if isinstance(url, (list, tuple)) else str(url))
            )
            self._log_multimodal_inference(
                session_id=session_id or "global",
                turn_name="keyframe",
                input_prompt={
                    "prompt": prompt_text,
                    "reference_image_uris": list(ref_url_to_token.keys()),
                },
                output_data={
                    "media_url": url_str,
                    "gcs_uri": url_str if url_str.startswith("gs://") else None,
                    "generation_mode": "MOCK_SVG" if self.mock_mode else "LIVE_GEMINI_IMAGE",
                    "error_message": None,
                },
                characters=char_objs,
                keyframe_image_url=anchor_keyframe_url,
                reference_image_uris=list(ref_url_to_token.keys()),
                start_time_ns=start_ns,
                latency_ms=lat_ms,
            )
            if return_compiled_prompt:
                return url, prompt_text
            return url

        if self.mock_mode or not genai:
            return _return(_get_mock_keyframe())

        start_time_ns = time.time_ns()
        try:
            contents: list[Any] = []
            if anchor_keyframe_url:
                anchor_bytes, anchor_mime = self._fetch_image_bytes(anchor_keyframe_url)
                if anchor_bytes:
                    self._append_image_part(contents, anchor_bytes, anchor_mime)

            if reference_image_urls:
                for ref_url in reference_image_urls:
                    if anchor_keyframe_url and ref_url == anchor_keyframe_url:
                        continue
                    img_bytes, mime_type = self._fetch_image_bytes(ref_url)
                    if img_bytes:
                        self._append_image_part(contents, img_bytes, mime_type)

            logger.info(
                "==================== [KEYFRAME PROMPT SENT TO GEMINI] ====================\n%s\n=====================================================================",
                prompt_text,
            )
            contents.append(prompt_text)

            live_url = self._execute_gemini_image_generation(
                contents=contents,
                image_model=image_model,
                aspect_ratio=aspect_ratio,
                blob_prefix="keyframes/keyframe",
                log_context="keyframe",
            )
            latency_ms = (time.time_ns() - start_time_ns) / 1_000_000.0
            if live_url:
                return _return(live_url, start_ns=start_time_ns, lat_ms=latency_ms)
            return _return(_get_mock_keyframe(), start_ns=start_time_ns, lat_ms=latency_ms)
        except Exception as exc:
            logger.warning("Failed to generate keyframe image via GenAI client: %s", exc)
            return _return(_get_mock_keyframe())

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
        """Generates a multi-panel character reference sheet image using Gemini Flash Image."""
        tags_str = ", ".join(aesthetic_tags) if aesthetic_tags else ""
        style_directive = (
            f" in the exact artistic style of {style_preset}"
            if style_preset and style_preset.strip()
            else ""
        )
        if custom_prompt_override and custom_prompt_override.strip():
            prompt_text = custom_prompt_override.strip()
            if style_directive and style_preset and style_preset not in prompt_text:
                prompt_text = f"{prompt_text} (Artistic Style: {style_preset})"
        else:
            prompt_text = (
                f"A multi-panel character sheet layout on a white background{style_directive}, "
                f"featuring a single, consistent character based on your source @Image1, their visual likeness and description ({description}), "
                f"and their wardrobe and aesthetic style signifiers ({tags_str}). Re-draw and re-style Attached Image #1 into the specified artistic medium ({style_preset if style_preset else 'cinematic photo realistic'}). On the far left, a high-detail, close-up feature bust. "
                f"To the right of that, a vertical column featuring front, profile, and back head busts in high detail. "
                f"To the right of that, a horizontal row of three matching-style full-body figures: direct front, three-quarter front, "
                f"and three-quarter back views, all in neutral poses showing full gear. The perspectives and layout are precise, "
                f"replicating exactly with the new character's details. No additional text."
            )

        if source_image_url and "(Reference Image: @Image1)" not in prompt_text:
            prompt_text = f"{prompt_text} (Reference Image: @Image1)"

        def _get_mock_ref_sheet() -> str:
            return build_mock_ref_sheet_svg_data_uri(
                character_name=character_name,
                description=description,
                aspect_ratio=aspect_ratio,
            )

        def _return(
            url: str,
            start_ns: int | None = None,
            lat_ms: float | None = None,
        ) -> Any:
            url_str = (
                url
                if isinstance(url, str)
                else (url[0] if isinstance(url, (list, tuple)) else str(url))
            )
            self._log_multimodal_inference(
                session_id=session_id or "global",
                turn_name="turnaround",
                input_prompt={
                    "prompt": prompt_text,
                    "reference_image_uris": [source_image_url] if source_image_url else [],
                },
                output_data={
                    "media_url": url_str,
                    "gcs_uri": url_str if url_str.startswith("gs://") else None,
                    "generation_mode": "MOCK_SVG" if self.mock_mode else "LIVE_GEMINI_IMAGE",
                    "error_message": None,
                },
                reference_image_uris=[source_image_url] if source_image_url else [],
                start_time_ns=start_ns,
                latency_ms=lat_ms,
            )
            if return_compiled_prompt:
                return url, prompt_text
            return url

        if self.mock_mode or not genai:
            return _return(_get_mock_ref_sheet())

        start_time_ns = time.time_ns()
        try:
            contents: list[Any] = []
            if source_image_url:
                img_bytes, mime_type = self._fetch_image_bytes(source_image_url)
                if img_bytes:
                    self._append_image_part(contents, img_bytes, mime_type)

            contents.append(prompt_text)

            live_url = self._execute_gemini_image_generation(
                contents=contents,
                image_model=image_model,
                aspect_ratio=aspect_ratio,
                blob_prefix="ref_sheets/ref_sheet",
                log_context="reference sheet",
            )
            latency_ms = (time.time_ns() - start_time_ns) / 1_000_000.0
            if live_url:
                return _return(live_url, start_ns=start_time_ns, lat_ms=latency_ms)
            return _return(_get_mock_ref_sheet(), start_ns=start_time_ns, lat_ms=latency_ms)
        except Exception as exc:
            logger.warning("Failed to generate character reference sheet via GenAI client: %s", exc)
            return _return(_get_mock_ref_sheet())

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
        """Generates a multi-panel character turnaround reference sheet image using Gemini Flash Image."""
        return self.generate_character_reference_sheet(
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
    "OmniClient",
    "OmniEngineClient",
    "OmniFlashClient",
    "_abstract_prompt_for_responsible_ai",
    "_generate_dynamic_audio_wav",
    "_get_relaxed_safety_settings",
    "ensure_rendered_video",
    "extract_clean_dialogue_summary",
    "get_relaxed_safety_settings",
    "parse_guardrail_error_guidance",
]
