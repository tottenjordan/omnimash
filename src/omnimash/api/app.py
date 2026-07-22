"""FastAPI application factory.

Wiring only: the agent is constructed in :func:`create_app` and stored on
``app.state.agent`` (so ``TestClient(app)`` without a context manager still gets
a working agent), while the ffmpeg warm-up is deferred to a ``lifespan`` handler
so importing this module triggers no ffmpeg/network side effects. Endpoints live
in domain routers under :mod:`omnimash.api.routers`; request/response models live
in :mod:`omnimash.api.schemas`.
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from omnimash.agent.orchestrator import OmniMashAgent
from omnimash.api.deps import _load_ui_html, load_ui_html
from omnimash.api.routers import characters, generation, media, sessions
from omnimash.api.routers.media import _parse_range_header
from omnimash.api.schemas import (
    ALLOWED_REFERENCE_HOSTS,
    CharacterListResponse,
    CharacterRoleModel,
    CommitRequest,
    ConceptDeconstructRequest,
    DeconstructResponse,
    ExtendSceneRequest,
    ExtractReferenceRequest,
    GenerateRequest,
    GenerateResponse,
    LoadCharacterRequest,
    OptSafeIdentifier,
    ResearchRequest,
    SafeIdentifier,
    SaveCharacterRequest,
    SaveCharacterResponse,
    SaveFinalRequest,
    SaveFinalResponse,
    SaveRosterRequest,
    SessionListResponse,
    StitchClipsRequest,
    _sanitize_identifier,
    validate_reference_url,
)
from omnimash.errors import is_external_service_error, sanitized_error_message

log = logging.getLogger("omnimash.api")

# Backward-compatible re-exports: existing tests and callers import these names
# straight from ``omnimash.api.app``. Kept after the router split so the public
# import surface is unchanged.
__all__ = [
    "ALLOWED_REFERENCE_HOSTS",
    "CharacterListResponse",
    "CharacterRoleModel",
    "CommitRequest",
    "ConceptDeconstructRequest",
    "DeconstructResponse",
    "ExtendSceneRequest",
    "ExtractReferenceRequest",
    "GenerateRequest",
    "GenerateResponse",
    "LoadCharacterRequest",
    "OptSafeIdentifier",
    "ResearchRequest",
    "SafeIdentifier",
    "SaveCharacterRequest",
    "SaveCharacterResponse",
    "SaveFinalRequest",
    "SaveFinalResponse",
    "SaveRosterRequest",
    "SessionListResponse",
    "StitchClipsRequest",
    "_load_ui_html",
    "_parse_range_header",
    "_sanitize_identifier",
    "app",
    "create_app",
    "load_ui_html",
    "validate_reference_url",
]


def create_app(mock_mode: bool | None = None) -> FastAPI:
    is_mock = (
        mock_mode
        if mock_mode is not None
        else (os.environ.get("MOCK_MODE", "false").lower() in ("true", "1"))
    )
    agent = OmniMashAgent(mock_mode=is_mock)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Warm the ffmpeg render path on startup only. Deferred out of import and
        # out of create_app so module import / non-context TestClient construction
        # never shell out to ffmpeg.
        from omnimash.engine.omni_client import ensure_rendered_video

        ensure_rendered_video("/static/rendered/mock.mp4", prompt="Trapwarts trailer")
        yield

    app = FastAPI(title="OmniMash API", version="0.1.0", lifespan=lifespan)
    app.state.agent = agent

    static_dir = os.path.join(os.getcwd(), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

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

    app.include_router(sessions.router)
    app.include_router(generation.router)
    app.include_router(characters.router)
    app.include_router(media.router)

    return app


app = create_app()
