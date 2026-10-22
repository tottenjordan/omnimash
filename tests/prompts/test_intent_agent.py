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


def test_auto_fill_preserves_vault_character_profiles_and_reference_urls():
    from omnimash.api.models import CharacterRoleModel

    vault_char = CharacterRoleModel(
        role_id="Role A",
        name="Dumble Dior",
        description="Elderly high-fashion wizard headmaster with diamond spectacles",
        reference_url="gs://omnimash-media-hybrid-vertex/projects/trapwarts/sessions/dd_office_v13/character_sheets/dumble_dior_office_sheet_v13.png",
        wardrobe="Floor-length custom silk monogram wizard robe",
        voice_style="Sharp, vigorous Oxford English cadence",
    )
    analyzer = IntentGapAnalyzer(mock_mode=True)
    gap_res = analyzer.analyze(
        intent="Inspecting glowing gold galleons in the vault",
        inputs=IntentSlotInputs(character_profiles=[vault_char]),
    )
    assert "characters" not in gap_res.missing_slots

    autofiller = IntentAutoFiller(mock_mode=True)
    res = autofiller.generate_plan(
        intent="Inspecting glowing gold galleons in the vault",
        inputs=IntentSlotInputs(character_profiles=[vault_char]),
        answers={},
    )
    assert res.success is True
    plan = res.plan
    assert len(plan.characters) >= 2
    assert plan.characters[0].name == "Dumble Dior"
    assert (
        plan.characters[0].reference_url
        == "gs://omnimash-media-hybrid-vertex/projects/trapwarts/sessions/dd_office_v13/character_sheets/dumble_dior_office_sheet_v13.png"
    )
    assert "silk monogram wizard robe" in plan.characters[0].wardrobe
    assert "Dumble Dior" in plan.raw_compiled_prompt
    assert "@Image1" in plan.raw_compiled_prompt


def test_auto_fill_incorporates_dialogue_direction_guidance():
    direction = "Trade sarcastic corporate audit jargon mixed with calm East London wizard slang"
    analyzer = IntentGapAnalyzer(mock_mode=True)
    gap_res = analyzer.analyze(
        intent="Two wizards auditing a mountain of gold coins",
        inputs=IntentSlotInputs(dialogue_direction=direction),
    )
    assert "dialogue" not in gap_res.missing_slots
    assert gap_res.filled_slots.get("dialogue_direction") == direction

    autofiller = IntentAutoFiller(mock_mode=True)
    res = autofiller.generate_plan(
        intent="Two wizards auditing a mountain of gold coins",
        inputs=IntentSlotInputs(dialogue_direction=direction),
        answers={},
    )
    assert res.success is True
    plan = res.plan
    assert plan.dialogue_direction == direction
    assert direction in plan.vocal_delivery
    assert "Dialogue Direction" in plan.raw_compiled_prompt
    assert direction in plan.raw_compiled_prompt
    # Ensure the direction itself was used as guidance rather than pasted verbatim as the literal spoken quote
    assert f'"{direction}"' not in plan.screenplay_script


def test_auto_fill_three_characters_includes_all_three_in_timeline_and_dialogue():
    """Verify that when 3 characters are present, all 3 are included in the timeline, dialogue, and vault references."""
    autofiller = IntentAutoFiller(mock_mode=True)
    res = autofiller.generate_plan(
        intent="YoTotti, Bee Allison, and Dumble Dior are smoking fat cigars and laughing in a luxury office",
        inputs=IntentSlotInputs(
            characters=["Bee Allison", "YoTotti", "Dumble Dior"],
        ),
        answers={},
    )
    assert res.success is True
    plan = res.plan
    assert len(plan.characters) == 3
    names = [c.name for c in plan.characters]
    assert "Bee Allison" in names
    assert "YoTotti" in names
    assert "Dumble Dior" in names

    # Verify Bee Allison wardrobe matches reference sheet (bucket hat, black tracksuit) and not generic crimson velvet
    bee_char = next(c for c in plan.characters if c.name == "Bee Allison")
    assert (
        "bucket hat" in bee_char.wardrobe.lower() or "black tracksuit" in bee_char.wardrobe.lower()
    )
    assert "crimson velvet" not in bee_char.wardrobe.lower()

    # Verify all 3 characters appear in TIMELINE action
    timeline_text = plan.raw_compiled_prompt.split("### TIMELINE")[-1]
    assert "Bee Allison" in timeline_text
    assert "YoTotti" in timeline_text
    assert "Dumble Dior" in timeline_text

    # Verify all 3 characters have dialogue or action scripted
    assert "Dumble Dior:" in plan.screenplay_script or "Dumble Dior (" in plan.screenplay_script
    assert len(plan.scenes[0].active_roles) == 3
    assert set(plan.scenes[0].active_roles) == {"Role A", "Role B", "Role C"}
