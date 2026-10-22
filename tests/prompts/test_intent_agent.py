"""Tests for IntentGapAnalyzer and IntentAutoFiller."""

from omnimash.api.models import IntentSlotInputs
from omnimash.prompts.intent_agent import IntentAutoFiller, IntentGapAnalyzer


def test_analyze_gaps_identifies_empty_slots_and_generates_questions():
    analyzer = IntentGapAnalyzer(mock_mode=True)
    res = analyzer.analyze(
        intent="Two wizards having an aggressive rap battle in a medieval tavern",
        inputs=IntentSlotInputs(),
    )
    assert res.success is True
    assert "audio_beat" in res.missing_slots or "characters" in res.missing_slots
    assert len(res.questions) >= 2
    assert len(res.questions) <= 3
    for q in res.questions:
        assert len(q.options) >= 2
        assert q.allow_custom is True


def test_analyze_gaps_respects_supplied_inputs():
    analyzer = IntentGapAnalyzer(mock_mode=True)
    res = analyzer.analyze(
        intent="A cooking showdown",
        inputs=IntentSlotInputs(
            characters=["Chef Gordon", "Chef Julia"],
            audio_beat="140 BPM Heavy 808 Trap Beat",
        ),
    )
    assert "characters" not in res.missing_slots
    assert "audio_beat" not in res.missing_slots
    assert res.filled_slots["audio_beat"] == "140 BPM Heavy 808 Trap Beat"


def test_auto_fill_plan_produces_valid_four_block_prompt():
    autofiller = IntentAutoFiller(mock_mode=True)
    res = autofiller.generate_plan(
        intent="Cyberpunk detectives investigating a glitching neon alley",
        inputs=IntentSlotInputs(setting="Neo Tokyo rainy alleyway"),
        answers={},
    )
    assert res.success is True
    plan = res.plan
    assert "Neo Tokyo" in plan.environment
    assert len(plan.characters) >= 2
    assert "### INPUT ROLES & REFERENCES" in plan.raw_compiled_prompt
    assert "### CHARACTER PROFILES" in plan.raw_compiled_prompt
    assert "### SCENE INSTRUCTIONS" in plan.raw_compiled_prompt
    assert "### TIMELINE" in plan.raw_compiled_prompt
    assert "[0-3s]" in plan.raw_compiled_prompt
    assert "[3-6s]" in plan.raw_compiled_prompt
    assert "[6-10s]" in plan.raw_compiled_prompt


def test_auto_fill_plan_incorporates_question_answers():
    autofiller = IntentAutoFiller(mock_mode=True)
    answers = {
        "q_audio": "90s Boom-Bap Hip Hop Beat with scratching",
        "q_camera": "Dutch angle continuous handheld camera with green phosphor flare",
    }
    res = autofiller.generate_plan(
        intent="Two hackers cracking a mainframe",
        inputs=IntentSlotInputs(),
        answers=answers,
    )
    assert res.success is True
    plan = res.plan
    assert "Boom-Bap" in plan.audio_beat or "Boom-Bap" in plan.raw_compiled_prompt
    assert "Dutch angle" in plan.camera_lighting or "Dutch angle" in plan.raw_compiled_prompt


def test_deterministic_mock_mode_resilience():
    analyzer = IntentGapAnalyzer(mock_mode=True)
    res = analyzer.analyze(
        intent="",
        inputs=IntentSlotInputs(),
    )
    assert res.success is True
    assert len(res.questions) >= 2

    autofiller = IntentAutoFiller(mock_mode=True)
    plan_res = autofiller.generate_plan(
        intent="",
        inputs=None,
        answers=None,
    )
    assert plan_res.success is True
    assert plan_res.plan.raw_compiled_prompt != ""
