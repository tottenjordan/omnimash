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


def test_session_manager_sanitizes_default_key_and_private_attr():
    from omnimash.state.session_manager import SessionManager, sanitize_session_id

    assert sanitize_session_id("  test session/name! ") == "test_session_name_"
    sm = SessionManager()
    sess = sm.get_or_create_session("user/../admin", "proj:evil")
    assert ".." not in sess.session_id
    assert ":" not in sess.session_id
    assert sess.session_id == "user____admin_proj_evil"
    assert hasattr(sess, "_last_allocated_turn_index")
    assert sess._last_allocated_turn_index == -1


def test_add_turn_and_commit_turn_hydrate_from_storage_on_cold_start():
    from omnimash.storage.gcs import GcsStorageManager

    storage = GcsStorageManager(bucket_name="test-bucket", mock_mode=True)
    sm1 = SessionManager(storage=storage)
    s1 = sm1.get_or_create_session("u1", "p1", session_name="cold_start_sess")
    t1 = sm1.add_turn(s1.session_id, 0, "Prompt 1", "thread_1", "/clip1.mp4")

    # Brand new session manager instance with empty _sessions dict
    sm2 = SessionManager(storage=storage)
    assert "cold_start_sess" not in sm2._sessions

    # add_turn should hydrate from storage rather than raising KeyError
    t2 = sm2.add_turn(
        "cold_start_sess", 0, "Prompt 2", "thread_1", "/clip2.mp4", parent_turn_id=t1.turn_id
    )
    assert t2.edit_depth_in_thread == 1

    # commit_turn should also hydrate
    sm3 = SessionManager(storage=storage)
    committed = sm3.commit_turn("cold_start_sess", t2.turn_id)
    assert committed.is_committed is True


def test_allocate_turn_index_monotonic_with_nonstandard_url_and_shot_index():
    sm = SessionManager()
    sess = sm.get_or_create_session("u1", "p1")
    # Clip index is 5, but this is turn 0 (initial turn)
    t1 = sm.add_turn(
        sess.session_id,
        clip_index=5,
        prompt="Shot 5",
        interaction_thread_id="t1",
        video_url="https://signed-url.com/custom_uuid.mp4",
    )
    assert hasattr(t1, "turn_index")
    assert t1.turn_index == 0
    next_idx = sm.allocate_turn_index(sess)
    # Next turn index must be 1, NOT 6 (which conflated clip_index with turn sequence)
    assert next_idx == 1


def test_parent_turn_id_validation_handles_missing_parent():
    sm = SessionManager()
    sess = sm.get_or_create_session("u1", "p1")
    t1 = sm.add_turn(
        sess.session_id,
        clip_index=0,
        prompt="Orphan prompt",
        interaction_thread_id="t1",
        video_url="/clip1.mp4",
        parent_turn_id="non_existent_turn_uuid",
    )
    assert t1.parent_turn_id is None
    assert t1.edit_depth_in_thread == 0


def test_session_turn_limit_enforcement():
    import pytest
    from omnimash.state.session_manager import MAX_TURNS_PER_SESSION

    sm = SessionManager()
    sess = sm.get_or_create_session("u1", "p1")
    # Populate up to limit
    for i in range(MAX_TURNS_PER_SESSION):
        sess.turns[f"turn_{i}"] = sm.add_turn(
            sess.session_id, 0, f"Prompt {i}", "t1", f"/clip_{i}.mp4"
        )
        if len(sess.turns) >= MAX_TURNS_PER_SESSION:
            break

    with pytest.raises(ValueError, match="reached maximum turn limit"):
        sm.add_turn(sess.session_id, 0, "Exceed prompt", "t1", "/exceed.mp4")


def test_cumulative_state_methods_on_session_manager():
    sm = SessionManager()
    sess = sm.get_or_create_session("u1", "p1")
    assert sm.get_cumulative_state(sess.session_id) == {}

    state_data = {"character_states": {"Chef": ["has spatula"]}, "scene_states": ["neon kitchen"]}
    sm.update_cumulative_state(sess.session_id, state_data)
    assert sm.get_cumulative_state(sess.session_id) == state_data
