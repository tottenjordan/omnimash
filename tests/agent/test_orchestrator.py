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


def test_stitch_session_master_and_multi_clip_save():
    agent = OmniMashAgent(mock_mode=True)
    assert hasattr(agent, "stitcher")
    s_name = "multi_clip_session_test"
    r1 = agent.process_user_turn(
        user_id="u1",
        project_id="p1",
        prompt="Clip 1",
        clip_index=0,
        session_name=s_name,
    )
    r2 = agent.process_user_turn(
        user_id="u1",
        project_id="p1",
        prompt="Clip 2",
        clip_index=1,
        parent_turn_id=r1.turn_id,
        session_name=s_name,
    )
    assert r1.video_url is not None
    assert r2.video_url is not None

    pub_url, gcs_uri = agent.stitch_session_master(s_name, "direct_stitch_master")
    assert "final_masters" in gcs_uri
    assert "direct_stitch_master.mp4" in gcs_uri
    assert pub_url.startswith("https://")

    pub_url2, gcs_uri2 = agent.save_final_master(
        session_id=s_name,
        video_url=r2.video_url,
        master_title="auto_stitched_master",
    )
    assert "final_masters" in gcs_uri2
    assert "auto_stitched_master.mp4" in gcs_uri2


def test_orchestrator_save_final_master_with_raw_compiled_prompt(monkeypatch):
    agent = OmniMashAgent(mock_mode=True)
    calls = []

    def mock_save_final_master(
        session_id, source_rel_path, master_title, prompt_data=None
    ):
        calls.append((session_id, source_rel_path, master_title, prompt_data))
        return "https://pub/master.mp4", "gs://bucket/master.mp4"

    monkeypatch.setattr(agent.storage, "save_final_master", mock_save_final_master)

    pub_url, gcs_uri = agent.save_final_master(
        session_id="sess_123",
        video_url="/static/rendered/turn_0_video.mp4",
        master_title="final_rap_battle",
        raw_compiled_prompt="[SUBJECT ANCHOR]: Snape",
    )
    assert len(calls) == 1
    s_id, src_path, title, prompt_data = calls[0]
    assert s_id == "sess_123"
    assert src_path == "/static/rendered/turn_0_video.mp4"
    assert title == "final_rap_battle"
    assert prompt_data == "[SUBJECT ANCHOR]: Snape"


def test_orchestrator_intermediate_turn_video_naming():
    agent = OmniMashAgent(mock_mode=True)
    res0 = agent.process_user_turn(
        user_id="u1",
        project_id="p1",
        prompt="Turn 0 prompt",
        clip_index=0,
        session_name="naming_test_session",
    )
    assert res0.success is True
    assert res0.video_url is not None
    assert "turn_0_video.mp4" in res0.video_url

    res1 = agent.process_user_turn(
        user_id="u1",
        project_id="p1",
        prompt="Turn 1 prompt diff",
        clip_index=0,
        parent_turn_id=res0.turn_id,
        session_name="naming_test_session",
    )
    assert res1.success is True
    assert res1.video_url is not None
    assert "turn_1_video.mp4" in res1.video_url
