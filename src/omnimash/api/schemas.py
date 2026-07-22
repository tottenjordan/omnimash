"""Pydantic request/response models and identifier/URL validators for the API.

Kept separate from ``app.py`` and the routers so schema definitions have no
dependency on app wiring (avoids import cycles) and can be imported anywhere.
"""

from typing import Annotated
from urllib.parse import urlparse

from pydantic import AfterValidator, BaseModel, field_validator

from omnimash.storage.gcs import GcsStorageManager


def _sanitize_identifier(value: str | None) -> str | None:
    """Normalize an identifier that flows into a GCS key (traversal-safe).

    Applied only to structured identifiers (session names, titles, slugs) —
    never to free-text creative fields (prompts, descriptions, dialogue), which
    stay untouched so content behavior remains permissive.
    """
    if value is None:
        return None
    return GcsStorageManager.sanitize_path_segment(value)


# Required identifier: sanitized, still mandatory.
SafeIdentifier = Annotated[str, AfterValidator(_sanitize_identifier)]
# Optional identifier: sanitized when present, None passes through.
OptSafeIdentifier = Annotated[str | None, AfterValidator(_sanitize_identifier)]


# Hosts the reference extractor is allowed to fetch. Keeps the SSRF surface to
# well-formed http(s) YouTube URLs; scheme/host abuse is rejected before any fetch.
ALLOWED_REFERENCE_HOSTS = frozenset(
    {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}
)


def validate_reference_url(value: str) -> str:
    """Reject non-http(s) schemes and non-allow-listed hosts (SSRF guard)."""
    parsed = urlparse(value.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must use http or https")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_REFERENCE_HOSTS:
        raise ValueError(f"URL host '{host}' is not an allow-listed reference source")
    return value.strip()


class CharacterRoleModel(BaseModel):
    role_id: str
    name: str = ""
    description: str = ""
    reference_url: str | None = None
    aesthetic_tags: list[str] = []
    voice_style: str = ""


class SaveCharacterRequest(BaseModel):
    session_name: OptSafeIdentifier = None
    character: CharacterRoleModel
    is_library: bool = True


class SaveCharacterResponse(BaseModel):
    success: bool = True
    gcs_uri: str = ""
    message: str = ""


class SessionListResponse(BaseModel):
    sessions: list[str]


class CharacterListResponse(BaseModel):
    characters: list[CharacterRoleModel] = []


class LoadCharacterRequest(BaseModel):
    slug: SafeIdentifier
    session_name: OptSafeIdentifier = None


class SaveRosterRequest(BaseModel):
    session_name: SafeIdentifier
    characters: list[CharacterRoleModel]


class DeconstructResponse(BaseModel):
    characters: list[CharacterRoleModel] = []
    aesthetic_tags: list[str] = []
    environment_tag: str = ""
    camera_lighting_tag: str = ""
    audio_beat: str = ""
    vocal_delivery: str = ""


class ConceptDeconstructRequest(BaseModel):
    concept: str


class ResearchRequest(BaseModel):
    subject: str
    aesthetic: str


class ExtractReferenceRequest(BaseModel):
    url: str
    session_name: OptSafeIdentifier = None

    @field_validator("url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return validate_reference_url(value)


class GenerateRequest(BaseModel):
    user_id: str = "usr_default"
    project_id: str = "prj_default"
    prompt: str = ""
    clip_index: int = 0
    parent_turn_id: str | None = None
    reference_url: str | None = None
    audio_stem: str | None = None
    voiceover: str | None = None
    is_silent: bool = False
    on_screen_text: str | None = None
    compiled_override: str | None = None
    session_name: OptSafeIdentifier = None
    concept: str | None = None
    characters: list[CharacterRoleModel | dict] | None = None
    scenes: list[dict] | None = None
    aesthetic_tags: list[str] | None = None
    environment_tag: str | None = None
    vocal_delivery: str = ""
    optimize_prompt: bool = False


class CommitRequest(BaseModel):
    user_id: str = "usr_default"
    project_id: str = "prj_default"
    turn_id: str
    next_prompt: str = ""
    session_name: OptSafeIdentifier = None


class SaveFinalRequest(BaseModel):
    session_name: OptSafeIdentifier = None
    video_url: str
    master_title: SafeIdentifier


class StitchClipsRequest(BaseModel):
    session_name: SafeIdentifier
    clip_urls: list[str]
    master_title: SafeIdentifier = "custom_stitched_cut"


class SaveFinalResponse(BaseModel):
    success: bool
    gcs_uri: str
    message: str


class ExtendSceneRequest(BaseModel):
    session_name: OptSafeIdentifier = None
    turn_id: str | None = None
    next_scene_action: str = ""
    dialogue: str | None = None
    active_roles: list[str] | None = None
    vocal_delivery: str = ""


class GenerateResponse(BaseModel):
    success: bool
    status: str
    video_url: str | None = None
    turn_id: str | None = None
    depth: int = 0
    error: str | None = None
    generation_mode: str = "LIVE_OMNI_FLASH"
    raw_compiled_prompt: str | None = None
    reference_analysis: dict | None = None
