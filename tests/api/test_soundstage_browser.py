"""End-to-end headless Chromium Playwright verification for Mode 5: Commercial Soundstage (7-Stage Production & Premiere)."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import threading
import time

import pytest
import uvicorn

from omnimash.agent.soundstage_runner import get_soundstage_service
from omnimash.api import ui_loader
from omnimash.api.app import create_app

_PLAYWRIGHT_SKILL_CANDIDATES = (
    "/usr/local/google/home/jordantotten/.gemini/config/skills/playwright-skill",
    "/usr/local/google/home/jordantotten/.gemini/jetski/skills/playwright-skill",
)


def _resolve_playwright_skill_dir() -> str:
    skill_dir = next((p for p in _PLAYWRIGHT_SKILL_CANDIDATES if os.path.exists(p)), None)
    assert skill_dir is not None, (
        "Playwright skill runtime is required for @pytest.mark.browser tests"
    )
    return skill_dir


@pytest.mark.slow
@pytest.mark.browser
def test_soundstage_seven_stage_production_premiere_and_auto_advance_e2e(tmp_path: Path) -> None:
    """Drives Chromium across Guided Intake -> Cast Gate (Older, Tweak, Vault 'Dumble Dior') -> 3x3 Boards -> SSE Filming -> Premiere NLE/Revise/ZIP/Variation/Promote + Auto-Advance."""
    skill_dir = _resolve_playwright_skill_dir()

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
        script_file = tmp_path / "run_task5_e2e.js"
        script_file.write_text(
            f"""
const {{ chromium }} = require('playwright');

(async () => {{
  const browser = await chromium.launch({{ headless: true }});
  const page = await browser.newPage({{ viewport: {{ width: 1440, height: 900 }} }});
  await page.route('**fonts.googleapis.com**', (r) => r.abort());
  await page.route('**fonts.gstatic.com**', (r) => r.abort());

  const pageErrors = [];
  page.on('pageerror', (err) => pageErrors.push(err.message));

  const observedEndpoints = [];
  page.on('request', (req) => {{
    const u = req.url();
    if (u.includes('/api/soundstage/') || u.includes('/api/characters/save')) {{
      observedEndpoints.push(req.method() + ' ' + new URL(u).pathname);
    }}
  }});

  await page.goto('http://127.0.0.1:{port}/', {{ waitUntil: 'domcontentloaded' }});
  await page.waitForSelector('#btn-mode-soundstage', {{ timeout: 15000 }});
  await page.click('#btn-mode-soundstage');
  await page.waitForSelector('#soundstage-guided-canvas', {{ timeout: 5000 }});

  // 1. Guided Intake -> Launch into Stage 4 Smart Cast Gate
  await page.getByRole('button', {{ name: /Trapwarts Arcane Wand/i }}).click();
  await page.click('[data-step-rail="10"]');
  await page.waitForSelector('#soundstage-ready-signoff', {{ timeout: 5000 }});
  await page.click('#soundstage-btn-make-film');
  await page.waitForSelector('#soundstage-production-room', {{ timeout: 10000 }});
  await page.waitForSelector('#soundstage-cast-gate', {{ timeout: 5000 }});

  // Capture initial run_id & sessionName
  const headerBadgesText = await page.locator('#soundstage-production-room').innerText();
  const runIdMatch = headerBadgesText.match(/sstage_[a-f0-9]+/);
  if (!runIdMatch) throw new Error('Expected sstage_<hex> run_id in production header');
  const originalRunId = runIdMatch[0];

  // 2. Inspect Stage 1 (Brief), Stage 2 (World), Stage 3 (Story), then return to Stage 4 (Cast Gate)
  await page.click('[data-stage-tab="brief"]');
  await page.waitForSelector('#soundstage-view-brief', {{ timeout: 3000 }});
  const briefText = await page.locator('#soundstage-view-brief').innerText();
  if (!briefText.includes('Act 1 Causality Law') || !briefText.includes('Act 3 Causality Law')) {{
    throw new Error('Stage 1 Brief view missing 3-Act Causality Laws');
  }}

  await page.click('[data-stage-tab="world"]');
  await page.waitForSelector('#soundstage-view-world', {{ timeout: 3000 }});
  const worldText = (await page.locator('#soundstage-view-world').textContent()) || '';
  if (!/Verbatim UI/i.test(worldText) || !/Omni-Safe Prompt Descriptors/i.test(worldText)) {{
    throw new Error('Stage 2 World view missing Dual-Layer Brand & Cast Safety Card: ' + worldText);
  }}

  await page.click('[data-stage-tab="story"]');
  await page.waitForSelector('#soundstage-view-story', {{ timeout: 3000 }});
  const storyText = await page.locator('#soundstage-view-story').innerText();
  if (!storyText.includes('<FIRST_FRAME>') || !storyText.includes('<LAST_FRAME>') || !storyText.includes('Pre-Flight Passed')) {{
    throw new Error('Stage 3 Story view missing dual-keyframe anchor badges or Pre-Flight Passed badge');
  }}

  await page.click('[data-stage-tab="cast"]');
  await page.waitForSelector('#soundstage-cast-gate', {{ timeout: 3000 }});

  // 3. Smart Cast Gate: Older -> Wardrobe/Look Tweak -> Character Vault Hydration ('Dumble Dior')
  await page.click('#soundstage-btn-cast-older');
  await page.waitForFunction(
    () => !document.querySelector('#soundstage-btn-cast-older').disabled,
    {{ timeout: 5000 }}
  );

  await page.fill('#soundstage-input-cast-wardrobe', 'Charcoal tailored atelier wool coat');
  await page.fill('#soundstage-input-cast-tweak', 'Subtle silver rim-frame spectacles');
  await page.click('#soundstage-btn-cast-tweak');
  await page.waitForFunction(
    () => document.querySelector('#soundstage-cast-gate').innerText.includes('Charcoal tailored atelier wool coat'),
    {{ timeout: 5000 }}
  );

  const dumbleVaultBtn = page.locator('#soundstage-vault-cast-picker [data-vault-char="Dumble Dior"]');
  if ((await dumbleVaultBtn.count()) !== 1) {{
    throw new Error('Expected Dumble Dior in #soundstage-vault-cast-picker');
  }}
  await dumbleVaultBtn.click();
  await page.waitForFunction(
    () => document.querySelector('#soundstage-cast-gate').innerText.includes('silk monogram wizard robe'),
    {{ timeout: 5000 }}
  );
  if (!observedEndpoints.includes('POST /api/characters/save')) {{
    throw new Error('Expected POST /api/characters/save before vault cast hydration');
  }}

  // 4. Enable Manual 3x3 Storyboard Gate switch & Draw 3x3 Storyboard
  const manualSwitch = page.locator('#soundstage-cast-toggle-manual-boards');
  if ((await manualSwitch.getAttribute('aria-checked')) !== 'true') {{
    await manualSwitch.click();
  }}
  if ((await manualSwitch.getAttribute('aria-checked')) !== 'true') {{
    throw new Error('Expected #soundstage-cast-toggle-manual-boards aria-checked=true');
  }}

  await page.click('#soundstage-btn-approve-cast');
  await page.waitForSelector('#soundstage-boards-gate', {{ timeout: 10000 }});

  // Verify all 9 canonical tiles 1.1..3.3 & Human-Free Macro isolation badges on 1.3, 2.2, 3.3
  const expectedShots = ['1.1', '1.2', '1.3', '2.1', '2.2', '2.3', '3.1', '3.2', '3.3'];
  const humanFreeShots = new Set(['1.3', '2.2', '3.3']);
  for (const sid of expectedShots) {{
    const card = page.locator(`[data-board-shot="${{sid}}"]`);
    if ((await card.count()) !== 1) throw new Error('Missing storyboard tile ' + sid);
    const txt = await card.innerText();
    if (humanFreeShots.has(sid)) {{
      if (!txt.includes('Human-Free Macro (@Image4 Only)')) {{
        throw new Error('Expected Human-Free Macro badge on shot ' + sid + ', got: ' + txt);
      }}
    }} else {{
      if (!txt.includes('Lead Cast (@Image3)')) {{
        throw new Error('Expected Lead Cast (@Image3) badge on shot ' + sid + ', got: ' + txt);
      }}
    }}
  }}

  // Single-tile Redraw Frame on shot 2.2
  const boardsCountBeforeRedraw = observedEndpoints.filter((x) => x === 'POST /api/soundstage/boards').length;
  await page.fill('input[aria-label="Director note for shot 2.2"]', 'Tighter macro glint along obsidian fluting');
  await page.click('[data-redraw-shot="2.2"]');
  await page.waitForFunction(
    () => !document.querySelector('[data-redraw-shot="2.2"]').disabled,
    {{ timeout: 8000 }}
  );
  const boardsCountAfterRedraw = observedEndpoints.filter((x) => x === 'POST /api/soundstage/boards').length;
  if (boardsCountAfterRedraw !== boardsCountBeforeRedraw + 1) {{
    throw new Error('Expected single-tile redraw POST /api/soundstage/boards');
  }}

  // 5. Roll Cameras (Live SSE Filming) -> Auto-transition to Stage 7 Premiere Room
  await page.click('#soundstage-btn-roll-cameras');
  await page.waitForSelector('#soundstage-premiere-view', {{ timeout: 30000 }});
  await page.waitForSelector('#soundstage-premiere-video', {{ timeout: 10000 }});

  if (!observedEndpoints.some((e) => e.endsWith('/events'))) {{
    throw new Error('Expected SSE GET /api/soundstage/{{run_id}}/events during filming');
  }}

  // 6. Switch 30s Master (16:9) -> 15s Cutdown (9:16) -> 6s Bumper (9:16) format tabs
  const statusAfterFilm = await (await page.request.get(`http://127.0.0.1:{port}/api/soundstage/${{originalRunId}}/status`)).json();
  const url30s = await page.getAttribute('#soundstage-premiere-video', 'data-deliverable-url');
  if (!url30s || !url30s.includes('30s_16x9_master') || url30s !== statusAfterFilm.deliverables.master_30s_16x9_url) {{
    throw new Error('Expected 30s deliverable URL matching master_30s_16x9_url, got: ' + url30s);
  }}
  await page.click('#soundstage-tab-15s');
  await page.waitForFunction(
    () => document.querySelector('#soundstage-premiere-video').getAttribute('data-format') === '15s',
    {{ timeout: 3000 }}
  );
  const url15s = await page.getAttribute('#soundstage-premiere-video', 'data-deliverable-url');
  if (!url15s || !url15s.includes('15s_9x16_cutdown') || url15s !== statusAfterFilm.deliverables.cutdown_15s_9x16_url) {{
    throw new Error('Expected 15s deliverable URL matching cutdown_15s_9x16_url, got: ' + url15s);
  }}
  await page.click('#soundstage-tab-6s');
  await page.waitForFunction(
    () => document.querySelector('#soundstage-premiere-video').getAttribute('data-format') === '6s',
    {{ timeout: 3000 }}
  );
  const url6s = await page.getAttribute('#soundstage-premiere-video', 'data-deliverable-url');
  if (!url6s || !url6s.includes('6s_9x16_bumper') || url6s !== statusAfterFilm.deliverables.bumper_6s_9x16_url) {{
    throw new Error('Expected 6s deliverable URL matching bumper_6s_9x16_url, got: ' + url6s);
  }}
  await page.click('#soundstage-tab-30s');

  // 7. Sub-Shot NLE Trimmer: bypass 1.2, trim-in +0.25s on 2.1, click Reconform -> 9 to 8 active sub-shots
  const initialSubshotBadge = await page.locator('#soundstage-active-subshot-badge').innerText();
  if (!initialSubshotBadge.includes('9 active sub-shots')) {{
    throw new Error('Expected 9 active sub-shots initially, got: ' + initialSubshotBadge);
  }}
  await page.click('[data-nle-bypass="1.2"]');
  await page.click('[data-nle-trim-in-inc="2.1"]');
  const shot21Text = await page.locator('[data-nle-shot="2.1"]').innerText();
  if (!shot21Text.includes('0.25s – 3.30s · 3.05s')) {{
    throw new Error('Expected live NLE effective window 0.25s – 3.30s · 3.05s on shot 2.1, got: ' + shot21Text);
  }}
  await page.click('#soundstage-btn-reconform');
  await page.waitForFunction(
    () => document.querySelector('#soundstage-active-subshot-badge').innerText.includes('8 active sub-shots'),
    {{ timeout: 15000 }}
  );

  // 8. Single-Line Director Note Surgical Re-Cut on Act 2 (auto-inferred from note!)
  await page.fill('#soundstage-input-director-note', 'Add warm amber rim light in Act 2');
  await page.click('#soundstage-btn-revise');
  await page.waitForFunction(
    () => {{
      const a2 = document.querySelector('[data-act-card="2"]');
      return a2 && a2.getAttribute('data-act-revisions') === '1';
    }},
    {{ timeout: 15000 }}
  );
  const rev1 = await page.getAttribute('[data-act-card="1"]', 'data-act-revisions');
  const rev2 = await page.getAttribute('[data-act-card="2"]', 'data-act-revisions');
  const rev3 = await page.getAttribute('[data-act-card="3"]', 'data-act-revisions');
  if (rev1 !== '0' || rev2 !== '1' || rev3 !== '0') {{
    throw new Error(`Expected revisions Act1=0, Act2=1, Act3=0; got ${{rev1}}, ${{rev2}}, ${{rev3}}`);
  }}

  // 9. Verify Campaign Package (.zip) download endpoint returns HTTP 200 application/zip
  const zipHref = await page.getAttribute('#soundstage-btn-download-zip', 'href');
  if (!zipHref || !zipHref.endsWith('/package.zip')) {{
    throw new Error('Expected /package.zip href on #soundstage-btn-download-zip, got: ' + zipHref);
  }}
  const zipResp = await page.request.get('http://127.0.0.1:{port}' + zipHref);
  if (zipResp.status() !== 200 || !(zipResp.headers()['content-type'] || '').includes('application/zip')) {{
    throw new Error('Expected HTTP 200 application/zip from ' + zipHref + ', got ' + zipResp.status());
  }}

  // 10. Fork a Place Variation ('Milan · Brera'), verify new run_id, parent_run_id badge, and updated sessionName
  await page.click('[data-variation-axis="place"]');
  await page.fill('#soundstage-input-variation-value', 'Milan · Brera');
  await page.click('#soundstage-btn-fork-variation');
  await page.waitForSelector('#soundstage-forked-badge', {{ timeout: 10000 }});
  await page.waitForSelector('#soundstage-boards-gate', {{ timeout: 5000 }});

  const forkedBadgeText = await page.locator('#soundstage-forked-badge').innerText();
  if (!forkedBadgeText.includes('Forked Variation (place)') || !forkedBadgeText.includes('Parent ' + originalRunId)) {{
    throw new Error('Unexpected forked badge text: ' + forkedBadgeText);
  }}
  const forkedHeaderText = await page.locator('#soundstage-production-room').innerText();
  const allRunIds = forkedHeaderText.match(/sstage_[a-f0-9]+/g) || [];
  const forkedRunId = allRunIds[0];
  if (!forkedRunId || forkedRunId === originalRunId) {{
    throw new Error('Expected new forked run_id !== ' + originalRunId + ', got: ' + forkedRunId);
  }}
  const forkedStatusResp = await page.request.get(`http://127.0.0.1:{port}/api/soundstage/${{forkedRunId}}/status`);
  const forkedStatusJson = await forkedStatusResp.json();
  const headerSelectValues = await page.locator('header select').evaluateAll((els) => els.map((e) => e.value));
  const prodSessionBadge = await page.locator('#soundstage-session-badge').innerText();
  const sessionSynced = headerSelectValues.includes(forkedStatusJson.session_name) && prodSessionBadge === forkedStatusJson.session_name;
  if (!forkedStatusJson.session_name.includes('_place_') || !sessionSynced) {{
    throw new Error('Expected top-level studio sessionName to update to ' + forkedStatusJson.session_name + ', got selects=' + JSON.stringify(headerSelectValues) + ' badge=' + prodSessionBadge);
  }}

  // 11. Promote to Mode 2 (Screenplay Storyboard)
  await page.click('[data-stage-tab="premiere"]');
  await page.waitForSelector('#soundstage-premiere-view', {{ timeout: 3000 }});
  await page.click('#soundstage-btn-promote-mode2');
  await page.waitForFunction(
    () => !document.querySelector('#soundstage-production-room') && document.body.innerText.includes('Screenplay'),
    {{ timeout: 5000 }}
  );

  // 12. Test Candidate #2 Backend Persistence Across Boards + Auto-Advance Filming (manualBoardGate = false & 0 flagged frames -> Cast Gate straight to Premiere!)
  await page.click('#btn-mode-soundstage');
  await page.waitForSelector('#soundstage-guided-canvas', {{ timeout: 5000 }});
  await page.click('#soundstage-toggle-guided');
  await page.waitForSelector('#soundstage-express-canvas', {{ timeout: 3000 }});
  await page.getByRole('button', {{ name: /Brera Botanical Aperitif/i }}).click();
  await page.click('#soundstage-btn-make-film-express');
  await page.waitForSelector('#soundstage-cast-gate', {{ timeout: 10000 }});

  const autoHeaderText = await page.locator('#soundstage-production-room').innerText();
  const autoRunMatch = autoHeaderText.match(/sstage_[a-f0-9]+/);
  if (!autoRunMatch) throw new Error('Expected auto-advance run_id in header');
  const autoRunId = autoRunMatch[0];
  const preSelectJson = await (await page.request.get(`http://127.0.0.1:{port}/api/soundstage/${{autoRunId}}/status`)).json();
  const initialCands = preSelectJson.reference_kit.lead_cast_candidates || [];
  if (initialCands.length !== 2 || initialCands[0] === initialCands[1]) {{
    throw new Error('Expected 2 distinct cast candidates on launch');
  }}
  const cand2Expected = initialCands[1];
  await page.click('[data-cast-candidate="2"]');
  await page.waitForFunction(
    () => {{
      const btn2 = document.querySelector('[data-cast-candidate="2"]');
      return btn2 && !btn2.disabled && btn2.getAttribute('aria-pressed') === 'true';
    }},
    {{ timeout: 5000 }}
  );

  const autoSwitch = page.locator('#soundstage-cast-toggle-manual-boards');
  if ((await autoSwitch.getAttribute('aria-checked')) === 'true') {{
    await autoSwitch.click();
  }}
  await page.click('#soundstage-btn-approve-cast');
  await page.waitForSelector('#soundstage-premiere-view', {{ timeout: 30000 }});
  await page.waitForSelector('#soundstage-premiere-video', {{ timeout: 10000 }});
  const postAutoJson = await (await page.request.get(`http://127.0.0.1:{port}/api/soundstage/${{autoRunId}}/status`)).json();
  if (
    postAutoJson.reference_kit.lead_cast_url !== cand2Expected ||
    postAutoJson.plan.lead_character.reference_url !== cand2Expected
  ) {{
    throw new Error('Candidate #2 selection did not persist across 3x3 boards & filming');
  }}
  const autoMasterUrl = await page.getAttribute('#soundstage-premiere-video', 'data-deliverable-url');
  if (!autoMasterUrl || !autoMasterUrl.includes('30s_16x9_master')) {{
    throw new Error('Auto-advance filming failed to land in Premiere with conformed 30s_16x9_master, got: ' + autoMasterUrl);
  }}

  // 13. LOW-4 (3-decimal NLE), HIGH-2 (es.close() + timeout unlock), and MEDIUM-3 (in-flight remount without re-POSTing /run)
  const origEventsHits = observedEndpoints.filter((e) => e === `GET /api/soundstage/${{originalRunId}}/events`).length;
  if (origEventsHits !== 1) throw new Error('Expected exactly 1 SSE connection for originalRunId (no reconnect), got ' + origEventsHits);
  const win3Dec = await page.evaluate(() => computeSubshotEffectiveWindow({{ default_start_sec: 0.125, default_duration_sec: 3.333, trim_in_sec: 0, trim_out_sec: 0 }}));
  if (win3Dec.startSec !== 0.125 || win3Dec.endSec !== 3.458 || win3Dec.durSec !== 3.333) {{
    throw new Error('Expected 3-decimal NLE window, got: ' + JSON.stringify(win3Dec));
  }}

  let simPhase = 'timeout';
  let simRunPosts = 0;
  let timeoutSseHits = 0;
  const inflightSnap = {{ ...postAutoJson, stage: 'filming_acts', progress_pct: 42, deliverables: null }};
  await page.route('**/api/soundstage/run', async (route) => {{
    simRunPosts += 1;
    await route.fulfill({{ status: 200, contentType: 'application/json', body: JSON.stringify(inflightSnap) }});
  }});
  await page.route(`**/api/soundstage/${{autoRunId}}/status`, async (route) => {{
    const bodyObj = simPhase === 'timeout' ? inflightSnap : postAutoJson;
    await route.fulfill({{ status: 200, contentType: 'application/json', body: JSON.stringify(bodyObj) }});
  }});
  await page.route(`**/api/soundstage/${{autoRunId}}/events`, async (route) => {{
    if (simPhase === 'timeout') {{
      timeoutSseHits += 1;
      await route.fulfill({{ status: 200, contentType: 'text/event-stream', body: `event: timeout\\ndata: {{"run_id":"${{autoRunId}}","stage":"filming_acts","progress_pct":42}}\\n\\n` }});
    }} else {{
      await route.fulfill({{ status: 200, contentType: 'text/event-stream', body: `event: complete\\ndata: {{"run_id":"${{autoRunId}}","stage":"completed","progress_pct":100}}\\n\\n` }});
    }}
  }});

  await page.click('[data-stage-tab="filming"]');
  await page.waitForSelector('#soundstage-filming-view', {{ timeout: 3000 }});
  await page.getByRole('button', {{ name: 'Film / Re-Master in 360p' }}).click();
  await page.waitForFunction(
    () => {{
      const alertEl = document.querySelector('[role="alert"]');
      const btn = Array.from(document.querySelectorAll('#soundstage-filming-view button')).find((b) => b.textContent.includes('360p'));
      return alertEl && /timed out/i.test(alertEl.textContent || '') && btn && !btn.disabled;
    }},
    {{ timeout: 5000 }}
  );
  if (timeoutSseHits !== 1) throw new Error('Expected 1 timeout SSE stream without reconnect, got ' + timeoutSseHits);

  simPhase = 'remount';
  const runsBeforeRemount = simRunPosts;
  await page.click('#soundstage-btn-edit-brief');
  await page.waitForSelector('#soundstage-btn-return-production', {{ timeout: 3000 }});
  await page.click('#soundstage-btn-return-production');
  await page.waitForSelector('#soundstage-premiere-view', {{ timeout: 8000 }});
  if (simRunPosts !== runsBeforeRemount) throw new Error('In-flight remount must not re-POST /api/soundstage/run');

  if (pageErrors.length !== 0) {{
    throw new Error('Uncaught browser pageerror(s): ' + pageErrors.join(' | '));
  }}

  console.log('SOUNDSTAGE_TASK5_BROWSER_E2E_OK');
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
        assert res.returncode == 0, f"Playwright Task 5 E2E failed:\n{output}"
        assert "SOUNDSTAGE_TASK5_BROWSER_E2E_OK" in output, (
            f"Expected SOUNDSTAGE_TASK5_BROWSER_E2E_OK marker:\n{output}"
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5.0)
