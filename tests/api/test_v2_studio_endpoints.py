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
    assert 'id="mode1-gate1-contact-sheet-panel"' in index_html
    assert 'id="mode3-gate1-contact-sheet-panel"' in index_html
    assert "handleSelectPreset" in premiere_jsx
    assert "soundstage-dsp-enable-guillotine" in premiere_jsx
    assert "onSetError(errMsg)" in prod_jsx


def test_master_3stem_live_gcs_media_proxy_download_disallowed_bucket_and_upload_failure(
    monkeypatch,
) -> None:
    from omnimash.audio import LoudnessReport

    app = create_app(mock_mode=True)
    agent = app.state.agent
    agent.mock_mode = False

    downloaded_uris: list[str] = []
    uploaded_calls: list[tuple[str, str]] = []

    class _FakeStorage:
        bucket_name = "omnimash-media-hybrid-vertex"
        mock_mode = False

        def download_blob_bytes(self, gs_uri: str) -> tuple[bytes, str]:
            downloaded_uris.append(gs_uri)
            return (b"fake_live_mp4_bytes", "video/mp4")

        def upload_file(self, local_path: str, dest: str) -> str:
            uploaded_calls.append((local_path, dest))
            return f"gs://{self.bucket_name}/{dest}"

        def get_gcs_uri(self, blob_name: str) -> str:
            return f"gs://{self.bucket_name}/{blob_name}"

    agent.storage = _FakeStorage()

    class _FakeMasteringEngine:
        def __init__(self, mock_mode: bool | None = None) -> None:
            self.mock_mode = mock_mode

        def mix_and_master_scene(self, **kwargs) -> LoudnessReport:
            with open(kwargs["output_video_path"], "wb") as f:
                f.write(b"mastered_live_bytes")
            assert kwargs["video_path"].endswith(".mp4")
            return LoudnessReport(
                integrated_lufs=-14.0,
                true_peak_dbtp=-1.0,
                lra_lu=6.0,
                threshold_lufs=-24.0,
                target_offset_lu=0.0,
                passed_spec=True,
            )

    monkeypatch.setattr(
        "omnimash.api.routers.storyboard.ThreeStemMasteringEngine",
        _FakeMasteringEngine,
    )
    monkeypatch.setattr(
        "omnimash.api.routers.storyboard.GeminiTTSClient",
        lambda mock_mode=False: SimpleNamespace(
            synthesize_narrator_stem=lambda **kw: SimpleNamespace(duration_seconds=3.2)
        ),
    )
    monkeypatch.setattr(
        "omnimash.api.routers.storyboard.LyriaClient",
        lambda mock_mode=False: SimpleNamespace(
            generate_score=lambda **kw: SimpleNamespace(model_id="lyria-3-clip-preview")
        ),
    )

    client = TestClient(app)

    # Valid /api/media-proxy?uri=gs://omnimash-media-hybrid-vertex/...
    res_ok = client.post(
        "/api/storyboard/master-3stem",
        json={
            "session_name": "live_proxy_session",
            "video_path": "/api/media-proxy?uri=gs%3A%2F%2Fomnimash-media-hybrid-vertex%2Fsessions%2Fs1%2Fmaster.mp4",
            "preset": "commercial",
        },
    )
    assert res_ok.status_code == 200, res_ok.text
    assert downloaded_uris == ["gs://omnimash-media-hybrid-vertex/sessions/s1/master.mp4"]
    assert len(uploaded_calls) == 1
    assert res_ok.json()["master_video_url"].startswith("/api/media-proxy?uri=gs%3A%2F%2F")

    # Disallowed bucket -> HTTP 403
    res_forbidden = client.post(
        "/api/storyboard/master-3stem",
        json={
            "session_name": "live_proxy_session",
            "video_path": "gs://evil-bucket/x.mp4",
            "preset": "commercial",
        },
    )
    assert res_forbidden.status_code == 403

    # Upload failure in mock_mode=False -> HTTP 500 (never silent mock.mp4 fallback)
    agent.storage.upload_file = lambda local_path, dest: ""
    res_upload_fail = client.post(
        "/api/storyboard/master-3stem",
        json={
            "session_name": "live_proxy_session",
            "video_path": "gs://omnimash-media-hybrid-vertex/sessions/s1/master.mp4",
            "preset": "commercial",
        },
    )
    assert res_upload_fail.status_code == 500


def test_gate1_batch_rejects_traversal_shot_label_and_shot_pair_rejects_bad_scene_id() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)

    bad_label = client.post(
        "/api/storyboard/gate1-batch",
        json={
            "prompt": "Wide establishing shot",
            "shot_label": "../../arbitrary/path",
            "session_name": "valid_session",
        },
    )
    assert bad_label.status_code == 400

    bad_scene = client.post(
        "/api/storyboard/shot-pair-plan",
        json={
            "scene_id": "../bad_scene",
            "character_name": "Alchemist",
            "wide_action_summary": "stepping forward",
        },
    )
    assert bad_scene.status_code == 400


def test_master_3stem_diegetic_without_guillotine_bounds_leaves_guillotine_none(
    monkeypatch,
) -> None:
    from omnimash.audio import LoudnessReport

    app = create_app(mock_mode=True)
    captured_guillotine: list[object] = []

    class _SpyMasteringEngine:
        def __init__(self, mock_mode: bool | None = None) -> None:
            self.mock_mode = mock_mode

        def mix_and_master_scene(self, **kwargs) -> LoudnessReport:
            captured_guillotine.append(kwargs.get("guillotine"))
            with open(kwargs["output_video_path"], "wb") as f:
                f.write(b"mock_master")
            return LoudnessReport(
                integrated_lufs=-14.0,
                true_peak_dbtp=-1.0,
                lra_lu=7.5,
                threshold_lufs=-24.0,
                target_offset_lu=0.0,
                passed_spec=True,
            )

    monkeypatch.setattr(
        "omnimash.api.routers.storyboard.ThreeStemMasteringEngine",
        _SpyMasteringEngine,
    )

    client = TestClient(app)
    res = client.post(
        "/api/storyboard/master-3stem",
        json={
            "session_name": "diegetic_test",
            "preset": "diegetic",
            "lyria_prompt": "Subtle ambient underscore",
        },
    )
    assert res.status_code == 200
    assert captured_guillotine == [None]
