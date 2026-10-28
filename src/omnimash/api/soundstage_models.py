"""Pydantic v2 request, response, progress event, and status schemas for Mode 5: Commercial Soundstage."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from omnimash.prompts.commercial_planner import (
    DualLayerIdentitySpec,
    Palette603010,
    SoundstageCommercialPlan,
    SoundstageDiscoveryResult,
    TerritoryAtmosphereSpec,
)
from omnimash.prompts.offering_physics import OfferingPhysicsSpec
from omnimash.stitching.commercial_conformer import (
    CANONICAL_SUBSHOT_IDS,
    ConformedDeliverables,
    SubShotTrimSpec,
)

SoundstageResolution = Literal["360p", "720p", "1080p", "4k"]
SoundstageStage = Literal[
    "planned",
    "cast_ready",
    "boards_ready",
    "filming_acts",
    "conforming",
    "critic_evaluated",
    "completed",
    "failed",
]

_ACT1_EXPLICIT_RE = re.compile(r"\b(?:act\s*(?:1|i\b)|shot\s*1\.[123]|1\.[123])\b", re.IGNORECASE)
_ACT2_EXPLICIT_RE = re.compile(r"\b(?:act\s*(?:2|ii\b)|shot\s*2\.[123]|2\.[123])\b", re.IGNORECASE)
_ACT3_EXPLICIT_RE = re.compile(r"\b(?:act\s*(?:3|iii\b)|shot\s*3\.[123]|3\.[123])\b", re.IGNORECASE)
_ACT1_KEYWORD_RE = re.compile(
    r"\b(?:opening|arrival|anticipation|establishing|intro|first\s+act)\b",
    re.IGNORECASE,
)
_ACT3_KEYWORD_RE = re.compile(
    r"\b(?:ending|packshot|finale|payoff|closing|final\s+act|end\s+frame|hero\s+lockup)\b",
    re.IGNORECASE,
)


def infer_target_act_from_note(director_note: str) -> Literal[1, 2, 3]:
    """Deterministically infers target act (1, 2, or 3) from a single-line Director Note."""
    text = (director_note or "").strip()
    if not text:
        return 2
    if _ACT1_EXPLICIT_RE.search(text):
        return 1
    if _ACT2_EXPLICIT_RE.search(text):
        return 2
    if _ACT3_EXPLICIT_RE.search(text):
        return 3
    if _ACT1_KEYWORD_RE.search(text):
        return 1
    if _ACT3_KEYWORD_RE.search(text):
        return 3
    return 2


def _require_non_empty_text(value: str, field_label: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_label} must be a non-empty string.")
    return cleaned


class SoundstageDiscoverRequest(BaseModel):
    """Request schema for `POST /api/soundstage/discover`."""

    subject: str
    offering: str | None = None
    territory: str | None = None
    custom_dna: str | None = None

    @field_validator("subject")
    @classmethod
    def _validate_subject(cls, value: str) -> str:
        return _require_non_empty_text(value, "subject")


class SoundstageDiscoverResponse(BaseModel):
    """Response schema for `POST /api/soundstage/discover` wrapping discovery + offering physics."""

    subject: str
    suggested_offerings: list[dict[str, str]] = Field(default_factory=list)
    suggested_territories: list[TerritoryAtmosphereSpec] = Field(default_factory=list)
    palette: Palette603010
    cultural_moments: list[dict[str, str]] = Field(default_factory=list)
    spoken_languages: list[dict[str, str]] = Field(default_factory=list)
    tagline: str
    emblem_prompt: str
    packshot_prompt: str
    physics: OfferingPhysicsSpec
    identity: DualLayerIdentitySpec

    @classmethod
    def from_discovery_result(cls, result: SoundstageDiscoveryResult) -> SoundstageDiscoverResponse:
        return cls(**result.model_dump())


class SoundstagePlanRequest(BaseModel):
    """Request schema for `POST /api/soundstage/plan`."""

    subject: str
    offering: str | None = None
    territory: str | None = None
    weather_condition: str | None = None
    tagline: str | None = None
    palette_hexes: tuple[str, str, str] | list[str] | dict[str, Any] | Palette603010 | None = None
    moment: str | None = None
    language: str = "English"
    vocal_cadence: str | None = None
    lead_name: str | None = None
    lead_wardrobe: str | None = None
    emblem_url: str | None = None
    packshot_url: str | None = None
    custom_dna: str | None = None
    manual_board_gate: bool = False
    resolution: SoundstageResolution = "720p"
    session_name: str = "soundstage_session"
    project_name: str = "default_project"

    @field_validator("subject")
    @classmethod
    def _validate_subject(cls, value: str) -> str:
        return _require_non_empty_text(value, "subject")


class SoundstageCastRequest(BaseModel):
    """Request schema for `POST /api/soundstage/cast`."""

    run_id: str
    action: Literal[
        "generate",
        "recast",
        "older",
        "younger",
        "tweak",
        "select",
        "vault",
        "emblem",
        "packshot",
    ] = "generate"
    tweak_note: str | None = None
    wardrobe_note: str | None = None
    vault_character_slug: str | None = None
    custom_image_url: str | None = None
    candidate_count: int = Field(default=1, ge=1, le=4)

    @field_validator("run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        return _require_non_empty_text(value, "run_id")


class SoundstageBoardsRequest(BaseModel):
    """Request schema for `POST /api/soundstage/boards`."""

    run_id: str
    shot_id: str | None = None
    director_note: str | None = None
    manual_board_gate: bool | None = None

    @field_validator("run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        return _require_non_empty_text(value, "run_id")

    @field_validator("shot_id")
    @classmethod
    def _validate_shot_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned not in CANONICAL_SUBSHOT_IDS:
            raise ValueError(
                f"Invalid shot_id '{cleaned}': expected one of {CANONICAL_SUBSHOT_IDS}."
            )
        return cleaned


class SoundstageRunRequest(BaseModel):
    """Request schema for `POST /api/soundstage/run`."""

    run_id: str
    resolution: SoundstageResolution | None = None
    background_music_path: str | None = None
    end_card_duration_sec: float = Field(default=2.0, gt=0.0, le=10.0)
    async_execution: bool = False

    @field_validator("run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        return _require_non_empty_text(value, "run_id")


class SoundstageReviseRequest(BaseModel):
    """Request schema for `POST /api/soundstage/{run_id}/revise`."""

    director_note: str
    target_act: Literal[1, 2, 3] | None = None
    resolution: SoundstageResolution | None = None

    @field_validator("director_note")
    @classmethod
    def _validate_director_note(cls, value: str) -> str:
        return _require_non_empty_text(value, "director_note")


class SoundstageReconformRequest(BaseModel):
    """Request schema for `POST /api/soundstage/{run_id}/reconform`."""

    subshot_specs: list[SubShotTrimSpec | dict[str, Any]]
    end_card_duration_sec: float | None = Field(default=None, gt=0.0, le=10.0)
    background_music_path: str | None = None


class SoundstageVariationRequest(BaseModel):
    """Request schema for `POST /api/soundstage/{run_id}/variations`."""

    axis: Literal["place", "cast", "offering"]
    new_value: str
    new_session_name: str | None = None
    auto_generate_boards: bool = False
    auto_film: bool = False

    @field_validator("new_value")
    @classmethod
    def _validate_new_value(cls, value: str) -> str:
        return _require_non_empty_text(value, "new_value")


class SoundstageProgressEvent(BaseModel):
    """Calibrated progress event emitted during Mode 5 Commercial Soundstage execution."""

    event_id: int
    stage: str
    progress_pct: int = Field(ge=0, le=100)
    message: str
    timestamp: str
    data: dict[str, Any] = Field(default_factory=dict)


class SoundstageBoardCheck(BaseModel):
    """DOMA pre-filming continuity and human-free isolation check for a storyboard tile."""

    shot_id: str
    image_url: str
    has_person_expected: bool
    passed: bool
    flagged_reason: str | None = None


class SoundstageActRenderRecord(BaseModel):
    """Rendered 10-second continuous-shot act record produced by Gemini Omni Flash."""

    act_number: int
    video_url: str
    gcs_uri: str | None = None
    resolution: str
    generation_mode: str
    compiled_prompt: str
    revision_count: int = 0
    last_director_note: str | None = None


class SoundstageStatusResponse(BaseModel):
    """Authoritative persistent run snapshot returned by Mode 5 Soundstage lifecycle endpoints."""

    run_id: str
    parent_run_id: str | None = None
    variation_axis: str | None = None
    project_name: str
    session_name: str
    stage: str
    progress_pct: int = Field(ge=0, le=100)
    resolution: str
    manual_board_gate: bool
    auto_advance_filming: bool = False
    end_card_duration_sec: float = 2.0
    background_music_path: str | None = None
    plan: SoundstageCommercialPlan
    reference_kit: dict[str, Any] = Field(default_factory=dict)
    boards: dict[str, str] = Field(default_factory=dict)
    board_checks: dict[str, SoundstageBoardCheck] = Field(default_factory=dict)
    flagged_shot_ids: list[str] = Field(default_factory=list)
    acts: list[SoundstageActRenderRecord] = Field(default_factory=list)
    subshot_specs: list[SubShotTrimSpec] = Field(default_factory=list)
    deliverables: ConformedDeliverables | None = None
    critic_scorecards: dict[str, dict[str, Any]] = Field(default_factory=dict)
    package_zip_url: str | None = None
    events: list[SoundstageProgressEvent] = Field(default_factory=list)
    error: str | None = None


__all__ = [
    "SoundstageActRenderRecord",
    "SoundstageBoardCheck",
    "SoundstageBoardsRequest",
    "SoundstageCastRequest",
    "SoundstageDiscoverRequest",
    "SoundstageDiscoverResponse",
    "SoundstagePlanRequest",
    "SoundstageProgressEvent",
    "SoundstageReconformRequest",
    "SoundstageResolution",
    "SoundstageReviseRequest",
    "SoundstageRunRequest",
    "SoundstageStage",
    "SoundstageStatusResponse",
    "SoundstageVariationRequest",
    "infer_target_act_from_note",
]
