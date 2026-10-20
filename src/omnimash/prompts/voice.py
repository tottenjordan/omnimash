"""Voice style profiling, conversational voice edits, and dialogue enrichment for OmniMash prompts."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from omnimash.prompts.image_tags import get_character_identifier
from omnimash.prompts.parody import sanitize_real_names

if TYPE_CHECKING:
    from omnimash.prompts.character_roles import CharacterRole

logger = logging.getLogger(__name__)


def ensure_character_voice_style(char: CharacterRole | dict[str, Any], concept: str = "") -> str:
    """Ensures every character has a clear, explicit accent and vocal delivery prompt instruction."""
    v_style = (
        getattr(char, "voice_style", None)
        if not isinstance(char, dict)
        else char.get("voice_style")
    ) or ""
    v_profile = (
        getattr(char, "voice_profile", None)
        if not isinstance(char, dict)
        else char.get("voice_profile")
    ) or ""
    v_str = str(v_style or v_profile or "").strip()
    if v_str and v_str != "Cinematic theatrical voice with distinct expressive delivery":
        return v_str

    name = str(
        getattr(char, "name", "") if not isinstance(char, dict) else char.get("name", "") or ""
    ).lower()
    desc = str(
        getattr(char, "description", "")
        if not isinstance(char, dict)
        else char.get("description", "") or ""
    ).lower()
    role = str(
        getattr(char, "role_id", "")
        if not isinstance(char, dict)
        else char.get("role_id", "") or ""
    ).lower()
    combined = f"{name} {desc} {role} {concept.lower()}".strip()

    if any(
        k in combined
        for k in (
            "dumbledore",
            "dior",
            "headmaster",
            "snape",
            "harry",
            "draco",
            "wizard",
            "gothic",
            "british",
            "potter",
            "malfoy",
        )
    ):
        return "Pompous Queen's English British drawl with theatrical cadence"
    elif any(
        k in combined for k in ("totti", "yototti", "trap", "rap", "hip-hop", "808", "atlanta")
    ):
        return "Smooth Atlanta rap flow with distinct rhythmic trap cadence"
    elif any(k in combined for k in ("ramsay", "chef")):
        return "Fiery intense British accent with rapid explosive delivery"
    elif any(k in combined for k in ("julia", "culinary")):
        return "High-pitched cheerful mid-Atlantic accent with enthusiastic lilt"
    else:
        return "Distinct cinematic voice with clear regional accent delivery"


def apply_conversational_voice_edits(
    directive_text: str, characters: list[CharacterRole] | list[dict[str, Any]] | None
) -> None:
    """Parses conversational edit directives like 'Make Role C have a thick Scottish accent'

    and updates the targeted character's voice_style attribute in place.
    """
    if not directive_text or not characters:
        return

    pattern = re.compile(
        r"(?:make|give|change|set)\s+(Role\s+[A-Za-z0-9_\-]+|[A-Za-z0-9_\-]+)\s+(?:have\s+a|have|a|to\s+a|with\s+a|voice\s+style\s+to|accent\s+to)?\s*([A-Za-z0-9_\-\s]+?\b(?:accent|drawl|voice|flow|tone|delivery|cadence)\b)",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(directive_text):
        raw_target = match.group(1).strip().lower()
        new_voice = match.group(2).strip()

        for c in characters:
            c_name = (
                str(getattr(c, "name", "") if not isinstance(c, dict) else c.get("name", "") or "")
                .strip()
                .lower()
            )
            c_role = (
                str(
                    getattr(c, "role_id", "")
                    if not isinstance(c, dict)
                    else c.get("role_id", "") or ""
                )
                .strip()
                .lower()
            )
            c_id = get_character_identifier(c, use_role_id=True).lower()

            if raw_target in (c_name, c_role, c_id) or c_role in raw_target or c_id in raw_target:
                if isinstance(c, dict):
                    c["voice_style"] = new_voice
                    c["voice_profile"] = new_voice
                else:
                    setattr(c, "voice_style", new_voice)
                    setattr(c, "voice_profile", new_voice)


def enrich_timeline_dialogue_speakers(
    diag_raw: str,
    characters: list[CharacterRole] | None,
    char_tag_map: dict[str, str] | None = None,
    enable_sanitization: bool = True,
) -> tuple[str, bool]:
    """Enriches multi-speaker dialogue strings by replacing character speaker labels

    with their official identifier and image reference tag format:
    'Role X - Name <IMAGE_REF_N> says:'.
    Returns (enriched_dialogue, replaced_flag).
    """
    if not diag_raw or not isinstance(diag_raw, str) or not diag_raw.strip():
        return diag_raw, False
    has_narrator = bool(
        re.search(
            r"\bNarrator\s*(?:\(Voiceover\)|\(VO\))?\s*(?:says)?\s*:", diag_raw, re.IGNORECASE
        )
    )
    if not characters:
        if has_narrator:
            enriched = re.sub(
                r"\bNarrator\s*(?:\(Voiceover\)|\(VO\))?\s*(?:says)?\s*:",
                "Narrator (Voiceover):",
                diag_raw,
                flags=re.IGNORECASE,
            )
            return enriched, True
        return diag_raw, False

    cand_list: list[tuple[str, str, str]] = []
    for c in characters:
        c_id = get_character_identifier(c)
        c_name = str(
            getattr(c, "name", "") if not isinstance(c, dict) else c.get("name", "") or ""
        ).strip()
        c_role = str(
            getattr(c, "role_id", "") if not isinstance(c, dict) else c.get("role_id", "") or ""
        ).strip()
        c_voice_style = ensure_character_voice_style(c)

        tag_map = char_tag_map or {}
        tag = tag_map.get(c_id)
        if not tag:
            tag = tag_map.get(c_id.lower()) or tag_map.get(c_name) or tag_map.get(c_name.lower())

        if c_role and c_name:
            target_char_id = f"{c_role} - {c_name}"
        elif c_role:
            target_char_id = c_role
        elif c_name:
            target_char_id = c_name
        else:
            target_char_id = c_id

        tag_str = f" {tag}" if tag else ""
        target_replacement = f"{target_char_id}{tag_str} says:"

        candidates: set[str] = set()
        if c_id:
            candidates.add(c_id)
            if tag:
                candidates.add(f"{c_id} {tag}")
        if c_name:
            candidates.add(c_name)
            name_clean = sanitize_real_names(c_name) if c_name else ""
            if name_clean and name_clean.strip():
                candidates.add(name_clean.strip())
            base_name = re.sub(r"\s*\(.*?\)", "", c_name).strip() if c_name else ""
            if base_name and base_name.strip():
                candidates.add(base_name.strip())
                if tag:
                    candidates.add(f"{base_name.strip()} {tag}")
            if tag:
                candidates.add(f"{c_name} {tag}")
        if c_role:
            candidates.add(c_role)
            if tag:
                candidates.add(f"{c_role} {tag}")

        for cand in candidates:
            if cand and cand.strip():
                cand_list.append((cand.strip(), target_replacement, c_voice_style))

    if not cand_list:
        return diag_raw, False

    # Sort longest candidates first so more specific labels take precedence
    cand_list.sort(key=lambda x: len(x[0]), reverse=True)

    cand_map: dict[str, tuple[str, str]] = {}
    pattern_parts: list[str] = []
    for cand, target, c_voice in cand_list:
        cand_lower = cand.lower()
        if cand_lower not in cand_map:
            cand_map[cand_lower] = (target, c_voice)
            pattern_parts.append(re.escape(cand))

    if not pattern_parts:
        return diag_raw, False

    pattern = re.compile(
        r"(?:\[("
        + "|".join(pattern_parts)
        + r")\]|(?:\b)("
        + "|".join(pattern_parts)
        + r")(?:\s*says)?\s*:)",
        flags=re.IGNORECASE,
    )

    replaced = False

    def repl_func(match: re.Match[str]) -> str:
        nonlocal replaced
        bracket_cand = match.group(1)
        colon_cand = match.group(2)
        matched_cand = (bracket_cand or colon_cand or "").lower()

        if matched_cand in cand_map:
            replaced = True
            target, c_voice = cand_map[matched_cand]
            if c_voice:
                voice_clean = sanitize_real_names(c_voice) if enable_sanitization else c_voice
                if bracket_cand:
                    replacement = f"[{bracket_cand}] [Voice Style: {voice_clean}]"
                elif target.endswith("says:"):
                    target_base = target[:-5].strip()
                    replacement = f"{target_base} [Voice Style: {voice_clean}] says:"
                else:
                    replacement = f"{target} [Voice Style: {voice_clean}]"
                if match.end() < len(diag_raw) and not diag_raw[match.end()].isspace():
                    replacement += " "
                return replacement
            return f"[{bracket_cand}]" if bracket_cand else target
        return match.group(0)

    enriched = pattern.sub(repl_func, diag_raw)
    if has_narrator:
        enriched = re.sub(
            r"\bNarrator\s*(?:\(Voiceover\)|\(VO\))?\s*(?:says)?\s*:",
            "Narrator (Voiceover):",
            enriched,
            flags=re.IGNORECASE,
        )
        replaced = True
    return enriched, replaced


__all__ = [
    "apply_conversational_voice_edits",
    "enrich_timeline_dialogue_speakers",
    "ensure_character_voice_style",
]
