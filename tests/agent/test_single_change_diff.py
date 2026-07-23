from omnimash.agent.orchestrator import OmniMashAgent


def test_validate_conversational_edit_single_changes():
    agent = OmniMashAgent(mock_mode=True)

    single_change_prompts = [
        "Change the jacket to green",
        "Add gold chains",
        "Switch background to sunset",
        "Make the lighting warmer",
        "Replace hat with a crown",
        "Remove the sunglasses",
        "Adjust camera angle to wide shot",
        "Add neon lights",
        "Add fog",
    ]

    for prompt in single_change_prompts:
        is_valid, msg = agent.validate_conversational_edit(prompt)
        assert is_valid is True, f"Expected '{prompt}' to be valid single change"
        assert msg == ""


def test_validate_conversational_edit_compound_multi_changes():
    agent = OmniMashAgent(mock_mode=True)
    expected_msg = (
        "Gemini Omni Flash performs best with one edit per turn to maintain scene coherence. "
        "Please split your request into single edits (e.g. first change the outfit, then adjust camera angle)."
    )

    compound_prompts = [
        "change X, switch Y, and add Z",
        "Change the jacket to green, switch background to studio, and add sunglasses",
        "first change the outfit, then adjust camera angle",
        "Change jacket to green and add gold chains",
        "Remove hat and switch background",
        "Make shirt red and change hair to blonde",
        "Add gold chains, neon lights, and fog",
    ]

    for prompt in compound_prompts:
        is_valid, msg = agent.validate_conversational_edit(prompt)
        assert is_valid is False, f"Expected '{prompt}' to be rejected as compound multi-change"
        assert msg == expected_msg


def test_process_user_turn_single_change_success():
    agent = OmniMashAgent(mock_mode=True)

    # Initial Turn
    r1 = agent.process_user_turn(
        user_id="u_single",
        project_id="p_single",
        prompt="Make Snape in 90s rap video",
        clip_index=0,
    )
    assert r1.success is True
    assert r1.turn_id is not None

    # Valid Conversational Delta Edit
    r2 = agent.process_user_turn(
        user_id="u_single",
        project_id="p_single",
        prompt="Change the jacket to green",
        clip_index=0,
        parent_turn_id=r1.turn_id,
    )
    assert r2.success is True
    assert r2.status_event in ["COMPLETED", "COMMIT_RECOMMENDED"]
    assert r2.video_url is not None


def test_process_user_turn_compound_multi_change_rejection():
    agent = OmniMashAgent(mock_mode=True)

    # Initial Turn
    r1 = agent.process_user_turn(
        user_id="u_multi",
        project_id="p_multi",
        prompt="Make Snape in 90s rap video",
        clip_index=0,
    )
    assert r1.success is True
    assert r1.turn_id is not None

    # Compound Multi-Change Delta Edit
    r2 = agent.process_user_turn(
        user_id="u_multi",
        project_id="p_multi",
        prompt="Change the jacket to green, switch background to studio, and add sunglasses",
        clip_index=0,
        parent_turn_id=r1.turn_id,
    )
    assert r2.success is False
    assert r2.status_event == "MULTI_CHANGE_REJECTED"
    assert "Gemini Omni Flash performs best with one edit per turn" in (
        r2.error_message or ""
    )
