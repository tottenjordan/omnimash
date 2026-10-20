"""Character role definitions for OmniMash prompt engineering."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CharacterRole:
    role_id: str
    name: str
    description: str
    reference_url: str | None = None
    aesthetic_tags: list[str] = field(default_factory=list)
    voice_style: str = ""
    voice_profile: str = ""
    wardrobe: str = ""
    image_role: str = "Character Reference"
    is_offscreen_narrator: bool = False


def normalize_character_role(
    char: Any,
    clean_fn: Callable[[str | None], str] | None = None,
) -> CharacterRole:
    """Normalizes any character representation into a canonical CharacterRole instance, preserving all fields including wardrobe."""
    _c = clean_fn or (lambda x: str(x) if x is not None else "")

    if isinstance(char, CharacterRole):
        return CharacterRole(
            role_id=char.role_id,
            name=_c(char.name),
            description=_c(char.description),
            reference_url=char.reference_url,
            aesthetic_tags=[_c(t) for t in (char.aesthetic_tags or [])],
            voice_style=_c(char.voice_style or char.voice_profile or ""),
            voice_profile=_c(char.voice_profile or char.voice_style or ""),
            wardrobe=_c(char.wardrobe or ""),
            image_role=getattr(char, "image_role", "Character Reference") or "Character Reference",
            is_offscreen_narrator=bool(getattr(char, "is_offscreen_narrator", False)),
        )

    if hasattr(char, "model_dump"):
        data: dict[str, Any] = char.model_dump()
    elif isinstance(char, dict):
        data = char
    else:
        data = {
            "role_id": getattr(char, "role_id", ""),
            "name": getattr(char, "name", ""),
            "description": getattr(char, "description", ""),
            "reference_url": getattr(char, "reference_url", None),
            "aesthetic_tags": getattr(char, "aesthetic_tags", []),
            "voice_style": getattr(char, "voice_style", "") or getattr(char, "voice_profile", ""),
            "voice_profile": getattr(char, "voice_profile", "") or getattr(char, "voice_style", ""),
            "wardrobe": getattr(char, "wardrobe", ""),
            "image_role": getattr(char, "image_role", "Character Reference"),
            "is_offscreen_narrator": getattr(char, "is_offscreen_narrator", False),
        }

    raw_name = data.get("name")
    name_str = str(raw_name) if raw_name is not None else ""
    raw_desc = data.get("description")
    desc_str = str(raw_desc) if raw_desc is not None else ""
    raw_ref = data.get("reference_url")
    ref_str = str(raw_ref) if raw_ref is not None else None
    raw_tags = data.get("aesthetic_tags")
    tags_list: list[str] = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
    raw_vs = data.get("voice_style") or data.get("voice_profile")
    vs_str = str(raw_vs) if raw_vs is not None else ""
    raw_vp = data.get("voice_profile") or data.get("voice_style")
    vp_str = str(raw_vp) if raw_vp is not None else ""
    raw_ward = data.get("wardrobe")
    ward_str = str(raw_ward) if raw_ward is not None else ""
    raw_img = data.get("image_role")
    img_str = str(raw_img) if raw_img else "Character Reference"
    is_narrator = bool(data.get("is_offscreen_narrator", False))

    return CharacterRole(
        role_id=str(data.get("role_id", "")),
        name=_c(name_str),
        description=_c(desc_str),
        reference_url=ref_str,
        aesthetic_tags=[_c(t) for t in tags_list],
        voice_style=_c(vs_str),
        voice_profile=_c(vp_str),
        wardrobe=_c(ward_str),
        image_role=img_str,
        is_offscreen_narrator=is_narrator,
    )


__all__ = ["CharacterRole", "normalize_character_role"]
