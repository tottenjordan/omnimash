from omnimash.agent.orchestrator import OmniMashAgent


def test_agent_initial_creation_flow():
    agent = OmniMashAgent(mock_mode=True)
    res = agent.process_user_turn(
        user_id="user_1",
        project_id="proj_1",
        prompt="Make Snape in 90s rap video",
        clip_index=0,
    )
    assert res.success is True
    assert res.video_url is not None
    assert res.status_event == "COMPLETED"


def test_agent_guardrail_rejection():
    agent = OmniMashAgent(mock_mode=True)
    res = agent.process_user_turn(
        user_id="user_1",
        project_id="proj_1",
        prompt="Generate illegal hate speech content",
        clip_index=0,
    )
    assert res.success is False
    assert "Policy violation" in (res.error_message or "")


def test_commit_recommended_and_branch_flow():
    agent = OmniMashAgent(mock_mode=True)
    # Turn 1
    r1 = agent.process_user_turn("u1", "p1", "Snape 90s rap", 0)
    assert r1.status_event == "COMPLETED"

    # Turn 2, 3, 4
    r2 = agent.process_user_turn("u1", "p1", "Add gold chains", 0, r1.turn_id)
    r3 = agent.process_user_turn("u1", "p1", "Add neon lights", 0, r2.turn_id)
    r4 = agent.process_user_turn("u1", "p1", "Add fog", 0, r3.turn_id)
    assert r4.status_event == "COMMIT_RECOMMENDED"

    # Commit and branch
    assert r4.turn_id is not None
    c_res = agent.commit_and_branch("u1", "p1", r4.turn_id, "Add laser eyes")
    assert c_res.success is True
    assert c_res.status_event == "REANCHORED"
