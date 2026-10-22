from __future__ import annotations


from omnimash.agent.adk_pipeline import (
    STORYBOARD_COMPILER_DEFAULT_INSTRUCTION,
    create_storyboard_compiler_agent,
)
from omnimash.agent.orchestrator import OmniMashAgent, OmniMashOrchestrator


def test_storyboard_compiler_instruction_references_preflight_gatekeeper():
    """STORYBOARD_COMPILER_DEFAULT_INSTRUCTION explicitly references PreFlightGatekeeper invariants."""
    assert "PreFlightGatekeeper" in STORYBOARD_COMPILER_DEFAULT_INSTRUCTION
    assert (
        "Tag collision" in STORYBOARD_COMPILER_DEFAULT_INSTRUCTION
        or "tag collision" in STORYBOARD_COMPILER_DEFAULT_INSTRUCTION
    )
    assert (
        "audio ducking" in STORYBOARD_COMPILER_DEFAULT_INSTRUCTION
        or "Audio ducking" in STORYBOARD_COMPILER_DEFAULT_INSTRUCTION
    )


def test_create_storyboard_compiler_agent_includes_preflight_tool():
    """create_storyboard_compiler_agent equips the agent with PreFlightGatekeeper validation tool."""
    agent = create_storyboard_compiler_agent()
    assert agent.name == "storyboard_compiler"
    tool_names = [getattr(t, "__name__", str(t)) for t in agent.tools]
    assert any("preflight" in name.lower() for name in tool_names)


def test_orchestrator_alias_exists():
    """OmniMashOrchestrator alias is exposed from orchestrator module."""
    assert OmniMashOrchestrator is OmniMashAgent


def test_orchestrator_process_user_turn_records_preflight_violations_on_prompt():
    """OmniMashOrchestrator.process_user_turn runs PreFlightGatekeeper on prompt and records violations."""
    orchestrator = OmniMashOrchestrator(mock_mode=True)

    # Prompt with unattached phantom token and duplicate @Image tokens
    defective_prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0> <IMAGE_REF_1>@Image1 KeyframeSeed\n"
        "- Role A: gs://bucket/char.jpg (@Image1)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (@Image1 @Image1): Detective Vance.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic noir.\n"
        "Environment: Dark alley.\n"
        "Audio: Heavy synth beat.\n\n"
        "### TIMELINE\n"
        '[0-3s] Vance: "Looking for answers."'
    )

    res = orchestrator.process_user_turn(
        user_id="test_user",
        project_id="test_project",
        prompt=defective_prompt,
        clip_index=0,
    )

    assert res.success is True
    # Verify preflight violations are recorded in turn response and metadata
    assert len(res.preflight_violations) > 0 or (
        res.metadata
        and "preflight_violations" in res.metadata
        and len(res.metadata["preflight_violations"]) > 0
    )
    # Check that session turn node also recorded preflight metadata
    session = orchestrator.session_manager.get_session("test_user_test_project")
    assert session is not None
    turn = session.turns.get(res.turn_id)
    assert turn is not None
    assert getattr(turn, "preflight_violations", None) or (
        getattr(turn, "metadata", None) and "preflight_violations" in turn.metadata
    )


def test_orchestrator_process_user_turn_records_preflight_violations_on_compiled_override():
    """OmniMashOrchestrator.process_user_turn lints compiled_override and auto-repairs violations."""
    orchestrator = OmniMashOrchestrator(mock_mode=True)

    defective_override = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0> <IMAGE_REF_1>@Image1\n"
        "- Role A: gs://bucket/hero.jpg (@Image1)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Hero.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Bright sunlight.\n"
        "Environment: Meadow.\n"
        "Audio: acoustic guitar.\n\n"
        "### TIMELINE\n"
        '[0-3s] Hero: "We ride at dawn."'
    )

    res = orchestrator.process_user_turn(
        user_id="test_user_override",
        project_id="test_proj_override",
        prompt="Initial prompt",
        compiled_override=defective_override,
        clip_index=0,
    )

    assert res.success is True
    assert res.raw_compiled_prompt is not None
    assert "<IMAGE_REF_0> <IMAGE_REF_1>" not in res.raw_compiled_prompt
    # Pre-flight violations are detected and recorded in metadata and telemetry
    assert len(res.preflight_violations) > 0 or (
        res.metadata
        and "preflight_violations" in res.metadata
        and len(res.metadata["preflight_violations"]) > 0
    )


def test_orchestrator_process_user_turn_clean_prompt_no_violations():
    """Clean prompts without invariant defects produce empty preflight_violations."""
    orchestrator = OmniMashOrchestrator(mock_mode=True)
    res = orchestrator.process_user_turn(
        user_id="clean_user",
        project_id="clean_project",
        prompt="A peaceful quiet sunset over calm ocean waters",
        clip_index=0,
    )
    assert res.success is True
    assert len(res.preflight_violations) == 0


def test_orchestrator_process_user_turn_phantom_token_repaired():
    """Unattached phantom tokens (like KeyframeSeed) are stripped and reported in turn metadata."""
    orchestrator = OmniMashOrchestrator(mock_mode=True)
    defective = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0>@Image1 KeyframeSeed\n"
        "- Role A: gs://bucket/char.jpg (@Image1)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Detective.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Noir.\n"
        "Environment: Alley.\n"
        "Audio: instrumental ambient.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Walking."
    )
    res = orchestrator.process_user_turn(
        user_id="phantom_user",
        project_id="phantom_project",
        prompt=defective,
        clip_index=0,
    )
    assert res.success is True
    assert res.raw_compiled_prompt is not None
    assert "KeyframeSeed" not in res.raw_compiled_prompt
    assert any(
        getattr(v, "rule_id", "") == "TAG_COLLISION"
        or (isinstance(v, dict) and v.get("rule_id") == "TAG_COLLISION")
        for v in res.preflight_violations
    ) or any(
        v.get("rule_id") == "TAG_COLLISION" for v in res.metadata.get("preflight_violations", [])
    )
