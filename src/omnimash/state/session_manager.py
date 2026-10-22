import logging
import re
import threading
from typing import Any, Protocol, runtime_checkable
import uuid

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

from omnimash.config import settings

logger = logging.getLogger("omnimash.state")

MAX_TURNS_PER_SESSION = 500


def sanitize_session_id(name: str) -> str:
    """Sanitizes session identifiers to be safe for GCS blob paths and file systems."""
    if not name or not name.strip():
        return "default"
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip())


@runtime_checkable
class SessionStorageProtocol(Protocol):
    """Protocol defining the storage interface required by SessionManager."""

    def save_session_manifest(
        self, session_id: str, manifest_data: dict[str, Any], project_id: str | None = None
    ) -> str: ...

    def get_session_manifest(
        self, session_id: str, project_id: str | None = None
    ) -> dict[str, Any] | None: ...


def _normalize_image_model(value: Any) -> str:
    default_model = getattr(settings, "image_model_id", "gemini-nano-banana-2.1")
    if not isinstance(value, str):
        return default_model
    cleaned = value.strip()
    if not cleaned or cleaned.startswith("gemini-3.1-flash-image"):
        return default_model
    return cleaned


class TurnNode(BaseModel):
    turn_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    turn_index: int | None = None
    parent_turn_id: str | None = None
    clip_index: int
    prompt: str
    interaction_thread_id: str
    video_url: str
    gcs_uri: str | None = None
    edit_depth_in_thread: int = 0
    is_committed: bool = False
    base_video_anchor_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    preflight_violations: list[dict[str, Any]] = Field(default_factory=list)


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
    image_model: str = Field(
        default_factory=lambda: getattr(settings, "image_model_id", "gemini-nano-banana-2.1")
    )
    enable_safety_sanitization: bool = True
    characters: list[dict[str, Any]] = Field(default_factory=list)
    products: list[dict[str, Any]] = Field(default_factory=list)
    shot_cards: list[dict[str, Any]] = Field(default_factory=list)
    cumulative_state: dict[str, Any] = Field(default_factory=dict)

    _last_allocated_turn_index: int = PrivateAttr(default=-1)

    @field_validator("image_model", mode="before")
    @classmethod
    def _validate_image_model(cls, v: Any) -> str:
        return _normalize_image_model(v)


class SessionManager:
    def __init__(self, storage: Any | None = None):
        self._sessions: dict[str, ProjectSession] = {}
        self.storage = storage
        self._lock = threading.RLock()

    def _persist_session(self, session: ProjectSession) -> None:
        """Persists the session manifest to storage without holding the in-memory mutex lock."""
        if self.storage is None or not hasattr(self.storage, "save_session_manifest"):
            return

        try:
            manifest_data = session.model_dump(mode="json")
            self.storage.save_session_manifest(
                session_id=session.session_id,
                manifest_data=manifest_data,
                project_id=session.project_id,
            )
        except Exception as exc:
            logger.warning(
                "Failed to persist session manifest for session '%s': %s",
                session.session_id,
                exc,
                exc_info=True,
            )

    def get_or_create_session(
        self, user_id: str, project_id: str, session_name: str | None = None
    ) -> ProjectSession:
        with self._lock:
            if session_name and session_name.strip():
                session_key = sanitize_session_id(session_name)
            else:
                clean_user = sanitize_session_id(user_id or "usr_default")
                clean_project = sanitize_session_id(project_id or "prj_default")
                session_key = f"{clean_user}_{clean_project}"

            if session_key not in self._sessions:
                # Check legacy colon key if present in cache
                legacy_key = f"{user_id}:{project_id}"
                if legacy_key in self._sessions:
                    return self._sessions[legacy_key]

                if self.storage is not None and hasattr(self.storage, "get_session_manifest"):
                    try:
                        manifest = self.storage.get_session_manifest(
                            session_key, project_id=project_id
                        )
                        if not manifest and legacy_key != session_key:
                            manifest = self.storage.get_session_manifest(
                                legacy_key, project_id=project_id
                            )
                        if isinstance(manifest, dict):
                            hydrated = {
                                **manifest,
                                "session_id": manifest.get("session_id") or session_key,
                                "user_id": manifest.get("user_id") or user_id,
                                "project_id": manifest.get("project_id") or project_id,
                            }
                            self._sessions[session_key] = ProjectSession.model_validate(hydrated)
                            return self._sessions[session_key]
                    except Exception as exc:
                        logger.warning(
                            "Failed to hydrate session '%s' from storage manifest: %s",
                            session_key,
                            exc,
                            exc_info=True,
                        )
                self._sessions[session_key] = ProjectSession(
                    session_id=session_key, user_id=user_id, project_id=project_id
                )
            return self._sessions[session_key]

    def get_session(self, session_id: str, project_id: str | None = None) -> ProjectSession | None:
        """Retrieves a session from in-memory cache or hydrates from GCS storage manifest."""
        with self._lock:
            if not session_id:
                return None
            if session_id in self._sessions:
                return self._sessions[session_id]
            sanitized = sanitize_session_id(session_id)
            if sanitized in self._sessions:
                return self._sessions[sanitized]
            for session in self._sessions.values():
                if session.session_id in (session_id, sanitized):
                    return session
            if self.storage is not None and hasattr(self.storage, "get_session_manifest"):
                try:
                    manifest = self.storage.get_session_manifest(sanitized, project_id=project_id)
                    if not manifest and session_id != sanitized:
                        manifest = self.storage.get_session_manifest(
                            session_id, project_id=project_id
                        )
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
                except Exception as exc:
                    logger.warning(
                        "Failed to hydrate session '%s' from storage manifest: %s",
                        session_id,
                        exc,
                        exc_info=True,
                    )
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
        turn_index: int | None = None,
        metadata: dict[str, Any] | None = None,
        preflight_violations: list[Any] | None = None,
    ) -> TurnNode:
        session: ProjectSession | None = None
        turn: TurnNode | None = None

        with self._lock:
            session = self.get_session(session_id)
            if session is None:
                raise KeyError(
                    f"Session '{session_id}' not found in memory cache or persistent storage."
                )

            if len(session.turns) >= MAX_TURNS_PER_SESSION:
                raise ValueError(
                    f"Session '{session_id}' reached maximum turn limit ({MAX_TURNS_PER_SESSION})."
                )

            valid_parent = (
                parent_turn_id if (parent_turn_id and parent_turn_id in session.turns) else None
            )
            if parent_turn_id and not valid_parent:
                logger.warning(
                    "Parent turn '%s' not found in session '%s'; attaching turn as root node.",
                    parent_turn_id,
                    session_id,
                )

            depth = 0
            if valid_parent:
                parent = session.turns[valid_parent]
                if parent.interaction_thread_id == interaction_thread_id and not is_checkpoint:
                    depth = parent.edit_depth_in_thread + 1

            if turn_index is not None:
                effective_turn_idx = turn_index
            else:
                m = re.search(r"turn_(\d+)_video\.mp4", video_url or "")
                if m:
                    effective_turn_idx = int(m.group(1))
                else:
                    effective_turn_idx = self.allocate_turn_index(session)

            session._last_allocated_turn_index = max(
                session._last_allocated_turn_index, effective_turn_idx
            )

            clean_violations: list[dict[str, Any]] = []
            for v in preflight_violations or []:
                if hasattr(v, "model_dump"):
                    clean_violations.append(v.model_dump())
                elif isinstance(v, dict):
                    clean_violations.append(v)
                elif hasattr(v, "__dataclass_fields__"):
                    from dataclasses import asdict

                    clean_violations.append(asdict(v))
                else:
                    clean_violations.append({"violation": str(v)})

            turn_metadata = dict(metadata or {})
            if clean_violations and "preflight_violations" not in turn_metadata:
                turn_metadata["preflight_violations"] = clean_violations

            turn = TurnNode(
                parent_turn_id=valid_parent,
                turn_index=effective_turn_idx,
                clip_index=clip_index,
                prompt=prompt,
                interaction_thread_id=interaction_thread_id,
                video_url=video_url,
                edit_depth_in_thread=depth,
                is_committed=is_checkpoint,
                base_video_anchor_url=base_video_anchor_url,
                metadata=turn_metadata,
                preflight_violations=clean_violations,
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

        # Non-blocking persistence outside critical section
        if session and turn:
            self._persist_session(session)
            return turn
        raise RuntimeError("Failed to create turn node")

    def allocate_turn_index(self, session_or_id: ProjectSession | str) -> int:
        """Calculates the next available turn index monotonically from existing turns."""
        with self._lock:
            session = (
                session_or_id
                if isinstance(session_or_id, ProjectSession)
                else self.get_session(session_or_id)
            )
            if not session:
                return 0
            max_idx = session._last_allocated_turn_index
            for t in session.turns.values():
                if t.turn_index is not None:
                    max_idx = max(max_idx, t.turn_index)
                else:
                    m = re.search(r"turn_(\d+)_video\.mp4", t.video_url or "")
                    if m:
                        max_idx = max(max_idx, int(m.group(1)))
                    else:
                        max_idx = max(max_idx, getattr(t, "clip_index", 0))
            next_idx = max(len(session.turns), max_idx + 1)
            session._last_allocated_turn_index = next_idx
            return next_idx

    def update_turn_video(
        self,
        session_id: str,
        turn_id: str,
        video_url: str,
        gcs_uri: str | None = None,
    ) -> None:
        """Updates the video URL and GCS URI for an existing turn and persists the updated session."""
        session: ProjectSession | None = None
        with self._lock:
            session = self.get_session(session_id)
            if session and turn_id in session.turns:
                node = session.turns[turn_id]
                node.video_url = video_url
                if gcs_uri is not None:
                    node.gcs_uri = gcs_uri

        if session:
            self._persist_session(session)

    def commit_turn(self, session_id: str, turn_id: str) -> TurnNode:
        session: ProjectSession | None = None
        node: TurnNode | None = None
        with self._lock:
            session = self.get_session(session_id)
            if session is None:
                raise KeyError(
                    f"Session '{session_id}' not found in memory cache or persistent storage."
                )
            if turn_id not in session.turns:
                raise KeyError(f"Turn '{turn_id}' not found in session '{session_id}'.")
            node = session.turns[turn_id]
            node.is_committed = True

        if session and node:
            self._persist_session(session)
            return node
        raise RuntimeError("Failed to commit turn node")

    def get_cumulative_state(
        self, session_id: str, project_id: str | None = None
    ) -> dict[str, Any]:
        """Returns the cumulative shot and character state for the given session."""
        session = self.get_session(session_id, project_id=project_id)
        if session:
            return dict(session.cumulative_state)
        return {}

    def update_cumulative_state(
        self,
        session_id: str,
        cumulative_state: dict[str, Any],
        project_id: str | None = None,
    ) -> None:
        """Updates and persists the cumulative shot and character state for the given session."""
        session: ProjectSession | None = None
        with self._lock:
            session = self.get_session(session_id, project_id=project_id)
            if session:
                session.cumulative_state = dict(cumulative_state)

        if session:
            self._persist_session(session)
