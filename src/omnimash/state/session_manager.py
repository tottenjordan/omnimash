import re
from typing import Any
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_image_model(value: Any) -> str:
    if not isinstance(value, str):
        return "gemini-nano-banana-2.1"
    cleaned = value.strip()
    if not cleaned or cleaned.startswith("gemini-3.1-flash-image"):
        return "gemini-nano-banana-2.1"
    return cleaned


class TurnNode(BaseModel):
    turn_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_turn_id: str | None = None
    clip_index: int
    prompt: str
    interaction_thread_id: str
    video_url: str
    gcs_uri: str | None = None
    edit_depth_in_thread: int = 0
    is_committed: bool = False
    base_video_anchor_url: str | None = None


class ClipSegment(BaseModel):
    clip_index: int
    active_turn_id: str
    interaction_thread_id: str


class ProjectSession(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str
    user_id: str = "usr_default"
    project_id: str
    turns: dict[str, TurnNode] = Field(default_factory=dict)
    timeline: list[ClipSegment] = Field(default_factory=list)
    master_description: str = ""
    style_preset: str = ""
    aspect_ratio: str = "16:9"
    image_model: str = "gemini-nano-banana-2.1"
    enable_safety_sanitization: bool = True
    characters: list[dict[str, Any]] = Field(default_factory=list)
    products: list[dict[str, Any]] = Field(default_factory=list)
    shot_cards: list[dict[str, Any]] = Field(default_factory=list)
    cumulative_state: dict[str, Any] = Field(default_factory=dict)

    @field_validator("image_model", mode="before")
    @classmethod
    def _validate_image_model(cls, v: Any) -> str:
        return _normalize_image_model(v)


class SessionManager:
    def __init__(self, storage: Any | None = None):
        self._sessions: dict[str, ProjectSession] = {}
        self.storage = storage

    def _persist_session(self, session: ProjectSession) -> None:
        if self.storage is not None and hasattr(self.storage, "save_session_manifest"):
            try:
                manifest_data = session.model_dump()
                if hasattr(self.storage, "get_session_manifest"):
                    existing = self.storage.get_session_manifest(
                        session.session_id, project_id=session.project_id
                    )
                    if isinstance(existing, dict):
                        for key in (
                            "master_description",
                            "style_preset",
                            "aspect_ratio",
                            "image_model",
                            "enable_safety_sanitization",
                            "characters",
                            "products",
                            "shot_cards",
                            "cumulative_state",
                        ):
                            if not manifest_data.get(key) and existing.get(key):
                                val = (
                                    _normalize_image_model(existing[key])
                                    if key == "image_model"
                                    else existing[key]
                                )
                                manifest_data[key] = val
                                setattr(session, key, val)
                self.storage.save_session_manifest(
                    session_id=session.session_id,
                    manifest_data=manifest_data,
                    project_id=session.project_id,
                )
            except Exception:
                pass

    def get_or_create_session(
        self, user_id: str, project_id: str, session_name: str | None = None
    ) -> ProjectSession:
        if session_name and session_name.strip():
            session_key = re.sub(r"[^a-zA-Z0-9_-]", "_", session_name.strip())
        else:
            session_key = f"{user_id}:{project_id}"
        if session_key not in self._sessions:
            if self.storage is not None and hasattr(self.storage, "get_session_manifest"):
                try:
                    manifest = self.storage.get_session_manifest(session_key, project_id=project_id)
                    if isinstance(manifest, dict):
                        hydrated = {
                            **manifest,
                            "session_id": manifest.get("session_id") or session_key,
                            "user_id": manifest.get("user_id") or user_id,
                            "project_id": manifest.get("project_id") or project_id,
                        }
                        self._sessions[session_key] = ProjectSession.model_validate(hydrated)
                        return self._sessions[session_key]
                except Exception:
                    pass
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
        self._persist_session(session)
        return turn

    def get_session(self, session_id: str, project_id: str | None = None) -> ProjectSession | None:
        """Retrieves a session from in-memory cache or hydrates from GCS storage manifest."""
        if not session_id:
            return None
        if session_id in self._sessions:
            return self._sessions[session_id]
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id.strip())
        if sanitized in self._sessions:
            return self._sessions[sanitized]
        for session in self._sessions.values():
            if session.session_id in (session_id, sanitized):
                return session
        if self.storage is not None and hasattr(self.storage, "get_session_manifest"):
            try:
                manifest = self.storage.get_session_manifest(sanitized, project_id=project_id)
                if isinstance(manifest, dict) and manifest:
                    hydrated = {
                        **manifest,
                        "session_id": manifest.get("session_id") or sanitized,
                        "user_id": manifest.get("user_id") or "usr_default",
                        "project_id": manifest.get("project_id") or project_id or sanitized,
                    }
                    sess = ProjectSession.model_validate(hydrated)
                    self._sessions[sanitized] = sess
                    return sess
            except Exception:
                pass
        return None

    def allocate_turn_index(self, session_or_id: ProjectSession | str) -> int:
        """Calculates the next available turn index from existing turns in the session."""
        session = (
            session_or_id
            if isinstance(session_or_id, ProjectSession)
            else self.get_session(session_or_id)
        )
        if not session:
            return 0
        max_idx = -1
        for t in session.turns.values():
            m = re.search(r"turn_(\d+)_video\.mp4", t.video_url or "")
            if m:
                max_idx = max(max_idx, int(m.group(1)))
            else:
                max_idx = max(max_idx, getattr(t, "clip_index", 0))
        return max(len(session.turns), max_idx + 1)

    def update_turn_video(
        self,
        session_id: str,
        turn_id: str,
        video_url: str,
        gcs_uri: str | None = None,
    ) -> None:
        """Updates the video URL and GCS URI for an existing turn and persists the updated session."""
        session = self.get_session(session_id)
        if session and turn_id in session.turns:
            node = session.turns[turn_id]
            node.video_url = video_url
            if gcs_uri is not None:
                node.gcs_uri = gcs_uri
            self._persist_session(session)

    def commit_turn(self, session_id: str, turn_id: str) -> TurnNode:
        session = self._sessions[session_id]
        if turn_id not in session.turns:
            raise KeyError(f"Turn {turn_id} not found in session {session_id}")
        node = session.turns[turn_id]
        node.is_committed = True
        self._persist_session(session)
        return node
