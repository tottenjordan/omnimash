"""API & Dual-Surface Studio UI tests for OmniMash v2.0 (PR 7)."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from omnimash.api.app import create_app


def test_gate1_batch_default_single_candidate_and_6_seed_contact_sheet() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)

    # Default num_candidates=1 per Q2 Option A
    res_default = client.post(
        "/api/storyboard/gate1-batch",
        json={
            "prompt": "Wide 28mm establishing shot of a neon-lit rain-slicked courtyard",
            "shot_label": "shot_a",
            "session_name": "gate1_valid_session",
        },
    )
    assert res_default.status_code == 200
    data_default = res_default.json()
    assert data_default["success"] is True
    assert len(data_default["candidates"]) == 1
    assert data_default["candidates"][0]["image_size"] == "2K"
    assert data_default["candidates"][0]["seed"] == 4101
    assert data_default["contact_sheet_url"] is None

    # Explicit 6-seed contact sheet batch
    res_six = client.post(
        "/api/storyboard/gate1-batch",
        json={
            "prompt": "Wide 28mm establishing shot of a neon-lit rain-slicked courtyard",
            "shot_label": "shot_a",
            "num_candidates": 6,
            "base_seed": 4101,
            "image_size": "2K",
            "session_name": "gate1_valid_session",
        },
    )
    assert res_six.status_code == 200
    data_six = res_six.json()
    assert data_six["success"] is True
    assert len(data_six["candidates"]) == 6
    seeds = [c["seed"] for c in data_six["candidates"]]
    assert seeds == [4101, 4102, 4103, 4104, 4105, 4106]
    assert all(c["image_size"] == "2K" for c in data_six["candidates"])
    assert data_six["contact_sheet_url"]


def test_gate1_batch_security_session_name_and_guardrail() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)

    bad_sess = client.post(
        "/api/storyboard/gate1-batch",
        json={
            "prompt": "Wide establishing shot",
            "session_name": "../escape_attempt",
        },
    )
    assert bad_sess.status_code == 400

    # Guardrail blocks unsafe prompt
    orig_guardrail = app.state.agent.guardrail
    app.state.agent.guardrail = SimpleNamespace(
        validate_prompt=lambda text: SimpleNamespace(
            is_approved=False,
            rejection_reason="Blocked by test Model Armor guardrail.",
            sanitized_prompt=text,
            deidentified=False,
        )
    )
    try:
        blocked = client.post(
            "/api/storyboard/gate1-batch",
            json={
                "prompt": "Unsafe prompt payload",
                "session_name": "safe_session",
            },
        )
        assert blocked.status_code == 403
        assert "Blocked by test Model Armor guardrail" in blocked.json()["detail"]
    finally:
        app.state.agent.guardrail = orig_guardrail


def test_shot_pair_plan_returns_prelinted_28mm_and_85mm_specs_and_screens_guardrail() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res = client.post(
        "/api/storyboard/shot-pair-plan",
        json={
            "scene_id": "scene_courtyard_01",
            "character_name": "Alchemist",
            "speaker_descriptor": "the tattooed alchemist in dark velvet robes",
            "voice_style": "cold, unhurried, deadpan Glasgow Scottish accent",
            "fixed_character_block": "Weathered jawline, dark velvet overcoat, silver signet ring on left hand",
            "wetness_lighting_block": "Rain-beaded wool shoulders lit by cool sodium archway lamps",
            "matched_location_block": "Wet granite courtyard outside an arched iron gate at twilight",
            "wide_action_summary": "stepping slowly into the archway glow",
            "mcu_spoken_line": "Ten-Seventeen keeps the vault sealed.",
            "narrator_text": "No lock holds forever.",
            "root_note_808": "D1",
            "session_name": "pair_plan_session",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["plan"]["scene_id"] == "scene_courtyard_01"
    assert "28mm" in data["shot_a_keyframe_prompt"]
    assert "85mm" in data["shot_b_keyframe_prompt"]
    assert "Use this image as the starting frame." in data["shot_a_i2v_prompt"]
    assert "Use this image as the starting frame." in data["shot_b_i2v_prompt"]
    assert '"Ten-Seventeen' not in data["shot_b_i2v_prompt"]

    # Guardrail check
    orig_guardrail = app.state.agent.guardrail
    app.state.agent.guardrail = SimpleNamespace(
        validate_prompt=lambda text: SimpleNamespace(
            is_approved=False,
            rejection_reason="Shot pair blocked by guardrail.",
            sanitized_prompt=text,
            deidentified=False,
        )
    )
    try:
        blocked = client.post(
            "/api/storyboard/shot-pair-plan",
            json={
                "character_name": "Alchemist",
                "wide_action_summary": "walking through archway",
            },
        )
        assert blocked.status_code == 403
    finally:
        app.state.agent.guardrail = orig_guardrail


def test_master_3stem_presets_and_security_validation() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)

    for preset in ("trailer", "commercial", "diegetic"):
        res = client.post(
            "/api/storyboard/master-3stem",
            json={
                "session_name": f"master_3stem_{preset}",
                "preset": preset,
                "narrator_text": "1017 <short pause> echoes through the stone hall.",
                "lyria_prompt": "Dark minimalist orchestral trap underscore",
                "bpm_808": 142.0,
                "raw_808_timestamp_sec": 9.78,
                "guillotine_start_sec": 5.5,
                "guillotine_end_sec": 9.75,
            },
        )
        assert res.status_code == 200, f"Preset {preset} failed: {res.text}"
        data = res.json()
        assert data["success"] is True
        assert data["preset"] == preset
        assert data["loudness_report"]["passed_spec"] is True
        assert data["master_video_url"]
        if preset == "trailer":
            assert data["snapped_808_timestamp_sec"] is not None

    bad_session = client.post(
        "/api/storyboard/master-3stem",
        json={"session_name": "../bad", "preset": "trailer"},
    )
    assert bad_session.status_code == 400

    bad_preset = client.post(
        "/api/storyboard/master-3stem",
        json={"session_name": "valid_sess", "preset": "invalid_preset"},
    )
    assert bad_preset.status_code == 400


def test_generate_shot_i2v_delta_only_routing_and_soundstage_compilation_mode() -> None:
    from omnimash.agent.soundstage_runner import get_soundstage_service
    from omnimash.api.soundstage_models import SoundstagePlanRequest, SoundstageRunRequest

    app = create_app(mock_mode=True)
    client = TestClient(app)

    res = client.post(
        "/api/generate-shot",
        json={
            "session_name": "delta_i2v_session",
            "shot_index": 1,
            "action": "He lifts his chin slightly and looks directly into the lens",
            "dialogue": "Every promise leaves a mark.",
            "keyframe_image_url": "https://example.com/anchor_shot.png",
            "compilation_mode": "i2v_delta_only",
            "duration_seconds": 7.0,
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Harry",
                    "description": "Wizard in dark coat",
                    "voice_style": "calm deadpan baritone",
                }
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    compiled = data.get("raw_compiled_prompt", "")
    assert "Use this image as the starting frame." in compiled
    assert "### SCENE INSTRUCTIONS" not in compiled
    assert "### TIMELINE" not in compiled
    assert "says: Every promise leaves a mark" in compiled

    # Verify SoundstageProductionService supports compilation_mode cleanly
    service = get_soundstage_service(app.state.agent)
    plan_res = service.create_plan(
        SoundstagePlanRequest(
            subject="Atelier Kuroda",
            session_name="sstage_delta_mode_test",
            project_name="default_project",
        )
    )
    run_res = service.execute_filming_and_conform(
        SoundstageRunRequest(
            run_id=plan_res.run_id,
            compilation_mode="i2v_delta_only",
        )
    )
    assert run_res.stage == "completed"
    assert run_res.compilation_mode == "i2v_delta_only"
    assert len(run_res.acts) == 3
    assert "Use this image as the starting frame." in run_res.acts[0].compiled_prompt


def test_dual_surface_studio_ui_components_and_8gate_scorecard() -> None:
    from pathlib import Path

    from omnimash.api import app as app_module
    from omnimash.api.app import get_ui_html

    ui_html = get_ui_html()
    templates_dir = Path(app_module.__file__).resolve().parent / "templates"
    prod_jsx = (templates_dir / "soundstage_production.jsx").read_text(encoding="utf-8")
    premiere_jsx = (templates_dir / "soundstage_premiere.jsx").read_text(encoding="utf-8")
    index_html = (templates_dir / "index.html").read_text(encoding="utf-8")

    # 1. Soundstage Gate-1 Contact Sheet Drawer
    assert 'id="soundstage-gate1-drawer"' in prod_jsx
    assert 'id="soundstage-gate1-drawer"' in ui_html
    assert "/api/storyboard/gate1-batch" in prod_jsx or "/api/storyboard/gate1-batch" in ui_html

    # 2. Soundstage Audio Guillotine & SonicMixPreset Panel
    assert 'id="soundstage-audio-guillotine-panel"' in premiere_jsx
    assert 'id="soundstage-audio-guillotine-panel"' in ui_html
    for preset_name in ("trailer", "commercial", "diegetic"):
        assert preset_name in premiere_jsx
    assert "<details" in premiere_jsx and "Advanced DSP" in premiere_jsx
    assert (
        "/api/storyboard/master-3stem" in premiere_jsx or "/api/storyboard/master-3stem" in ui_html
    )

    # 3. Soundstage 8-Gate Scorecard & RemediationActionTier badge
    assert 'id="soundstage-8gate-scorecard"' in premiere_jsx
    assert 'id="soundstage-8gate-scorecard"' in ui_html
    for gate_label in (
        "1. Clean Single Ref",
        "2. Wide Scale 15-20%",
        "3. MCU Intimacy",
        "4. World & Architecture Lock",
        "5. Bilateral Prop Lock",
        "6. 3D Parallax & Syllables",
        "7. Stem Guillotine & Sub-Bass",
        "8. 1080p24 & -14 LUFS",
    ):
        assert gate_label in premiere_jsx
        assert gate_label in ui_html
    assert "RemediationActionTier" in premiere_jsx or "TIER_" in premiere_jsx

    # 4. Mode 1/3 Storyboard UI buttons in index.html
    assert "Gate-1 Contact Sheet (6 Seeds)" in index_html
    assert "3-Stem -14 LUFS Master" in index_html
    assert "/api/storyboard/gate1-batch" in index_html
    assert "/api/storyboard/master-3stem" in index_html
