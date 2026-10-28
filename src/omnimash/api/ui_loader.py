"""Frontend SPA HTML template and modular Soundstage JSX partial-splice loader."""

from __future__ import annotations

import os

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
_TEMPLATE_PATH = os.path.join(_TEMPLATES_DIR, "index.html")
_SOUNDSTAGE_SPLICE_MARKER = "/* __SOUNDSTAGE_STUDIO_COMPONENTS__ */"
_SOUNDSTAGE_JSX_PARTIALS: tuple[str, ...] = (
    os.path.join(_TEMPLATES_DIR, "soundstage_shared.jsx"),
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

__all__ = ["UI_HTML", "get_ui_html"]
