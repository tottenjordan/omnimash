"""Multimodal content packaging and character reference bindings for Gemini Omni Flash."""

from __future__ import annotations

import base64
import logging
import os
import re
import tempfile
from typing import Any, Callable

from omnimash.engine.media_loader import coerce_character_roles
from omnimash.prompts.compiler import (
    CharacterRole,
    build_character_image_ref_tags,
    get_character_identifier,
    sanitize_real_names,
    sort_characters_by_role_id,
)

logger = logging.getLogger("omnimash.engine.multimodal")

try:
    from google import genai
except ImportError:
    genai: Any = None


def load_reference_images_as_input(
    session_id: str | None,
    characters: list[CharacterRole] | None = None,
    fetch_image_fn: Callable[[str], tuple[bytes, str]] | None = None,
    genai_client: Any | None = None,
    dev_client: Any | None = None,
    starting_index: int = 1,
) -> tuple[list[Any], dict[str, int]]:
    """Loads reference images for characters, base64-encoding them into Gemini multimodal input dicts with ordinal payload index mapping."""
    if not characters or fetch_image_fn is None:
        return [], {}

    image_objects: list[Any] = []
    char_img_map: dict[str, int] = {}
    curr_idx = starting_index

    sorted_chars = sort_characters_by_role_id(characters)

    for char in sorted_chars:
        role_id = (
            getattr(char, "role_id", "") if not isinstance(char, dict) else char.get("role_id", "")
        )
        name = getattr(char, "name", "") if not isinstance(char, dict) else char.get("name", "")
        ref_url = (
            getattr(char, "reference_url", None)
            if not isinstance(char, dict)
            else char.get("reference_url")
        )
        if not ref_url or not isinstance(ref_url, str):
            continue

        img_bytes, mime_type = fetch_image_fn(ref_url)

        if img_bytes:
            lower_ref = ref_url.lower()
            if lower_ref.endswith(".mp4"):
                mime_type = "video/mp4"
            elif lower_ref.endswith(".png"):
                mime_type = "image/png"
            elif lower_ref.endswith(".jpg") or lower_ref.endswith(".jpeg"):
                mime_type = "image/jpeg"

            upload_client = (
                genai_client
                if (genai_client and getattr(genai_client, "vertexai", False) is not True)
                else dev_client
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


def build_multimodal_contents(
    prompt: str,
    session_id: str | None = None,
    characters: list[CharacterRole] | None = None,
    keyframe_image_url: str | None = None,
    directors_notes: dict[str, Any] | str | None = None,
    enable_safety_sanitization: bool = True,
    motion_reference_clip: str | None = None,
    fetch_image_fn: Callable[[str], tuple[bytes, str]] | None = None,
    genai_client: Any | None = None,
    dev_client: Any | None = None,
    last_frame_image_url: str | None = None,
    is_seamless_loop: bool = False,
) -> list[dict[str, Any]] | str:
    """Assembles keyframe seed image, motion reference video clip, character reference images, character roster header with visual reference bindings, and timecoded prompt text cleanly into Omni Flash multimodal payload."""
    if is_seamless_loop and keyframe_image_url:
        # KeyframeSeed serves as both FIRST and LAST frame for seamless loop
        pass
    elif last_frame_image_url and last_frame_image_url.strip():
        char_list: list[Any] = list(characters) if characters is not None else []
        has_last = any(
            (getattr(c, "image_role", "") if not isinstance(c, dict) else c.get("image_role", ""))
            in ("Ending Frame", "Keyframe Last Anchor")
            for c in char_list
        )
        if not has_last:
            char_list.append(
                CharacterRole(
                    role_id="Ending Frame",
                    name="Ending Frame Anchor",
                    description="Ending Frame Anchor concept image",
                    reference_url=last_frame_image_url.strip(),
                    image_role="Ending Frame",
                )
            )
        characters = char_list
    keyframe_image_parts: list[dict[str, Any]] = []
    if keyframe_image_url and fetch_image_fn:
        img_bytes, mime_type = fetch_image_fn(keyframe_image_url)
        if img_bytes:
            b64_str = base64.b64encode(img_bytes).decode("utf-8")
            type_key = (
                "video"
                if (mime_type.startswith("video/") or keyframe_image_url.lower().endswith(".mp4"))
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
    if motion_reference_clip and fetch_image_fn:
        m_bytes, _ = fetch_image_fn(motion_reference_clip)
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

    is_video_kf = any(
        (getattr(p, "get", lambda k: None)("type") == "video")
        for p in (keyframe_image_parts or [])
    ) or bool(
        keyframe_image_url
        and keyframe_image_url.lower().endswith((".mp4", ".mov", ".webm", ".avi", ".mkv"))
    )

    has_kf_seed = (not is_video_kf) and (
        bool(keyframe_image_parts)
        or bool(keyframe_image_url)
    )
    start_ref_idx = 1
    ref_image_parts, _ = load_reference_images_as_input(
        session_id,
        characters,
        fetch_image_fn=fetch_image_fn,
        genai_client=genai_client,
        dev_client=dev_client,
        starting_index=start_ref_idx,
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

    if is_seamless_loop and has_kf_seed:
        if "<LAST_FRAME>@KeyframeSeed" not in sources_items:
            sources_items.append("<LAST_FRAME>@KeyframeSeed")

    input_roles_lines: list[str] = []
    if sources_items:
        input_roles_lines.append(f"[# Sources {' '.join(sources_items)}]")
    if references_items:
        input_roles_lines.append(f"[# References {' '.join(references_items)}]")

    input_roles_header = (
        "### INPUT ROLES & REFERENCES\n" + "\n".join(input_roles_lines) + "\n\n"
        if input_roles_lines
        else ""
    )

    tone_header = ""
    if keyframe_image_parts and not is_video_kf and "# Visual Tone & Starting Frame Anchor" not in prompt:
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
        sanitize_real_names(prompt) if (prompt and enable_safety_sanitization) else (prompt or "")
    )
    if char_tag_map and clean_prompt:
        for c_id in sorted(char_tag_map.keys(), key=len, reverse=True):
            tag = char_tag_map[c_id]
            if tag not in clean_prompt and re.search(rf"\b{re.escape(c_id)}\b", clean_prompt):
                clean_prompt = re.sub(rf"\b{re.escape(c_id)}\b", f"{c_id} {tag}", clean_prompt)

    if "### INPUT ROLES" in clean_prompt and input_roles_header:
        clean_prompt = re.sub(
            r"### INPUT ROLES(?: & REFERENCES)?\n.*?(?=\n###|\Z)",
            input_roles_header.rstrip("\n") + "\n\n",
            clean_prompt,
            flags=re.DOTALL,
        )
        input_roles_header = ""

    if (
        "# Character Roster & Visual Directives:" in clean_prompt
        or "### CHARACTER PROFILES" in clean_prompt
    ):
        character_roster_header = ""

    has_first_frame = (
        ((bool(keyframe_image_parts) or bool(keyframe_image_url)) and not is_video_kf)
        or any("<FIRST_FRAME>" in s for s in sources_items)
        or ("<FIRST_FRAME>" in clean_prompt)
        or any(
            (getattr(c, "image_role", "") if not isinstance(c, dict) else c.get("image_role", ""))
            in ("Starting Frame", "Keyframe Seed Anchor")
            for c in (characters or [])
        )
    )

    has_last_frame = (
        bool(last_frame_image_url)
        or any("<LAST_FRAME>" in s for s in sources_items)
        or ("<LAST_FRAME>" in clean_prompt)
        or any(
            (getattr(c, "image_role", "") if not isinstance(c, dict) else c.get("image_role", ""))
            in ("Ending Frame", "Keyframe Last Anchor")
            for c in (characters or [])
        )
    )

    prompt_first_tags = set(re.findall(r"<FIRST_FRAME>@([^\s\]]+)", clean_prompt))
    prompt_last_tags = set(re.findall(r"<LAST_FRAME>@([^\s\]]+)", clean_prompt))
    sources_first_tags = {
        m.group(1)
        for s in sources_items
        for m in [re.search(r"<FIRST_FRAME>@([^\s\]]+)", s)]
        if m
    }
    sources_last_tags = {
        m.group(1)
        for s in sources_items
        for m in [re.search(r"<LAST_FRAME>@([^\s\]]+)", s)]
        if m
    }

    has_same_char_keyframe_urls = bool(characters) and any(
        (getattr(c1, "image_role", "") if not isinstance(c1, dict) else c1.get("image_role", ""))
        in ("Starting Frame", "Keyframe Seed Anchor")
        and (getattr(c2, "image_role", "") if not isinstance(c2, dict) else c2.get("image_role", ""))
        in ("Ending Frame", "Keyframe Last Anchor")
        and bool(getattr(c1, "reference_url", "") if not isinstance(c1, dict) else c1.get("reference_url", ""))
        and (getattr(c1, "reference_url", "") if not isinstance(c1, dict) else c1.get("reference_url", "")).strip()
        == (getattr(c2, "reference_url", "") if not isinstance(c2, dict) else c2.get("reference_url", "")).strip()
        for c1 in characters
        for c2 in characters
    )

    is_loop = (
        bool(is_seamless_loop)
        or ("<LAST_FRAME>@KeyframeSeed" in clean_prompt)
        or any("<LAST_FRAME>@KeyframeSeed" in s for s in sources_items)
        or bool(prompt_first_tags and (prompt_first_tags & prompt_last_tags))
        or bool(sources_first_tags and (sources_first_tags & sources_last_tags))
        or has_same_char_keyframe_urls
        or (
            bool(keyframe_image_url and last_frame_image_url)
            and keyframe_image_url.strip() == last_frame_image_url.strip()
        )
    )

    is_dual_keyframe = has_first_frame and has_last_frame and not is_loop

    has_image_refs = (
        any("<IMAGE_REF_" in r for r in references_items)
        or ("<IMAGE_REF_" in clean_prompt)
        or any(
            (
                getattr(c, "reference_url", None)
                if not isinstance(c, dict)
                else c.get("reference_url")
            )
            and (
                getattr(c, "image_role", "") if not isinstance(c, dict) else c.get("image_role", "")
            )
            not in (
                "Starting Frame",
                "Keyframe Seed Anchor",
                "Ending Frame",
                "Keyframe Last Anchor",
            )
            for c in (characters or [])
        )
    )

    has_video_refs = (
        has_motion_ref
        or bool(motion_reference_clip)
        or any("<VIDEO_REF_" in r for r in references_items)
        or ("<VIDEO_REF_" in clean_prompt)
    )

    guiding_lines: list[str] = []

    if is_loop:
        directive = "Use this image as the first frame and the last frame."
        if directive not in clean_prompt:
            guiding_lines.append(directive)
    elif is_dual_keyframe:
        directive = (
            "Use the first image as the starting frame and the second image as the ending frame."
        )
        if directive not in clean_prompt:
            guiding_lines.append(directive)
    elif has_first_frame:
        directive = "Use this image as the starting frame."
        if directive not in clean_prompt:
            guiding_lines.append(directive)

    if has_image_refs:
        directive = (
            "Use the given image(s) as references for video generation. "
            "The images should not be used as literal initial frames."
        )
        if directive not in clean_prompt:
            guiding_lines.append(directive)

    if has_video_refs:
        directive = (
            "Use the given video(s) as references. Do not use them as a source for video editing."
        )
        if directive not in clean_prompt:
            guiding_lines.append(directive)

    if guiding_lines:
        guiding_block = "\n".join(guiding_lines)
        if clean_prompt.strip():
            clean_prompt = clean_prompt.rstrip() + "\n\n" + guiding_block + "\n"
        else:
            clean_prompt = guiding_block + "\n"

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


__all__ = [
    "build_multimodal_contents",
    "load_reference_images_as_input",
]
