from omnimash.agent.orchestrator import OmniMashAgent, build_adk_agent


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
    assert hasattr(res, "error_message")
    assert res.generation_mode in ["LIVE_OMNI_FLASH", "LOCAL_PROCEDURAL_ANIMATION"]


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


def test_adk_agent_instruction_and_compiler_integration():
    adk_agent = build_adk_agent(mock_mode=True)
    assert isinstance(adk_agent.instruction, str)
    assert "Prompt Compiler" in adk_agent.instruction
    assert "[SUBJECT ANCHOR]" in adk_agent.instruction


def test_adk_agent_delta_prompt_instruction_rules():
    adk_agent = build_adk_agent(mock_mode=True)
    assert isinstance(adk_agent.instruction, str)
    assert "[PRESERVATION LOCK]" in adk_agent.instruction
    assert "[ISOLATED DIFF]" in adk_agent.instruction


def test_orchestrator_processes_youtube_reference_url():
    agent = OmniMashAgent(mock_mode=True)
    res = agent.process_user_turn(
        user_id="u_yt",
        project_id="p_yt",
        prompt="DumbleDior rapping to reference beat",
        reference_url="https://www.youtube.com/watch?v=sample_beat",
    )
    assert res.success is True
    assert res.video_url is not None


def test_orchestrator_accepts_audio_stem_and_compiled_override():
    agent = OmniMashAgent(mock_mode=True)
    res = agent.process_user_turn(
        user_id="u_custom",
        project_id="p_custom",
        prompt="Harry with custom drill",
        clip_index=0,
        audio_stem="140 BPM UK Drill 808s",
        compiled_override="[SUBJECT ANCHOR]: Harry | [AESTHETIC INJECTION]: Streetwear | [ENVIRONMENT]: London | [CAMERA/LIGHTING]: 4K | [MOTION]: Gestures | [AUDIO TRACK]: 140 BPM Drill",
    )
    assert res.success is True
    assert res.video_url is not None
