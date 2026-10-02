from omnimash.state.session_manager import SessionManager


def test_session_creation_and_branching():
    manager = SessionManager()
    session = manager.get_or_create_session("user_123", "proj_456")
    assert session.project_id == "proj_456"

    # Add initial turn
    turn1 = manager.add_turn(
        session_id=session.session_id,
        clip_index=0,
        prompt="Snape in 90s rap video",
        interaction_thread_id="thread_abc",
        video_url="/videos/clip1_turn1.mp4",
    )
    assert turn1.turn_id is not None

    # Branch new edit from turn1
    turn2 = manager.add_turn(
        session_id=session.session_id,
        clip_index=0,
        prompt="Add sunglasses",
        interaction_thread_id="thread_abc",
        video_url="/videos/clip1_turn2.mp4",
        parent_turn_id=turn1.turn_id,
    )
    assert turn2.parent_turn_id == turn1.turn_id


def test_commit_turn_and_depth_tracking():
    sm = SessionManager()
    session = sm.get_or_create_session("user_test", "proj_test")
    t1 = sm.add_turn(session.session_id, 0, "Prompt 1", "thread_1", "/clip1.mp4")
    assert t1.edit_depth_in_thread == 0
    assert t1.is_committed is False

    t2 = sm.add_turn(
        session.session_id,
        0,
        "Prompt 2",
        "thread_1",
        "/clip2.mp4",
        parent_turn_id=t1.turn_id,
    )
    assert t2.edit_depth_in_thread == 1

    committed = sm.commit_turn(session.session_id, t2.turn_id)
    assert committed.is_committed is True


def test_session_manager_custom_session_name():
    sm = SessionManager()
    session = sm.get_or_create_session("u_1", "p_1", session_name="Dripwarts Vol 1!")
    assert session.session_id == "Dripwarts_Vol_1_"
    assert session.user_id == "u_1"


def test_session_manager_persists_and_reloads_turns_via_storage():
    from omnimash.storage.gcs import GcsStorageManager

    storage = GcsStorageManager(bucket_name="test-omnimash-bucket", mock_mode=True)
    sm1 = SessionManager(storage=storage)
    s1 = sm1.get_or_create_session("user_1", "proj_1", session_name="persisted_sess")
    t1 = sm1.add_turn(
        session_id=s1.session_id,
        clip_index=0,
        prompt="Opening wide shot",
        interaction_thread_id="thread_001",
        video_url="/static/rendered/clip_0.mp4",
    )
    sm1.commit_turn(s1.session_id, t1.turn_id)

    # Simulate new instance / container restart backed by the same storage
    sm2 = SessionManager(storage=storage)
    s2 = sm2.get_or_create_session("user_1", "proj_1", session_name="persisted_sess")
    assert t1.turn_id in s2.turns
    assert s2.turns[t1.turn_id].is_committed is True
    assert len(s2.timeline) == 1
    assert s2.timeline[0].active_turn_id == t1.turn_id
