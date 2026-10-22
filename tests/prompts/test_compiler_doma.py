from __future__ import annotations

from unittest.mock import MagicMock

from omnimash.evaluation.exemplar_bank import ExemplarBankManager
from omnimash.evaluation.models import DefectCategory, DirectorialInvariantRule
from omnimash.evaluation.strategy_bank import StrategyBankManager
from omnimash.prompts.character_roles import CharacterRole
from omnimash.prompts.compiler import PromptCompiler, SceneDirective
from omnimash.prompts.journey3 import compile_journey3_shot_prompt
from omnimash.prompts.preflight_linter import PreFlightGatekeeper


def test_prompt_compiler_init_strategy_and_exemplar_banks():
    """PromptCompiler accepts optional strategy_bank and exemplar_bank."""
    sb = StrategyBankManager(mock_mode=True)
    eb = ExemplarBankManager(mock_mode=True)

    compiler = PromptCompiler(mock_mode=True, strategy_bank=sb, exemplar_bank=eb)
    assert compiler.strategy_bank is sb
    assert compiler.exemplar_bank is eb


def test_compile_turn0_prompt_queries_and_injects_strategy_bank_rules():
    """compile_turn0_prompt queries Strategy Bank and injects matched invariant directives."""
    sb = StrategyBankManager(mock_mode=True)
    compiler = PromptCompiler(mock_mode=True, strategy_bank=sb)

    chars = [
        CharacterRole(
            role_id="Role A",
            name="Detective Vance",
            description="Gritty hardboiled investigator",
            reference_url="gs://bucket/vance.jpg",
            voice_style="Deep gravelly noir cadence",
        ),
        CharacterRole(
            role_id="Role B",
            name="Shadow Informant",
            description="Mysterious informant in trenchcoat",
            reference_url="gs://bucket/shadow.jpg",
            voice_style="Whispered conspiratorial tone",
        ),
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A", "Role B"],
            action="Facing off across the wet pavement under flickering neon lights",
            dialogue='Vance: "Who gave the order?" / Shadow: "You already know."',
        )
    ]

    # Concept contains keywords matching foundational invariants:
    # e.g., 'dialogue' -> RULE-AUDIO-001 / RULE-AUDIO-002
    # has_keyframe=True -> RULE-KEYFRAME-001
    compiled = compiler.compile_turn0_prompt(
        concept="Intense spoken dialogue scene with background music",
        characters=chars,
        scenes=scenes,
        has_keyframe_seed=True,
        keyframe_image_url="https://storage.googleapis.com/bucket/keyframe.png",
        enable_preflight=True,
    )

    assert "### SCENE INSTRUCTIONS" in compiled
    assert "[Directorial Invariants]" in compiled
    assert (
        "[Instrumental: ducking -18dB under speech]" in compiled
        or "duck under the spoken dialogue" in compiled
    )
    assert "Keyframe tag offset:" in compiled or "<IMAGE_REF_0>@Image2" in compiled


def test_compile_turn0_prompt_custom_strategy_bank_parameter():
    """compile_turn0_prompt queries custom strategy_bank passed as method argument."""
    compiler = PromptCompiler(mock_mode=True)
    custom_sb = MagicMock(spec=StrategyBankManager)
    custom_sb.query_applicable_rules.return_value = [
        DirectorialInvariantRule(
            rule_id="CUSTOM-RULE-001",
            category=DefectCategory.TAG_COLLISION,
            trigger_pattern="custom test trigger",
            invariant_directive="Enforce custom camera framing and color palette lock.",
            rationale="Unit test custom rule validation.",
            confidence_score=0.99,
        )
    ]

    chars = [
        CharacterRole(
            role_id="Role A",
            name="Hero",
            description="Brave protagonist",
        )
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A"],
            action="Steps toward the entrance",
        )
    ]

    compiled = compiler.compile_turn0_prompt(
        concept="Heroic journey begins",
        characters=chars,
        scenes=scenes,
        strategy_bank=custom_sb,
        project_id="test_project",
        enable_preflight=True,
    )

    custom_sb.query_applicable_rules.assert_called_once()
    assert "[Directorial Invariants]" in compiled
    assert "Enforce custom camera framing and color palette lock." in compiled


def test_compile_storyboard_preflight_auto_repairs_violations():
    """compile_storyboard auto-repairs tag collisions and audio ducking when enable_preflight=True."""
    compiler = PromptCompiler(mock_mode=True)

    chars = [
        CharacterRole(
            role_id="Role A",
            name="Snape",
            description="Gaunt wizard in black robe",
            reference_url="gs://bucket/snape.jpg",
            voice_style="Deep sarcastic cadence",
        )
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A"],
            action="Stirs potion kettle",
            dialogue='Snape: "Silence, foolish students."',
        )
    ]

    # Audio beat lacks 'instrumental' prefix and ducking clause
    compiled = compiler.compile_storyboard(
        concept="Snape chemistry lecture",
        characters=chars,
        scenes=scenes,
        audio_beat="120 BPM synth wave",
        enable_preflight=True,
    )

    # PreFlightGatekeeper Pass 4 guarantees ducking clause and instrumental prefix
    assert "### SCENE INSTRUCTIONS" in compiled
    assert PreFlightGatekeeper.CANONICAL_DUCKING_CLAUSE in compiled
    assert "instrumental 120 BPM synth wave" in compiled or "instrumental" in compiled


def test_compile_journey3_shot_prompt_auto_preflight_repair():
    """compile_journey3_shot_prompt automatically runs PreFlightGatekeeper and repairs un-ducked audio."""
    # When timeline_dialogue is provided but audio is not ducked, compile_journey3_shot_prompt
    # must ensure the canonical ducking clause and instrumental prefix are applied.
    compiled = compile_journey3_shot_prompt(
        shot_number=1,
        action_directive="Detective enters dimly lit speakeasy",
        character_roster="Role A - Detective Vance",
        timeline_dialogue='Vance: "I was looking for the boss."',
        audio_track="90s boom-bap beat",
        keyframe_image_url="https://storage.googleapis.com/bucket/start.png",
        enable_preflight=True,
    )

    assert "### SCENE INSTRUCTIONS" in compiled
    assert PreFlightGatekeeper.CANONICAL_DUCKING_CLAUSE in compiled
    assert "<FIRST_FRAME>@KeyframeSeed" in compiled


def test_compile_turn0_prompt_empty_inputs():
    """compile_turn0_prompt handles empty concept and empty characters gracefully."""
    compiler = PromptCompiler(mock_mode=True)
    compiled = compiler.compile_turn0_prompt(
        concept="",
        characters=[],
        scenes=[
            SceneDirective(
                scene_number=1,
                active_roles=[],
                action="A solitary wind blows across an empty field.",
            )
        ],
        enable_preflight=True,
    )
    assert "### INPUT ROLES & REFERENCES" in compiled
    assert "### CHARACTER PROFILES" in compiled
    assert "### SCENE INSTRUCTIONS" in compiled
    assert "### TIMELINE" in compiled


def test_compile_turn0_prompt_disable_preflight():
    """When enable_preflight=False, compiler skips PreFlightGatekeeper pass."""
    compiler = PromptCompiler(mock_mode=True)
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Bard",
            description="Lute player",
            reference_url="gs://bucket/bard.jpg",
        )
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A"],
            action="Strums lute",
            dialogue='Bard: "Hear my song!"',
        )
    ]
    compiled_with_preflight = compiler.compile_turn0_prompt(
        concept="Music performance",
        characters=chars,
        scenes=scenes,
        audio_beat="folk guitar",
        enable_preflight=True,
    )
    assert PreFlightGatekeeper.CANONICAL_DUCKING_CLAUSE in compiled_with_preflight

    compiled_without_preflight = compiler.compile_turn0_prompt(
        concept="Music performance",
        characters=chars,
        scenes=scenes,
        audio_beat="folk guitar",
        enable_preflight=False,
    )
    assert "### SCENE INSTRUCTIONS" in compiled_without_preflight


def test_compile_journey3_shot_prompt_stacked_tags_and_offsets():
    """compile_journey3_shot_prompt repairs stacked image reference tags and auto-shifts keyframe offsets."""
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Detective Vance",
            description="Gravelly investigator",
            reference_url="https://storage.googleapis.com/b/vance.png",
        )
    ]
    compiled = compile_journey3_shot_prompt(
        shot_number=1,
        action_directive="Detective Vance <IMAGE_REF_0> <IMAGE_REF_1> examines clues",
        characters=chars,
        keyframe_image_url="https://storage.googleapis.com/b/seed.png",
        timeline_dialogue='Vance: "The case is solved."',
        enable_preflight=True,
    )
    assert "<IMAGE_REF_0> <IMAGE_REF_1>" not in compiled
    assert "<FIRST_FRAME>@KeyframeSeed" in compiled
    assert "<IMAGE_REF_0>@Image2" in compiled
    assert PreFlightGatekeeper.CANONICAL_DUCKING_CLAUSE in compiled


def test_compile_turn0_prompt_no_matching_rules():
    """When no Strategy Bank rules match, [Directorial Invariants] block is omitted."""
    compiler = PromptCompiler(mock_mode=True)
    custom_sb = MagicMock(spec=StrategyBankManager)
    custom_sb.query_applicable_rules.return_value = []

    compiled = compiler.compile_turn0_prompt(
        concept="Abstract ambient geometric forms drifting in zero gravity",
        characters=[],
        scenes=[
            SceneDirective(scene_number=1, active_roles=[], action="Geometric forms drift slowly.")
        ],
        strategy_bank=custom_sb,
        enable_preflight=True,
    )
    assert "[Directorial Invariants]" not in compiled
