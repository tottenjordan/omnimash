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


def test_find_session_sanitize_and_stored_id_fallback():
    sm = SessionManager()
    created = sm.get_or_create_session("u", "p", session_name="Dripwarts Vol 1!")
    # Exact stored key resolves.
    assert sm.find_session("Dripwarts_Vol_1_") is created
    # Raw (unsanitized) name resolves via the sanitize fallback.
    assert sm.find_session("Dripwarts Vol 1!") is created
    # Unknown id returns None (no reaching into private state).
    assert sm.find_session("does-not-exist") is None
    assert sm.find_session(None) is None


def test_lru_eviction_bounds_session_count():
    sm = SessionManager(max_sessions=2)
    a = sm.get_or_create_session("u", "p", session_name="A")
    sm.get_or_create_session("u", "p", session_name="B")
    # Touch A so it becomes most-recently-used; C should then evict B.
    assert sm.find_session("A") is a
    sm.get_or_create_session("u", "p", session_name="C")

    assert sm.find_session("A") is not None
    assert sm.find_session("C") is not None
    assert sm.find_session("B") is None


def test_session_not_found_raised_for_missing_session_and_turn():
    import pytest

    from omnimash.state.session_manager import SessionNotFound

    sm = SessionManager()
    with pytest.raises(SessionNotFound):
        sm.add_turn("ghost", 0, "p", "thread", "/x.mp4")

    session = sm.get_or_create_session("u", "p", session_name="real")
    with pytest.raises(SessionNotFound):
        sm.commit_turn(session.session_id, "no-such-turn")
    # SessionNotFound is a KeyError subclass for backward compatibility.
    assert issubclass(SessionNotFound, KeyError)
