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
