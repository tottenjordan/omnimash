"""Shared FastAPI dependencies and asset helpers for the API routers."""

import os

from fastapi import Request

from omnimash.agent.orchestrator import OmniMashAgent

# The dashboard UI (React via CDN Babel) lives as a static asset next to this
# module so the API modules stay focused on wiring. Loaded once and cached.
_UI_HTML_PATH = os.path.join(os.path.dirname(__file__), "static", "index.html")
_ui_html_cache: str | None = None


def load_ui_html() -> str:
    """Return the dashboard HTML, reading the packaged asset once and caching it."""
    global _ui_html_cache
    if _ui_html_cache is None:
        with open(_UI_HTML_PATH, encoding="utf-8") as fh:
            _ui_html_cache = fh.read()
    return _ui_html_cache


# Backward-compatible private alias (tests / older imports reference this name).
_load_ui_html = load_ui_html


def get_agent(request: Request) -> OmniMashAgent:
    """Return the process-wide agent stored on ``app.state`` by ``create_app``."""
    return request.app.state.agent
