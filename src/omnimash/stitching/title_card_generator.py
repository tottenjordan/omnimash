"""Generative 24k Gold / Brand-Locked Title Card Renderer anchored to a canonical style frame."""

from __future__ import annotations

import base64
import logging
import os
import shutil
import subprocess
from typing import Any, Literal
import uuid

from omnimash.config import settings
from omnimash.engine.guardrails import (
    _get_relaxed_safety_settings as _guardrails_get_relaxed_safety_settings,
)
from omnimash.stitching.stitcher import (
    HAS_PIL,
    _get_font,
    resolve_target_dimensions,
)
from omnimash.storage.gcs import GcsStorageManager

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]

try:
    from google import genai
except ImportError:
    genai: Any = None

logger = logging.getLogger(__name__)

TitleCardPreset = Literal[
    "gothic_24k_gold",
    "neon_cyber",
    "editorial_minimal",
    "brand_palette_lock",
]

_PRESET_ALIASES: dict[str, str] = {
    "gothic_gold": "gothic_24k_gold",
    "gothic_24k_gold": "gothic_24k_gold",
    "neon_cyber": "neon_cyber",
    "editorial_minimal": "editorial_minimal",
    "brand_palette_lock": "brand_palette_lock",
}

_PRESET_PALETTES: dict[str, dict[str, tuple[int, int, int]]] = {
    "gothic_24k_gold": {
        "bg": (0, 0, 0),
        "title": (218, 175, 58),
        "subtitle": (236, 208, 128),
    },
    "neon_cyber": {
        "bg": (0, 0, 0),
        "title": (0, 255, 240),
        "subtitle": (255, 0, 200),
    },
    "editorial_minimal": {
        "bg": (0, 0, 0),
        "title": (248, 246, 240),
        "subtitle": (205, 202, 195),
    },
    "brand_palette_lock": {
        "bg": (0, 0, 0),
        "title": (245, 230, 200),
        "subtitle": (212, 175, 55),
    },
}


def _normalize_preset(style_preset: str | None) -> str:
    """Normalizes preset aliases into canonical title card preset identifiers."""
    key = (style_preset or "gothic_24k_gold").strip().lower()
    return _PRESET_ALIASES.get(key, "gothic_24k_gold")


def _parse_hex_color(value: str | None, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    """Parses a #RRGGBB hex string into an RGB tuple, falling back safely."""
    if not isinstance(value, str):
        return fallback
    cleaned = value.strip().lstrip("#")
    if len(cleaned) == 3 and all(c in "0123456789abcdefABCDEF" for c in cleaned):
        cleaned = "".join(ch * 2 for ch in cleaned)
    if len(cleaned) == 6 and all(c in "0123456789abcdefABCDEF" for c in cleaned):
        return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))
    return fallback


def build_title_card_image_prompt(
    title_text: str,
    subtitle_text: str = "",
    style_preset: TitleCardPreset | str = "gothic_24k_gold",
    has_style_anchor_image: bool = False,
    brand_palette: dict[str, str] | None = None,
) -> str:
    """Compiles a positive-phrased 2K title card prompt for gemini-3-pro-image."""
    clean_title = title_text.strip().upper()
    clean_sub = subtitle_text.strip().upper()
    preset = _normalize_preset(style_preset)

    palette = brand_palette or {}
    primary_hex = palette.get("primary", "#F5E6C8").strip().upper()
    secondary_hex = palette.get("secondary", "#D4AF37").strip().upper()
    bg_hex = (palette.get("background") or palette.get("neutral") or "#000000").strip().upper()

    if preset == "gothic_24k_gold":
        sub_clause = (
            f' with smaller matching gold subtitle text below reading "{clean_sub}"'
            if clean_sub
            else ""
        )
        if has_style_anchor_image:
            return (
                "Create an image matching the exact 3D chiselled brushed-matte 24k gold serif font family, "
                "bevel geometry, metallic specular lighting, letter spacing, and solid uniform #000000 "
                f'pitch-black background of reference image 1 (@Image1), displaying the exact centered text "{clean_title}"'
                f"{sub_clause}. Centered on a pure, solid, uniform #000000 pitch-black background."
            )
        return (
            "Create an image of a theatrical movie title card displaying the exact centered text "
            f'"{clean_title}"{sub_clause} rendered in 3D chiselled brushed-matte 24k gold serif typography '
            "with crisp bevelled edges and subtle warm metallic reflections, centered on a pure, solid, "
            "uniform #000000 pitch-black background."
        )

    sub_clause = (
        f' with smaller matching subtitle text below reading "{clean_sub}"' if clean_sub else ""
    )

    if preset == "neon_cyber":
        if has_style_anchor_image:
            return (
                "Create an image matching the exact luminous cyan-teal and electric magenta neon-lit "
                "geometric display font family, chrome bevel geometry, glow intensity, letter spacing, "
                "and solid uniform #000000 pitch-black background of reference image 1 (@Image1), "
                f'displaying the exact centered text "{clean_title}"{sub_clause}. '
                "Centered on a pure, solid, uniform #000000 pitch-black background."
            )
        return (
            "Create an image of a theatrical title card displaying the exact centered text "
            f'"{clean_title}"{sub_clause} rendered in razor-sharp 3D luminous cyan-teal (#00FFF0) '
            "and electric magenta (#FF00C8) neon-lit geometric display typography with crisp chrome "
            "bevels and controlled volumetric glow, centered on a pure, solid, uniform #000000 "
            "pitch-black background."
        )

    if preset == "editorial_minimal":
        if has_style_anchor_image:
            return (
                "Create an image matching the exact crisp ivory modern grotesque sans-serif font family, "
                "stroke weight, optical tracking, and solid uniform #000000 pitch-black background of "
                f'reference image 1 (@Image1), displaying the exact centered text "{clean_title}"'
                f"{sub_clause}. Centered on a pure, solid, uniform #000000 pitch-black background."
            )
        return (
            "Create an image of a theatrical editorial title card displaying the exact centered text "
            f'"{clean_title}"{sub_clause} rendered in refined crisp ivory (#F8F6F0) modern grotesque '
            "sans-serif typography with generous optical tracking and balanced Swiss-grid proportions, "
            "centered on a pure, solid, uniform #000000 pitch-black background."
        )

    # brand_palette_lock
    if has_style_anchor_image:
        return (
            f"Create an image matching the exact brand typography family, {primary_hex} primary finish, "
            f"{secondary_hex} accent lighting, letter spacing, and solid uniform {bg_hex} background "
            f'of reference image 1 (@Image1), displaying the exact centered text "{clean_title}"'
            f"{sub_clause}. Centered on a pure, solid, uniform {bg_hex} background."
        )
    return (
        "Create an image of a brand-locked theatrical title card displaying the exact centered text "
        f'"{clean_title}"{sub_clause} rendered in bespoke architectural serif typography finished in '
        f"primary brand hue {primary_hex} with secondary accent tone {secondary_hex} rim highlights, "
        f"centered on a pure, solid, uniform {bg_hex} background."
    )


class GenerativeTitleCardRenderer:
    """Renders style-anchored 2K title card images and encodes 1080p24 48kHz MP4 clips."""

    def __init__(
        self,
        mock_mode: bool | None = None,
        storage: GcsStorageManager | None = None,
        image_model: str | None = None,
        api_key: str | None = None,
        project: str | None = None,
        location: str | None = None,
    ) -> None:
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self.project = project or os.environ.get(
            "GOOGLE_CLOUD_PROJECT",
            getattr(settings, "google_cloud_project", "hybrid-vertex"),
        )
        self.location = location or os.environ.get(
            "GEMINI_LOCATION",
            getattr(settings, "gemini_location", "global"),
        )
        self.image_model = image_model or getattr(settings, "image_model_id", "gemini-3-pro-image")
        self.api_key = api_key
        self.storage = storage or GcsStorageManager(
            project_id=self.project,
            mock_mode=self.mock_mode,
        )

    def _render_pillow_title_card_png(
        self,
        *,
        title_text: str,
        subtitle_text: str,
        style_preset: str,
        width: int,
        height: int,
        out_image_path: str,
        brand_palette: dict[str, str] | None = None,
    ) -> str:
        """Renders a deterministic high-contrast title card PNG using Pillow (or minimal PNG fallback)."""
        os.makedirs(os.path.dirname(os.path.abspath(out_image_path)), exist_ok=True)
        if not HAS_PIL or Image is None or ImageDraw is None:
            # 1x1 black PNG fallback when Pillow is unavailable.
            minimal_png = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAH2FzhVAAAAAElFTkSuQmCC"
            )
            with open(out_image_path, "wb") as f:
                f.write(minimal_png)
            return out_image_path

        preset = _normalize_preset(style_preset)
        defaults = _PRESET_PALETTES[preset]
        palette = brand_palette or {}
        bg_rgb = (
            _parse_hex_color(palette.get("background") or palette.get("neutral"), defaults["bg"])
            if preset == "brand_palette_lock"
            else defaults["bg"]
        )
        title_rgb = (
            _parse_hex_color(palette.get("primary"), defaults["title"])
            if preset == "brand_palette_lock"
            else defaults["title"]
        )
        sub_rgb = (
            _parse_hex_color(palette.get("secondary"), defaults["subtitle"])
            if preset == "brand_palette_lock"
            else defaults["subtitle"]
        )

        img = Image.new("RGB", (width, height), color=bg_rgb)
        draw = ImageDraw.Draw(img)

        title_size = max(36, int(round(height * 0.075)))
        sub_size = max(24, int(round(height * 0.038)))
        title_font = _get_font("DejaVuSerif-Bold.ttf", title_size)
        sub_font = _get_font("DejaVuSerif.ttf", sub_size)

        clean_title = title_text.strip().upper()
        clean_sub = subtitle_text.strip().upper()
        t_bbox = draw.textbbox((0, 0), clean_title, font=title_font)
        t_w = t_bbox[2] - t_bbox[0]
        t_h = t_bbox[3] - t_bbox[1]

        if clean_sub:
            s_bbox = draw.textbbox((0, 0), clean_sub, font=sub_font)
            s_w = s_bbox[2] - s_bbox[0]
            s_h = s_bbox[3] - s_bbox[1]
            spacing = max(16, int(round(height * 0.025)))
            total_h = t_h + spacing + s_h
            t_y = (height - total_h) / 2
            s_y = t_y + t_h + spacing
            draw.text(((width - t_w) / 2, t_y), clean_title, fill=title_rgb, font=title_font)
            draw.text(((width - s_w) / 2, s_y), clean_sub, fill=sub_rgb, font=sub_font)
        else:
            t_y = (height - t_h) / 2
            draw.text(((width - t_w) / 2, t_y), clean_title, fill=title_rgb, font=title_font)

        img.save(out_image_path)
        return out_image_path

    def _generate_live_title_card_png(
        self,
        *,
        prompt: str,
        aspect_ratio: str,
        style_anchor_image_path: str | None,
        out_image_path: str,
    ) -> bool:
        """Attempts live 2K title card generation with gemini-3-pro-image, anchoring @Image1 when provided."""
        if not genai:
            return False

        effective_key = (
            self.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        )
        image_client: Any = None
        try:
            image_client = (
                genai.Client(api_key=effective_key, vertexai=False)
                if effective_key
                else genai.Client(vertexai=True, project=self.project, location=self.location)
            )
            contents: list[Any] = []
            if style_anchor_image_path and os.path.exists(style_anchor_image_path):
                with open(style_anchor_image_path, "rb") as af:
                    anchor_bytes = af.read()
                if anchor_bytes:
                    if hasattr(genai, "types") and hasattr(genai.types, "Part"):
                        contents.append(
                            genai.types.Part.from_bytes(data=anchor_bytes, mime_type="image/png")
                        )
                    else:
                        contents.append(
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": base64.b64encode(anchor_bytes).decode("utf-8"),
                                }
                            }
                        )
            contents.append(prompt)

            config = None
            if hasattr(genai, "types") and hasattr(genai.types, "GenerateContentConfig"):
                image_cfg = (
                    genai.types.ImageConfig(aspect_ratio=aspect_ratio)
                    if hasattr(genai.types, "ImageConfig") and aspect_ratio
                    else None
                )
                config = genai.types.GenerateContentConfig(
                    safety_settings=_guardrails_get_relaxed_safety_settings(genai_module=genai),
                    image_config=image_cfg,
                )

            response = image_client.models.generate_content(
                model=self.image_model,
                contents=contents,
                config=config,
            )
            for candidate in getattr(response, "candidates", []) or []:
                content = getattr(candidate, "content", None)
                for part in getattr(content, "parts", []) or []:
                    if getattr(part, "thought", False) is True:
                        continue
                    inline_data = getattr(part, "inline_data", None)
                    data = getattr(inline_data, "data", None) if inline_data else None
                    if data:
                        img_bytes = base64.b64decode(data) if isinstance(data, str) else data
                        os.makedirs(os.path.dirname(os.path.abspath(out_image_path)), exist_ok=True)
                        with open(out_image_path, "wb") as f:
                            f.write(img_bytes)
                        return True
        except Exception as exc:
            logger.warning(
                "Live title card image generation failed, falling back to Pillow: %s", exc
            )
        finally:
            if image_client is not None and hasattr(image_client, "close"):
                try:
                    image_client.close()
                except Exception:
                    pass
        return False

    def render_title_card_image(
        self,
        title_text: str,
        subtitle_text: str = "",
        style_preset: TitleCardPreset | str = "gothic_24k_gold",
        style_anchor_image_path: str | None = None,
        brand_palette: dict[str, str] | None = None,
        aspect_ratio: str = "16:9",
        resolution: str | None = None,
        output_dir: str = "/tmp",
    ) -> str:
        """Generates a title card PNG anchored to @Image1 when style_anchor_image_path is given."""
        os.makedirs(output_dir, exist_ok=True)
        out_image_path = os.path.join(output_dir, f"gen_title_card_{uuid.uuid4().hex[:8]}.png")
        width, height = resolve_target_dimensions(aspect_ratio=aspect_ratio, resolution=resolution)

        has_anchor = bool(style_anchor_image_path and os.path.exists(style_anchor_image_path))
        prompt = build_title_card_image_prompt(
            title_text=title_text,
            subtitle_text=subtitle_text,
            style_preset=style_preset,
            has_style_anchor_image=has_anchor,
            brand_palette=brand_palette,
        )

        if not self.mock_mode and self._generate_live_title_card_png(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            style_anchor_image_path=style_anchor_image_path if has_anchor else None,
            out_image_path=out_image_path,
        ):
            return out_image_path

        return self._render_pillow_title_card_png(
            title_text=title_text,
            subtitle_text=subtitle_text,
            style_preset=style_preset,
            width=width,
            height=height,
            out_image_path=out_image_path,
            brand_palette=brand_palette,
        )

    def _encode_image_to_mp4(
        self,
        *,
        image_path: str,
        out_path: str,
        duration_seconds: float,
        width: int,
        height: int,
        session_id: str | None = None,
    ) -> str:
        """Encodes a title card PNG to a 1080p24 CRF 16 48kHz stereo MP4 clip."""
        sample_rate = int(getattr(settings, "audio_sample_rate_hz", 48000))
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            cmd = [
                ffmpeg_bin,
                "-y",
                "-loop",
                "1",
                "-i",
                image_path,
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=channel_layout=stereo:sample_rate={sample_rate}",
                "-c:v",
                "libx264",
                "-crf",
                "16",
                "-c:a",
                "aac",
                "-ar",
                str(sample_rate),
                "-ac",
                "2",
                "-b:a",
                "320k",
                "-t",
                str(duration_seconds),
                "-pix_fmt",
                "yuv420p",
                "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                "-r",
                "24",
                "-shortest",
                out_path,
            ]
            timeout_secs = float(getattr(settings, "ffmpeg_timeout_seconds", 120.0))
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_secs)
                if (
                    res.returncode == 0
                    and os.path.exists(out_path)
                    and os.path.getsize(out_path) > 0
                ):
                    if session_id:
                        blob_name = self.storage.build_session_blob_path(
                            session_id=session_id,
                            category="title_cards",
                            filename=os.path.basename(out_path),
                        )
                        self.storage.upload_file(out_path, destination_blob_name=blob_name)
                    return out_path
                logger.warning(
                    "FFmpeg title card encode failed (%s): %s", res.returncode, res.stderr
                )
            except Exception as exc:
                logger.warning("FFmpeg title card encode raised %s", exc)

        # Fallback placeholder when ffmpeg binary is unavailable or fails.
        with open(out_path, "wb") as f:
            f.write(b"mock 1080p24 title card mp4 content")
        return out_path

    def render_title_card_clip(
        self,
        title_text: str,
        subtitle_text: str = "",
        duration_seconds: float = 3.0,
        style_preset: TitleCardPreset | str = "gothic_24k_gold",
        style_anchor_image_path: str | None = None,
        brand_palette: dict[str, str] | None = None,
        aspect_ratio: str = "16:9",
        resolution: str | None = None,
        output_dir: str = "/tmp",
        session_id: str | None = None,
    ) -> str:
        """Renders a 1080p24 CRF 16 48kHz stereo MP4 title card clip."""
        os.makedirs(output_dir, exist_ok=True)
        width, height = resolve_target_dimensions(aspect_ratio=aspect_ratio, resolution=resolution)
        out_path = os.path.join(output_dir, f"gen_title_card_{uuid.uuid4().hex[:8]}.mp4")

        img_path = self.render_title_card_image(
            title_text=title_text,
            subtitle_text=subtitle_text,
            style_preset=style_preset,
            style_anchor_image_path=style_anchor_image_path,
            brand_palette=brand_palette,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            output_dir=output_dir,
        )
        return self._encode_image_to_mp4(
            image_path=img_path,
            out_path=out_path,
            duration_seconds=duration_seconds,
            width=width,
            height=height,
            session_id=session_id,
        )

    def render_title_card_sequence(
        self,
        cards: list[dict[str, Any]],
        *,
        style_preset: TitleCardPreset | str = "gothic_24k_gold",
        brand_palette: dict[str, str] | None = None,
        aspect_ratio: str = "16:9",
        resolution: str | None = None,
        output_dir: str = "/tmp",
        session_id: str | None = None,
    ) -> list[str]:
        """Renders a sequence of title cards, anchoring Card 2+ to Card 1's style image (@Image1)."""
        os.makedirs(output_dir, exist_ok=True)
        width, height = resolve_target_dimensions(aspect_ratio=aspect_ratio, resolution=resolution)
        anchor_image_path: str | None = None
        clip_paths: list[str] = []

        for idx, card in enumerate(cards):
            title = str(card.get("title") or card.get("title_text") or "")
            subtitle = str(card.get("subtitle") or card.get("subtitle_text") or "")
            duration = float(card.get("duration") or card.get("duration_seconds") or 3.0)
            preset = str(card.get("style_preset") or card.get("style") or style_preset)

            img_path = self.render_title_card_image(
                title_text=title,
                subtitle_text=subtitle,
                style_preset=preset,
                style_anchor_image_path=anchor_image_path,
                brand_palette=brand_palette,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                output_dir=output_dir,
            )
            if idx == 0:
                anchor_image_path = img_path

            out_path = os.path.join(output_dir, f"gen_title_card_{idx}_{uuid.uuid4().hex[:8]}.mp4")
            clip_paths.append(
                self._encode_image_to_mp4(
                    image_path=img_path,
                    out_path=out_path,
                    duration_seconds=duration,
                    width=width,
                    height=height,
                    session_id=session_id,
                )
            )

        return clip_paths


__all__ = [
    "GenerativeTitleCardRenderer",
    "TitleCardPreset",
    "build_title_card_image_prompt",
]
