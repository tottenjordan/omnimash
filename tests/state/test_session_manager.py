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
