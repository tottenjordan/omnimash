import pytest
from pydantic import ValidationError

from omnimash.evaluation.models import (
    DefectCategory,
    DimensionScore,
    DirectorialInvariantRule,
    ExemplarPromptRecord,
    StrategyBank,
    UserFeedbackRecord,
    VideoEvaluationScorecard,
)


def test_defect_category_enum_values():
    assert DefectCategory.TAG_COLLISION == "TAG_COLLISION"
    assert DefectCategory.PHANTOM_KEYFRAME == "PHANTOM_KEYFRAME"
    assert DefectCategory.LIKENESS_DRIFT == "LIKENESS_DRIFT"
    assert DefectCategory.WARDROBE_CONTRADICTION == "WARDROBE_CONTRADICTION"
    assert DefectCategory.AUDIO_DROWNED == "AUDIO_DROWNED"
    assert DefectCategory.AUDIO_VOCAL_HALLUCINATION == "AUDIO_VOCAL_HALLUCINATION"
    assert DefectCategory.TEMPORAL_BEAT_MISSED == "TEMPORAL_BEAT_MISSED"
    assert DefectCategory.OFFSCREEN_LIPSYNC_ERROR == "OFFSCREEN_LIPSYNC_ERROR"


def test_user_feedback_record_valid():
    record = UserFeedbackRecord(
        session_id="sess_123",
        turn_id="turn_1",
        rating=4,
        defects=[DefectCategory.LIKENESS_DRIFT],
        critique_text="Face shifted slightly at second 4.",
    )
    assert record.rating == 4
    assert record.session_id == "sess_123"
    assert record.turn_id == "turn_1"
    assert DefectCategory.LIKENESS_DRIFT in record.defects
    assert record.feedback_id is not None
    assert record.timestamp is not None


def test_user_feedback_record_rating_validation():
    with pytest.raises(ValidationError):
        UserFeedbackRecord(session_id="s1", turn_id="t1", rating=0)

    with pytest.raises(ValidationError):
        UserFeedbackRecord(session_id="s1", turn_id="t1", rating=6)


def test_dimension_score_validation():
    dim = DimensionScore(score=88.5, passed=True, evidence="Clear visual coherence")
    assert dim.score == 88.5
    assert dim.passed is True

    with pytest.raises(ValidationError):
        DimensionScore(score=-1.0, passed=False)

    with pytest.raises(ValidationError):
        DimensionScore(score=101.0, passed=True)


def test_video_evaluation_scorecard_serialization():
    dim1 = DimensionScore(score=90.0, passed=True, evidence="Matches screenplay")
    dim2 = DimensionScore(score=80.0, passed=True, evidence="Likeness maintained")
    dim3 = DimensionScore(score=95.0, passed=True, evidence="Audio ducked correctly")
    dim4 = DimensionScore(score=100.0, passed=True, evidence="Tags symmetric")

    scorecard = VideoEvaluationScorecard(
        session_id="sess_abc",
        turn_id="turn_0",
        overall_rating=91.25,
        video_text_adherence=dim1,
        character_likeness=dim2,
        audio_visual_harmony=dim3,
        tag_and_index_integrity=dim4,
        detected_defects=[],
        verbal_critique="High quality render.",
        suggested_prompt_patch=None,
        pass_verdict=True,
    )
    data = scorecard.model_dump()
    assert data["session_id"] == "sess_abc"
    assert data["overall_rating"] == 91.25
    assert data["pass_verdict"] is True

    reloaded = VideoEvaluationScorecard.model_validate(data)
    assert reloaded.evaluation_id == scorecard.evaluation_id


def test_directorial_invariant_rule_and_strategy_bank():
    rule = DirectorialInvariantRule(
        rule_id="RULE-AUDIO-001",
        category=DefectCategory.AUDIO_DROWNED,
        trigger_pattern="spoken dialogue with background music",
        invariant_directive="Add [Instrumental: ducking -18dB under speech] directive.",
        rationale="Prevents synthesized background score from masking vocal tracks.",
        confidence_score=0.95,
        times_applied=10,
        defect_reduction_rate=0.82,
    )
    assert rule.rule_id == "RULE-AUDIO-001"
    assert rule.confidence_score == 0.95

    bank = StrategyBank(rules=[rule])
    assert bank.version == "1.0.0"
    assert len(bank.rules) == 1
    assert bank.rules[0].rule_id == "RULE-AUDIO-001"


def test_exemplar_prompt_record():
    record = ExemplarPromptRecord(
        session_id="sess_123",
        concept="Cyberpunk street duel",
        style_preset="cyberpunk",
        compiled_4block_prompt="### CHARACTER PROFILES\n[Role A]...",
        user_rating=5,
    )
    assert record.exemplar_id.startswith("ex_")
    assert record.user_rating == 5
    assert "Cyberpunk" in record.concept
