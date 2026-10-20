"""Image reference tag assembly and character identification for Gemini Omni Flash.

Handles <IMAGE_REF_N>, <FIRST_FRAME>, <LAST_FRAME> tagging and single-pass
prompt mention replacement.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from omnimash.prompts.parody import sanitize_real_names

if TYPE_CHECKING:
    from omnimash.prompts.character_roles import CharacterRole

_STOP_WORDS: frozenset[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "is",
        "was",
        "are",
        "were",
    }
)


def get_character_identifier(
    char: CharacterRole | dict[str, Any] | Any,
    enable_sanitization: bool = True,
    use_role_id: bool = False,
) -> str:
    """Returns character identifier string.

    When use_role_id is True (default for Gemini API prompt compilation), returns 'role_id' (e.g. 'Role A', 'Role B')
    to ensure Gemini API prompts remain 100% clean and free of real-person/celebrity name tokens.
    """
    if isinstance(char, dict):
        role_id = str(char.get("role_id", "") or "").strip()
        name = str(char.get("name", "") or "").strip()
    else:
        role_id = str(getattr(char, "role_id", "") or "").strip()
        name = str(getattr(char, "name", "") or "").strip()

    if use_role_id and role_id:
        return role_id

    if enable_sanitization:
        name_clean = sanitize_real_names(name) if name else ""
    else:
        name_clean = name if name else ""

    if name_clean:
        return name_clean
    if role_id:
        return role_id
    return "Character"


def sort_characters_by_role_id(characters: list[Any] | None) -> list[Any]:
    """Sorts character role list deterministically: Starting Frame / Keyframe Seed first, followed by Ending Frame, Role A, Role B, Role C, Role D."""
    if not characters:
        return []

    def _role_key(c: Any) -> tuple[int, int, str]:
        img_role = (
            getattr(c, "image_role", "")
            if not isinstance(c, dict)
            else c.get("image_role", "") or ""
        )
        if img_role in ("Starting Frame", "Keyframe Seed Anchor"):
            return (0, 0, "")
        if img_role in ("Ending Frame", "Keyframe Last Anchor"):
            return (0, 1, "")

        r_id = (
            str(
                getattr(c, "role_id", "") if not isinstance(c, dict) else c.get("role_id", "") or ""
            )
            .strip()
            .upper()
        )
        m = re.search(r"ROLE\s*([A-Z0-9]+)", r_id)
        if m:
            val = m.group(1)
            if val.isdigit():
                return (1, 0, f"{int(val):04d}")
            elif len(val) == 1 and "A" <= val <= "Z":
                return (1, 0, f"{ord(val) - ord('A'):04d}")
        return (1, 1, r_id)

    return sorted(characters, key=_role_key)


def build_character_image_ref_tags(
    characters: list[CharacterRole] | None,
    starting_index: int = 1,
    has_keyframe_seed: bool = False,
    enable_sanitization: bool = True,
) -> tuple[list[str], list[str], dict[str, str]]:
    """Builds official Gemini Omni Flash <IMAGE_REF_N>, <FIRST_FRAME>, and <LAST_FRAME> tag structures.

    Returns:
      (sources_items, references_items, char_tag_map)
    """
    sources_items: list[str] = []
    references_items: list[str] = []
    char_tag_map: dict[str, str] = {}

    if has_keyframe_seed:
        sources_items.append("<FIRST_FRAME>@KeyframeSeed")

    if not characters:
        return sources_items, references_items, char_tag_map

    sorted_chars = sort_characters_by_role_id(characters)
    ref_counter = 0
    img_idx = starting_index

    for char in sorted_chars:
        ref_url = (
            getattr(char, "reference_url", None)
            if not isinstance(char, dict)
            else char.get("reference_url")
        )
        if not ref_url or not isinstance(ref_url, str) or not ref_url.strip():
            continue

        char_id = get_character_identifier(char, enable_sanitization=enable_sanitization)
        role_id = str(
            getattr(char, "role_id", "")
            if not isinstance(char, dict)
            else char.get("role_id", "") or ""
        ).strip()
        name = str(
            getattr(char, "name", "") if not isinstance(char, dict) else char.get("name", "") or ""
        ).strip()
        img_role = (
            getattr(char, "image_role", "Character Reference")
            if not isinstance(char, dict)
            else char.get("image_role", "Character Reference")
        ) or "Character Reference"

        if img_role in ("Starting Frame", "Keyframe Seed Anchor"):
            tag = "<FIRST_FRAME>"
            sources_items.append(f"<FIRST_FRAME>@Image{img_idx}")
        elif img_role in ("Ending Frame", "Keyframe Last Anchor"):
            tag = "<LAST_FRAME>"
            sources_items.append(f"<LAST_FRAME>@Image{img_idx}")
        else:
            tag = f"<IMAGE_REF_{ref_counter}>"
            references_items.append(f"{tag}@Image{img_idx}")
            ref_counter += 1

        name_clean = (sanitize_real_names(name) if name else "") if enable_sanitization else name
        base_name = re.sub(r"\s*\(.*?\)", "", name).strip() if name else ""
        base_name_clean = (
            (sanitize_real_names(base_name) if base_name else "")
            if enable_sanitization
            else base_name
        )

        candidate_keys: set[str] = set()
        for k in (char_id, role_id, name, name_clean, base_name, base_name_clean):
            if k and k.strip():
                candidate_keys.add(k.strip())

        for source_name in (base_name, name):
            if source_name:
                for token in source_name.split():
                    tok = token.strip()
                    # Filter out short or generic stop-words to prevent false speaker candidate matches
                    if tok and len(tok) >= 3 and tok.lower() not in _STOP_WORDS:
                        candidate_keys.add(tok)
                        tok_clean = sanitize_real_names(tok) if enable_sanitization else tok
                        if (
                            tok_clean
                            and len(tok_clean.strip()) >= 3
                            and tok_clean.lower() not in _STOP_WORDS
                        ):
                            candidate_keys.add(tok_clean.strip())

        for key in candidate_keys:
            if key and key.strip():
                k_str = key.strip()
                char_tag_map[k_str] = tag
                char_tag_map[k_str.lower()] = tag

        img_idx += 1

    has_first_frame = has_keyframe_seed or any(s.startswith("<FIRST_FRAME>") for s in sources_items)
    has_last_frame = any(s.startswith("<LAST_FRAME>") for s in sources_items)
    if has_last_frame and not has_first_frame:
        raise ValueError(
            "<LAST_FRAME> anchor requires a corresponding <FIRST_FRAME> anchor in prompt payload."
        )

    return sources_items, references_items, char_tag_map


def replace_character_in_text_image_tags(
    text: str,
    name_to_tag: dict[str, str],
) -> str:
    """Replaces character name mentions in text with 'name (@ImageN)' if not already tagged.

    Uses a single-pass compiled alternation regular expression O(L) instead of repeated O(K * L) passes.
    """
    if not text or not name_to_tag:
        return text

    # Filter out empty or 1-char keys and sort longest first
    valid_keys = [k for k in name_to_tag if k and len(k.strip()) >= 2 and name_to_tag[k]]
    if not valid_keys:
        return text

    sorted_keys = sorted(valid_keys, key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted_keys) + r")\b")

    def _repl(match: re.Match) -> str:
        matched_text = match.group(1)
        tag = name_to_tag.get(matched_text) or name_to_tag.get(matched_text.lower(), "")
        if not tag:
            return matched_text

        end_pos = match.end()
        remaining = text[end_pos:]
        if re.match(r"\s*\(" + re.escape(tag) + r"\)", remaining) or re.match(
            r"\s*" + re.escape(tag), remaining
        ):
            return matched_text
        return f"{matched_text} ({tag})"

    return pattern.sub(_repl, text)


__all__ = [
    "build_character_image_ref_tags",
    "get_character_identifier",
    "replace_character_in_text_image_tags",
    "sort_characters_by_role_id",
]
