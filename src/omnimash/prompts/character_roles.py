"""Character role definitions for OmniMash prompt engineering."""

from dataclasses import dataclass, field


@dataclass
class CharacterRole:
    role_id: str
    name: str
    description: str
    reference_url: str | None = None
    aesthetic_tags: list[str] = field(default_factory=list)
    voice_style: str = ""
    voice_profile: str = ""
