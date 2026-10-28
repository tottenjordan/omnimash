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
_SHARED_JSX_PATH = _TEMPLATES_DIR / "soundstage_shared.jsx"
_INTAKE_JSX_PATH = _TEMPLATES_DIR / "soundstage_intake.jsx"
_PRODUCTION_JSX_PATH = _TEMPLATES_DIR / "soundstage_production.jsx"
_PREMIERE_JSX_PATH = _TEMPLATES_DIR / "soundstage_premiere.jsx"


def test_app_py_thin_budget_and_ui_loader_exports() -> None:
    """Verifies app.py stays < 120 lines by delegating JSX splicing to omnimash.api.ui_loader while re-exporting UI_HTML & get_ui_html."""
    from omnimash.api import ui_loader

    app_lines = (_API_DIR / "app.py").read_text(encoding="utf-8").splitlines()
    assert len(app_lines) < 120, f"Expected app.py < 120 lines, got {len(app_lines)}"
    assert ui_loader.get_ui_html() == get_ui_html()
    assert isinstance(UI_HTML, str) and len(UI_HTML) > 10_000


def test_modular_jsx_partials_exist_within_line_budget() -> None:
    """Verifies modular Soundstage JSX partial files exist and stay well under the 750/850-line and 190-line/fn budgets."""
    for path in (
        _SHARED_JSX_PATH,
        _INTAKE_JSX_PATH,
        _PRODUCTION_JSX_PATH,
        _PREMIERE_JSX_PATH,
        Path(__file__).resolve().parent / "test_soundstage_browser.py",
    ):
        assert path.is_file(), f"Missing {path.name}"
        lines = path.read_text(encoding="utf-8").splitlines()
        max_lines = (
            450
            if path.name == "test_soundstage_browser.py"
            else (750 if path in (_PRODUCTION_JSX_PATH, _PREMIERE_JSX_PATH) else 850)
        )
        assert 30 <= len(lines) < max_lines, (
            f"{path.name} should be < {max_lines} lines, got {len(lines)}"
        )
        fn_starts = [
            idx
            for idx, line in enumerate(lines)
            if line.startswith("function ") or line.startswith("async function ")
        ]
        if fn_starts:
            fn_bounds = [*fn_starts, len(lines)]
            for i in range(len(fn_starts)):
                span = fn_bounds[i + 1] - fn_bounds[i]
                assert span < 190, (
                    f"Function at line {fn_starts[i] + 1} in {path.name} is {span} lines (>= 190)"
                )


def test_get_ui_html_and_root_endpoint_splice_soundstage_partials() -> None:
    """Verifies get_ui_html() and GET / splice Soundstage partials with zero leftover splice markers and pure-CSS switches."""
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
    assert '.sstage-switch[aria-checked="true"]' in ui_html
    assert ".sstage-switch-thumb" in ui_html

    client = TestClient(create_app(mock_mode=True))
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "/* __SOUNDSTAGE_STUDIO_COMPONENTS__ */" not in body
    assert "function getSafeSoundstageMediaUrl(" in body
    assert "async function postSoundstageJson(" in body
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

    escape_pos = ui_html.find('if (e.key === "Escape")')
    assert escape_pos != -1
    escape_block = ui_html[escape_pos : escape_pos + 900]
    assert "setSoundstageFullscreen(false);" in escape_block

    assert "}, [visualConcept, j3MasterDescription]);" in ui_html
    assert "}, [j3MasterDescription, visualConcept]);" in ui_html


def test_soundstage_intake_components_a11y_and_security_guards() -> None:
    """Verifies Mode 5 components, WCAG switch labels, aria-pressed, mobile grid, safe media URL guard, and error parser."""
    ui_html = get_ui_html()
    intake_src = _INTAKE_JSX_PATH.read_text(encoding="utf-8")

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

    # WCAG 4.1.2 switch accessible names, aria-pressed states, no duplicate SVG tabIndex, mobile 375px grid
    assert 'aria-label="Guide the brief"' in intake_src
    assert 'aria-label="Manual Storyboard Approval Gate before Omni Flash filming"' in intake_src
    assert "aria-pressed=" in intake_src
    assert "tabIndex={0}" not in intake_src
    assert "grid-cols-1 sm:grid-cols-3" in intake_src

    # Security & state hygiene helpers
    assert "getSafeSoundstageMediaUrl" in ui_html
    assert "cleanSoundstageOptionalText" in ui_html
    assert "png|jpeg|jpg|webp|svg\\+xml" in ui_html
    assert "sanitizeSoundstageIdentifier" in ui_html
    assert "safeProjectName" in ui_html
    assert "computePlanSignature(brief, safeProjectName, safeSessionName)" in intake_src
    assert "selectInspirationChip" in ui_html
    assert "Precision crafted for the quiet pulse of Tokyo." not in ui_html

    for endpoint in (
        "/api/soundstage/discover",
        "/api/soundstage/plan",
        "/api/soundstage/cast",
    ):
        assert endpoint in ui_html, f"Missing endpoint binding {endpoint}"


def test_soundstage_seven_stage_production_and_premiere_ui_controls() -> None:
    """Verifies all Stage 1-7 Production & Premiere controls, ARIA labels, and API bindings exist in UI_HTML."""
    ui_html = get_ui_html()

    for component_name in (
        "SoundstageBriefStageView",
        "SoundstageWorldStageView",
        "SoundstageStoryStageView",
        "SoundstageCastGateView",
        "SoundstageBoardsGateView",
        "SoundstageFilmingStageView",
        "SoundstagePremierePlayerCard",
        "SoundstageNleTrimmerPanel",
        "SoundstageDirectorNoteBar",
        "SoundstageVariationsAndExportPanel",
        "SoundstagePremiereStageView",
        "SoundstageProductionRoom",
    ):
        assert f"function {component_name}(" in ui_html, f"Missing component {component_name}"

    for required_id in (
        "soundstage-production-room",
        "soundstage-stage-rail",
        "soundstage-btn-edit-brief",
        "soundstage-prod-btn-fullscreen",
        "soundstage-view-brief",
        "soundstage-view-world",
        "soundstage-view-story",
        "soundstage-cast-gate",
        "soundstage-btn-recast",
        "soundstage-btn-cast-older",
        "soundstage-btn-cast-younger",
        "soundstage-input-cast-wardrobe",
        "soundstage-input-cast-tweak",
        "soundstage-btn-cast-tweak",
        "soundstage-vault-cast-picker",
        "soundstage-cast-toggle-manual-boards",
        "soundstage-btn-approve-cast",
        "soundstage-boards-gate",
        "soundstage-btn-draw-boards",
        "soundstage-btn-redraw-all-boards",
        "soundstage-btn-roll-cameras",
        "soundstage-filming-view",
        "soundstage-premiere-view",
        "soundstage-format-tabs",
        "soundstage-tab-30s",
        "soundstage-tab-15s",
        "soundstage-tab-6s",
        "soundstage-premiere-video",
        "soundstage-nle-trimmer",
        "soundstage-btn-reconform",
        "soundstage-btn-reset-trims",
        "soundstage-director-note-bar",
        "soundstage-input-director-note",
        "soundstage-select-target-act",
        "soundstage-btn-revise",
        "soundstage-variations-panel",
        "soundstage-input-variation-value",
        "soundstage-btn-fork-variation",
        "soundstage-export-bar",
        "soundstage-btn-download-zip",
        "soundstage-btn-promote-mode2",
        "soundstage-btn-promote-mode3",
    ):
        assert f'id="{required_id}"' in ui_html, f"Missing production/premiere id={required_id}"

    for token in (
        'aria-label="Pause at 3x3 Storyboard Gate before filming"',
        'aria-label="Soundstage filming progress"',
        "Human-Free Macro (@Image4 Only)",
        "Lead Cast (@Image3)",
        "Forked Variation",
        "EventSource",
        "/api/characters/save",
        "/api/soundstage/boards",
        "/api/soundstage/run",
        "/events",
        "/status",
        "/reconform",
        "/revise",
        "/variations",
        "/package.zip",
    ):
        assert token in ui_html, f"Missing production/premiere token: {token}"


def test_soundstage_sse_lifecycle_remount_and_3_decimal_nle_guards() -> None:
    """HIGH-2, MEDIUM-3, LOW-4: Verifies SSE es.close() on terminal events, idle/timeout unlock, stale-runId guard, in-flight remount reconciliation, and 3-decimal NLE rounding."""
    shared_src = _SHARED_JSX_PATH.read_text(encoding="utf-8")
    prod_src = _PRODUCTION_JSX_PATH.read_text(encoding="utf-8")
    premiere_src = _PREMIERE_JSX_PATH.read_text(encoding="utf-8")

    # LOW-4: 3-decimal NLE precision in computeSubshotEffectiveWindow & handleAdjustTrim
    assert "* 100) / 100" not in shared_src
    assert "* 100) / 100" not in premiere_src
    assert "Math.round(start * 1000) / 1000" in shared_src
    assert "Math.round(end * 1000) / 1000" in shared_src
    assert "Math.round((end - start) * 1000) / 1000" in shared_src
    assert "Math.round(((spec[field] || 0) + delta) * 1000) / 1000" in premiere_src

    # MEDIUM-3: In-flight filming stage detection & automatic remount monitor attachment
    assert "function isSoundstageFilmingStage(" in shared_src
    assert "isSoundstageFilmingStage(activeRun.stage)" in prod_src
    assert "function attachSoundstageFilmingMonitor(" in prod_src

    # HIGH-2: Stale-runId guard, immediate es.close() on terminal SSE events, and idle/timeout unlock
    assert "lastRunIdRef.current !== runId" in prod_src
    assert "es.close()" in prod_src
    assert 'reason === "idle" || reason === "timeout"' in prod_src
    assert 'if (reason === "timeout")' in prod_src


def test_soundstage_originality_and_video_model_hygiene() -> None:
    """Ensures zero prohibited external inspiration terms/URLs or prohibited video model names appear."""
    targets = [get_ui_html()]
    for path in (
        _SHARED_JSX_PATH,
        _INTAKE_JSX_PATH,
        _PRODUCTION_JSX_PATH,
        _PREMIERE_JSX_PATH,
        Path(__file__).resolve().parent / "test_soundstage_browser.py",
    ):
        if path.is_file():
            targets.append(path.read_text(encoding="utf-8"))

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
    """Exercises Mode 5 security URL guards, whitespace trimming, 422 error formatting, Step 1 Continue auto-discover, switch a11y, and Express flow."""
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

  await page.addInitScript(() => {{
    localStorage.setItem('omnimash_active_project', 'bad project/../name!');
  }});

  const planPayloads = [];
  const castPayloads = [];
  let simulate422Once = false;
  await page.route('**/api/soundstage/plan', async (route) => {{
    if (simulate422Once) {{
      simulate422Once = false;
      await route.fulfill({{
        status: 422,
        contentType: 'application/json',
        body: JSON.stringify({{ detail: [{{ loc: ['body', 'subject'], msg: 'Subject fails schema check' }}] }})
      }});
      return;
    }}
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

  // 1. Verify WCAG switch accessible names & pure-CSS track color transition
  const guidedSwitch = page.getByRole('switch', {{ name: 'Guide the brief' }});
  if ((await guidedSwitch.count()) !== 1) throw new Error('Missing switch accessible name: Guide the brief');
  const activeBg = await guidedSwitch.evaluate((el) => getComputedStyle(el).backgroundColor);
  if (activeBg !== 'rgb(225, 29, 72)') throw new Error('Expected active rose switch track rgb(225, 29, 72), got: ' + activeBg);

  // 2. Test Fullscreen Focus hides <header> AND pressing Escape exits fullscreen & restores <header>
  await page.click('#soundstage-btn-fullscreen');
  if ((await page.locator('header').count()) !== 0) throw new Error('Expected header hidden during fullscreen focus');
  await page.keyboard.press('Escape');
  await page.waitForSelector('header', {{ timeout: 3000 }});

  // 3. Test Step 1 footer Continue -> auto-discovers an undiscovered subject (and inspiration chip clears editedFields)
  await page.click('[data-step-rail="2"]');
  await page.fill('#soundstage-input-offering', 'Stale Manual Offering');
  await page.click('[data-step-rail="1"]');
  await page.getByRole('button', {{ name: /Brera Botanical Aperitif/i }}).click();
  await page.getByRole('button', {{ name: 'Continue →', exact: true }}).click();
  await page.waitForSelector('#soundstage-input-offering', {{ timeout: 5000 }});
  const offeringAfterContinue = await page.inputValue('#soundstage-input-offering');
  if (offeringAfterContinue === 'Stale Manual Offering' || offeringAfterContinue === 'Signature Grand Touring Coupe' || !offeringAfterContinue) {{
    throw new Error('Expected Step 1 Continue -> to auto-discover fresh offering, got: ' + offeringAfterContinue);
  }}

  // 4. Test Safe Media URL Allowlist & Whitespace-Only Input Trimming on Step 5
  await page.click('[data-step-rail="5"]');
  await page.fill('#soundstage-input-emblem-url', 'javascript:alert(1)');
  if ((await page.locator('#soundstage-emblem-plate img[alt="Studio emblem preview"]').count()) !== 0) {{
    throw new Error('Unsafe javascript: URI must never render in <img src>');
  }}
  await page.click('#soundstage-btn-synthesize-emblem');
  const alertText = await page.locator('[role="alert"]').innerText();
  if (!alertText.includes('Invalid Studio Emblem URI')) {{
    throw new Error('Expected validation error banner on unsafe javascript: emblem URI, got: ' + alertText);
  }}
  if (planPayloads.length !== 0) {{
    throw new Error('Expected /api/soundstage/plan not to be called when emblem URI has unsafe scheme');
  }}

  // Whitespace-only emblemUrl & language must trim cleanly to null / "English"
  await page.fill('#soundstage-input-emblem-url', '    ');
  if ((await page.getByRole('button', {{ name: 'Clear Emblem' }}).count()) !== 0) {{
    throw new Error('Whitespace-only emblemUrl must not render Clear Emblem button');
  }}
  await page.click('[data-step-rail="8"]');
  await page.fill('#soundstage-input-language', '   ');
  await page.click('[data-step-rail="10"]');
  const signoffText = await page.locator('#soundstage-ready-signoff').innerText();
  if (signoffText.includes('Studio Mark Locked')) {{
    throw new Error('Whitespace-only emblemUrl must not report Studio Mark Locked on Step 10');
  }}
  if ((await page.getByRole('switch', {{ name: 'Manual Storyboard Approval Gate before Omni Flash filming' }}).count()) !== 1) {{
    throw new Error('Missing accessible name on Manual Storyboard Approval Gate switch');
  }}

  // 5. Test FastAPI HTTP 422 array detail formatting (never "[object Object]")
  simulate422Once = true;
  await page.click('#soundstage-btn-make-film');
  await page.waitForSelector('[role="alert"]', {{ timeout: 3000 }});
  const err422Text = await page.locator('[role="alert"]').innerText();
  if (err422Text.includes('[object Object]') || !err422Text.includes('Subject fails schema check')) {{
    throw new Error('Expected formatted 422 array error message, got: ' + err422Text);
  }}

  // 6. Test Client-Side MIME upload validation on Step 5 (reject image/gif, accept image/png) + Draft Fingerprint
  await page.click('[data-step-rail="5"]');
  await page.setInputFiles('#soundstage-emblem-upload', {{
    name: 'bad.gif',
    mimeType: 'image/gif',
    buffer: Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64')
  }});
  await page.waitForTimeout(100);
  if ((await page.inputValue('#soundstage-input-emblem-url')).trim() !== '') {{
    throw new Error('Expected unsupported image/gif upload to be rejected');
  }}
  await page.setInputFiles('#soundstage-emblem-upload', {{
    name: 'mark.png',
    mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
  }});
  await page.waitForFunction(() => document.querySelector('#soundstage-input-emblem-url').value.startsWith('data:image/png;base64,'), {{ timeout: 3000 }});

  await page.click('#soundstage-btn-synthesize-emblem');
  await page.waitForFunction(() => document.querySelectorAll('#soundstage-emblem-plate img').length >= 2, {{ timeout: 5000 }});
  if (planPayloads.length !== 1 || castPayloads.length !== 1) {{
    throw new Error('Expected 1 plan + 1 cast after emblem synthesis, got ' + planPayloads.length + '/' + castPayloads.length);
  }}
  if (planPayloads[0].project_name !== 'bad_project_name' || planPayloads[0].language !== 'English') {{
    throw new Error('Expected sanitized project_name=bad_project_name and fallback language=English, got: ' + JSON.stringify(planPayloads[0]));
  }}
  const firstDraftRunId = castPayloads[0].run_id;

  await page.click('[data-step-rail="6"]');
  await page.getByRole('button', {{ name: /Nocturne Cobalt & Quartz/i }}).click();
  await page.click('[data-step-rail="9"]');
  await page.click('#soundstage-btn-synthesize-packshot');
  await page.waitForFunction(() => document.querySelectorAll('img[alt^="Packshot candidate"]').length >= 1, {{ timeout: 5000 }});
  if (planPayloads.length !== 2 || castPayloads[1].run_id === firstDraftRunId) {{
    throw new Error('Expected palette edit to invalidate draft plan signature and re-plan before packshot synthesis');
  }}

  // 7. Mobile 375px check on Step 10 Ready Sign-Off (zero horizontal overflow on resolution buttons)
  await page.setViewportSize({{ width: 375, height: 812 }});
  await page.click('[data-step-rail="10"]');
  await page.waitForSelector('#soundstage-ready-signoff', {{ timeout: 3000 }});
  const stdBtnBox = await page.getByRole('button', {{ name: '720p Standard' }}).boundingBox();
  if (!stdBtnBox || stdBtnBox.x < 0 || stdBtnBox.x + stdBtnBox.width > 375) {{
    throw new Error('720p Standard button overflows 375px mobile viewport: ' + JSON.stringify(stdBtnBox));
  }}
  await page.setViewportSize({{ width: 1440, height: 900 }});

  // Launch Guided Film -> Production Room -> Edit Brief -> Express Mode fresh discovery
  await page.click('#soundstage-btn-make-film');
  await page.waitForSelector('#soundstage-production-room', {{ timeout: 5000 }});
  await page.click('#soundstage-btn-edit-brief');
  await page.click('#soundstage-toggle-guided');
  await page.waitForSelector('#soundstage-express-canvas', {{ timeout: 3000 }});
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
  const expressPlan = planPayloads[planPayloads.length - 1];
  if (
    planPayloads.length !== plansBeforeExpress + 1 ||
    expressPlan.moment !== 'Midnight Ginza Threshold' ||
    expressPlan.language !== 'Japanese' ||
    expressPlan.vocal_cadence !== 'Poised Tokyo nocturnal baritone'
  ) {{
    throw new Error('Express plan missed freshly discovered fields: ' + JSON.stringify(expressPlan));
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
