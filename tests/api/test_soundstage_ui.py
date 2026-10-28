"""UI integration, modular JSX splice, hygiene, and browser interaction tests for Mode 5: Commercial Soundstage."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient
import pytest

from omnimash.api import app as app_module
from omnimash.api.app import UI_HTML, create_app, get_ui_html

_API_DIR = Path(app_module.__file__).resolve().parent
_TEMPLATES_DIR = _API_DIR / "templates"
_INTAKE_JSX_PATH = _TEMPLATES_DIR / "soundstage_intake.jsx"
_PRODUCTION_JSX_PATH = _TEMPLATES_DIR / "soundstage_production.jsx"


def test_app_py_thin_budget_and_ui_loader_exports() -> None:
    """Verifies app.py stays < 120 lines by delegating JSX splicing to omnimash.api.ui_loader while re-exporting UI_HTML & get_ui_html."""
    from omnimash.api import ui_loader

    app_lines = (_API_DIR / "app.py").read_text(encoding="utf-8").splitlines()
    assert len(app_lines) < 120, f"Expected app.py < 120 lines, got {len(app_lines)}"
    assert ui_loader.get_ui_html() == get_ui_html()
    assert isinstance(UI_HTML, str) and len(UI_HTML) > 10_000


def test_modular_jsx_partials_exist_within_line_budget() -> None:
    """Verifies modular Soundstage JSX partial files exist and stay well under the 850-line budget."""
    assert _INTAKE_JSX_PATH.is_file(), "Missing templates/soundstage_intake.jsx"
    assert _PRODUCTION_JSX_PATH.is_file(), "Missing templates/soundstage_production.jsx"

    intake_text = _INTAKE_JSX_PATH.read_text(encoding="utf-8")
    intake_lines = intake_text.splitlines()
    production_lines = _PRODUCTION_JSX_PATH.read_text(encoding="utf-8").splitlines()

    assert 100 <= len(intake_lines) < 850, (
        f"soundstage_intake.jsx should be < 850 lines, got {len(intake_lines)}"
    )
    assert 30 <= len(production_lines) < 850, (
        f"soundstage_production.jsx should be < 850 lines, got {len(production_lines)}"
    )

    # Every top-level function / component / hook in soundstage_intake.jsx must be < 200 lines
    fn_starts = [idx for idx, line in enumerate(intake_lines) if line.startswith("function ")]
    assert len(fn_starts) >= 6
    fn_bounds = [*fn_starts, len(intake_lines)]
    for i in range(len(fn_starts)):
        span = fn_bounds[i + 1] - fn_bounds[i]
        assert span < 200, (
            f"Function at line {fn_starts[i] + 1} in soundstage_intake.jsx is {span} lines (>= 200)"
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


def test_five_tab_mode_switcher_escape_fullscreen_and_mode1_to_3_sync_hooks() -> None:
    """Verifies 5-tab mode switcher, Escape fullscreen dismissal, and intact Mode 1-3 dual sync useEffects."""
    ui_html = get_ui_html()
    assert "xl:grid-cols-5" in ui_html
    assert 'id="btn-mode-soundstage"' in ui_html
    assert "Mode 5: Commercial Soundstage" in ui_html
    assert "30s + 15s + 6s Campaign" in ui_html
    assert "soundstageFullscreen" in ui_html
    assert "setSoundstageFullscreen" in ui_html

    # Escape handler dismisses soundstageFullscreen
    escape_pos = ui_html.find('if (e.key === "Escape")')
    assert escape_pos != -1
    escape_block = ui_html[escape_pos : escape_pos + 900]
    assert "setSoundstageFullscreen(false);" in escape_block

    # Original two separate cross-mode sync useEffect dependency arrays remain intact
    assert "}, [visualConcept, j3MasterDescription]);" in ui_html
    assert "}, [j3MasterDescription, visualConcept]);" in ui_html


def test_soundstage_intake_components_steps_and_security_guards() -> None:
    """Verifies all Mode 5 intake components, 10 steps, MIME upload validation, draft fingerprint, and project_name sanitization."""
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

    # Client-side Data URI subtype validation, identifier sanitization, and draft fingerprint
    assert "png|jpeg|jpg|webp|svg\\+xml" in ui_html
    assert "sanitizeSoundstageIdentifier" in ui_html
    assert "safeProjectName" in ui_html
    assert "computePlanSignature" in ui_html
    assert "selectInspirationChip" in ui_html

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
    """Exercises Mode 5 Escape fullscreen exit, MIME upload check, chip reset, draft fingerprint, and Express fresh discovery."""
    import socket
    import threading
    import time
    import uvicorn
    from omnimash.agent.soundstage_runner import get_soundstage_service
    from omnimash.api import ui_loader

    skill_dir_candidates = (
        "/usr/local/google/home/jordantotten/.gemini/config/skills/playwright-skill",
        "/usr/local/google/home/jordantotten/.gemini/jetski/skills/playwright-skill",
    )
    skill_dir = next((p for p in skill_dir_candidates if os.path.exists(p)), None)
    assert skill_dir is not None, "Playwright skill runtime is expected on this workstation"

    ui_loader._CACHED_UI_HTML = None
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

  // Seed an unsafe activeProject in localStorage before loading to test safeProjectName sanitization
  await page.addInitScript(() => {{
    localStorage.setItem('omnimash_active_project', 'bad project/../name!');
  }});

  const planPayloads = [];
  const castPayloads = [];
  await page.route('**/api/soundstage/plan', async (route) => {{
    planPayloads.push(JSON.parse(route.request().postData() || '{{}}'));
    await route.continue();
  }});
  await page.route('**/api/soundstage/cast', async (route) => {{
    castPayloads.push(JSON.parse(route.request().postData() || '{{}}'));
    await route.continue();
  }});

  await page.goto('http://127.0.0.1:{port}/', {{ waitUntil: 'domcontentloaded' }});
  await page.waitForSelector('#btn-mode-soundstage', {{ timeout: 15000 }});
  await page.click('#btn-mode-soundstage');
  await page.waitForSelector('#soundstage-guided-canvas', {{ timeout: 5000 }});

  // 1. Test Fullscreen Focus hides <header> AND pressing Escape exits fullscreen & restores <header>
  if ((await page.locator('header').count()) !== 1) throw new Error('Expected header visible before fullscreen');
  await page.click('#soundstage-btn-fullscreen');
  if ((await page.locator('header').count()) !== 0) throw new Error('Expected header hidden during fullscreen focus');
  await page.keyboard.press('Escape');
  await page.waitForSelector('header', {{ timeout: 3000 }});
  if ((await page.locator('header').count()) !== 1) throw new Error('Expected Escape key to exit fullscreen focus');

  // 2. Test Inspiration Chip resets editedFields after manual edit on Step 2
  await page.click('[data-step-rail="2"]');
  await page.fill('#soundstage-input-offering', 'Stale Manual Offering');
  await page.click('[data-step-rail="1"]');
  await page.getByRole('button', {{ name: /Brera Botanical Aperitif/i }}).click();
  await page.click('#soundstage-btn-discover');
  await page.waitForSelector('#soundstage-input-offering', {{ timeout: 5000 }});
  const offeringAfterChipDiscover = await page.inputValue('#soundstage-input-offering');
  if (offeringAfterChipDiscover === 'Stale Manual Offering' || !offeringAfterChipDiscover) {{
    throw new Error('Expected inspiration chip to clear editedFields so discover refreshes offering, got: ' + offeringAfterChipDiscover);
  }}

  // 3. Test Client-Side MIME upload validation on Step 5 (reject image/gif, accept image/png)
  await page.click('[data-step-rail="5"]');
  await page.waitForSelector('#soundstage-emblem-upload', {{ timeout: 3000 }});
  await page.setInputFiles('#soundstage-emblem-upload', {{
    name: 'bad.gif',
    mimeType: 'image/gif',
    buffer: Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64')
  }});
  await page.waitForTimeout(100);
  if ((await page.inputValue('#soundstage-input-emblem-url')) !== '') {{
    throw new Error('Expected unsupported image/gif upload to be rejected');
  }}
  const toastAfterGif = await page.locator('.ToastNotificationRegion').innerText();
  if (!toastAfterGif.includes('Unsupported image format')) {{
    throw new Error('Expected error toast on unsupported image/gif upload, got: ' + toastAfterGif);
  }}
  await page.setInputFiles('#soundstage-emblem-upload', {{
    name: 'mark.png',
    mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
  }});
  await page.waitForFunction(() => document.querySelector('#soundstage-input-emblem-url').value.startsWith('data:image/png;base64,'), {{ timeout: 3000 }});

  // 4. Test Draft Run Fingerprint: Step 5 synthesize -> Step 6 palette edit -> Step 9 packshot synthesize re-plans!
  await page.click('#soundstage-btn-synthesize-emblem');
  await page.waitForFunction(() => document.querySelectorAll('#soundstage-emblem-plate img').length >= 2, {{ timeout: 5000 }});
  if (planPayloads.length !== 1 || castPayloads.length !== 1) {{
    throw new Error('Expected 1 plan + 1 cast after emblem synthesis, got ' + planPayloads.length + '/' + castPayloads.length);
  }}
  if (planPayloads[0].project_name !== 'bad_project_name') {{
    throw new Error('Expected sanitized project_name bad_project_name, got: ' + planPayloads[0].project_name);
  }}
  const firstDraftRunId = castPayloads[0].run_id;

  await page.click('[data-step-rail="6"]');
  await page.getByRole('button', {{ name: /Nocturne Cobalt & Quartz/i }}).click();
  await page.click('[data-step-rail="9"]');
  await page.click('#soundstage-btn-synthesize-packshot');
  await page.waitForFunction(() => document.querySelectorAll('img[alt^="Packshot candidate"]').length >= 1, {{ timeout: 5000 }});
  if (planPayloads.length !== 2 || castPayloads.length !== 2) {{
    throw new Error('Expected palette edit to invalidate draft plan signature and re-plan before packshot synthesis');
  }}
  const secondDraftRunId = castPayloads[1].run_id;
  if (secondDraftRunId === firstDraftRunId) {{
    throw new Error('Expected new draft run_id after palette edit, got same ' + secondDraftRunId);
  }}
  if (planPayloads[1].palette_hexes.primary_hex !== '#192334') {{
    throw new Error('Expected updated Nocturne Cobalt primary_hex in re-planned draft payload');
  }}

  // 5. Verify Ready Sign-Off Edit -> jumps back to Step 3, then Step 10 Make the film -> Production Room
  await page.click('[data-step-rail="10"]');
  await page.click('[data-edit-step="3"]');
  await page.waitForSelector('#soundstage-world-map', {{ timeout: 3000 }});
  await page.click('[data-step-rail="10"]');
  await page.click('#soundstage-btn-make-film');
  await page.waitForSelector('#soundstage-production-room', {{ timeout: 5000 }});
  const prodRunTextBefore = await page.locator('#soundstage-production-room').innerText();

  // Clicking <- Edit Brief and synthesizing an emblem must NOT mutate the launched production run
  await page.click('#soundstage-btn-edit-brief');
  await page.waitForSelector('#soundstage-btn-return-production', {{ timeout: 3000 }});
  await page.click('[data-step-rail="5"]');
  const castCountBeforeEditSynth = castPayloads.length;
  await page.click('#soundstage-btn-synthesize-emblem');
  await page.waitForTimeout(300);
  if (castPayloads.length <= castCountBeforeEditSynth) {{
    throw new Error('Expected synthesize emblem after Edit Brief to run');
  }}
  await page.click('#soundstage-btn-return-production');
  await page.waitForSelector('#soundstage-production-room', {{ timeout: 3000 }});
  const prodRunTextAfter = await page.locator('#soundstage-production-room').innerText();
  if (prodRunTextAfter !== prodRunTextBefore) {{
    throw new Error('Expected launched production run in Production Room to remain untouched by intake draft synthesis');
  }}

  // 6. Test Express Mode passes freshly discovered moment, language, and vocal_cadence on first click (no stale state)
  await page.click('#soundstage-btn-edit-brief');
  await page.click('#soundstage-toggle-guided');
  await page.waitForSelector('#soundstage-express-canvas', {{ timeout: 3000 }});
  // Click chip to ensure editedFields is empty
  await page.getByRole('button', {{ name: /Aoyama Grand Tourer/i }}).click();
  await page.route('**/api/soundstage/discover', async (route) => {{
    const resp = await route.fetch();
    const json = await resp.json();
    json.cultural_moments = [{{ title: 'Midnight Ginza Threshold', description: 'Rain-slicked nocturnal calm.' }}];
    json.spoken_languages = [{{ code: 'ja', label: 'Japanese', vocal_cadence: 'Poised Tokyo nocturnal baritone' }}];
    await route.fulfill({{ response: resp, json }});
  }});
  const plansBeforeExpress = planPayloads.length;
  await page.click('#soundstage-btn-make-film-express');
  await page.waitForSelector('#soundstage-production-room', {{ timeout: 5000 }});
  if (planPayloads.length !== plansBeforeExpress + 1) {{
    throw new Error('Expected Express Make the film to call /api/soundstage/plan once');
  }}
  const expressPlan = planPayloads[planPayloads.length - 1];
  if (expressPlan.moment !== 'Midnight Ginza Threshold') {{
    throw new Error('Express plan missed freshly discovered moment: ' + JSON.stringify(expressPlan));
  }}
  if (expressPlan.language !== 'Japanese' || expressPlan.vocal_cadence !== 'Poised Tokyo nocturnal baritone') {{
    throw new Error('Express plan missed freshly discovered language/vocal_cadence: ' + JSON.stringify(expressPlan));
  }}

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
