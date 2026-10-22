from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel

from omnimash.evaluation.models import (
    DefectCategory,
    UserFeedbackRecord,
    VideoEvaluationScorecard,
)

logger = logging.getLogger(__name__)


class PromptRefinementResult(BaseModel):
    """Result of Reflexion prompt repair containing patched prompt and explanation."""

    repaired_prompt: str
    diff_summary: str
    reflection: str


class PromptRefiner:
    """Reflexion-based prompt optimizer applying surgical repair directives to 4-Block prompts."""

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode

    def generate_reflection(
        self,
        original_prompt: str,
        scorecard: VideoEvaluationScorecard,
        user_feedback: UserFeedbackRecord | dict[str, Any] | None = None,
    ) -> str:
        """Synthesizes a diagnostic verbal self-reflection analyzing why the previous render had defects."""
        feedback_critique = ""
        feedback_rating = None
        if user_feedback:
            if isinstance(user_feedback, dict):
                feedback_critique = user_feedback.get("critique_text", "")
                feedback_rating = user_feedback.get("rating")
            else:
                feedback_critique = user_feedback.critique_text
                feedback_rating = user_feedback.rating

        reflections = []
        if feedback_rating is not None:
            reflections.append(f"Director Star Rating: {feedback_rating}/5.")

        if feedback_critique:
            reflections.append(f'Director Feedback: "{feedback_critique}".')

        if scorecard.detected_defects:
            defect_list = ", ".join(
                d.value if hasattr(d, "value") else str(d) for d in scorecard.detected_defects
            )
            reflections.append(f"Critic Identified Defects: {defect_list}.")

        for defect in scorecard.detected_defects:
            if defect == DefectCategory.AUDIO_DROWNED:
                reflections.append(
                    "Root Cause (Audio Drowned): Spoken vocal lines were overpowered by background music track. "
                    "Remedy: Inject explicit [Instrumental: ducking -18dB under speech] directive into screenplay block."
                )
            elif defect in (DefectCategory.WARDROBE_CONTRADICTION, DefectCategory.LIKENESS_DRIFT):
                reflections.append(
                    "Root Cause (Wardrobe / Likeness Drift): Prompt contains redundant or contradictory clothing descriptions "
                    "that conflict with character reference turnaround sheet. "
                    "Remedy: Apply Zero Wardrobe Redundancy by stripping ad-hoc garments and locking to reference turnaround sheet."
                )
            elif defect == DefectCategory.TAG_COLLISION:
                reflections.append(
                    "Root Cause (Tag Collision): Multiple characters shared or blurred tag designations. "
                    "Remedy: Enforce strict 1:1 ordinal tag symmetry ([Role A], [Role B]) and spatial screen-staging."
                )
            elif defect == DefectCategory.TEMPORAL_BEAT_MISSED:
                reflections.append(
                    "Root Cause (Temporal Beat Missed): Key screenplay actions did not land on expected timeline markers. "
                    "Remedy: Enforce explicit chronological markers [0-3s], [3-6s], and [6-10s]."
                )

        if not reflections:
            return "No critical defects detected. Prompt adheres to directorial invariants."

        return " ".join(reflections)

    def refine_prompt(
        self,
        original_prompt: str,
        scorecard: VideoEvaluationScorecard,
        user_feedback: UserFeedbackRecord | dict[str, Any] | None = None,
    ) -> PromptRefinementResult:
        """Applies surgical heuristic prompt mutations based on diagnosed defects and user feedback."""
        reflection = self.generate_reflection(original_prompt, scorecard, user_feedback)
        repaired = original_prompt
        changes_applied = []

        all_defects = set(scorecard.detected_defects)
        if user_feedback:
            if isinstance(user_feedback, dict):
                user_defs = user_feedback.get("defects", [])
            else:
                user_defs = user_feedback.defects
            for ud in user_defs:
                try:
                    all_defects.add(DefectCategory(ud))
                except Exception:
                    pass

        # 1. AUDIO_DROWNED Repair: Inject ducking directives
        if DefectCategory.AUDIO_DROWNED in all_defects:
            ducking_directive = "[Instrumental: ducking -18dB under speech]"
            if ducking_directive not in repaired:
                if "### SCREENPLAY" in repaired:
                    repaired = repaired.replace(
                        "### SCREENPLAY",
                        f"### SCREENPLAY\n{ducking_directive}",
                        1,
                    )
                elif "### TIMELINE" in repaired:
                    repaired = repaired.replace(
                        "### TIMELINE",
                        f"### TIMELINE\n{ducking_directive}",
                        1,
                    )
                elif "### SCENE INSTRUCTIONS" in repaired:
                    repaired = repaired.replace(
                        "### SCENE INSTRUCTIONS",
                        f"### SCENE INSTRUCTIONS\n{ducking_directive}",
                        1,
                    )
                elif "### AUDIO & ATMOSPHERE" in repaired:
                    repaired = repaired.replace(
                        "### AUDIO & ATMOSPHERE",
                        f"### AUDIO & ATMOSPHERE\n{ducking_directive}",
                        1,
                    )
                else:
                    repaired = f"{ducking_directive}\n{repaired}"
                changes_applied.append("Injected -18dB audio ducking directive into prompt.")

        # 2. WARDROBE_CONTRADICTION / LIKENESS_DRIFT Repair: Zero Wardrobe Redundancy
        if (
            DefectCategory.WARDROBE_CONTRADICTION in all_defects
            or DefectCategory.LIKENESS_DRIFT in all_defects
        ):

            def _strip_wardrobe(match: re.Match[str]) -> str:
                return "wearing signature attire per turnaround sheet"

            old_repaired = repaired
            repaired = re.sub(
                r"(?:wearing|dressed in|in|attired in)\s+[^.\n,]+",
                _strip_wardrobe,
                repaired,
                flags=re.IGNORECASE,
            )
            if old_repaired != repaired:
                changes_applied.append(
                    "Applied Zero Wardrobe Redundancy: stripped contradictory wardrobe descriptions and anchored to reference sheet."
                )
            else:
                # If regex didn't change anything, ensure explicit lock invariant is injected
                invariant_tag = (
                    "[Wardrobe Invariant: Signature attire locked to reference turnaround sheet]"
                )
                if invariant_tag not in repaired:
                    if "### CHARACTER PROFILES" in repaired:
                        repaired = repaired.replace(
                            "### CHARACTER PROFILES",
                            f"### CHARACTER PROFILES\n{invariant_tag}",
                            1,
                        )
                        changes_applied.append(
                            "Added reference turnaround sheet wardrobe lock to character profiles."
                        )
                    else:
                        repaired = f"{invariant_tag}\n{repaired}"
                        changes_applied.append(
                            "Injected reference turnaround sheet wardrobe lock invariant."
                        )

        # 3. TAG_COLLISION Repair: normalize tag collision and inject spatial staging
        if DefectCategory.TAG_COLLISION in all_defects:
            spatial_directive = "[Spatial Staging: [Role A] frame-left, [Role B] frame-right]"
            if (
                "[Role A]" in repaired
                and "[Role B]" not in repaired
                and ("second character" in repaired or "two characters" in repaired)
            ):
                parts = repaired.split("[Role A]")
                if len(parts) > 2:
                    repaired = (
                        parts[0] + "[Role A]" + parts[1] + "[Role B]" + "[Role B]".join(parts[2:])
                    )
                    changes_applied.append(
                        "Resolved tag collision by assigning distinct [Role B] tag."
                    )
            if spatial_directive not in repaired:
                if "[0-3s]" in repaired:
                    repaired = repaired.replace("[0-3s]", f"[0-3s] {spatial_directive}", 1)
                    changes_applied.append(
                        "Injected Left/Right spatial screen-staging directive into [0-3s] beat."
                    )
                elif "### SCENE INSTRUCTIONS" in repaired:
                    repaired = repaired.replace(
                        "### SCENE INSTRUCTIONS",
                        f"### SCENE INSTRUCTIONS\n{spatial_directive}",
                        1,
                    )
                    changes_applied.append(
                        "Injected spatial screen-staging directive into scene instructions."
                    )

        # 4. TEMPORAL_BEAT_MISSED Repair: Ensure interval headers exist
        if DefectCategory.TEMPORAL_BEAT_MISSED in all_defects:
            if "[0-3s]" not in repaired:
                if "### SCREENPLAY" in repaired:
                    repaired = repaired.replace(
                        "### SCREENPLAY",
                        "### SCREENPLAY\n[0-3s] Opening action.\n[3-6s] Midpoint progression.\n[6-10s] Climax action.",
                        1,
                    )
                    changes_applied.append(
                        "Added strict 3-interval time markers [0-3s], [3-6s], [6-10s] to screenplay."
                    )
                elif "### TIMELINE" in repaired:
                    repaired = repaired.replace(
                        "### TIMELINE",
                        "### TIMELINE\n[0-3s] Opening action.\n[3-6s] Midpoint progression.\n[6-10s] Climax action.",
                        1,
                    )
                    changes_applied.append(
                        "Added strict 3-interval time markers [0-3s], [3-6s], [6-10s] to timeline."
                    )
                else:
                    repaired = f"{repaired}\n\n### TIMELINE\n[0-3s] Opening action.\n[3-6s] Midpoint progression.\n[6-10s] Climax action."
                    changes_applied.append(
                        "Added strict 3-interval time markers [0-3s], [3-6s], [6-10s]."
                    )

        # 5. OFFSCREEN_LIPSYNC_ERROR Repair: Explicitly annotate offscreen narrators
        if DefectCategory.OFFSCREEN_LIPSYNC_ERROR in all_defects:
            if "[Voiceover/Offscreen]" not in repaired:
                if "narrator" in repaired.lower() or "voiceover" in repaired.lower():
                    repaired = re.sub(
                        r"(narrator|voiceover)",
                        r"[Voiceover/Offscreen] \1",
                        repaired,
                        count=1,
                        flags=re.IGNORECASE,
                    )
                    changes_applied.append(
                        "Annotated narrator lines with [Voiceover/Offscreen] directive."
                    )

        if not changes_applied:
            diff_summary = (
                "No prompt mutations were required; prompt meets directorial quality bar."
            )
        else:
            diff_summary = "; ".join(changes_applied)

        return PromptRefinementResult(
            repaired_prompt=repaired,
            diff_summary=diff_summary,
            reflection=reflection,
        )
