import pytest

from omnimash.evaluation.models import (
    DefectCategory,
    DirectorialInvariantRule,
    StrategyBank,
    UserFeedbackRecord,
    VideoEvaluationScorecard,
    DimensionScore,
)
from omnimash.evaluation.rule_inducer import DirectorialRuleInducer
from omnimash.evaluation.strategy_bank import StrategyBankManager
from omnimash.storage.gcs import GcsStorageManager


@pytest.fixture
def storage():
    return GcsStorageManager(mock_mode=True)


@pytest.fixture
def strategy_bank_mgr(storage):
    return StrategyBankManager(storage=storage, mock_mode=True)


@pytest.fixture
def inducer(storage, strategy_bank_mgr):
    return DirectorialRuleInducer(storage=storage, strategy_bank=strategy_bank_mgr, mock_mode=True)


def test_rule_inducer_initialization(storage):
    inducer = DirectorialRuleInducer(storage=storage, mock_mode=True)
    assert inducer.mock_mode is True
    assert inducer.storage is storage
    assert isinstance(inducer.strategy_bank, StrategyBankManager)


def test_defect_clustering(inducer, storage):
    project_id = "proj_cluster_test"

    # Feedback 1: AUDIO_DROWNED, WARDROBE_CONTRADICTION
    storage.save_feedback(
        session_id="sess_1",
        turn_id="turn_0",
        feedback=UserFeedbackRecord(
            session_id="sess_1",
            turn_id="turn_0",
            rating=2,
            defects=[DefectCategory.AUDIO_DROWNED, DefectCategory.WARDROBE_CONTRADICTION],
            project_id=project_id,
        ),
        project_id=project_id,
    )

    # Feedback 2: AUDIO_DROWNED
    storage.save_feedback(
        session_id="sess_2",
        turn_id="turn_0",
        feedback=UserFeedbackRecord(
            session_id="sess_2",
            turn_id="turn_0",
            rating=3,
            defects=[DefectCategory.AUDIO_DROWNED],
            project_id=project_id,
        ),
        project_id=project_id,
    )

    # Scorecard 1: AUDIO_DROWNED, LIKENESS_DRIFT
    dummy_score = DimensionScore(score=80.0, passed=True)
    storage.save_scorecard(
        session_id="sess_3",
        turn_id="turn_0",
        scorecard=VideoEvaluationScorecard(
            session_id="sess_3",
            turn_id="turn_0",
            overall_rating=65.0,
            video_text_adherence=dummy_score,
            character_likeness=dummy_score,
            audio_visual_harmony=dummy_score,
            tag_and_index_integrity=dummy_score,
            detected_defects=[DefectCategory.AUDIO_DROWNED, DefectCategory.LIKENESS_DRIFT],
            project_id=project_id,
        ),
        project_id=project_id,
    )

    # Scorecard 2: LIKENESS_DRIFT
    storage.save_scorecard(
        session_id="sess_4",
        turn_id="turn_0",
        scorecard=VideoEvaluationScorecard(
            session_id="sess_4",
            turn_id="turn_0",
            overall_rating=70.0,
            video_text_adherence=dummy_score,
            character_likeness=dummy_score,
            audio_visual_harmony=dummy_score,
            tag_and_index_integrity=dummy_score,
            detected_defects=[DefectCategory.LIKENESS_DRIFT],
            project_id=project_id,
        ),
        project_id=project_id,
    )

    # Record in another project (should be isolated)
    storage.save_feedback(
        session_id="sess_other",
        turn_id="turn_0",
        feedback=UserFeedbackRecord(
            session_id="sess_other",
            turn_id="turn_0",
            rating=1,
            defects=[DefectCategory.TAG_COLLISION],
            project_id="other_proj",
        ),
        project_id="other_proj",
    )

    counts = inducer.cluster_defects(project_id=project_id)
    assert counts[DefectCategory.AUDIO_DROWNED] == 3
    assert counts[DefectCategory.LIKENESS_DRIFT] == 2
    assert counts[DefectCategory.WARDROBE_CONTRADICTION] == 1
    assert DefectCategory.TAG_COLLISION not in counts


def test_induce_rules_from_history_threshold(inducer, storage):
    project_id = "proj_induce_test"

    # Save 2 AUDIO_DROWNED and 1 WARDROBE_CONTRADICTION
    storage.save_feedback(
        session_id="s1",
        turn_id="t1",
        feedback=UserFeedbackRecord(
            session_id="s1",
            turn_id="t1",
            rating=2,
            defects=[DefectCategory.AUDIO_DROWNED],
            project_id=project_id,
        ),
        project_id=project_id,
    )
    storage.save_feedback(
        session_id="s2",
        turn_id="t1",
        feedback=UserFeedbackRecord(
            session_id="s2",
            turn_id="t1",
            rating=2,
            defects=[DefectCategory.AUDIO_DROWNED, DefectCategory.WARDROBE_CONTRADICTION],
            project_id=project_id,
        ),
        project_id=project_id,
    )

    # Min defect count = 2 -> only AUDIO_DROWNED should be induced
    induced = inducer.induce_rules_from_history(project_id=project_id, min_defect_count=2)
    assert len(induced) == 1
    rule = induced[0]
    assert rule.rule_id.startswith("RULE-INDUCED-")
    assert rule.category == DefectCategory.AUDIO_DROWNED
    assert 0.90 <= rule.confidence_score <= 0.98
    assert rule.times_applied == 0
    assert rule.defect_reduction_rate == 0.0
    assert len(rule.trigger_pattern) > 5
    assert len(rule.invariant_directive) > 5
    assert len(rule.rationale) > 10

    # Verify rule was added to StrategyBank for project_id
    bank = inducer.strategy_bank.get_strategy_bank(project_id=project_id)
    assert any(r.rule_id == rule.rule_id for r in bank.rules)


def test_induce_rules_mock_mode_fallback(inducer, storage):
    project_id = "proj_fallback_test"

    # Only 1 defect total
    storage.save_feedback(
        session_id="s_single",
        turn_id="t0",
        feedback=UserFeedbackRecord(
            session_id="s_single",
            turn_id="t0",
            rating=2,
            defects=[DefectCategory.AUDIO_VOCAL_HALLUCINATION],
            project_id=project_id,
        ),
        project_id=project_id,
    )

    # With default min_defect_count=2, fallback induces the single detected defect in mock mode
    induced = inducer.induce_rules_from_history(project_id=project_id, min_defect_count=2)
    assert len(induced) == 1
    assert induced[0].category == DefectCategory.AUDIO_VOCAL_HALLUCINATION

    # With empty storage, returns empty list
    empty_induced = inducer.induce_rules_from_history(project_id="proj_empty", min_defect_count=2)
    assert empty_induced == []


def test_counterfactual_validation(inducer):
    bank = StrategyBank(
        version="1.0.0",
        rules=[
            DirectorialInvariantRule(
                rule_id="RULE-AUDIO-001",
                category=DefectCategory.AUDIO_DROWNED,
                trigger_pattern="spoken dialogue with background music",
                invariant_directive="[Instrumental: ducking -18dB under speech]",
                rationale="Protects speech clarity.",
                confidence_score=0.98,
            )
        ],
    )

    # Compatible candidate
    compatible_rule = DirectorialInvariantRule(
        rule_id="RULE-INDUCED-123456",
        category=DefectCategory.TEMPORAL_BEAT_MISSED,
        trigger_pattern="rapid action sequence",
        invariant_directive="Decompose into distinct [0-3s] and [3-6s] action beats.",
        rationale="Prevents attention drift.",
        confidence_score=0.95,
    )
    assert inducer.validate_counterfactual(compatible_rule, bank) is True

    # Rule ID collision conflict
    duplicate_rule = DirectorialInvariantRule(
        rule_id="RULE-AUDIO-001",
        category=DefectCategory.AUDIO_DROWNED,
        trigger_pattern="spoken dialogue with background music",
        invariant_directive="[Instrumental: ducking -18dB under speech]",
        rationale="ID collision.",
        confidence_score=0.95,
    )
    assert inducer.validate_counterfactual(duplicate_rule, bank) is False

    # Direct semantic contradiction conflict (e.g. "no ducking" vs "ducking -18dB")
    contradicting_rule = DirectorialInvariantRule(
        rule_id="RULE-INDUCED-BAD001",
        category=DefectCategory.AUDIO_DROWNED,
        trigger_pattern="spoken dialogue with background music",
        invariant_directive="[Instrumental: no ducking under speech]",
        rationale="Contradicting existing directive.",
        confidence_score=0.95,
    )
    assert inducer.validate_counterfactual(contradicting_rule, bank) is False

    # Low confidence candidate (< 0.70)
    low_confidence_rule = DirectorialInvariantRule(
        rule_id="RULE-INDUCED-LOW001",
        category=DefectCategory.TAG_COLLISION,
        trigger_pattern="screen staging",
        invariant_directive="Separate left and right actors.",
        rationale="Weak signal.",
        confidence_score=0.55,
    )
    assert inducer.validate_counterfactual(low_confidence_rule, bank) is False


def test_pareto_prune_deduplication(inducer, strategy_bank_mgr):
    project_id = "proj_prune_dedup"
    # Seed bank with two near-identical rules for same category and trigger
    rule_a = DirectorialInvariantRule(
        rule_id="RULE-A",
        category=DefectCategory.WARDROBE_CONTRADICTION,
        trigger_pattern="character reference sheet with detailed text wardrobe",
        invariant_directive="Zero Wardrobe Redundancy: Rely on visual reference turnaround sheet.",
        rationale="Rule A",
        confidence_score=0.85,
        times_applied=2,
        defect_reduction_rate=0.2,
    )
    rule_b = DirectorialInvariantRule(
        rule_id="RULE-B",
        category=DefectCategory.WARDROBE_CONTRADICTION,
        trigger_pattern="Character reference sheet with detailed text wardrobe!",
        invariant_directive="Zero Wardrobe Redundancy: Rely on visual turnaround reference.",
        rationale="Rule B (Superior)",
        confidence_score=0.96,
        times_applied=10,
        defect_reduction_rate=0.5,
    )
    strategy_bank_mgr.add_rule(rule_a, project_id=project_id)
    strategy_bank_mgr.add_rule(rule_b, project_id=project_id)

    pruned_bank = inducer.pareto_prune_rules(project_id=project_id, max_rules=20)
    wardrobe_rules = [
        r for r in pruned_bank.rules if r.category == DefectCategory.WARDROBE_CONTRADICTION
    ]
    # Check deduplication occurred: only the higher-confidence rule (RULE-B or foundational) remains
    assert any(r.rule_id == "RULE-B" for r in wardrobe_rules)
    assert not any(r.rule_id == "RULE-A" for r in wardrobe_rules)


def test_pareto_prune_low_confidence_and_negative_reduction(inducer, strategy_bank_mgr):
    project_id = "proj_prune_quality"

    bad_confidence_rule = DirectorialInvariantRule(
        rule_id="RULE-LOW-CONF",
        category="STYLE",
        trigger_pattern="abstract pattern",
        invariant_directive="Do something risky.",
        rationale="Low quality rule.",
        confidence_score=0.62,  # < 0.70
        times_applied=5,
        defect_reduction_rate=0.1,
    )
    negative_rate_rule = DirectorialInvariantRule(
        rule_id="RULE-NEG-REDUCTION",
        category="PACING",
        trigger_pattern="fast cut montage",
        invariant_directive="Increase shot speed drastically.",
        rationale="Causes more defects.",
        confidence_score=0.92,
        times_applied=12,
        defect_reduction_rate=-0.25,  # < 0.0
    )
    good_rule = DirectorialInvariantRule(
        rule_id="RULE-GOOD-001",
        category="LIGHTING",
        trigger_pattern="indoor volumetric haze",
        invariant_directive="Lock volumetric lighting intensity.",
        rationale="Good performance.",
        confidence_score=0.94,
        times_applied=8,
        defect_reduction_rate=0.35,
    )

    strategy_bank_mgr.add_rule(bad_confidence_rule, project_id=project_id)
    strategy_bank_mgr.add_rule(negative_rate_rule, project_id=project_id)
    strategy_bank_mgr.add_rule(good_rule, project_id=project_id)

    pruned = inducer.pareto_prune_rules(project_id=project_id, max_rules=20)
    rule_ids = {r.rule_id for r in pruned.rules}

    assert "RULE-GOOD-001" in rule_ids
    assert "RULE-LOW-CONF" not in rule_ids
    assert "RULE-NEG-REDUCTION" not in rule_ids


def test_pareto_prune_max_rules_truncation(inducer, strategy_bank_mgr):
    project_id = "proj_prune_limit"

    # Add 25 synthetic high-quality rules with varying confidence scores
    for i in range(25):
        rule = DirectorialInvariantRule(
            rule_id=f"RULE-LIMIT-{i:03d}",
            category=f"CATEGORY_{i}",
            trigger_pattern=f"unique trigger scenario {i}",
            invariant_directive=f"Directive directive instruction {i}",
            rationale=f"Rationale explanation {i}",
            confidence_score=round(0.75 + (i * 0.008), 3),
            times_applied=i * 2,
            defect_reduction_rate=0.1,
        )
        strategy_bank_mgr.add_rule(rule, project_id=project_id)

    pruned = inducer.pareto_prune_rules(project_id=project_id, max_rules=10)
    assert len(pruned.rules) <= 10

    # Ensure retained rules are sorted by confidence and times_applied descending
    for i in range(len(pruned.rules) - 1):
        r1, r2 = pruned.rules[i], pruned.rules[i + 1]
        assert (r1.confidence_score, r1.times_applied) >= (r2.confidence_score, r2.times_applied)


def test_defect_clustering_null_and_casing_resilience(inducer, storage):
    project_id = "proj_null_case_test"

    # Feedback with null defects key and lower-case string defects
    storage.save_feedback(
        session_id="s_null",
        turn_id="t0",
        feedback={"session_id": "s_null", "turn_id": "t0", "defects": None},
        project_id=project_id,
    )
    storage.save_feedback(
        session_id="s_case",
        turn_id="t0",
        feedback={
            "session_id": "s_case",
            "turn_id": "t0",
            "defects": ["audio_drowned", "wardrobe_contradiction"],
        },
        project_id=project_id,
    )

    # Scorecard with null detected_defects
    storage.save_scorecard(
        session_id="sc_null",
        turn_id="t0",
        scorecard={"session_id": "sc_null", "turn_id": "t0", "detected_defects": None},
        project_id=project_id,
    )

    counts = inducer.cluster_defects(project_id=project_id)
    assert counts[DefectCategory.AUDIO_DROWNED] == 1
    assert counts[DefectCategory.WARDROBE_CONTRADICTION] == 1


def test_counterfactual_contradiction_precision(inducer):
    bank = StrategyBank(
        version="1.0.0",
        rules=[
            DirectorialInvariantRule(
                rule_id="RULE-VOCAL-001",
                category=DefectCategory.AUDIO_VOCAL_HALLUCINATION,
                trigger_pattern="spoken dialogue",
                invariant_directive="Always format dialogue lines with speaker tags.",
                rationale="Dialogue structure.",
                confidence_score=0.95,
            ),
            DirectorialInvariantRule(
                rule_id="RULE-CAMERA-001",
                category="CAMERA",
                trigger_pattern="action scene",
                invariant_directive="Single continuous camera move without cuts.",
                rationale="Camera stability.",
                confidence_score=0.90,
            ),
        ],
    )

    # Directive containing "eliminate" must NOT conflict with "Always format dialogue"
    compatible_rule = DirectorialInvariantRule(
        rule_id="RULE-INDUCED-VOC01",
        category=DefectCategory.AUDIO_VOCAL_HALLUCINATION,
        trigger_pattern="spoken character dialogue",
        invariant_directive='Wrap all vocal lines in [Dialogue: speaker: "quote"] to eliminate unscripted vocal gibberish.',
        rationale="Eliminates gibberish phonemes.",
        confidence_score=0.96,
    )
    assert inducer.validate_counterfactual(compatible_rule, bank) is True

    # True polarity contradiction on cuts: "Allow jump cuts" vs "Single continuous camera move without cuts"
    contradictory_camera = DirectorialInvariantRule(
        rule_id="RULE-INDUCED-CAM01",
        category="CAMERA",
        trigger_pattern="action scene",
        invariant_directive="Allow jump cuts between shots.",
        rationale="Dynamic editing.",
        confidence_score=0.92,
    )
    assert inducer.validate_counterfactual(contradictory_camera, bank) is False

    # Empty trigger pattern or rationale is rejected
    invalid_candidate = DirectorialInvariantRule(
        rule_id="RULE-INDUCED-INV01",
        category=DefectCategory.AUDIO_DROWNED,
        trigger_pattern="",
        invariant_directive="Ducking -18dB.",
        rationale="",
        confidence_score=0.95,
    )
    assert inducer.validate_counterfactual(invalid_candidate, bank) is False
