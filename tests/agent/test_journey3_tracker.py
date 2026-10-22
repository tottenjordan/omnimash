from omnimash.agent.orchestrator import Journey3StateTracker


def test_journey3_state_persists_across_shots():
    tracker = Journey3StateTracker()
    tracker.record_shot_directive(
        session_id="test_j3",
        shot_index=1,
        action_text="Yo Totti puts on a golden velvet blindfold",
    )
    state = tracker.get_cumulative_state(session_id="test_j3")
    assert "blindfold" in state.format_cumulative_state_block().lower()


def test_journey3_state_unset_keywords():
    tracker = Journey3StateTracker()
    tracker.record_shot_directive(
        session_id="test_j3",
        shot_index=1,
        action_text="Yo Totti puts on a golden velvet blindfold",
    )
    state1 = tracker.get_cumulative_state(session_id="test_j3")
    assert "blindfold" in state1.format_cumulative_state_block().lower()

    tracker.record_shot_directive(
        session_id="test_j3",
        shot_index=2,
        action_text="Totti removes blindfold and steps into the ring",
    )
    state2 = tracker.get_cumulative_state(session_id="test_j3")
    assert "blindfold" not in state2.format_cumulative_state_block().lower()


def test_journey3_state_keywords_and_clear_session():
    tracker = Journey3StateTracker()
    tracker.record_shot_directive(
        session_id="sess_1",
        shot_index=1,
        action_text="Snape holding golden cup surrounded by neon candles",
    )
    state = tracker.get_cumulative_state(session_id="sess_1")
    block = state.format_cumulative_state_block().lower()
    assert "golden cup" in block or "holding" in block
    assert "neon candles" in block

    tracker.clear_session("sess_1")
    cleared_state = tracker.get_cumulative_state("sess_1")
    assert cleared_state.format_cumulative_state_block() == "None."


def test_journey3_state_unset_does_not_remove_unrelated_states():
    tracker = Journey3StateTracker()
    tracker.record_shot_directive(
        session_id="test_j3_unrelated",
        shot_index=1,
        action_text="Totti puts on a golden velvet blindfold and wears diamond ring",
    )
    state1 = tracker.get_cumulative_state(session_id="test_j3_unrelated")
    block1 = state1.format_cumulative_state_block().lower()
    assert "blindfold" in block1
    assert "ring" in block1

    # Totti removes blindfold and steps into the ring -> must only remove blindfold, not diamond ring
    tracker.record_shot_directive(
        session_id="test_j3_unrelated",
        shot_index=2,
        action_text="Totti removes blindfold and steps into the ring",
    )
    state2 = tracker.get_cumulative_state(session_id="test_j3_unrelated")
    block2 = state2.format_cumulative_state_block().lower()
    assert "blindfold" not in block2
    assert "ring" in block2


def test_cumulative_state_tracker_delegates_to_session_manager():
    from omnimash.state.session_manager import SessionManager
    from omnimash.storage.gcs import GcsStorageManager

    storage = GcsStorageManager(bucket_name="test-bucket", mock_mode=True)
    sm = SessionManager(storage=storage)
    session = sm.get_or_create_session("u1", "p1", session_name="unified_sync_sess")
    sm.add_turn(session.session_id, 0, "Initial turn", "thread_1", "/clip0.mp4")

    tracker = Journey3StateTracker(storage=storage, session_manager=sm)
    tracker.record_shot_directive(
        session_id=session.session_id,
        shot_index=0,
        action_text="Chef Gordon enters holding glowing cyber spatula",
        project_id="p1",
    )

    # In-memory session should immediately reflect the cumulative state
    assert session.cumulative_state != {}
    assert "Chef" in session.cumulative_state.get("character_states", {})

    # GCS manifest should contain BOTH turns and cumulative state without clobbering
    manifest = storage.get_session_manifest(session.session_id, project_id="p1")
    assert manifest is not None
    assert "turns" in manifest
    assert len(manifest["turns"]) == 1
    assert "cumulative_state" in manifest
    assert "Chef" in manifest["cumulative_state"]["character_states"]
