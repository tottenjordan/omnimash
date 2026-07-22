import logging
import os
from typing import Annotated
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AfterValidator, BaseModel, field_validator

from omnimash.agent.orchestrator import OmniMashAgent
from omnimash.errors import is_external_service_error, sanitized_error_message
from omnimash.ingestion.media_extractor import (
    ParodyResearchResult,
    ReferenceAnalysisReport,
)
from omnimash.storage.gcs import GcsStorageManager

log = logging.getLogger("omnimash.api")


def _parse_range_header(range_header: str | None, size: int) -> tuple[int, int] | None | str:
    """Parse a single-range HTTP ``Range`` header against a known object size.

    Returns ``None`` when there is no (or an unparseable, hence ignorable)
    Range header — the caller then serves the full body with 200. Returns an
    inclusive ``(start, end)`` for a satisfiable range. Returns the sentinel
    ``"invalid"`` for a syntactically-valid but unsatisfiable range so the
    caller can answer 416. Only ``bytes=`` single ranges are supported; anything
    else falls back to a full 200 response.
    """
    if not range_header:
        return None
    range_header = range_header.strip()
    if not range_header.startswith("bytes=") or "," in range_header:
        return None
    spec = range_header[len("bytes=") :].strip()
    start_s, sep, end_s = spec.partition("-")
    if not sep:
        return None

    if not start_s:
        # Suffix range: last N bytes (bytes=-500).
        if not end_s.isdigit():
            return None
        suffix = int(end_s)
        if suffix == 0 or size == 0:
            return "invalid"
        start = max(0, size - suffix)
        return (start, size - 1)

    if not start_s.isdigit():
        return None
    start = int(start_s)
    if start >= size:
        return "invalid"
    if end_s:
        if not end_s.isdigit():
            return None
        end = int(end_s)
    else:
        end = size - 1
    end = min(end, size - 1)
    if end < start:
        return "invalid"
    return (start, end)


def _sanitize_identifier(value: str | None) -> str | None:
    """Normalize an identifier that flows into a GCS key (traversal-safe).

    Applied only to structured identifiers (session names, titles, slugs) —
    never to free-text creative fields (prompts, descriptions, dialogue), which
    stay untouched so content behavior remains permissive.
    """
    if value is None:
        return None
    return GcsStorageManager.sanitize_path_segment(value)


# Required identifier: sanitized, still mandatory.
SafeIdentifier = Annotated[str, AfterValidator(_sanitize_identifier)]
# Optional identifier: sanitized when present, None passes through.
OptSafeIdentifier = Annotated[str | None, AfterValidator(_sanitize_identifier)]


# Hosts the reference extractor is allowed to fetch. Keeps the SSRF surface to
# well-formed http(s) YouTube URLs; scheme/host abuse is rejected before any fetch.
ALLOWED_REFERENCE_HOSTS = frozenset(
    {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}
)


def validate_reference_url(value: str) -> str:
    """Reject non-http(s) schemes and non-allow-listed hosts (SSRF guard)."""
    parsed = urlparse(value.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must use http or https")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_REFERENCE_HOSTS:
        raise ValueError(f"URL host '{host}' is not an allow-listed reference source")
    return value.strip()


class CharacterRoleModel(BaseModel):
    role_id: str
    name: str = ""
    description: str = ""
    reference_url: str | None = None
    aesthetic_tags: list[str] = []
    voice_style: str = ""


class SaveCharacterRequest(BaseModel):
    session_name: OptSafeIdentifier = None
    character: CharacterRoleModel
    is_library: bool = True


class SaveCharacterResponse(BaseModel):
    success: bool = True
    gcs_uri: str = ""
    message: str = ""


class SessionListResponse(BaseModel):
    sessions: list[str]


class CharacterListResponse(BaseModel):
    characters: list[CharacterRoleModel] = []


class LoadCharacterRequest(BaseModel):
    slug: SafeIdentifier
    session_name: OptSafeIdentifier = None


class SaveRosterRequest(BaseModel):
    session_name: SafeIdentifier
    characters: list[CharacterRoleModel]


class DeconstructResponse(BaseModel):
    characters: list[CharacterRoleModel] = []
    aesthetic_tags: list[str] = []
    environment_tag: str = ""
    camera_lighting_tag: str = ""
    audio_beat: str = ""
    vocal_delivery: str = ""


class ConceptDeconstructRequest(BaseModel):
    concept: str


class ResearchRequest(BaseModel):
    subject: str
    aesthetic: str


class ExtractReferenceRequest(BaseModel):
    url: str
    session_name: OptSafeIdentifier = None

    @field_validator("url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return validate_reference_url(value)


class GenerateRequest(BaseModel):
    user_id: str = "usr_default"
    project_id: str = "prj_default"
    prompt: str = ""
    clip_index: int = 0
    parent_turn_id: str | None = None
    reference_url: str | None = None
    audio_stem: str | None = None
    voiceover: str | None = None
    is_silent: bool = False
    on_screen_text: str | None = None
    compiled_override: str | None = None
    session_name: OptSafeIdentifier = None
    concept: str | None = None
    characters: list[CharacterRoleModel | dict] | None = None
    scenes: list[dict] | None = None
    aesthetic_tags: list[str] | None = None
    environment_tag: str | None = None
    vocal_delivery: str = ""
    optimize_prompt: bool = False


class CommitRequest(BaseModel):
    user_id: str = "usr_default"
    project_id: str = "prj_default"
    turn_id: str
    next_prompt: str = ""
    session_name: OptSafeIdentifier = None


class SaveFinalRequest(BaseModel):
    session_name: OptSafeIdentifier = None
    video_url: str
    master_title: SafeIdentifier


class StitchClipsRequest(BaseModel):
    session_name: SafeIdentifier
    clip_urls: list[str]
    master_title: SafeIdentifier = "custom_stitched_cut"


class SaveFinalResponse(BaseModel):
    success: bool
    gcs_uri: str
    message: str


class ExtendSceneRequest(BaseModel):
    session_name: OptSafeIdentifier = None
    turn_id: str | None = None
    next_scene_action: str = ""
    dialogue: str | None = None
    active_roles: list[str] | None = None
    vocal_delivery: str = ""


class GenerateResponse(BaseModel):
    success: bool
    status: str
    video_url: str | None = None
    turn_id: str | None = None
    depth: int = 0
    error: str | None = None
    generation_mode: str = "LIVE_OMNI_FLASH"
    raw_compiled_prompt: str | None = None
    reference_analysis: dict | None = None


# The dashboard UI (React via CDN Babel) lives as a static asset next to this
# module so app.py stays focused on API wiring. Loaded once and cached.
_UI_HTML_PATH = os.path.join(os.path.dirname(__file__), "static", "index.html")
_ui_html_cache: str | None = None


def _load_ui_html() -> str:
    """Return the dashboard HTML, reading the packaged asset once and caching it."""
    global _ui_html_cache
    if _ui_html_cache is None:
        with open(_UI_HTML_PATH, encoding="utf-8") as fh:
            _ui_html_cache = fh.read()
    return _ui_html_cache


def create_app(mock_mode: bool | None = None) -> FastAPI:
    app = FastAPI(title="OmniMash API", version="0.1.0")
    is_mock = (
        mock_mode
        if mock_mode is not None
        else (os.environ.get("MOCK_MODE", "false").lower() in ("true", "1"))
    )
    agent = OmniMashAgent(mock_mode=is_mock)

    static_dir = os.path.join(os.getcwd(), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    from omnimash.engine.omni_client import ensure_rendered_video

    ensure_rendered_video(
        "/static/rendered/mock.mp4",
        prompt="Trapwarts trailer",
    )

    @app.exception_handler(Exception)
    def handle_external_service_error(request: Request, exc: Exception) -> Response:
        # Known storage/engine failures (GCS, ffmpeg) become a sanitized 502 so
        # callers get a clear "upstream failed" signal without leaking bucket
        # names, URIs, or stack traces. Anything else re-raises as a normal 500.
        if isinstance(exc, HTTPException):
            raise exc
        if is_external_service_error(exc):
            log.error("External service error on %s: %s", request.url.path, exc, exc_info=True)
            return JSONResponse(
                status_code=502,
                content={"detail": sanitized_error_message(exc)},
            )
        raise exc

    @app.get("/", response_class=HTMLResponse)
    def get_dashboard() -> HTMLResponse:
        return HTMLResponse(content=_load_ui_html())

    @app.post("/api/deconstruct-concept", response_model=DeconstructResponse)
    def deconstruct_concept(req: ConceptDeconstructRequest) -> DeconstructResponse:
        tags = agent.deconstruct_concept(req.concept)
        return DeconstructResponse(
            characters=[
                CharacterRoleModel(
                    role_id=c.role_id,
                    name=c.name,
                    description=c.description,
                    reference_url=c.reference_url,
                    aesthetic_tags=c.aesthetic_tags,
                    voice_style=c.voice_style,
                )
                for c in tags.characters
            ],
            aesthetic_tags=tags.aesthetic_tags,
            environment_tag=tags.environment_tag,
            camera_lighting_tag=tags.camera_lighting_tag,
            audio_beat=tags.audio_beat,
            vocal_delivery=tags.vocal_delivery,
        )

    @app.post("/api/generate", response_model=GenerateResponse)
    @app.post("/api/diff", response_model=GenerateResponse)
    def generate_video(req: GenerateRequest) -> GenerateResponse:
        agent_turn = agent.process_user_turn(
            user_id=req.user_id,
            project_id=req.project_id,
            prompt=req.prompt,
            clip_index=req.clip_index,
            parent_turn_id=req.parent_turn_id,
            reference_url=req.reference_url,
            audio_stem=req.audio_stem,
            voiceover=req.voiceover,
            is_silent=req.is_silent,
            on_screen_text=req.on_screen_text,
            compiled_override=req.compiled_override,
            session_name=req.session_name,
            concept=req.concept,
            characters=req.characters,
            scenes=req.scenes,
            aesthetic_tags=req.aesthetic_tags,
            environment_tag=req.environment_tag,
            vocal_delivery=req.vocal_delivery,
            optimize_prompt=req.optimize_prompt,
        )
        return GenerateResponse(
            success=agent_turn.success,
            status=agent_turn.status_event,
            video_url=agent_turn.video_url,
            turn_id=agent_turn.turn_id,
            depth=agent_turn.depth,
            error=agent_turn.error_message,
            generation_mode=agent_turn.generation_mode,
            raw_compiled_prompt=agent_turn.raw_compiled_prompt,
            reference_analysis=agent_turn.reference_analysis,
        )

    @app.post("/api/commit", response_model=GenerateResponse)
    def commit_and_branch(req: CommitRequest) -> GenerateResponse:
        agent_turn = agent.commit_and_branch(
            user_id=req.user_id,
            project_id=req.project_id,
            turn_id=req.turn_id,
            prompt=req.next_prompt,
            session_name=req.session_name,
        )
        return GenerateResponse(
            success=agent_turn.success,
            status=agent_turn.status_event,
            video_url=agent_turn.video_url,
            turn_id=agent_turn.turn_id,
            depth=agent_turn.depth,
            error=agent_turn.error_message,
            generation_mode=agent_turn.generation_mode,
            raw_compiled_prompt=agent_turn.raw_compiled_prompt,
            reference_analysis=agent_turn.reference_analysis,
        )

    @app.post("/api/save-final", response_model=SaveFinalResponse)
    def save_final(req: SaveFinalRequest) -> SaveFinalResponse:
        _pub_url, gcs_uri = agent.save_final_master(
            session_name=req.session_name,
            video_url=req.video_url,
            master_title=req.master_title,
        )
        if not gcs_uri:
            raise HTTPException(
                status_code=502,
                detail="Save produced no artifact; the master was not persisted.",
            )
        return SaveFinalResponse(
            success=True,
            gcs_uri=gcs_uri,
            message=f"Final master successfully saved to {gcs_uri}",
        )

    @app.post("/api/stitch-clips", response_model=SaveFinalResponse)
    def stitch_clips(req: StitchClipsRequest) -> SaveFinalResponse:
        if not req.clip_urls:
            raise HTTPException(
                status_code=400,
                detail="At least one clip URL is required for stitching.",
            )
        stitched_path = agent.stitcher.concatenate_clips(req.clip_urls, session_id=req.session_name)
        _pub_url, gcs_uri = agent.storage.save_final_master(
            session_id=req.session_name,
            source_rel_path=stitched_path,
            master_title=req.master_title,
        )
        if not gcs_uri:
            raise HTTPException(
                status_code=502,
                detail="Stitching produced no artifact; the master was not persisted.",
            )
        return SaveFinalResponse(
            success=True,
            gcs_uri=gcs_uri,
            message=f"Custom stitched master successfully saved to {gcs_uri}",
        )

    @app.post("/api/extend-scene", response_model=GenerateResponse)
    def extend_scene(req: ExtendSceneRequest) -> GenerateResponse:
        agent_turn = agent.extend_scene(
            session_name=req.session_name,
            turn_id=req.turn_id,
            next_scene_action=req.next_scene_action,
            dialogue=req.dialogue,
            active_roles=req.active_roles,
            vocal_delivery=req.vocal_delivery,
        )
        return GenerateResponse(
            success=agent_turn.success,
            status=agent_turn.status_event,
            video_url=agent_turn.video_url,
            turn_id=agent_turn.turn_id,
            depth=agent_turn.depth,
            error=agent_turn.error_message,
            generation_mode=agent_turn.generation_mode,
            raw_compiled_prompt=agent_turn.raw_compiled_prompt,
            reference_analysis=agent_turn.reference_analysis,
        )

    @app.post("/api/research", response_model=ParodyResearchResult)
    def research_parody(req: ResearchRequest) -> ParodyResearchResult:
        return agent.media_extractor.research_parody_clash(req.subject, req.aesthetic)

    @app.post("/api/extract-reference", response_model=ReferenceAnalysisReport)
    def extract_reference(req: ExtractReferenceRequest) -> ReferenceAnalysisReport:
        return agent.media_extractor.analyze_youtube_reference(
            req.url, session_id=req.session_name or "default"
        )

    @app.post("/api/characters/save", response_model=SaveCharacterResponse)
    def save_character(req: SaveCharacterRequest) -> SaveCharacterResponse:
        _pub_url, gcs_uri = agent.storage.save_character(
            req.character.model_dump(),
            session_id=req.session_name,
            is_library=req.is_library,
        )
        return SaveCharacterResponse(
            success=True,
            gcs_uri=gcs_uri,
            message=f"Character saved successfully to {gcs_uri}",
        )

    @app.get("/api/characters", response_model=CharacterListResponse)
    def list_characters(session_name: str | None = None) -> CharacterListResponse:
        raw_chars = agent.storage.list_characters(session_id=session_name)
        characters = [
            CharacterRoleModel(
                role_id=c.get("role_id", "Role A"),
                name=c.get("name", ""),
                description=c.get("description", ""),
                reference_url=c.get("reference_url"),
                aesthetic_tags=c.get("aesthetic_tags", []),
                voice_style=c.get("voice_style", ""),
            )
            for c in (raw_chars or [])
        ]
        return CharacterListResponse(characters=characters)

    @app.get("/api/sessions", response_model=SessionListResponse)
    def list_sessions() -> SessionListResponse:
        return SessionListResponse(sessions=agent.storage.list_session_ids())

    @app.post("/api/characters/load", response_model=CharacterRoleModel)
    def load_character(req: LoadCharacterRequest) -> CharacterRoleModel:
        char_data = agent.storage.load_character(req.slug, session_id=req.session_name)
        if not char_data:
            raise HTTPException(
                status_code=404,
                detail=f"Character '{req.slug}' not found",
            )
        return CharacterRoleModel(
            role_id=char_data.get("role_id", "Role A"),
            name=char_data.get("name", ""),
            description=char_data.get("description", ""),
            reference_url=char_data.get("reference_url"),
            aesthetic_tags=char_data.get("aesthetic_tags", []),
            voice_style=char_data.get("voice_style", ""),
        )

    @app.post("/api/characters/save-roster", response_model=SaveCharacterResponse)
    def save_roster(req: SaveRosterRequest) -> SaveCharacterResponse:
        _pub_url, gcs_uri = agent.storage.save_session_roster(
            req.session_name,
            [c.model_dump() for c in req.characters],
        )
        return SaveCharacterResponse(
            success=True,
            gcs_uri=gcs_uri,
            message=f"Session roster saved successfully to {gcs_uri}",
        )

    @app.get("/api/characters/roster", response_model=CharacterListResponse)
    def get_session_roster(session_name: str) -> CharacterListResponse:
        raw_roster = agent.storage.load_session_roster(session_name)
        characters = [
            CharacterRoleModel(
                role_id=c.get("role_id", "Role A"),
                name=c.get("name", ""),
                description=c.get("description", ""),
                reference_url=c.get("reference_url"),
                aesthetic_tags=c.get("aesthetic_tags", []),
                voice_style=c.get("voice_style", ""),
            )
            for c in (raw_roster or [])
        ]
        return CharacterListResponse(characters=characters)

    @app.get("/api/media-proxy")
    def media_proxy(uri: str, request: Request) -> Response:
        if not uri or not uri.startswith("gs://"):
            raise HTTPException(
                status_code=400,
                detail="Invalid GCS URI. Must start with gs://",
            )

        # Metadata first: size drives Range math and lets us stream the body
        # instead of buffering the whole object in memory. A None result covers
        # both "not found" and "cross-bucket read blocked" (Task 1.2).
        meta = agent.storage.get_media_metadata(uri)
        if meta is None:
            raise HTTPException(status_code=404, detail="Media object not found or empty")
        size, content_type = meta

        base_headers = {
            "Cache-Control": "public, max-age=86400",
            "Accept-Ranges": "bytes",
        }

        range_spec = _parse_range_header(request.headers.get("range"), size)
        if range_spec == "invalid":
            # Unsatisfiable range -> 416 with the full size so clients can retry.
            raise HTTPException(
                status_code=416,
                detail="Requested range not satisfiable",
                headers={"Content-Range": f"bytes */{size}"},
            )

        if range_spec is None:
            body = agent.storage.iter_blob_range(uri, start=0, end=size - 1 if size else None)
            headers = {**base_headers, "Content-Length": str(size)}
            return StreamingResponse(body, media_type=content_type, headers=headers)

        start, end = range_spec
        body = agent.storage.iter_blob_range(uri, start=start, end=end)
        headers = {
            **base_headers,
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Content-Length": str(end - start + 1),
        }
        return StreamingResponse(
            body,
            status_code=206,
            media_type=content_type,
            headers=headers,
        )

    return app


app = create_app()
