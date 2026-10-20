"""SSRF-hardened media fetching, local path confinement, SVG rendering, and character role coercion."""

import base64
import html
import io
import ipaddress
import logging
import os
import re
import socket
import tempfile
from typing import Any
import urllib.error
from urllib.parse import parse_qs, urljoin, urlparse
import urllib.request

from omnimash.prompts.compiler import CharacterRole

logger = logging.getLogger("omnimash.engine")

MAX_MEDIA_FETCH_BYTES = 50 * 1024 * 1024  # 50 MB hard cap for remote media downloads
_SVG_TEXT_TAG_REGEX = re.compile(r"<text[^>]*>(.*?)</text>", re.IGNORECASE)
_DISALLOWED_HOSTNAMES = frozenset({"localhost", "metadata.google.internal", "metadata"})


def is_disallowed_ip(ip_str: str) -> bool:
    """Returns True if ip_str is loopback, private, link-local, reserved, multicast, or unspecified."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return bool(
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )
    except ValueError:
        return True


def validate_remote_media_url(url: str) -> bool:
    """Validates that a remote HTTP(S) URL does not target internal/private/loopback hosts or IPs."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname or hostname in _DISALLOWED_HOSTNAMES or hostname.endswith(".internal"):
        logger.warning("Blocked disallowed HTTP host in media fetch: %s", hostname)
        return False

    try:
        ipaddress.ip_address(hostname)
        if is_disallowed_ip(hostname):
            logger.warning("Blocked private/loopback literal IP in media fetch: %s", hostname)
            return False
        return True
    except ValueError:
        pass

    try:
        addr_infos = socket.getaddrinfo(
            hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
        )
    except OSError as exc:
        logger.warning("DNS resolution failed for media host %s: %s", hostname, exc)
        return False

    if not addr_infos:
        return False

    for info in addr_infos:
        sockaddr = info[4]
        resolved_ip = str(sockaddr[0])
        if is_disallowed_ip(resolved_ip):
            logger.warning(
                "Blocked hostname %s resolving to disallowed IP %s",
                hostname,
                resolved_ip,
            )
            return False

    return True


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """HTTPRedirectHandler that validates every redirect hop against SSRF rules."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        resolved_target = urljoin(req.full_url, newurl)
        if not validate_remote_media_url(resolved_target):
            raise urllib.error.URLError(f"Disallowed redirect target: {resolved_target}")
        return super().redirect_request(req, fp, code, msg, headers, resolved_target)


def validate_local_media_path(
    ref_url: str, allowed_roots: tuple[str, ...] | None = None
) -> str | None:
    """Resolves a local file path and verifies it is confined within allowed directories (static/, /tmp)."""
    roots = allowed_roots or (
        os.path.realpath("static"),
        os.path.realpath("/tmp"),
        os.path.realpath(tempfile.gettempdir()),
    )
    normalized_roots = tuple(os.path.realpath(r) for r in roots)

    candidates = [ref_url]
    if ref_url.startswith("/"):
        candidates.append(ref_url.lstrip("/"))

    for candidate in candidates:
        real_target = os.path.realpath(candidate)
        if any(
            real_target == root or real_target.startswith(root + os.sep)
            for root in normalized_roots
        ):
            if os.path.exists(real_target) and os.path.isfile(real_target):
                return real_target

    return None


def render_svg_to_png_bytes(svg_bytes: bytes | None = None) -> bytes:
    """Renders an SVG placeholder or reference frame into PNG bytes using Pillow."""
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (640, 360), color=(24, 24, 38))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(16, 16), (624, 344)], outline=(0, 210, 255), width=2)
        label = "OmniMash Reference Frame"
        if svg_bytes:
            svg_text = svg_bytes.decode("utf-8", errors="ignore")
            text_matches = _SVG_TEXT_TAG_REGEX.findall(svg_text)
            if text_matches:
                label = " | ".join(t.strip() for t in text_matches if t.strip())[:120]
        draw.text((32, 168), label, fill=(240, 240, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
            b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x03\x00\x05\xfe\x02\xfe\xa7\x9a\x9a\xaa\x00\x00\x00\x00IEND\xaeB`\x82"
        )


def fetch_media_bytes(
    ref_url: str,
    storage: Any,
    allowed_roots: tuple[str, ...] | None = None,
) -> tuple[bytes, str]:
    """Fetches media bytes from GCS, data URIs, confined local paths, or validated external HTTP(S) URLs."""
    if not ref_url or not isinstance(ref_url, str):
        return b"", "image/png"

    if ref_url.lower().endswith(".svg"):
        safe_svg_path = validate_local_media_path(ref_url, allowed_roots=allowed_roots)
        if safe_svg_path is None:
            logger.warning("Blocked local SVG read outside allowed directories: %s", ref_url)
            return b"", "image/png"
        svg_raw = b""
        try:
            with open(safe_svg_path, "rb") as sf:
                svg_raw = sf.read(MAX_MEDIA_FETCH_BYTES)
        except OSError:
            return b"", "image/png"
        return render_svg_to_png_bytes(svg_raw), "image/png"

    if ref_url.startswith("gs://"):
        return storage.download_blob_bytes(ref_url)

    if ref_url.startswith("https://storage.googleapis.com/"):
        try:
            gcs_path = ref_url.replace("https://storage.googleapis.com/", "", 1)
            return storage.download_blob_bytes(f"gs://{gcs_path}")
        except Exception as e:
            logger.warning("Failed to fetch authenticated GCS HTTPS image %s: %s", ref_url, e)

    if "/api/media-proxy?uri=" in ref_url:
        try:
            parsed = urlparse(ref_url)
            qs = parse_qs(parsed.query)
            if "uri" in qs and qs["uri"]:
                return storage.download_blob_bytes(qs["uri"][0])
        except Exception as e:
            logger.warning("Failed to parse media-proxy url %s: %s", ref_url, e)

    if ref_url.startswith("data:image/"):
        try:
            header, encoded = ref_url.split(",", 1)
            mime = header.split(";")[0].split(":")[1] if ":" in header else "image/png"
            if "svg" in mime.lower():
                svg_decoded = b""
                try:
                    svg_decoded = base64.b64decode(encoded)
                except Exception:
                    pass
                return render_svg_to_png_bytes(svg_decoded), "image/png"
            return base64.b64decode(encoded), mime
        except Exception as e:
            logger.warning("Failed to decode data URI image: %s", e)

    if ref_url.startswith("http://") or ref_url.startswith("https://"):
        try:
            if not validate_remote_media_url(ref_url):
                return b"", "image/png"

            req = urllib.request.Request(ref_url, headers={"User-Agent": "Mozilla/5.0"})
            opener = urllib.request.build_opener(_SafeRedirectHandler())
            with opener.open(req, timeout=5) as resp:
                ct = (
                    resp.headers.get("Content-Type", "image/png")
                    if hasattr(resp, "headers") and resp.headers
                    else "image/png"
                )
                body = resp.read(MAX_MEDIA_FETCH_BYTES + 1)
                if len(body) > MAX_MEDIA_FETCH_BYTES:
                    logger.warning(
                        "Blocked oversized HTTP media response (>%d bytes) from %s",
                        MAX_MEDIA_FETCH_BYTES,
                        ref_url,
                    )
                    return b"", "image/png"
                return body, ct
        except Exception as err:
            logger.warning("Failed to download HTTP image from %s: %s", ref_url, err)
            return b"", "image/png"

    if os.path.exists(ref_url) and os.path.isfile(ref_url):
        try:
            safe_local_path = validate_local_media_path(ref_url, allowed_roots=allowed_roots)
            if safe_local_path is None:
                logger.warning(
                    "Blocked local file read outside allowed directories: %s",
                    ref_url,
                )
                return b"", "image/png"
            mime_type = "image/png"
            lower_url = ref_url.lower()
            if lower_url.endswith(".mp4"):
                mime_type = "video/mp4"
            elif lower_url.endswith(".jpg") or lower_url.endswith(".jpeg"):
                mime_type = "image/jpeg"
            with open(safe_local_path, "rb") as f:
                return f.read(MAX_MEDIA_FETCH_BYTES), mime_type
        except Exception as err:
            logger.warning("Failed to read local image file %s: %s", ref_url, err)

    return b"", "image/png"


def coerce_character_roles(characters: list[Any] | None) -> list[CharacterRole]:
    """Normalizes a list of CharacterRole objects, dicts, or duck-typed objects into CharacterRole instances."""
    if not characters:
        return []
    result: list[CharacterRole] = []
    for c in characters:
        if isinstance(c, CharacterRole):
            result.append(c)
        elif isinstance(c, dict):
            raw_tags = c.get("aesthetic_tags", [])
            str_tags = [str(t) for t in raw_tags] if isinstance(raw_tags, (list, tuple)) else []
            result.append(
                CharacterRole(
                    role_id=c.get("role_id", ""),
                    name=c.get("name", ""),
                    description=c.get("description", ""),
                    reference_url=c.get("reference_url"),
                    aesthetic_tags=str_tags,
                    voice_style=c.get("voice_style", ""),
                    voice_profile=c.get("voice_profile", ""),
                    wardrobe=c.get("wardrobe", ""),
                )
            )
        elif hasattr(c, "role_id") or hasattr(c, "name"):
            raw_tags = getattr(c, "aesthetic_tags", [])
            str_tags = [str(t) for t in raw_tags] if isinstance(raw_tags, (list, tuple)) else []
            result.append(
                CharacterRole(
                    role_id=getattr(c, "role_id", ""),
                    name=getattr(c, "name", ""),
                    description=getattr(c, "description", ""),
                    reference_url=getattr(c, "reference_url", None),
                    aesthetic_tags=str_tags,
                    voice_style=getattr(c, "voice_style", ""),
                    voice_profile=getattr(c, "voice_profile", ""),
                    wardrobe=getattr(c, "wardrobe", ""),
                )
            )
    return result


def build_mock_keyframe_svg_data_uri(
    prompt: str,
    style_preset: str | None = None,
    style_tone: str = "",
    aspect_ratio: str = "16:9",
) -> str:
    """Builds an XML-safe SVG data URI for mock/fallback keyframe previews."""
    raw_prompt = prompt or ""
    line1 = html.escape(raw_prompt[:65], quote=True)
    line2 = html.escape(raw_prompt[65:130], quote=True) if len(raw_prompt) > 65 else ""

    raw_style = (style_preset or style_tone or "").strip()
    style_label = (
        f"STYLE: {html.escape(raw_style.upper(), quote=True)}"
        if raw_style
        else "STYLE: CINEMATIC PARODY"
    )
    safe_aspect = html.escape(str(aspect_ratio or "16:9"), quote=True)

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 1280 720" preserveAspectRatio="xMidYMid slice">'
        "<defs>"
        '<linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">'
        '<stop offset="0%" stop-color="#0b0f19"/>'
        '<stop offset="50%" stop-color="#111827"/>'
        '<stop offset="100%" stop-color="#1e1b4b"/>'
        "</linearGradient>"
        '<linearGradient id="badgeGrad" x1="0%" y1="0%" x2="100%" y2="0%">'
        '<stop offset="0%" stop-color="#9333ea"/>'
        '<stop offset="100%" stop-color="#3b82f6"/>'
        "</linearGradient>"
        "</defs>"
        '<rect width="100%" height="100%" fill="url(#bgGrad)"/>'
        "<!-- Viewfinder Corner Brackets -->"
        '<path d="M 40 80 L 40 40 L 80 40" fill="none" stroke="#a855f7" stroke-width="4" opacity="0.7"/>'
        '<path d="M 1240 80 L 1240 40 L 1200 40" fill="none" stroke="#a855f7" stroke-width="4" opacity="0.7"/>'
        '<path d="M 40 640 L 40 680 L 80 680" fill="none" stroke="#a855f7" stroke-width="4" opacity="0.7"/>'
        '<path d="M 1240 640 L 1240 680 L 1200 680" fill="none" stroke="#a855f7" stroke-width="4" opacity="0.7"/>'
        "<!-- Crosshairs -->"
        '<line x1="640" y1="340" x2="640" y2="380" stroke="#38bdf8" stroke-width="2" opacity="0.4"/>'
        '<line x1="620" y1="360" x2="660" y2="360" stroke="#38bdf8" stroke-width="2" opacity="0.4"/>'
        "<!-- Header Badge -->"
        '<rect x="440" y="50" width="400" height="44" rx="22" fill="url(#badgeGrad)"/>'
        '<text x="640" y="78" dominant-baseline="middle" text-anchor="middle" fill="#ffffff" font-size="18" font-weight="800" font-family="system-ui, sans-serif" letter-spacing="2">KEYFRAME PREVIEW DIRECTIVE</text>'
        "<!-- Content Frame -->"
        '<rect x="80" y="140" width="1120" height="440" fill="#000000" fill-opacity="0.4" rx="16" stroke="#334155" stroke-width="2"/>'
        "<!-- Main Action Directives -->"
        '<text x="640" y="280" dominant-baseline="middle" text-anchor="middle" fill="#f8fafc" font-size="28" font-weight="700" font-family="system-ui, sans-serif">'
        f"{line1}"
        "</text>"
        + (
            f'<text x="640" y="340" dominant-baseline="middle" text-anchor="middle" fill="#cbd5e1" font-size="24" font-weight="500" font-family="system-ui, sans-serif">{line2}</text>'
            if line2
            else ""
        )
        + "<!-- Style & Lighting Pill -->"
        '<rect x="340" y="440" width="600" height="48" rx="24" fill="#1e293b" stroke="#38bdf8" stroke-width="2"/>'
        f'<text x="640" y="470" dominant-baseline="middle" text-anchor="middle" fill="#38bdf8" font-size="18" font-weight="700" font-family="system-ui, sans-serif" letter-spacing="1">{style_label}</text>'
        "<!-- Footer Metadata -->"
        '<text x="100" y="640" fill="#64748b" font-size="16" font-family="monospace">REC ● 00:00:00:00</text>'
        f'<text x="1180" y="640" text-anchor="end" fill="#64748b" font-size="16" font-family="monospace">{safe_aspect} | 4K UHD | 24 FPS</text>'
        "</svg>"
    )
    b64_svg = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64_svg}"


def build_mock_ref_sheet_svg_data_uri(
    character_name: str = "",
    description: str = "",
    aspect_ratio: str = "16:9",
) -> str:
    """Builds an XML-safe SVG data URI for mock/fallback character reference sheets."""
    raw_name = (character_name or "Character Reference Sheet").upper()
    clean_name = html.escape(raw_name, quote=True)
    raw_desc = (description or "")[:60]
    clean_desc = html.escape(raw_desc, quote=True)
    desc_sub = f" - {clean_desc}" if clean_desc else ""
    safe_aspect = html.escape(str(aspect_ratio or "16:9"), quote=True)

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 1280 720" preserveAspectRatio="xMidYMid slice">'
        "<defs>"
        '<linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">'
        '<stop offset="0%" stop-color="#0f172a"/>'
        '<stop offset="100%" stop-color="#1e293b"/>'
        "</linearGradient>"
        "</defs>"
        '<rect width="100%" height="100%" fill="url(#bgGrad)"/>'
        '<rect x="40" y="40" width="1200" height="640" rx="12" fill="#ffffff"/>'
        '<rect x="40" y="40" width="1200" height="60" rx="12" fill="#0f172a"/>'
        f'<text x="60" y="78" fill="#f8fafc" font-size="22" font-weight="800" font-family="system-ui, sans-serif">CHARACTER REFERENCE SHEET: {clean_name}{desc_sub}</text>'
        f'<text x="1220" y="78" text-anchor="end" fill="#94a3b8" font-size="14" font-family="monospace">{safe_aspect} | MULTI-PANEL LAYOUT</text>'
        '<rect x="60" y="120" width="280" height="540" fill="#f1f5f9" rx="8" stroke="#cbd5e1" stroke-width="2"/>'
        '<text x="200" y="390" text-anchor="middle" fill="#64748b" font-size="16" font-weight="700">CLOSE-UP BUST</text>'
        '<rect x="360" y="120" width="220" height="170" fill="#f1f5f9" rx="8" stroke="#cbd5e1" stroke-width="2"/>'
        '<text x="470" y="210" text-anchor="middle" fill="#64748b" font-size="14" font-weight="600">FRONT HEAD BUST</text>'
        '<rect x="360" y="305" width="220" height="170" fill="#f1f5f9" rx="8" stroke="#cbd5e1" stroke-width="2"/>'
        '<text x="470" y="395" text-anchor="middle" fill="#64748b" font-size="14" font-weight="600">PROFILE HEAD BUST</text>'
        '<rect x="360" y="490" width="220" height="170" fill="#f1f5f9" rx="8" stroke="#cbd5e1" stroke-width="2"/>'
        '<text x="470" y="580" text-anchor="middle" fill="#64748b" font-size="14" font-weight="600">BACK HEAD BUST</text>'
        '<rect x="600" y="120" width="200" height="540" fill="#f1f5f9" rx="8" stroke="#cbd5e1" stroke-width="2"/>'
        '<text x="700" y="390" text-anchor="middle" fill="#64748b" font-size="16" font-weight="700">FULL-BODY FRONT</text>'
        '<rect x="820" y="120" width="200" height="540" fill="#f1f5f9" rx="8" stroke="#cbd5e1" stroke-width="2"/>'
        '<text x="920" y="390" text-anchor="middle" fill="#64748b" font-size="14" font-weight="600">FULL-BODY 3/4 FRONT</text>'
        '<rect x="1040" y="120" width="180" height="540" fill="#f1f5f9" rx="8" stroke="#cbd5e1" stroke-width="2"/>'
        '<text x="1130" y="390" text-anchor="middle" fill="#64748b" font-size="14" font-weight="600">FULL-BODY 3/4 BACK</text>'
        "</svg>"
    )
    b64_svg = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64_svg}"
