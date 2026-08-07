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
