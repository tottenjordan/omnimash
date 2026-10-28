from contextlib import asynccontextmanager
import os
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from omnimash.agent.orchestrator import OmniMashAgent
from omnimash.api.models import (
    GenerateRequest,
    GenerateShotRequest,
    StitchMasterRequest,
)
from omnimash.api.routers import (
    characters as characters_router,
    evaluation as evaluation_router,
    feedback as feedback_router,
    generation as generation_router,
    intent as intent_router,
    media as media_router,
    projects as projects_router,
    scenes_vault as scenes_vault_router,
    share as share_router,
    soundstage as soundstage_router,
    storyboard as storyboard_router,
)

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
_TEMPLATE_PATH = os.path.join(_TEMPLATES_DIR, "index.html")
_SOUNDSTAGE_SPLICE_MARKER = "/* __SOUNDSTAGE_STUDIO_COMPONENTS__ */"
_SOUNDSTAGE_JSX_PARTIALS: tuple[str, ...] = (
    os.path.join(_TEMPLATES_DIR, "soundstage_intake.jsx"),
    os.path.join(_TEMPLATES_DIR, "soundstage_production.jsx"),
)
_CACHED_UI_HTML: str | None = None


def get_ui_html() -> str:
    """Loads, splices modular Soundstage JSX partials, and caches the frontend SPA template."""
    global _CACHED_UI_HTML
    if _CACHED_UI_HTML is None:
        with open(_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            base_html = f.read()
        if _SOUNDSTAGE_SPLICE_MARKER in base_html:
            partial_blocks: list[str] = []
            for partial_path in _SOUNDSTAGE_JSX_PARTIALS:
                with open(partial_path, "r", encoding="utf-8") as partial_file:
                    partial_blocks.append(partial_file.read())
            base_html = base_html.replace(
                _SOUNDSTAGE_SPLICE_MARKER,
                "\n\n".join(partial_blocks),
                1,
            )
        _CACHED_UI_HTML = base_html
    return _CACHED_UI_HTML


UI_HTML = get_ui_html()

__all__ = [
    "UI_HTML",
    "GenerateRequest",
    "GenerateShotRequest",
    "StitchMasterRequest",
    "create_app",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    from omnimash.engine.omni_client import ensure_rendered_video

    ensure_rendered_video(
        "/static/rendered/mock.mp4",
        prompt="Trapwarts trailer",
    )
    yield


def create_app(mock_mode: bool | None = None) -> FastAPI:
    app = FastAPI(title="OmniMash API", version="0.1.0", lifespan=lifespan)
    is_mock = (
        mock_mode
        if mock_mode is not None
        else (os.environ.get("MOCK_MODE", "false").lower() in ("true", "1"))
    )
    agent = OmniMashAgent(mock_mode=is_mock)
    agent.session_manager.storage = agent.storage
    app.state.agent = agent
    app.middleware("http")(share_router.share_mode_lockdown_middleware)

    static_dir = os.path.join(os.getcwd(), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    def get_dashboard() -> HTMLResponse:
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        return HTMLResponse(content=get_ui_html(), headers=headers)

    app.include_router(media_router.router)
    app.include_router(storyboard_router.router)
    app.include_router(projects_router.router)
    app.include_router(characters_router.router)
    app.include_router(scenes_vault_router.router)
    app.include_router(generation_router.router)
    app.include_router(feedback_router.router)
    app.include_router(evaluation_router.router)
    app.include_router(share_router.router)
    app.include_router(intent_router.router)
    app.include_router(soundstage_router.router)

    return app


_default_app: FastAPI | None = None


def __getattr__(name: str) -> Any:
    global _default_app
    if name == "app":
        if _default_app is None:
            _default_app = create_app()
        return _default_app
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
