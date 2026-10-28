"""Editorial brand lockup end-card Pillow compositor and FFmpeg clip encoder for Mode 5 Soundstage."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import json
import logging
import math
import os
import re
import subprocess
import tempfile
from typing import Any, Literal
from urllib.parse import parse_qs, unquote, urlparse
import uuid
import zipfile

from omnimash.engine.media_loader import validate_local_media_path
from omnimash.stitching.resolver import resolve_media_source_to_local_path
from omnimash.stitching.stitcher import HAS_PIL, _get_font

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_IVORY_RGB: tuple[int, int, int] = (248, 246, 240)
_OBSIDIAN_RGB: tuple[int, int, int] = (17, 19, 24)
_HEX6_RE = re.compile(r"^[0-9A-Fa-f]{6}$")
_HEX3_RE = re.compile(r"^[0-9A-Fa-f]{3}$")


def _parse_hex_rgb(hex_value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    """Parses #RRGGBB (or #RGB) hex color string safely into an (R, G, B) tuple."""
    if not isinstance(hex_value, str):
        return fallback
    cleaned = hex_value.strip().lstrip("#")
    if _HEX3_RE.match(cleaned):
        cleaned = "".join(ch * 2 for ch in cleaned)
    if not _HEX6_RE.match(cleaned):
        return fallback
    return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    """Computes WCAG 2.1 sRGB relative luminance in [0.0, 1.0]."""
    channels: list[float] = []
    for comp in rgb:
        srgb = max(0.0, min(255.0, float(comp))) / 255.0
        lin = srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4
        channels.append(lin)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(rgb_a: tuple[int, int, int], rgb_b: tuple[int, int, int]) -> float:
    """Computes WCAG 2.1 contrast ratio in [1.0, 21.0]."""
    lum_a = _relative_luminance(rgb_a)
    lum_b = _relative_luminance(rgb_b)
    lighter, darker = (lum_a, lum_b) if lum_a >= lum_b else (lum_b, lum_a)
    return (lighter + 0.05) / (darker + 0.05)


def _blend_rgb(
    fg: tuple[int, int, int],
    bg: tuple[int, int, int],
    fg_weight: float,
) -> tuple[int, int, int]:
    """Linearly blends two RGB tuples in sRGB space."""
    w = max(0.0, min(1.0, fg_weight))
    return (
        int(round(fg[0] * w + bg[0] * (1.0 - w))),
        int(round(fg[1] * w + bg[1] * (1.0 - w))),
        int(round(fg[2] * w + bg[2] * (1.0 - w))),
    )


def _select_end_card_palette(
    primary_hex: str,
    secondary_hex: str,
    neutral_hex: str,
) -> dict[str, Any]:
    """Resolves contrast-verified editorial lockup colors from 60/30/10 palette hex inputs."""
    bg_rgb = _parse_hex_rgb(neutral_hex, _OBSIDIAN_RGB)
    primary_rgb = _parse_hex_rgb(primary_hex, (225, 29, 72))
    secondary_rgb = _parse_hex_rgb(secondary_hex, (212, 197, 176))

    is_dark_bg = _contrast_ratio(_IVORY_RGB, bg_rgb) >= _contrast_ratio(_OBSIDIAN_RGB, bg_rgb)
    subject_rgb = _IVORY_RGB if is_dark_bg else _OBSIDIAN_RGB
    tagline_rgb = (
        secondary_rgb
        if _contrast_ratio(secondary_rgb, bg_rgb) >= 4.5
        else _blend_rgb(subject_rgb, bg_rgb, 0.82)
    )
    accent_rgb = (
        primary_rgb
        if _contrast_ratio(primary_rgb, bg_rgb) >= 2.2
        else _blend_rgb(primary_rgb, subject_rgb, 0.45)
    )
    return {
        "bg_rgb": bg_rgb,
        "subject_rgb": subject_rgb,
        "tagline_rgb": tagline_rgb,
        "accent_rgb": accent_rgb,
        "is_dark_bg": is_dark_bg,
    }


def _measure_text(draw: Any, text: str, font: Any) -> tuple[int, int]:
    if not text:
        return (0, 0)
    bbox = draw.textbbox((0, 0), text, font=font)
    return (max(0, int(bbox[2] - bbox[0])), max(0, int(bbox[3] - bbox[1])))


def _wrap_text_to_width(
    draw: Any,
    text: str,
    font: Any,
    max_width: int,
    max_lines: int = 3,
) -> tuple[list[str], bool]:
    """Wraps text into at most `max_lines` fitting within `max_width`, returning (lines, truncated)."""
    words = text.split()
    if not words:
        return ([], False)

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if _measure_text(draw, candidate, font)[0] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        if _measure_text(draw, word, font)[0] <= max_width:
            current = word
        else:
            chunk = ""
            for ch in word:
                if _measure_text(draw, chunk + ch, font)[0] <= max_width:
                    chunk += ch
                else:
                    if chunk:
                        lines.append(chunk)
                    chunk = ch
            current = chunk

    if current:
        lines.append(current)
    if len(lines) <= max_lines:
        return (lines, False)

    kept = lines[:max_lines]
    tail = kept[-1].rstrip(".")
    while tail and _measure_text(draw, f"{tail}...", font)[0] > max_width:
        tail = tail[:-1].rstrip()
    kept[-1] = f"{tail}..." if tail else "..."
    return (kept, True)


def _composite_emblem_on_canvas(
    canvas: Any,
    draw: Any,
    emblem_img: Any,
    center_x: int,
    top_y: int,
    bg_rgb: tuple[int, int, int],
    is_dark_bg: bool,
) -> int:
    """Composites an RGBA emblem onto `canvas`, adding a rounded contrast plate if contrast < 2.5."""
    ew, eh = emblem_img.size
    raw_rgba = emblem_img.tobytes()
    r_sum, g_sum, b_sum, visible_px = 0, 0, 0, 0
    for idx in range(0, len(raw_rgba), 4):
        if raw_rgba[idx + 3] >= 32:
            r_sum += raw_rgba[idx]
            g_sum += raw_rgba[idx + 1]
            b_sum += raw_rgba[idx + 2]
            visible_px += 1

    needs_backing = False
    if visible_px > 0:
        avg_rgb = (r_sum // visible_px, g_sum // visible_px, b_sum // visible_px)
        needs_backing = _contrast_ratio(avg_rgb, bg_rgb) < 2.5

    pad_x, pad_y = (18, 14) if needs_backing else (0, 0)
    total_h = eh + pad_y * 2
    emblem_x = center_x - ew // 2
    if needs_backing:
        plate_fill = (248, 246, 240, 232) if is_dark_bg else (17, 19, 24, 224)
        draw.rounded_rectangle(
            (emblem_x - pad_x, top_y, emblem_x + ew + pad_x, top_y + total_h),
            radius=14,
            fill=plate_fill,
        )
    canvas.alpha_composite(emblem_img, dest=(emblem_x, top_y + pad_y))
    return total_h


def _write_text_fallback(path: str, content: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def resolve_confined_media_source(
    source_ref: str | None,
    temp_dir: str,
    output_dir: str = "/tmp",
    storage: Any = None,
    mock_mode: bool = False,
) -> str | None:
    """Unwraps `/api/media-proxy` (up to 3 hops) and resolves confined local, GCS, or remote media."""
    if not source_ref or not isinstance(source_ref, str):
        return None
    raw = source_ref.strip()
    if not raw:
        return None

    for _ in range(3):
        if "/api/media-proxy" in raw and "uri=" in raw:
            try:
                qs = parse_qs(urlparse(raw).query)
                raw = unquote(qs["uri"][0]).strip() if qs.get("uri") else ""
            except Exception:
                return None
        else:
            break
    if not raw or "/api/media-proxy" in raw:
        return None

    allowed_roots = (
        os.path.realpath("static"),
        os.path.realpath("/tmp"),
        os.path.realpath(tempfile.gettempdir()),
        os.path.realpath(output_dir),
        os.path.realpath(temp_dir),
    )

    if not raw.startswith(("gs://", "http://", "https://")):
        confined = validate_local_media_path(raw, allowed_roots=allowed_roots)
        if confined:
            return confined
        check_candidates = [raw, raw.lstrip("/")] if raw.startswith("/static/") else [raw]
        in_allowed_root = any(
            (real_c := os.path.realpath(c)) == root or real_c.startswith(root + os.sep)
            for c in check_candidates
            for root in allowed_roots
        )
        if mock_mode and in_allowed_root and not os.path.exists(raw) and ".." not in raw:
            return os.path.abspath(raw)
        logger.warning("Blocked unconfined or missing local media source: %s", source_ref)
        return None

    resolved = resolve_media_source_to_local_path(
        raw,
        temp_dir=temp_dir,
        storage=storage,
        mock_mode=mock_mode,
    )
    if resolved:
        confined_resolved = validate_local_media_path(resolved, allowed_roots=allowed_roots)
        if confined_resolved:
            return confined_resolved
    return None


def sanitize_zip_asset_key(raw_key: str, fallback: str = "asset") -> str:
    """Sanitizes user/reference asset keys against Zip Slip and directory traversal."""
    cleaned = (raw_key or "").strip()
    if cleaned.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        cleaned = os.path.splitext(cleaned)[0]
    cleaned = cleaned.replace("..", "_")
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]+", "_", cleaned).strip("_")
    return cleaned[:64] or fallback


def serialize_manifest_field(val: Any) -> Any:
    """Recursively converts Pydantic models and arbitrary metadata containers into JSON-safe structures."""
    if val is None:
        return {}
    if hasattr(val, "model_dump") and callable(val.model_dump):
        try:
            dumped = val.model_dump(mode="json")
        except TypeError:
            dumped = val.model_dump()
        return serialize_manifest_field(dumped)
    if isinstance(val, dict):
        return {
            str(k): (None if v is None else serialize_manifest_field(v)) for k, v in val.items()
        }
    if isinstance(val, (list, tuple)):
        return [None if item is None else serialize_manifest_field(item) for item in val]
    if isinstance(val, float):
        return val if math.isfinite(val) else str(val)
    if isinstance(val, (str, int, bool)):
        return val
    return str(val)


def _unique_arcname(prefix: str, stem: str, ext: str, used: set[str]) -> str:
    """Returns a collision-free ZIP archive member path using an incrementing `_2`, `_3` suffix."""
    candidate = f"{prefix}/{stem}{ext}"
    suffix = 2
    while candidate in used:
        candidate = f"{prefix}/{stem}_{suffix}{ext}"
        suffix += 1
    return candidate


def populate_campaign_zip_archive(
    local_zip_path: str,
    deliverable_sources: dict[str, tuple[str, str]],
    storyboard_frames: dict[str, str] | None,
    reference_kit: dict[str, str] | None,
    canonical_subshot_ids: Sequence[str],
    write_entry_fn: Callable[[zipfile.ZipFile, str, str, str, bytes], bool],
    temp_dir: str,
    build_manifest_fn: Callable[[dict[str, str]], dict[str, Any]],
) -> None:
    """Writes confined deliverables, collision-free storyboards/refs, and `campaign_manifest.json`."""
    written_archive_entries: dict[str, str] = {}
    with zipfile.ZipFile(local_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for key, (arcname, source_ref) in deliverable_sources.items():
            if write_entry_fn(
                zf,
                source_ref,
                arcname,
                temp_dir,
                f"mock {key} deliverable bytes".encode("utf-8"),
            ):
                written_archive_entries[key] = arcname

        used_arcnames: set[str] = set()
        for raw_shot_id, frame_src in (storyboard_frames or {}).items():
            if not frame_src:
                continue
            cleaned_id = str(raw_shot_id).strip()
            safe_shot_id = (
                cleaned_id
                if cleaned_id in canonical_subshot_ids
                else sanitize_zip_asset_key(cleaned_id, fallback="shot")
            )
            arcname = _unique_arcname("storyboards", f"shot_{safe_shot_id}", ".png", used_arcnames)
            if write_entry_fn(
                zf, frame_src, arcname, temp_dir, b"\x89PNG\r\n\x1a\nmock_storyboard"
            ):
                used_arcnames.add(arcname)

        for idx, (raw_asset_key, asset_src) in enumerate((reference_kit or {}).items()):
            if not asset_src:
                continue
            safe_key = sanitize_zip_asset_key(str(raw_asset_key), fallback=f"asset_{idx}")
            arcname = _unique_arcname("reference_kit", safe_key, ".png", used_arcnames)
            if write_entry_fn(zf, asset_src, arcname, temp_dir, b"\x89PNG\r\n\x1a\nmock_reference"):
                used_arcnames.add(arcname)

        manifest_payload = build_manifest_fn(written_archive_entries)
        zf.writestr(
            "campaign_manifest.json",
            json.dumps(manifest_payload, indent=2, ensure_ascii=False).encode("utf-8"),
        )


def render_brand_end_card_mp4(
    display_subject: str,
    display_tagline: str = "",
    primary_hex: str = "#E11D48",
    secondary_hex: str = "#D4C5B0",
    neutral_hex: str = "#111318",
    emblem_path: str | None = None,
    duration_seconds: float = 2.0,
    aspect_ratio: Literal["16:9", "9:16"] = "16:9",
    output_dir: str = "/tmp",
    mock_mode: bool = False,
    storage: Any = None,
    ffmpeg_timeout: float = 120.0,
) -> str:
    """Renders an editorial brand lockup end-card MP4 clip (`1280x720` or `720x1280`) at 24fps."""
    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, (int, float))
        or not math.isfinite(duration_seconds)
        or duration_seconds <= 0.0
    ):
        raise ValueError(
            f"duration_seconds must be a finite positive number, got {duration_seconds!r}."
        )
    os.makedirs(output_dir, exist_ok=True)
    aspect_slug = "9x16" if aspect_ratio == "9:16" else "16x9"
    out_path = os.path.join(output_dir, f"end_card_{aspect_slug}_{uuid.uuid4().hex[:8]}.mp4")
    safe_duration = max(0.2, float(duration_seconds))

    if mock_mode:
        return _write_text_fallback(out_path, "mock brand end card mp4 clip content")

    if not HAS_PIL or Image is None or ImageDraw is None:
        logger.warning("Pillow library not available, returning fallback brand end card clip.")
        return _write_text_fallback(out_path, "fallback brand end card video content")

    width, height = (720, 1280) if aspect_ratio == "9:16" else (1280, 720)
    img_path = os.path.join(output_dir, f"end_card_{aspect_slug}_{uuid.uuid4().hex[:8]}.png")

    try:
        pal = _select_end_card_palette(primary_hex, secondary_hex, neutral_hex)
        canvas = Image.new("RGBA", (width, height), color=(*pal["bg_rgb"], 255))
        draw = ImageDraw.Draw(canvas)
        max_text_w = int(width * 0.80)

        emblem_img: Any = None
        if emblem_path and isinstance(emblem_path, str) and emblem_path.strip():
            with tempfile.TemporaryDirectory() as emblem_tmp:
                resolved = resolve_confined_media_source(
                    emblem_path,
                    temp_dir=emblem_tmp,
                    output_dir=output_dir,
                    storage=storage,
                    mock_mode=mock_mode,
                )
                if resolved and os.path.isfile(resolved):
                    try:
                        with Image.open(resolved) as raw_emblem:
                            loaded = raw_emblem.convert("RGBA")
                        loaded.thumbnail(
                            (int(width * 0.24), int(height * 0.15)), Image.Resampling.LANCZOS
                        )
                        emblem_img = loaded
                    except Exception as exc:
                        logger.warning("Skipping unreadable emblem %s: %s", emblem_path, exc)

        subject_text = (display_subject or "Brand").strip() or "Brand"
        tagline_text = (display_tagline or "").strip()

        subj_sizes = (52, 44, 38, 32, 28) if aspect_ratio == "9:16" else (62, 54, 46, 38, 32)
        subject_font = _get_font("DejaVuSans-Bold.ttf", subj_sizes[-1])
        subject_lines = [subject_text]
        for cand_size in subj_sizes:
            cand_font = _get_font("DejaVuSans-Bold.ttf", cand_size)
            wrapped, truncated = _wrap_text_to_width(
                draw, subject_text, cand_font, max_text_w, max_lines=2
            )
            subject_font, subject_lines = cand_font, wrapped or [subject_text]
            if not truncated and (len(subject_lines) == 1 or cand_size <= subj_sizes[2]):
                break

        tagline_font = None
        tagline_lines: list[str] = []
        if tagline_text:
            for cand_size in (26, 23, 20, 18) if aspect_ratio == "9:16" else (30, 26, 22, 19):
                cand_font = _get_font("DejaVuSans.ttf", cand_size)
                wrapped, truncated = _wrap_text_to_width(
                    draw, tagline_text, cand_font, max_text_w, max_lines=3
                )
                tagline_font, tagline_lines = cand_font, wrapped
                if not truncated:
                    break

        subj_metrics = [_measure_text(draw, line, subject_font) for line in subject_lines]
        subj_gap = 10
        subj_h = sum(m[1] for m in subj_metrics) + subj_gap * max(0, len(subj_metrics) - 1)

        tag_metrics = (
            [_measure_text(draw, line, tagline_font) for line in tagline_lines]
            if tagline_font
            else []
        )
        tag_gap = 8
        tag_h = (
            sum(m[1] for m in tag_metrics) + tag_gap * max(0, len(tag_metrics) - 1)
            if tag_metrics
            else 0
        )

        rule_w, rule_h = (88 if aspect_ratio == "16:9" else 72), 4
        emblem_est_h = (emblem_img.size[1] + 28) if emblem_img is not None else 0
        emblem_gap = 28 if emblem_img is not None else 0
        rule_top_gap, rule_bot_gap = 24, (22 if tag_metrics else 0)

        total_h = emblem_est_h + emblem_gap + subj_h + rule_top_gap + rule_h + rule_bot_gap + tag_h
        cursor_y = max(32, (height - total_h) // 2)

        if emblem_img is not None:
            drawn_h = _composite_emblem_on_canvas(
                canvas, draw, emblem_img, width // 2, cursor_y, pal["bg_rgb"], pal["is_dark_bg"]
            )
            cursor_y += drawn_h + emblem_gap

        for line, (lw, lh) in zip(subject_lines, subj_metrics):
            draw.text(
                ((width - lw) / 2, cursor_y),
                line,
                fill=(*pal["subject_rgb"], 255),
                font=subject_font,
            )
            cursor_y += lh + subj_gap
        if subj_metrics:
            cursor_y -= subj_gap

        cursor_y += rule_top_gap
        rule_x0 = (width - rule_w) // 2
        draw.rectangle(
            (rule_x0, cursor_y, rule_x0 + rule_w, cursor_y + rule_h),
            fill=(*pal["accent_rgb"], 255),
        )
        cursor_y += rule_h + rule_bot_gap

        if tagline_font and tag_metrics:
            for line, (lw, lh) in zip(tagline_lines, tag_metrics):
                draw.text(
                    ((width - lw) / 2, cursor_y),
                    line,
                    fill=(*pal["tagline_rgb"], 255),
                    font=tagline_font,
                )
                cursor_y += lh + tag_gap

        canvas.convert("RGB").save(img_path, format="PNG")

        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            img_path,
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-t",
            f"{safe_duration:.3f}",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            f"scale={width}:{height},setsar=1",
            "-r",
            "24",
            "-shortest",
            out_path,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=ffmpeg_timeout)
            if res.returncode != 0:
                logger.warning("FFmpeg brand end-card rendering failed: %s", res.stderr)
                _write_text_fallback(out_path, "fallback brand end card video content")
        except subprocess.TimeoutExpired as exc:
            logger.warning(
                "FFmpeg brand end-card rendering timed out after %s seconds: %s",
                ffmpeg_timeout,
                exc,
            )
            _write_text_fallback(out_path, "fallback brand end card video content")
    except Exception as exc:
        logger.warning("Failed to render brand end-card clip: %s", exc)
        _write_text_fallback(out_path, "fallback brand end card video content")
    finally:
        if os.path.exists(img_path):
            try:
                os.remove(img_path)
            except OSError:
                pass

    return out_path


_COMMON_AV_ENCODE_ARGS: tuple[str, ...] = (
    "-c:v",
    "libx264",
    "-preset",
    "veryfast",
    "-pix_fmt",
    "yuv420p",
    "-r",
    "24",
    "-c:a",
    "aac",
    "-ar",
    "44100",
    "-ac",
    "2",
)


def probe_clip_media_info(clip_path: str, timeout_sec: float = 30.0) -> tuple[bool, float]:
    """Probes `(has_audio_stream, duration_sec)` via ffprobe with safe `(True, 10.0)` fallback."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            clip_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=min(timeout_sec, 30.0))
        if res.returncode != 0 or not isinstance(res.stdout, str) or not res.stdout.strip():
            return (True, 10.0)
        payload = json.loads(res.stdout)
        streams = payload.get("streams") or []
        has_audio = any(isinstance(s, dict) and s.get("codec_type") == "audio" for s in streams)
        raw_dur = (payload.get("format") or {}).get("duration")
        duration = float(raw_dur) if raw_dur is not None else 10.0
        if not math.isfinite(duration) or duration <= 0.0:
            duration = 10.0
        return (has_audio, duration)
    except Exception:
        return (True, 10.0)


def extract_normalized_subshot_segment(
    source_clip: str,
    start_sec: float,
    duration_sec: float,
    aspect_ratio: Literal["16:9", "9:16"],
    has_audio: bool,
    output_path: str,
    ffmpeg_timeout: float = 120.0,
) -> str:
    """Extracts a normalized 24fps H.264 + stereo 44.1kHz AAC sub-shot segment."""
    vf_filter = (
        "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=24,format=yuv420p,setsar=1"
        if aspect_ratio == "9:16"
        else "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p,setsar=1"
    )
    seek_args = ("-ss", f"{start_sec:.3f}", "-t", f"{duration_sec:.3f}", "-i", source_clip)

    def _build_cmd(with_source_audio: bool) -> list[str]:
        if with_source_audio:
            return [
                "ffmpeg",
                "-y",
                *seek_args,
                "-vf",
                vf_filter,
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                *_COMMON_AV_ENCODE_ARGS,
                "-shortest",
                output_path,
            ]
        return [
            "ffmpeg",
            "-y",
            *seek_args,
            "-f",
            "lavfi",
            "-t",
            f"{duration_sec:.3f}",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-vf",
            vf_filter,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            *_COMMON_AV_ENCODE_ARGS,
            "-shortest",
            output_path,
        ]

    try:
        res = subprocess.run(
            _build_cmd(has_audio), capture_output=True, text=True, timeout=ffmpeg_timeout
        )
        if res.returncode != 0 and has_audio:
            res = subprocess.run(
                _build_cmd(False), capture_output=True, text=True, timeout=ffmpeg_timeout
            )
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg sub-shot extraction failed: {res.stderr}")
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"FFmpeg sub-shot extraction timed out after {ffmpeg_timeout} seconds"
        ) from exc
    return output_path


def concatenate_normalized_av_segments(
    segment_paths: list[str],
    output_path: str,
    temp_dir: str,
    master_audio_path: str | None = None,
    storage: Any = None,
    mock_mode: bool = False,
    ffmpeg_timeout: float = 120.0,
) -> str:
    """Concatenates normalized video+audio segments via FFmpeg concat demuxer with re-encode fallback."""
    concat_list_path = os.path.join(temp_dir, f"concat_{uuid.uuid4().hex[:8]}.txt")
    temp_audio_to_cleanup: str | None = None
    out_dir = os.path.dirname(os.path.abspath(output_path)) or "/tmp"

    try:
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for seg in segment_paths:
                escaped = os.path.abspath(seg).replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        resolved_audio: str | None = None
        if master_audio_path:
            resolved_audio = resolve_confined_media_source(
                master_audio_path,
                temp_dir=temp_dir,
                output_dir=out_dir,
                storage=storage,
                mock_mode=mock_mode,
            )
            if resolved_audio and os.path.exists(resolved_audio):
                if os.path.realpath(resolved_audio) != os.path.realpath(
                    master_audio_path
                ) and os.path.dirname(os.path.realpath(resolved_audio)) == os.path.realpath(
                    temp_dir
                ):
                    temp_audio_to_cleanup = resolved_audio
                try:
                    if os.path.getsize(resolved_audio) < 64:
                        with open(resolved_audio, "rb") as af:
                            if af.read(64).startswith(b"fallback ducked audio content"):
                                resolved_audio = None
                except OSError:
                    pass
            else:
                resolved_audio = None

        base_in = ("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path)
        audio_map = ("-map", "0:v:0", "-map", "1:a:0", "-shortest")
        cmd_copy = (
            [
                *base_in,
                "-i",
                resolved_audio,
                "-c:v",
                "copy",
                "-af",
                "apad",
                "-c:a",
                "aac",
                "-ar",
                "44100",
                "-ac",
                "2",
                *audio_map,
                output_path,
            ]
            if resolved_audio
            else [*base_in, "-c", "copy", output_path]
        )

        try:
            res = subprocess.run(cmd_copy, capture_output=True, text=True, timeout=ffmpeg_timeout)
            if res.returncode != 0:
                cmd_reencode = (
                    [
                        *base_in,
                        "-i",
                        resolved_audio,
                        "-af",
                        "apad",
                        *_COMMON_AV_ENCODE_ARGS,
                        *audio_map,
                        output_path,
                    ]
                    if resolved_audio
                    else [*base_in, *_COMMON_AV_ENCODE_ARGS, output_path]
                )
                res_reencode = subprocess.run(
                    cmd_reencode, capture_output=True, text=True, timeout=ffmpeg_timeout
                )
                if res_reencode.returncode != 0:
                    raise RuntimeError(
                        f"FFmpeg deliverable concatenation failed: {res_reencode.stderr}"
                    )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"FFmpeg deliverable concatenation timed out after {ffmpeg_timeout} seconds"
            ) from exc
    finally:
        for tmp_file in (concat_list_path, temp_audio_to_cleanup):
            if tmp_file and os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
    return output_path
