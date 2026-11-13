"""Keyframe image generation and multi-panel turnaround sheet synthesis."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
import io
import logging
import math
import os
import re
import time
from typing import Any, Callable, Sequence
from urllib.parse import parse_qs, quote, urlparse
import uuid

from pydantic import BaseModel, Field

from omnimash.config import settings
from omnimash.engine.guardrails import (
    _get_relaxed_safety_settings as _guardrails_get_relaxed_safety_settings,
)
from omnimash.engine.media_loader import (
    build_mock_keyframe_svg_data_uri,
    build_mock_ref_sheet_svg_data_uri,
    coerce_character_roles,
    fetch_media_bytes,
    render_svg_to_png_bytes,
)
from omnimash.ingestion.ref_cleaner import ReferenceHygieneProcessor
from omnimash.prompts.compiler import (
    AESTHETIC_SIGNIFIERS,
    CharacterRole,
    get_character_identifier,
    replace_character_in_text_image_tags,
    sanitize_real_names,
)

logger = logging.getLogger("omnimash.engine.keyframe_client")

try:
    from google import genai
except ImportError:
    genai: Any = None

try:
    from PIL import Image, ImageDraw, ImageOps

    HAS_PIL = True
except ImportError:
    Image: Any = None
    ImageDraw: Any = None
    ImageOps: Any = None
    HAS_PIL = False

NO_SAMPLING_IMAGE_MODELS: frozenset[str] = frozenset({"gemini-nano-banana-2.1"})
LITE_1K_ONLY_MODELS: frozenset[str] = frozenset({"gemini-3.1-flash-lite-image"})
DEPRECATED_IMAGE_MODEL_MAP: dict[str, str] = {
    "gemini-3.1-flash-image": "gemini-nano-banana-2.1",
}
_SCENE_FRAME_PATH_RE = re.compile(r"(?:/keyframes/|keyframe_[0-9a-f]{8}|shot[AB]_)", re.IGNORECASE)

_LAST_KEYFRAME_PROMPT_VAR: ContextVar[str] = ContextVar("_last_keyframe_prompt", default="")
_STOP_WORDS = frozenset(
    {"the", "and", "fam", "bruv", "chef", "blood", "star", "queen", "king", "master"}
)


class Gate1CandidateItem(BaseModel):
    """Single seeded keyframe candidate produced during a Gate-1 batch run."""

    candidate_id: str
    shot_label: str
    model: str
    seed: int | None
    image_size: str
    aspect_ratio: str
    image_url: str
    gcs_uri: str | None = None
    compiled_prompt: str


class Gate1BatchResult(BaseModel):
    """Complete result of a Gate-1 multi-candidate keyframe batch run."""

    shot_label: str
    compiled_prompt: str
    candidates: list[Gate1CandidateItem] = Field(default_factory=list)
    contact_sheet_url: str | None = None
    recommended_candidate_id: str | None = None


def _resolve_image_model_and_size(
    image_model: str | None, image_size: str = "2K"
) -> tuple[str, str]:
    """Resolves deprecated image model aliases and enforces per-model image_size rules."""
    clean_model = (image_model or "").strip() or getattr(
        settings, "image_model_id", "gemini-3-pro-image"
    )
    if clean_model in DEPRECATED_IMAGE_MODEL_MAP:
        mapped_model = DEPRECATED_IMAGE_MODEL_MAP[clean_model]
        logger.warning(
            "Deprecated image model %s mapped to %s",
            clean_model,
            mapped_model,
        )
        target_model = mapped_model
    elif clean_model.startswith("gemini-3.1-flash-image"):
        logger.warning(
            "Deprecated image model %s mapped to %s",
            clean_model,
            "gemini-nano-banana-2.1",
        )
        target_model = "gemini-nano-banana-2.1"
    else:
        target_model = clean_model

    if target_model in LITE_1K_ONLY_MODELS:
        effective_size = "1K"
    else:
        normalized_size = (image_size or "2K").strip().upper()
        effective_size = normalized_size if normalized_size in {"1K", "2K", "4K"} else "2K"
    return target_model, effective_size


def _extract_gcs_uri(url: str) -> str | None:
    """Extracts a gs:// URI from a direct gs:// path or /api/media-proxy URL."""
    if not url:
        return None
    if url.startswith("gs://"):
        return url
    if "/api/media-proxy?uri=" in url:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "uri" in qs and qs["uri"]:
            return qs["uri"][0]
    return None


def render_gate1_contact_sheet(
    tiles: Sequence[tuple[str, bytes]],
    *,
    columns: int = 3,
    tile_width: int = 640,
    tile_height: int = 360,
    padding: int = 16,
    quality: int = 90,
) -> bytes:
    """Renders candidate keyframe tiles into a labeled JPEG contact sheet (default 3x2 for N=6)."""
    if not HAS_PIL:
        raise RuntimeError("Pillow is required to render Gate-1 contact sheets")

    cols = max(1, int(columns))
    rows = max(1, math.ceil(max(1, len(tiles)) / cols))
    canvas_w = cols * tile_width + (cols + 1) * padding
    canvas_h = rows * tile_height + (rows + 1) * padding
    sheet = Image.new("RGB", (canvas_w, canvas_h), (14, 18, 28))
    draw = ImageDraw.Draw(sheet)

    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)

    for idx, (label, img_bytes) in enumerate(tiles):
        row = idx // cols
        col = idx % cols
        x0 = padding + col * (tile_width + padding)
        y0 = padding + row * (tile_height + padding)

        tile_img: Any = None
        if img_bytes:
            try:
                with Image.open(io.BytesIO(img_bytes)) as opened:
                    tile_img = ImageOps.fit(
                        opened.convert("RGB"),
                        (tile_width, tile_height),
                        method=resample,
                    )
            except Exception as exc:
                logger.warning(
                    "Failed to decode candidate tile %s for contact sheet: %s", label, exc
                )
                tile_img = None

        if tile_img is None:
            tile_img = Image.new("RGB", (tile_width, tile_height), (26, 32, 46))

        sheet.paste(tile_img, (x0, y0))
        badge_w = min(tile_width - 16, max(120, len(label) * 8 + 20))
        draw.rectangle([(x0 + 8, y0 + 8), (x0 + 8 + badge_w, y0 + 34)], fill=(12, 16, 26))
        draw.text((x0 + 16, y0 + 14), label, fill=(248, 250, 252))

    out_buf = io.BytesIO()
    sheet.save(out_buf, format="JPEG", quality=quality)
    return out_buf.getvalue()


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
    return False


class KeyframeClient:
    """Handles keyframe concept art synthesis and character reference/turnaround sheets using Gemini image models."""

    def __init__(
        self,
        mock_mode: bool | None = None,
        storage: Any | None = None,
        api_key: str | None = None,
        project: str | None = None,
        genai_client: Any | None = None,
        log_inference_fn: Callable[..., None] | None = None,
        fetch_image_fn: Callable[[str], tuple[bytes, str]] | None = None,
        storage_getter: Callable[[], Any] | None = None,
        api_key_getter: Callable[[], str | None] | None = None,
        project_getter: Callable[[], str | None] | None = None,
    ) -> None:
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self._storage = storage
        self._api_key = api_key
        self._project = project
        self._genai_client = genai_client
        self._log_inference_fn = log_inference_fn
        self._fetch_image_fn = fetch_image_fn
        self._storage_getter = storage_getter
        self._api_key_getter = api_key_getter
        self._project_getter = project_getter

    @property
    def storage(self) -> Any:
        if self._storage_getter is not None:
            return self._storage_getter()
        return self._storage

    @storage.setter
    def storage(self, val: Any) -> None:
        self._storage = val

    @property
    def api_key(self) -> str | None:
        if self._api_key_getter is not None:
            return self._api_key_getter()
        return self._api_key

    @property
    def project(self) -> str:
        if self._project_getter is not None:
            res = self._project_getter()
            if res:
                return res
        return (
            self._project
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
            or os.environ.get("GCP_PROJECT")
            or getattr(settings, "gcp_project_id", "mock-project")
        )

    @property
    def last_keyframe_prompt(self) -> str:
        return _LAST_KEYFRAME_PROMPT_VAR.get()

    @last_keyframe_prompt.setter
    def last_keyframe_prompt(self, val: str) -> None:
        _LAST_KEYFRAME_PROMPT_VAR.set(val)

    @staticmethod
    def _render_svg_to_png_bytes(svg_bytes: bytes | None = None) -> bytes:
        return render_svg_to_png_bytes(svg_bytes)

    def _fetch_image_bytes(self, ref_url: str) -> tuple[bytes, str]:
        if self._fetch_image_fn is not None:
            return self._fetch_image_fn(ref_url)
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
        image_size: str = "2K",
        seed: int | None = None,
    ) -> str | None:
        """Shared execution helper for Gemini image generation with 2K/seed support and thought filtering."""
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
        target_model, effective_size = _resolve_image_model_and_size(image_model, image_size)

        def _build_config(*, include_seed: bool) -> Any:
            if not (hasattr(genai, "types") and hasattr(genai.types, "GenerateContentConfig")):
                return None
            image_cfg = None
            if hasattr(genai.types, "ImageConfig"):
                img_cfg_kwargs: dict[str, Any] = {}
                if aspect_ratio:
                    img_cfg_kwargs["aspect_ratio"] = aspect_ratio
                if effective_size:
                    img_cfg_kwargs["image_size"] = effective_size
                if img_cfg_kwargs:
                    try:
                        image_cfg = genai.types.ImageConfig(**img_cfg_kwargs)
                    except TypeError:
                        img_cfg_kwargs.pop("image_size", None)
                        image_cfg = (
                            genai.types.ImageConfig(**img_cfg_kwargs) if img_cfg_kwargs else None
                        )

            gen_cfg_kwargs: dict[str, Any] = {
                "safety_settings": _guardrails_get_relaxed_safety_settings(genai_module=genai),
                "image_config": image_cfg,
            }
            if include_seed and seed is not None and target_model not in NO_SAMPLING_IMAGE_MODELS:
                gen_cfg_kwargs["seed"] = int(seed)
            return genai.types.GenerateContentConfig(**gen_cfg_kwargs)

        try:
            used_seed = seed is not None and target_model not in NO_SAMPLING_IMAGE_MODELS
            config = _build_config(include_seed=used_seed)
            try:
                response = image_client.models.generate_content(
                    model=target_model,
                    contents=contents,
                    config=config,
                )
            except Exception as api_exc:
                err_lower = str(api_exc).lower()
                if used_seed and (
                    "seed" in err_lower
                    or "invalid" in err_lower
                    or "unsupported" in err_lower
                    or isinstance(api_exc, TypeError)
                ):
                    logger.warning(
                        "Image model %s rejected seed=%s (%s); retrying once without seed.",
                        target_model,
                        seed,
                        api_exc,
                    )
                    config = _build_config(include_seed=False)
                    response = image_client.models.generate_content(
                        model=target_model,
                        contents=contents,
                        config=config,
                    )
                else:
                    raise

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
                            effective_storage = self.storage
                            if effective_storage is not None and hasattr(
                                effective_storage, "upload_bytes"
                            ):
                                effective_storage.upload_bytes(
                                    img_bytes, blob_name, content_type="image/png"
                                )
                                gcs_uri = effective_storage.get_gcs_uri(blob_name)
                                return f"/api/media-proxy?uri={quote(gcs_uri, safe='')}"
        except Exception as e:
            logger.warning("Image generation (%s) failed for %s: %s", target_model, log_context, e)
        finally:
            if hasattr(image_client, "close"):
                try:
                    image_client.close()
                except Exception as close_exc:
                    logger.debug("Failed to close GenAI image client: %s", close_exc)
        return None

    def _log_inference(self, **kwargs: Any) -> None:
        if self._log_inference_fn is not None:
            try:
                self._log_inference_fn(**kwargs)
            except Exception as exc:
                logger.warning("Failed to emit multimodal inference log: %s", exc)

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
        image_size: str = "2K",
        seed: int | None = None,
    ) -> Any:
        """Generates a visual keyframe image directive using Gemini Nano Banana 2.1 (or Gemini 3 Pro Image)."""
        if anchor_keyframe_url and _SCENE_FRAME_PATH_RE.search(anchor_keyframe_url):
            logger.warning(
                "SCENE_KEYFRAME_CHAINING_BANNED: Stripping scene-frame anchor_keyframe_url=%s; "
                "camera angle transitions must render independently from cleaned character portrait.",
                anchor_keyframe_url,
            )
            anchor_keyframe_url = None

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
            self._log_inference(
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
                        cleaned_bytes, was_cropped = (
                            ReferenceHygieneProcessor.extract_clean_single_portrait(img_bytes)
                        )
                        effective_mime = "image/png" if was_cropped else mime_type
                        self._append_image_part(contents, cleaned_bytes, effective_mime)

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
                image_size=image_size,
                seed=seed,
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
            self._log_inference(
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

    def generate_gate1_candidate_batch(
        self,
        prompt: str,
        *,
        shot_label: str = "shot_a",
        style_tone: str = "",
        reference_image_urls: list[str] | None = None,
        characters: list[Any] | None = None,
        directors_notes: dict[str, Any] | str | None = None,
        style_preset: str | None = None,
        wardrobe: str | None = None,
        anchor_keyframe_url: str | None = None,
        aspect_ratio: str = "16:9",
        image_model: str = "gemini-3-pro-image",
        image_size: str = "2K",
        base_seed: int = 4101,
        num_candidates: int = 1,
        session_id: str | None = None,
    ) -> Gate1BatchResult:
        """Generates 1 (default Q2 Option A) or N seeded 2K candidates and a 3x2 JPEG contact sheet when N > 1."""
        count = max(1, int(num_candidates))
        resolved_model, effective_size = _resolve_image_model_and_size(image_model, image_size)

        def _render_single(idx: int) -> Gate1CandidateItem:
            seed_val: int | None = (
                None if resolved_model in NO_SAMPLING_IMAGE_MODELS else int(base_seed) + idx
            )
            res = self.generate_keyframe_image(
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
                return_compiled_prompt=True,
                session_id=session_id,
                image_size=effective_size,
                seed=seed_val,
            )
            url, compiled_prompt = res if isinstance(res, tuple) else (str(res), prompt)
            seed_suffix = str(seed_val) if seed_val is not None else "noseed"
            return Gate1CandidateItem(
                candidate_id=f"{shot_label}_c{idx + 1}_{seed_suffix}",
                shot_label=shot_label,
                model=resolved_model,
                seed=seed_val,
                image_size=effective_size,
                aspect_ratio=aspect_ratio,
                image_url=str(url),
                gcs_uri=_extract_gcs_uri(str(url)),
                compiled_prompt=compiled_prompt,
            )

        if count == 1:
            candidates = [_render_single(0)]
        else:
            with ThreadPoolExecutor(max_workers=min(3, count)) as pool:
                candidates = list(pool.map(_render_single, range(count)))

        contact_sheet_url: str | None = None
        if count > 1 and candidates:
            tiles: list[tuple[str, bytes]] = []
            for idx, item in enumerate(candidates):
                raw_bytes, _ = self._fetch_image_bytes(item.image_url)
                tile_bytes = (
                    bytes(raw_bytes)
                    if isinstance(raw_bytes, (bytes, bytearray)) and raw_bytes
                    else self._render_svg_to_png_bytes()
                )
                label = f"#{idx + 1} seed={item.seed}" if item.seed is not None else f"#{idx + 1}"
                tiles.append((label, tile_bytes))

            sheet_bytes = render_gate1_contact_sheet(tiles, columns=3)
            effective_storage = self.storage
            if effective_storage is not None and hasattr(effective_storage, "upload_bytes"):
                blob_name = f"keyframes/gate1_{shot_label}_{uuid.uuid4().hex[:8]}.jpg"
                effective_storage.upload_bytes(sheet_bytes, blob_name, content_type="image/jpeg")
                gcs_uri = effective_storage.get_gcs_uri(blob_name)
                contact_sheet_url = f"/api/media-proxy?uri={quote(gcs_uri, safe='')}"
            else:
                encoded = base64.b64encode(sheet_bytes).decode("utf-8")
                contact_sheet_url = f"data:image/jpeg;base64,{encoded}"

        return Gate1BatchResult(
            shot_label=shot_label,
            compiled_prompt=candidates[0].compiled_prompt if candidates else prompt,
            candidates=candidates,
            contact_sheet_url=contact_sheet_url,
            recommended_candidate_id=candidates[0].candidate_id if candidates else None,
        )


__all__ = [
    "DEPRECATED_IMAGE_MODEL_MAP",
    "Gate1BatchResult",
    "Gate1CandidateItem",
    "KeyframeClient",
    "LITE_1K_ONLY_MODELS",
    "NO_SAMPLING_IMAGE_MODELS",
    "_LAST_KEYFRAME_PROMPT_VAR",
    "render_gate1_contact_sheet",
]
