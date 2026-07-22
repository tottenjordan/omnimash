import re
import uuid

from pydantic import BaseModel, Field


class TurnNode(BaseModel):
    turn_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_turn_id: str | None = None
    clip_index: int
    prompt: str
    interaction_thread_id: str
    video_url: str
    edit_depth_in_thread: int = 0
    is_committed: bool = False
    base_video_anchor_url: str | None = None


class ClipSegment(BaseModel):
    clip_index: int
    active_turn_id: str
    interaction_thread_id: str


class ProjectSession(BaseModel):
    session_id: str
    user_id: str
    project_id: str
    turns: dict[str, TurnNode] = Field(default_factory=dict)
    timeline: list[ClipSegment] = Field(default_factory=list)


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, ProjectSession] = {}

    def get_or_create_session(
        self, user_id: str, project_id: str, session_name: str | None = None
    ) -> ProjectSession:
        if session_name and session_name.strip():
            session_key = re.sub(r"[^a-zA-Z0-9_-]", "_", session_name.strip())
        else:
            session_key = f"{user_id}:{project_id}"
        if session_key not in self._sessions:
            self._sessions[session_key] = ProjectSession(
                session_id=session_key, user_id=user_id, project_id=project_id
            )
        return self._sessions[session_key]

    def add_turn(
        self,
        session_id: str,
        clip_index: int,
        prompt: str,
        interaction_thread_id: str,
        video_url: str,
        parent_turn_id: str | None = None,
        is_checkpoint: bool = False,
        base_video_anchor_url: str | None = None,
    ) -> TurnNode:
        session = self._sessions[session_id]

        depth = 0
        if parent_turn_id and parent_turn_id in session.turns:
            parent = session.turns[parent_turn_id]
            if parent.interaction_thread_id == interaction_thread_id and not is_checkpoint:
                depth = parent.edit_depth_in_thread + 1

        turn = TurnNode(
            parent_turn_id=parent_turn_id,
            clip_index=clip_index,
            prompt=prompt,
            interaction_thread_id=interaction_thread_id,
            video_url=video_url,
            edit_depth_in_thread=depth,
            is_committed=is_checkpoint,
            base_video_anchor_url=base_video_anchor_url,
        )
        session.turns[turn.turn_id] = turn

        found = False
        for segment in session.timeline:
            if segment.clip_index == clip_index:
                segment.active_turn_id = turn.turn_id
                segment.interaction_thread_id = interaction_thread_id
                found = True
                break
        if not found:
            session.timeline.append(
                ClipSegment(
                    clip_index=clip_index,
                    active_turn_id=turn.turn_id,
                    interaction_thread_id=interaction_thread_id,
                )
            )
        return turn

    def commit_turn(self, session_id: str, turn_id: str) -> TurnNode:
        session = self._sessions[session_id]
        if turn_id not in session.turns:
            raise KeyError(f"Turn {turn_id} not found in session {session_id}")
        node = session.turns[turn_id]
        node.is_committed = True
        return node
