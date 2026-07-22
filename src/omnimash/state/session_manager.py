import re
import threading
import uuid
from collections import OrderedDict

from pydantic import BaseModel, Field

from omnimash.config import settings


class SessionNotFound(KeyError):
    """Raised when a session (or turn) id cannot be resolved to live state.

    Subclasses :class:`KeyError` so existing ``except KeyError`` call sites keep
    working, while giving callers a domain-specific type to catch.
    """


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
    """In-memory session store.

    Thread-safe (a single :class:`threading.Lock` guards all mutations) and
    bounded via LRU eviction so long-running processes don't grow without limit.

    Single-process only: state lives in this process's memory and is not shared
    across workers/replicas. Running multiple workers means a turn can land on a
    process that has never seen the session. See
    ``docs/notes/session-store-limitations.md``.
    """

    def __init__(self, max_sessions: int | None = None):
        self._sessions: OrderedDict[str, ProjectSession] = OrderedDict()
        self._lock = threading.Lock()
        self._max_sessions = max_sessions if max_sessions is not None else settings.max_sessions

    @staticmethod
    def _sanitize_key(session_id: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "_", session_id.strip())

    def _evict_if_needed(self) -> None:
        """Drop least-recently-used sessions past the cap. Caller holds the lock."""
        while self._max_sessions > 0 and len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)

    def _require(self, session_id: str) -> ProjectSession:
        """Fetch a session by exact key and mark it recently used. Lock held."""
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFound(f"Session {session_id!r} not found")
        self._sessions.move_to_end(session_id)
        return session

    def get_or_create_session(
        self, user_id: str, project_id: str, session_name: str | None = None
    ) -> ProjectSession:
        if session_name and session_name.strip():
            session_key = self._sanitize_key(session_name)
        else:
            session_key = f"{user_id}:{project_id}"
        with self._lock:
            existing = self._sessions.get(session_key)
            if existing is not None:
                self._sessions.move_to_end(session_key)
                return existing
            session = ProjectSession(session_id=session_key, user_id=user_id, project_id=project_id)
            self._sessions[session_key] = session
            self._evict_if_needed()
            return session

    def find_session(self, session_id: str | None) -> ProjectSession | None:
        """Resolve a session by raw key, sanitized key, or stored ``session_id``.

        Encapsulates the sanitize/fallback lookup so callers never reach into
        private state. Returns ``None`` when nothing matches.
        """
        if not session_id:
            return None
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                self._sessions.move_to_end(session_id)
                return session

            sanitized = self._sanitize_key(session_id)
            session = self._sessions.get(sanitized)
            if session is not None:
                self._sessions.move_to_end(sanitized)
                return session

            found_key = None
            for key, sess in self._sessions.items():
                if sess.session_id in (session_id, sanitized):
                    found_key = key
                    break
            if found_key is not None:
                self._sessions.move_to_end(found_key)
                return self._sessions[found_key]
            return None

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
        with self._lock:
            session = self._require(session_id)

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
        with self._lock:
            session = self._require(session_id)
            if turn_id not in session.turns:
                raise SessionNotFound(f"Turn {turn_id!r} not found in session {session_id!r}")
            node = session.turns[turn_id]
            node.is_committed = True
            return node
