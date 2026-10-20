from __future__ import annotations

from omnimash.agent.orchestrator import CumulativeStateTracker as OrchestratorTracker
from omnimash.agent.orchestrator import Journey3StateTracker as OrchestratorLegacyTracker
from omnimash.state import (
    CumulativeShotState,
    CumulativeStateTracker as StateTracker,
    Journey3StateTracker as StateLegacyTracker,
)
from omnimash.state.tracker import CumulativeStateTracker, Journey3StateTracker


def test_tracker_exports_and_aliases():
    """Verify tracker can be imported from state.tracker, state, and agent.orchestrator."""
    assert CumulativeStateTracker is StateTracker
    assert CumulativeStateTracker is OrchestratorTracker
    assert Journey3StateTracker is StateLegacyTracker
    assert Journey3StateTracker is OrchestratorLegacyTracker
    assert Journey3StateTracker is CumulativeStateTracker


def test_tracker_record_and_get_cumulative_state():
    """Verify recording shot directives accumulates character state."""
    tracker = CumulativeStateTracker()
    tracker.record_shot_directive(
        session_id="test_sess",
        shot_index=0,
        action_text="Harry puts on a wizard hat and holding a golden cup.",
        dialogue_text="",
        known_characters=["Harry"],
    )
    state = tracker.get_cumulative_state("test_sess")
    assert isinstance(state, CumulativeShotState)
    assert "Harry" in state.character_states
    assert any("wizard hat" in s for s in state.character_states["Harry"])
    assert any("golden cup" in s for s in state.character_states["Harry"])


def test_tracker_clear_session():
    """Verify clearing session resets state."""
    tracker = CumulativeStateTracker()
    tracker.record_shot_directive(
        session_id="test_clear",
        shot_index=0,
        action_text="Harry wearing wizard robe",
        known_characters=["Harry"],
    )
    assert len(tracker.get_cumulative_state("test_clear").character_states) > 0
    tracker.clear_session("test_clear")
    assert tracker.get_cumulative_state("test_clear").format_cumulative_state_block() == "None."
