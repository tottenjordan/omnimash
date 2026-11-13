"""Pydantic v2 request and response models for OmniMash v2.0 studio endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from omnimash.api.models import CharacterRoleModel
from omnimash.audio import LoudnessReport, SonicMixPreset
from omnimash.engine.keyframe_client import Gate1CandidateItem
from omnimash.prompts.shot_pair_planner import TwoShotHardCutPlan


class Gate1BatchRequest(BaseModel):
    prompt: str = ""
    shot_label: str = "shot_a"
    style_tone: str = ""
    reference_image_urls: list[str] | None = None
    characters: list[CharacterRoleModel | dict[str, Any]] | None = None
    style_preset: str | None = None
    wardrobe: str | None = None
    anchor_keyframe_url: str | None = None
    aspect_ratio: str = "16:9"
    image_model: str = "gemini-3-pro-image"
    image_size: str = "2K"
    base_seed: int = 4101
    num_candidates: int = Field(default=1, ge=1, le=12)
    session_name: str | None = None


class Gate1BatchResponse(BaseModel):
    success: bool = True
    shot_label: str
    compiled_prompt: str
    candidates: list[Gate1CandidateItem] = Field(default_factory=list)
    contact_sheet_url: str | None = None
    recommended_candidate_id: str | None = None


class ShotPairPlanRequest(BaseModel):
    scene_id: str = "scene_01"
    character_name: str
    speaker_descriptor: str = ""
    voice_style: str = ""
    fixed_character_block: str = ""
    wetness_lighting_block: str = ""
    matched_location_block: str = ""
    wide_action_summary: str
    mcu_spoken_line: str = ""
    narrator_text: str = ""
    ambient_noise: str = "steady rain on stone and distant wind"
    root_note_808: str = "D1"
    session_name: str | None = None


class ShotPairPlanResponse(BaseModel):
    success: bool = True
    plan: TwoShotHardCutPlan
    shot_a_keyframe_prompt: str
    shot_b_keyframe_prompt: str
    shot_a_i2v_prompt: str
    shot_b_i2v_prompt: str


class Master3StemRequest(BaseModel):
    session_name: str | None = None
    video_path: str = "/static/rendered/mock.mp4"
    preset: SonicMixPreset | str = SonicMixPreset.TRAILER
    narrator_text: str = ""
    narrator_voice: str | None = None
    narrator_style: str = ""
    narrator_delay_sec: float | None = Field(default=None, ge=0.0, le=60.0)
    narrator_target_window_sec: float | None = Field(default=3.8, gt=0.0, le=30.0)
    lyria_prompt: str = "Dark orchestral trap underscore with moody sub-bass pulse"
    lyria_duration_sec: float = Field(default=30.0, gt=0.0, le=120.0)
    score_offset_sec: float = Field(default=0.0, ge=0.0, le=120.0)
    enable_808_drops: bool | None = None
    root_note_808: str = "D1"
    bpm_808: float = Field(default=142.0, gt=20.0, le=300.0)
    raw_808_timestamp_sec: float = Field(default=9.78, ge=0.0, le=120.0)
    guillotine_start_sec: float | None = Field(default=None, ge=0.0, le=120.0)
    guillotine_end_sec: float | None = Field(default=None, gt=0.0, le=120.0)
    guillotine_attenuation_linear: float | None = Field(default=None, gt=0.0, le=1.0)
    target_lufs: float | None = Field(default=None, ge=-30.0, le=-5.0)
    target_true_peak_dbtp: float | None = Field(default=None, ge=-6.0, le=0.0)
    apply_narrator_baritone_dsp: bool | None = None


class Master3StemResponse(BaseModel):
    success: bool = True
    preset: str
    master_video_url: str
    gcs_uri: str | None = None
    snapped_808_timestamp_sec: float | None = None
    loudness_report: LoudnessReport
    narrator_duration_sec: float | None = None
    lyria_model_id: str | None = None


__all__ = [
    "Gate1BatchRequest",
    "Gate1BatchResponse",
    "Master3StemRequest",
    "Master3StemResponse",
    "ShotPairPlanRequest",
    "ShotPairPlanResponse",
]
