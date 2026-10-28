"""UI integration, modular JSX splice, hygiene, and browser interaction tests for Mode 5: Commercial Soundstage."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient
import pytest

from omnimash.api import app as app_module
from omnimash.api.app import create_app, get_ui_html

_TEMPLATES_DIR = Path(app_module.__file__).resolve().parent / "templates"
_INTAKE_JSX_PATH = _TEMPLATES_DIR / "soundstage_intake.jsx"
_PRODUCTION_JSX_PATH = _TEMPLATES_DIR / "soundstage_production.jsx"


def test_modular_jsx_partials_exist_within_line_budget() -> None:
    """Verifies modular Soundstage JSX partial files exist and stay well under the 850-line budget."""
    assert _INTAKE_JSX_PATH.is_file(), "Missing templates/soundstage_intake.jsx"
    assert _PRODUCTION_JSX_PATH.is_file(), "Missing templates/soundstage_production.jsx"

    intake_lines = _INTAKE_JSX_PATH.read_text(encoding="utf-8").splitlines()
    production_lines = _PRODUCTION_JSX_PATH.read_text(encoding="utf-8").splitlines()

    assert 100 <= len(intake_lines) < 850, (
        f"soundstage_intake.jsx should be < 850 lines, got {len(intake_lines)}"
    )
    assert 30 <= len(production_lines) < 850, (
        f"soundstage_production.jsx should be < 850 lines, got {len(production_lines)}"
    )


def test_get_ui_html_and_root_endpoint_splice_soundstage_partials() -> None:
    """Verifies get_ui_html() and GET / splice Soundstage partials with zero leftover splice markers."""
    ui_html = get_ui_html()
    assert "/* __SOUNDSTAGE_STUDIO_COMPONENTS__ */" not in ui_html
    assert "--sstage-bg: #090a0f;" in ui_html
    assert "--sstage-surface: #11131a;" in ui_html
    assert "--sstage-elevated: #171a24;" in ui_html
    assert "--sstage-ivory: #f5f2eb;" in ui_html
    assert "--sstage-rose: #e11d48;" in ui_html
    assert "--sstage-stone: #a8a29e;" in ui_html
    assert ".sstage-canvas" in ui_html
    assert ".sstage-card" in ui_html

    client = TestClient(create_app(mock_mode=True))
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "/* __SOUNDSTAGE_STUDIO_COMPONENTS__ */" not in body
    assert "function SoundstageStudio(" in body
    assert "function SoundstageProductionRoom(" in body


def test_five_tab_mode_switcher_and_fullscreen_header_gate() -> None:
    """Verifies the 5-tab mode switcher button, campaign badge, and fullscreen focus header hiding."""
    ui_html = get_ui_html()
    assert "xl:grid-cols-5" in ui_html
    assert 'id="btn-mode-soundstage"' in ui_html
    assert "Mode 5: Commercial Soundstage" in ui_html
    assert "30s + 15s + 6s Campaign" in ui_html
    assert "soundstageFullscreen" in ui_html
    assert "setSoundstageFullscreen" in ui_html


def test_soundstage_intake_components_steps_and_api_bindings() -> None:
    """Verifies all Mode 5 intake components, 10 steps, Express toggle, Fullscreen toggle, and API endpoints."""
    ui_html = get_ui_html()

    for component_name in (
        "SoundstageWorldMap",
        "SoundstageEmblemPlate",
        "SoundstagePaletteEditor",
        "SoundstageGuidedIntake",
        "SoundstageStudio",
        "SoundstageProductionRoom",
    ):
        assert f"function {component_name}(" in ui_html, f"Missing component {component_name}"

    for required_id in (
        "soundstage-world-map",
        "soundstage-emblem-plate",
        "soundstage-emblem-upload",
        "soundstage-btn-synthesize-emblem",
        "soundstage-palette-editor",
        "soundstage-toggle-guided",
        "soundstage-btn-fullscreen",
        "soundstage-express-canvas",
        "soundstage-express-subject",
        "soundstage-express-dna",
        "soundstage-btn-make-film-express",
        "soundstage-guided-canvas",
        "soundstage-input-subject",
        "soundstage-input-dna",
        "soundstage-btn-discover",
        "soundstage-input-offering",
        "soundstage-input-territory",
        "soundstage-input-weather",
        "soundstage-input-moment",
        "soundstage-input-language",
        "soundstage-input-cadence",
        "soundstage-packshot-upload",
        "soundstage-btn-synthesize-packshot",
        "soundstage-ready-signoff",
        "soundstage-input-tagline",
        "soundstage-toggle-manual-board-gate",
        "soundstage-btn-make-film",
    ):
        assert f'id="{required_id}"' in ui_html, f"Missing required element id={required_id}"

    for territory_pin in (
        "Tokyo · Aoyama",
        "Paris · Le Marais",
        "Milan · Brera",
        "New York · SoHo",
        "London · Soho",
        "Seoul · Hannam",
        "Kyoto · Higashiyama",
        "Reykjavik · Harbor",
        "São Paulo · Jardins",
        "Los Angeles · Silver Lake",
    ):
        assert territory_pin in ui_html, f"Missing world map pin {territory_pin}"

    for palette_preset in (
        "Obsidian & Sienna",
        "Brera Travertine & Espresso",
        "Kyoto Cedar & Alabaster",
        "Nocturne Cobalt & Quartz",
    ):
        assert palette_preset in ui_html, f"Missing palette preset {palette_preset}"

    assert "data-edit-step=" in ui_html
    assert "Guide the brief" in ui_html
    assert "Exit Fullscreen Focus" in ui_html
    assert "Make the film" in ui_html

    for endpoint in (
        "/api/soundstage/discover",
        "/api/soundstage/plan",
        "/api/soundstage/cast",
    ):
        assert endpoint in ui_html, f"Missing endpoint binding {endpoint}"


def test_soundstage_originality_and_video_model_hygiene() -> None:
    """Ensures zero prohibited external inspiration terms/URLs or prohibited video model names appear."""
    targets = [get_ui_html()]
    if _INTAKE_JSX_PATH.is_file():
        targets.append(_INTAKE_JSX_PATH.read_text(encoding="utf-8"))
    if _PRODUCTION_JSX_PATH.is_file():
        targets.append(_PRODUCTION_JSX_PATH.read_text(encoding="utf-8"))

    disallowed_patterns = (
        re.compile("".join(["crea", "tive", r"\s*", "os"]), re.IGNORECASE),
        re.compile("".join(["c", "o", "s", "-", "u", "i"]), re.IGNORECASE),
        re.compile(r"\b" + "".join(["c", "o", "s", "2"]) + r"\b", re.IGNORECASE),
        re.compile(r"\." + "".join(["run", r"\.", "app"]), re.IGNORECASE),
        re.compile(r"\b" + "".join(["v", "e", "o", "-"]) + r"[0-9a-z._-]+", re.IGNORECASE),
    )

    for content in targets:
        for pat in disallowed_patterns:
            match = pat.search(content)
            assert match is None, f"Disallowed token matched in UI asset: {match.group(0)}"


@pytest.mark.slow
@pytest.mark.browser
def test_soundstage_mode5_interactive_flows_in_headless_browser(tmp_path: Path) -> None:
    """Exercises Mode 5 tab switch, Fullscreen Focus, Express toggle, 10-step rail, Edit jump, and Make Film against live mock FastAPI."""
    import socket
    import threading
    import time
    import uvicorn
    from omnimash.agent.soundstage_runner import get_soundstage_service

    skill_dir_candidates = (
        "/usr/local/google/home/jordantotten/.gemini/config/skills/playwright-skill",
        "/usr/local/google/home/jordantotten/.gemini/jetski/skills/playwright-skill",
    )
    skill_dir = next((p for p in skill_dir_candidates if os.path.exists(p)), None)
    assert skill_dir is not None, "Playwright skill runtime is expected on this workstation"

    app_module._CACHED_UI_HTML = None
    app = create_app(mock_mode=True)
    get_soundstage_service(app.state.agent).output_dir = str(tmp_path)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10.0
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started, "Local test uvicorn server failed to start"

    try:
        script_file = tmp_path / "run_soundstage_check.js"
        script_file.write_text(
            f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch({{ headless: true }});
  const page = await browser.newPage({{ viewport: {{ width: 1440, height: 900 }} }});
  await page.route('**fonts.googleapis.com**', r => r.abort());
  await page.route('**fonts.gstatic.com**', r => r.abort());
  const pageErrors = [];
  page.on('pageerror', err => pageErrors.push(err.message));

  await page.goto('http://127.0.0.1:{port}/', {{ waitUntil: 'domcontentloaded' }});
  await page.waitForSelector('#btn-mode-soundstage', {{ timeout: 15000 }});
  await page.click('#btn-mode-soundstage');
  await page.waitForSelector('#soundstage-guided-canvas', {{ timeout: 5000 }});

  // Test Fullscreen Focus hides and restores global <header>
  const headerBefore = await page.locator('header').count();
  if (headerBefore !== 1) throw new Error('Expected header visible before fullscreen');
  await page.click('#soundstage-btn-fullscreen');
  const headerDuring = await page.locator('header').count();
  if (headerDuring !== 0) throw new Error('Expected header hidden during fullscreen focus');
  await page.click('#soundstage-btn-fullscreen');
  const headerAfter = await page.locator('header').count();
  if (headerAfter !== 1) throw new Error('Expected header restored after exiting fullscreen focus');

  // Test Guide the brief switch -> Express Canvas -> back to Guided
  await page.click('#soundstage-toggle-guided');
  await page.waitForSelector('#soundstage-express-canvas', {{ timeout: 3000 }});
  await page.click('#soundstage-toggle-guided');
  await page.waitForSelector('#soundstage-guided-canvas', {{ timeout: 3000 }});

  // Step 1: Enter subject and Discover Brief & Continue -> Step 2 (hits real mock /api/soundstage/discover)
  await page.fill('#soundstage-input-subject', 'Porsche');
  await page.click('#soundstage-btn-discover');
  await page.waitForSelector('#soundstage-input-offering', {{ timeout: 5000 }});

  // Jump to Step 3 (World Map), Step 5 (Emblem Plate + Synthesize), Step 6 (Palette), Step 10 (Ready Sign-Off)
  await page.click('[data-step-rail="3"]');
  await page.waitForSelector('#soundstage-world-map', {{ timeout: 3000 }});
  await page.click('[data-step-rail="5"]');
  await page.waitForSelector('#soundstage-emblem-plate', {{ timeout: 3000 }});
  await page.click('#soundstage-btn-synthesize-emblem');
  await page.click('[data-step-rail="6"]');
  await page.waitForSelector('#soundstage-palette-editor', {{ timeout: 3000 }});
  await page.click('[data-step-rail="10"]');
  await page.waitForSelector('#soundstage-ready-signoff', {{ timeout: 3000 }});

  // Verify Ready Sign-Off Edit -> jumps back to Step 3
  await page.click('[data-edit-step="3"]');
  await page.waitForSelector('#soundstage-world-map', {{ timeout: 3000 }});

  // Return to Step 10 and click Make the film -> transitions to SoundstageProductionRoom
  await page.click('[data-step-rail="10"]');
  await page.waitForSelector('#soundstage-btn-make-film', {{ timeout: 3000 }});
  await page.click('#soundstage-btn-make-film');
  await page.waitForSelector('#soundstage-production-room', {{ timeout: 5000 }});

  // Verify Edit Brief returns to intake with Return to Production Room button visible
  await page.click('#soundstage-btn-edit-brief');
  await page.waitForSelector('#soundstage-btn-return-production', {{ timeout: 3000 }});

  // Also verify 1-Step Express Canvas Make the film -> transitions directly to Production Room
  await page.click('#soundstage-toggle-guided');
  await page.waitForSelector('#soundstage-express-canvas', {{ timeout: 3000 }});
  await page.fill('#soundstage-express-subject', 'Trapwarts Alchemical Guild');
  await page.fill('#soundstage-express-dna', 'Hand-carved obsidian spellcraft wand');
  await page.click('#soundstage-btn-make-film-express');
  await page.waitForSelector('#soundstage-production-room', {{ timeout: 5000 }});

  if (pageErrors.length !== 0) {{
    throw new Error('Browser page errors: ' + pageErrors.join(' | '));
  }}
  console.log('SOUNDSTAGE_E2E_OK');
  await browser.close();
}})();
""",
            encoding="utf-8",
        )

        res = subprocess.run(
            ["node", str(script_file)],
            cwd=skill_dir,
            env={**os.environ, "NODE_PATH": os.path.join(skill_dir, "node_modules")},
            capture_output=True,
            text=True,
        )
        output = res.stdout + res.stderr
        assert res.returncode == 0, f"Playwright Mode 5 E2E failed: {output}"
        assert "SOUNDSTAGE_E2E_OK" in output, f"Expected SOUNDSTAGE_E2E_OK marker: {output}"
    finally:
        server.should_exit = True
        thread.join(timeout=5.0)
