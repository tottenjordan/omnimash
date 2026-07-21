from fastapi.testclient import TestClient
from omnimash.api.app import create_app


def test_full_e2e_flow() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)

    # 1. Initial clip generation
    resp1 = client.post(
        "/api/generate",
        json={
            "user_id": "usr_prod",
            "project_id": "prj_mashup",
            "prompt": "Severus Snape in 90s rap video",
            "clip_index": 0,
        },
    )
    assert resp1.status_code == 200
    turn1 = resp1.json()
    assert turn1["success"] is True
    turn_id_1 = turn1["turn_id"]

    # 2. Conversational diff branching
    resp2 = client.post(
        "/api/generate",
        json={
            "user_id": "usr_prod",
            "project_id": "prj_mashup",
            "prompt": "Add diamond chains and green neon lights",
            "clip_index": 0,
            "parent_turn_id": turn_id_1,
        },
    )
    assert resp2.status_code == 200
    turn2 = resp2.json()
    assert turn2["success"] is True
    assert turn2["turn_id"] != turn_id_1

    # 3. Test UI static / dashboard endpoint
    resp_ui = client.get("/")
    assert resp_ui.status_code == 200
    assert "OmniMash" in resp_ui.text


def test_e2e_commit_and_reanchor_pipeline() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)
    r1 = client.post(
        "/api/generate",
        json={
            "user_id": "u_e2e",
            "project_id": "p_e2e",
            "prompt": "Initial",
            "clip_index": 0,
        },
    )
    t1 = r1.json()["turn_id"]

    t_prev = t1
    for i in range(3):
        r = client.post(
            "/api/generate",
            json={
                "user_id": "u_e2e",
                "project_id": "p_e2e",
                "prompt": f"Edit {i}",
                "clip_index": 0,
                "parent_turn_id": t_prev,
            },
        )
        t_prev = r.json()["turn_id"]
        if i == 2:
            assert r.json()["status"] == "COMMIT_RECOMMENDED"

    rc = client.post(
        "/api/commit",
        json={
            "user_id": "u_e2e",
            "project_id": "p_e2e",
            "turn_id": t_prev,
            "next_prompt": "Reanchored turn",
        },
    )
    assert rc.json()["status"] == "REANCHORED"
    assert rc.json()["depth"] == 0


def test_e2e_compiled_prompt_generation() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/generate",
        json={
            "user_id": "u_comp",
            "project_id": "p_comp",
            "prompt": "Snape in 90s rap video",
            "clip_index": 0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "video_url" in data


def test_e2e_delta_prompt_generation_with_lock() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)
    # Turn 1
    r1 = client.post(
        "/api/generate",
        json={
            "user_id": "u_delta",
            "project_id": "p_delta",
            "prompt": "Snape 90s rap",
            "clip_index": 0,
        },
    )
    assert r1.status_code == 200
    t1_id = r1.json()["turn_id"]

    # Turn 2: Follow-up delta edit
    r2 = client.post(
        "/api/generate",
        json={
            "user_id": "u_delta",
            "project_id": "p_delta",
            "prompt": "make his chain bigger",
            "clip_index": 0,
            "parent_turn_id": t1_id,
        },
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["success"] is True
    assert data2["depth"] == 1


def test_e2e_youtube_reference_url_generation() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/generate",
        json={
            "user_id": "u_yt",
            "project_id": "p_yt",
            "prompt": "DumbleDior dropping bars",
            "clip_index": 0,
            "reference_url": "https://www.youtube.com/watch?v=sample_beat",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["video_url"] is not None


def test_e2e_audio_stem_and_on_screen_text_generation() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/generate",
        json={
            "user_id": "u_stem",
            "project_id": "p_stem",
            "prompt": "Voldemort with drill beat",
            "clip_index": 0,
            "reference_url": "https://www.youtube.com/watch?v=voldy",
            "audio_stem": "140 BPM UK Drill 808s and sliding bass",
            "on_screen_text": "VOLDY 1994 DISSTRACK",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["video_url"] is not None


def test_e2e_voiceover_and_silent_video_generation() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)

    # 1. Voiceover / Multi-Subject Dialogue
    res1 = client.post(
        "/api/generate",
        json={
            "user_id": "u_vo",
            "project_id": "p_vo",
            "prompt": "Snape and Harry",
            "clip_index": 0,
            "voiceover": 'Snape: "Potter, explain." / Harry: "It was the beat!"',
        },
    )
    assert res1.status_code == 200
    assert res1.json()["success"] is True

    # 2. Silent Video
    res2 = client.post(
        "/api/generate",
        json={
            "user_id": "u_silent",
            "project_id": "p_silent",
            "prompt": "Silent Snape walking",
            "clip_index": 0,
            "is_silent": True,
        },
    )
    assert res2.status_code == 200
    assert res2.json()["success"] is True


def test_e2e_generate_includes_reference_analysis_and_raw_prompt() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/generate",
        json={
            "user_id": "u_diag",
            "project_id": "p_diag",
            "prompt": "Snape 90s rap",
            "clip_index": 0,
            "reference_url": "https://www.youtube.com/watch?v=sample",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "reference_analysis" in data
    assert "raw_compiled_prompt" in data
    assert data["reference_analysis"] is not None


def test_e2e_custom_session_name_gcs_mapping() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/generate",
        json={
            "user_id": "u_custom",
            "project_id": "p_custom",
            "prompt": "Snape in 90s rap video",
            "clip_index": 0,
            "session_name": "dripwarts_vol1",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True


def test_api_research_endpoint() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/research",
        json={
            "subject": "Harry Potter and Draco Malfoy",
            "aesthetic": "Atlanta Trap Disstrack",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "Dripwarts" in data["synopsis"]
    assert len(data["suggested_props"]) > 0
    assert data["vibe_intensity"] == 75
    assert "Trap" in data["suggested_audio"] or "808" in data["suggested_audio"]


def test_api_extract_reference_endpoint() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/extract-reference",
        json={
            "url": "https://www.youtube.com/watch?v=sample_beat",
            "session_name": "test_sess",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["video_title"] == "Reference Beat & Character Baseline"
    assert data["detected_bpm"] == 120
    assert len(data["extracted_keyframes"]) >= 3


def test_e2e_directors_studio_3_act_flow() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)
    # Act 1: Research Clash
    r1 = client.post(
        "/api/research",
        json={"subject": "Harry & Draco", "aesthetic": "Atlanta Trap"},
    )
    assert r1.status_code == 200
    research = r1.json()

    # Act 2 & 3: Generate Video with Drip Props & Session Name
    r2 = client.post(
        "/api/generate",
        json={
            "user_id": "usr_studio",
            "project_id": "prj_studio",
            "prompt": "Trapwarts trailer",
            "session_name": "trapwarts_vol1",
            "clip_index": 0,
            "voiceover": research["suggested_dialogue"],
        },
    )
    assert r2.status_code == 200
    assert r2.json()["success"] is True


def test_dashboard_ui_html_features() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    # 1. Autoplay removed from video element
    assert "autoPlay" not in html

    # 2. Act 3 prompt viewer inspection box present
    assert "Final Generation Prompt (Active Version)" in html

    # 3. Act 1 character aesthetic tag manager present
    assert "Character Style Signifiers" in html or "Character Aesthetic Tags" in html
    assert "aesthetic_tags" in html

    # 4. Act 3 Save Final Master and Extend Scene UI present
    assert "Stitch & Save Master" in html
    assert "Extend Video / Next Scene" in html
    assert "/api/save-final" in html
    assert "/api/extend-scene" in html

    # 5. Act 1 Voice style and vocal delivery controls present
    assert "Voice Style & Accent" in html
    assert "Vocal Delivery / Voiceover Style" in html
    assert "[AUDIO & VOCAL DIRECTION]" in html

    # 6. Top header 1-click New Project / Start Over reset button present
    assert "New Project" in html or "Start Over" in html

    # 7. Character Vault & Saved Library features present
    assert "Character Vault" in html
    assert "Save to Vault" in html
    assert "Save Cast Roster" in html

    # 8. Act 3 Stitch & Combine Selected Clips UI present
    assert "Stitch & Combine Selected Clips" in html
    assert "/api/stitch-clips" in html
