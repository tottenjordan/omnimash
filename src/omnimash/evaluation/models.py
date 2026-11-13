from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from enum import Enum
import uuid

from pydantic import BaseModel, Field


class DefectCategory(str, Enum):
    """Categorized defects detected in Omni video/audio generation (DOMA v1 + v2 Trapwarts 8-Gate)."""

    TAG_COLLISION = "TAG_COLLISION"
    PHANTOM_KEYFRAME = "PHANTOM_KEYFRAME"
    LIKENESS_DRIFT = "LIKENESS_DRIFT"
    WARDROBE_CONTRADICTION = "WARDROBE_CONTRADICTION"
    AUDIO_DROWNED = "AUDIO_DROWNED"
    AUDIO_VOCAL_HALLUCINATION = "AUDIO_VOCAL_HALLUCINATION"
    TEMPORAL_BEAT_MISSED = "TEMPORAL_BEAT_MISSED"
    OFFSCREEN_LIPSYNC_ERROR = "OFFSCREEN_LIPSYNC_ERROR"
    # DOMA v2 (Trapwarts v22 8-Gate Production Checklist)
    REF_PANEL_OR_LANDMARK_BLEED = "REF_PANEL_OR_LANDMARK_BLEED"
    SCALE_OR_AXIS_FRAMING_MISS = "SCALE_OR_AXIS_FRAMING_MISS"
    ARCHITECTURAL_TROPE_DRIFT = "ARCHITECTURAL_TROPE_DRIFT"
    BILATERAL_PROP_GLITCH = "BILATERAL_PROP_GLITCH"
    FLAT_MATTE_NO_PARALLAX = "FLAT_MATTE_NO_PARALLAX"
    SYLLABLE_SKIP_OR_DIALECT_DRIFT = "SYLLABLE_SKIP_OR_DIALECT_DRIFT"
    GUILLOTINE_OR_808_MISALIGNED = "GUILLOTINE_OR_808_MISALIGNED"
    TECHNICAL_SPEC_NONCOMPLIANT = "TECHNICAL_SPEC_NONCOMPLIANT"

    @classmethod
    def _missing_(cls, value: object) -> DefectCategory | None:
        if isinstance(value, str):
            normalized = value.strip().upper().replace("-", "_")
            for member in cls:
                if member.value == normalized or member.name == normalized:
                    return member
        return None


class RemediationActionTier(str, Enum):
    """Cost-ordered remediation routing tiers (cheapest deterministic fix first)."""

    NONE = "NONE"
    TIER_1_REMUX_AUDIO_ONLY = "TIER_1_REMUX_AUDIO_ONLY"
    TIER_2_REGENERATE_TTS_ONLY = "TIER_2_REGENERATE_TTS_ONLY"
    TIER_3_RECREATE_VIDEO_CLIP = "TIER_3_RECREATE_VIDEO_CLIP"
    TIER_4_RECREATE_KEYFRAME_AND_CLIP = "TIER_4_RECREATE_KEYFRAME_AND_CLIP"


DEFECT_TO_REMEDIATION_TIER: dict[DefectCategory, RemediationActionTier] = {
    DefectCategory.TECHNICAL_SPEC_NONCOMPLIANT: RemediationActionTier.TIER_1_REMUX_AUDIO_ONLY,
    DefectCategory.GUILLOTINE_OR_808_MISALIGNED: RemediationActionTier.TIER_1_REMUX_AUDIO_ONLY,
    DefectCategory.AUDIO_DROWNED: RemediationActionTier.TIER_1_REMUX_AUDIO_ONLY,
    DefectCategory.OFFSCREEN_LIPSYNC_ERROR: RemediationActionTier.TIER_2_REGENERATE_TTS_ONLY,
    DefectCategory.SYLLABLE_SKIP_OR_DIALECT_DRIFT: RemediationActionTier.TIER_3_RECREATE_VIDEO_CLIP,
    DefectCategory.AUDIO_VOCAL_HALLUCINATION: RemediationActionTier.TIER_3_RECREATE_VIDEO_CLIP,
    DefectCategory.BILATERAL_PROP_GLITCH: RemediationActionTier.TIER_3_RECREATE_VIDEO_CLIP,
    DefectCategory.TEMPORAL_BEAT_MISSED: RemediationActionTier.TIER_3_RECREATE_VIDEO_CLIP,
    DefectCategory.FLAT_MATTE_NO_PARALLAX: RemediationActionTier.TIER_4_RECREATE_KEYFRAME_AND_CLIP,
    DefectCategory.REF_PANEL_OR_LANDMARK_BLEED: RemediationActionTier.TIER_4_RECREATE_KEYFRAME_AND_CLIP,
    DefectCategory.SCALE_OR_AXIS_FRAMING_MISS: RemediationActionTier.TIER_4_RECREATE_KEYFRAME_AND_CLIP,
    DefectCategory.ARCHITECTURAL_TROPE_DRIFT: RemediationActionTier.TIER_4_RECREATE_KEYFRAME_AND_CLIP,
    DefectCategory.LIKENESS_DRIFT: RemediationActionTier.TIER_4_RECREATE_KEYFRAME_AND_CLIP,
    DefectCategory.WARDROBE_CONTRADICTION: RemediationActionTier.TIER_4_RECREATE_KEYFRAME_AND_CLIP,
    DefectCategory.TAG_COLLISION: RemediationActionTier.TIER_3_RECREATE_VIDEO_CLIP,
    DefectCategory.PHANTOM_KEYFRAME: RemediationActionTier.TIER_3_RECREATE_VIDEO_CLIP,
}

_REMEDIATION_TIER_COST: dict[RemediationActionTier, int] = {
    RemediationActionTier.NONE: 0,
    RemediationActionTier.TIER_1_REMUX_AUDIO_ONLY: 1,
    RemediationActionTier.TIER_2_REGENERATE_TTS_ONLY: 2,
    RemediationActionTier.TIER_3_RECREATE_VIDEO_CLIP: 3,
    RemediationActionTier.TIER_4_RECREATE_KEYFRAME_AND_CLIP: 4,
}


def resolve_highest_cost_remediation_tier(
    defects: Sequence[DefectCategory] | None,
) -> RemediationActionTier:
    """Resolves the highest-cost remediation tier across all detected defects."""
    if not defects:
        return RemediationActionTier.NONE
    highest_tier = RemediationActionTier.NONE
    highest_cost = 0
    for defect in defects:
        tier = DEFECT_TO_REMEDIATION_TIER.get(defect, RemediationActionTier.NONE)
        cost = _REMEDIATION_TIER_COST[tier]
        if cost > highest_cost:
            highest_cost = cost
            highest_tier = tier
    return highest_tier


class UserFeedbackRecord(BaseModel):
    """Directorial feedback captured from user review in Act 3 Screening Room."""

    feedback_id: str = Field(default_factory=lambda: f"fb_{uuid.uuid4().hex[:12]}")
    session_id: str
    turn_id: str
    project_id: str | None = None
    rating: int = Field(ge=1, le=5, description="Director star rating between 1 and 5")
    defects: list[DefectCategory] = Field(default_factory=list)
    critique_text: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DimensionScore(BaseModel):
    """Granular verification score for an evaluation rubric dimension."""

    score: float = Field(ge=0.0, le=100.0, description="Dimension score 0 to 100")
    passed: bool = True
    evidence: str = ""
    timestamp_range: list[float] | tuple[float, float] | str | None = None


class VideoEvaluationScorecard(BaseModel):
    """Structured evaluation scorecard generated by multimodal VideoCriticAgent."""

    evaluation_id: str = Field(default_factory=lambda: f"eval_{uuid.uuid4().hex[:12]}")
    session_id: str
    turn_id: str
    project_id: str | None = None
    overall_rating: float = Field(ge=0.0, le=100.0, description="Overall quality score 0 to 100")
    video_text_adherence: DimensionScore
    character_likeness: DimensionScore
    audio_visual_harmony: DimensionScore
    tag_and_index_integrity: DimensionScore
    detected_defects: list[DefectCategory] = Field(default_factory=list)
    recommended_remediation_tier: RemediationActionTier = RemediationActionTier.NONE
    verbal_critique: str = ""
    suggested_prompt_patch: str | None = None
    pass_verdict: bool = True
    evaluated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DirectorialInvariantRule(BaseModel):
    """Synthesized engineering invariant rule persisted in Strategy Bank."""

    rule_id: str
    category: DefectCategory | str
    trigger_pattern: str
    invariant_directive: str
    rationale: str
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    times_applied: int = 0
    defect_reduction_rate: float = 0.0


class StrategyBank(BaseModel):
    """Collection of directorial invariants and prompt constraints."""

    version: str = "1.0.0"
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rules: list[DirectorialInvariantRule] = Field(default_factory=list)


class ExemplarPromptRecord(BaseModel):
    """Few-shot exemplar prompt paired with high-quality evaluation scorecard."""

    exemplar_id: str = Field(default_factory=lambda: f"ex_{uuid.uuid4().hex[:12]}")
    session_id: str
    concept: str
    style_preset: str = "cinematic"
    compiled_4block_prompt: str
    scorecard: VideoEvaluationScorecard | None = None
    user_rating: int = Field(default=5, ge=1, le=5)
    project_id: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def prompt(self) -> str:
        """Alias property returning the compiled 4-block prompt."""
        return self.compiled_4block_prompt
