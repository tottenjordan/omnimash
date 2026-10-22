from omnimash.evaluation.models import (
    DefectCategory,
    DimensionScore,
    UserFeedbackRecord,
    VideoEvaluationScorecard,
)
from omnimash.evaluation.prompt_refiner import PromptRefiner, PromptRefinementResult


def _make_scorecard(
    defects: list[DefectCategory], critique: str = "Defects found"
) -> VideoEvaluationScorecard:
    return VideoEvaluationScorecard(
        session_id="sess_refine",
        turn_id="turn_0",
        overall_rating=60.0,
        video_text_adherence=DimensionScore(score=80.0, passed=True),
        character_likeness=DimensionScore(
            score=50.0
            if any(
                d in defects
                for d in [DefectCategory.LIKENESS_DRIFT, DefectCategory.WARDROBE_CONTRADICTION]
            )
            else 90.0,
            passed=False
            if any(
                d in defects
                for d in [DefectCategory.LIKENESS_DRIFT, DefectCategory.WARDROBE_CONTRADICTION]
            )
            else True,
        ),
        audio_visual_harmony=DimensionScore(
            score=50.0 if DefectCategory.AUDIO_DROWNED in defects else 90.0,
            passed=False if DefectCategory.AUDIO_DROWNED in defects else True,
        ),
        tag_and_index_integrity=DimensionScore(
            score=50.0 if DefectCategory.TAG_COLLISION in defects else 90.0,
            passed=False if DefectCategory.TAG_COLLISION in defects else True,
        ),
        detected_defects=defects,
        verbal_critique=critique,
        suggested_prompt_patch=None,
        pass_verdict=False,
    )


def test_prompt_refiner_audio_drowned_patch():
    refiner = PromptRefiner()
    original_prompt = """### DIRECTORIAL INTENT
Parody scene.
### CHARACTER PROFILES
[Role A] Guest speaker.
### SCREENPLAY
[0-3s] [Role A] speaks to the audience: "Welcome everyone."
### AUDIO & ATMOSPHERE
Heavy club bass at 128bpm.
"""
    scorecard = _make_scorecard([DefectCategory.AUDIO_DROWNED], "Music masked spoken dialogue.")
    result = refiner.refine_prompt(original_prompt, scorecard)
    assert isinstance(result, PromptRefinementResult)
    assert "[Instrumental: ducking -18dB under speech]" in result.repaired_prompt
    assert "ducking" in result.diff_summary.lower()


def test_prompt_refiner_wardrobe_contradiction_patch():
    refiner = PromptRefiner()
    original_prompt = """### DIRECTORIAL INTENT
Catwalk duel.
### CHARACTER PROFILES
[Role A] Model wearing oversized pink puffer jacket, neon lime swim trunks, and cowboy boots. Reference sheet attached.
### SCREENPLAY
[0-3s] [Role A] struts.
### AUDIO & ATMOSPHERE
[Instrumental: house music]
"""
    scorecard = _make_scorecard(
        [DefectCategory.WARDROBE_CONTRADICTION], "Conflicting wardrobe descriptors."
    )
    result = refiner.refine_prompt(original_prompt, scorecard)
    assert "oversized pink puffer jacket" not in result.repaired_prompt
    assert (
        "signature attire per turnaround sheet" in result.repaired_prompt
        or "turnaround sheet" in result.repaired_prompt
    )
    assert "wardrobe" in result.diff_summary.lower()


def test_prompt_refiner_verbal_reflection():
    refiner = PromptRefiner()
    scorecard = _make_scorecard([DefectCategory.AUDIO_DROWNED, DefectCategory.LIKENESS_DRIFT])
    user_feedback = UserFeedbackRecord(
        session_id="sess_1",
        turn_id="turn_0",
        rating=2,
        defects=[DefectCategory.AUDIO_DROWNED],
        critique_text="Couldn't hear anything over the sub-bass.",
    )
    reflection = refiner.generate_reflection("Original prompt text", scorecard, user_feedback)
    assert "audio" in reflection.lower()
    assert "ducking" in reflection.lower() or "score" in reflection.lower()


def test_prompt_refiner_canonical_timeline_and_temporal_beat_patch():
    refiner = PromptRefiner()
    original_prompt = """### INPUT ROLES & REFERENCES
<IMAGE_REF_0>@Image1
### CHARACTER PROFILES
[Role A] Neon Warrior.
### SCENE INSTRUCTIONS
Continuous cinematic shot.
### TIMELINE
Screenplay without interval markers. Action occurs.
"""
    scorecard = _make_scorecard([DefectCategory.TEMPORAL_BEAT_MISSED, DefectCategory.AUDIO_DROWNED])
    result = refiner.refine_prompt(original_prompt, scorecard)
    assert "[0-3s]" in result.repaired_prompt
    assert "[3-6s]" in result.repaired_prompt
    assert "[6-10s]" in result.repaired_prompt
    assert "[Instrumental: ducking -18dB under speech]" in result.repaired_prompt


def test_prompt_refiner_tag_collision_and_spatial_staging_patch():
    refiner = PromptRefiner()
    original_prompt = """### CHARACTER PROFILES
[Role A] Detective.
### TIMELINE
[0-3s] [Role A] speaks to the suspect. Two characters face each other.
"""
    scorecard = _make_scorecard([DefectCategory.TAG_COLLISION])
    result = refiner.refine_prompt(original_prompt, scorecard)
    assert "Spatial Staging" in result.repaired_prompt
    assert "frame-left" in result.repaired_prompt or "frame-right" in result.repaired_prompt


def test_prompt_refiner_dressed_in_wardrobe_patch():
    refiner = PromptRefiner()
    original_prompt = """### CHARACTER PROFILES
[Role A] Hero dressed in neon green swim trunks and oversized parka. Reference sheet attached.
### TIMELINE
[0-3s] Action.
"""
    scorecard = _make_scorecard([DefectCategory.WARDROBE_CONTRADICTION])
    result = refiner.refine_prompt(original_prompt, scorecard)
    assert "oversized parka" not in result.repaired_prompt
    assert "signature attire per turnaround sheet" in result.repaired_prompt


def test_prompt_refiner_lipsync_error_patch():
    refiner = PromptRefiner()
    original_prompt = """### CHARACTER PROFILES
[Role A] Detective.
### TIMELINE
[0-3s] Narrator explains the clues while [Role A] examines the desk.
"""
    scorecard = _make_scorecard([DefectCategory.OFFSCREEN_LIPSYNC_ERROR])
    result = refiner.refine_prompt(original_prompt, scorecard)
    assert "[Voiceover/Offscreen]" in result.repaired_prompt
