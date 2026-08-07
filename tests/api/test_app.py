from fastapi.testclient import TestClient
from omnimash.api.app import (
    UI_HTML,
    GenerateRequest,
    GenerateShotRequest,
    StitchMasterRequest,
    create_app,
)


def test_api_generate_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    response = client.post(
        "/api/generate",
        json={
            "user_id": "usr_test",
            "project_id": "prj_test",
            "prompt": "Snape 90s rap video",
            "clip_index": 0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "video_url" in data


def test_api_commit_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    gen_res = client.post(
        "/api/generate",
        json={
            "user_id": "usr_c",
            "project_id": "prj_c",
            "prompt": "Snape rap",
            "clip_index": 0,
        },
    )
    turn_id = gen_res.json()["turn_id"]

    commit_res = client.post(
        "/api/commit",
        json={
            "user_id": "usr_c",
            "project_id": "prj_c",
            "turn_id": turn_id,
            "next_prompt": "Continue with lasers",
        },
    )
    assert commit_res.status_code == 200
    data = commit_res.json()
    assert data["success"] is True
    assert data["status"] == "REANCHORED"
    assert data["depth"] == 0


def test_save_final_master_and_extend_scene_endpoints():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res_save = client.post(
        "/api/save-final",
        json={
            "session_name": "trap_or_die_v1",
            "video_url": "/static/rendered/mock.mp4",
            "master_title": "official_rap_battle_master",
        },
    )
    assert res_save.status_code == 200
    data_save = res_save.json()
    assert data_save["success"] is True
    assert "final_masters" in data_save["gcs_uri"]
    assert "official_rap_battle_master.mp4" in data_save["gcs_uri"]

    gen_res = client.post(
        "/api/generate",
        json={
            "user_id": "usr_ext",
            "project_id": "prj_ext",
            "session_name": "trap_or_die_v1",
            "prompt": "Harry rap battle",
            "clip_index": 0,
        },
    )
    turn_id = gen_res.json()["turn_id"]

    res_extend = client.post(
        "/api/extend-scene",
        json={
            "session_name": "trap_or_die_v1",
            "turn_id": turn_id,
            "next_scene_action": "Harry drops the mic and walks away",
            "dialogue": "I'm out!",
            "active_roles": ["Role A"],
        },
    )
    assert res_extend.status_code == 200
    data_extend = res_extend.json()
    assert data_extend["success"] is True
    assert data_extend["video_url"] is not None


def test_api_generate_and_extend_scene_with_vocal_delivery_and_voice_style():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    gen_res = client.post(
        "/api/generate",
        json={
            "user_id": "usr_vocal",
            "project_id": "prj_vocal",
            "concept": "Harry rap battle",
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Harry Potter",
                    "description": "Young wizard",
                    "voice_style": "Melodic autotune trap flow",
                }
            ],
            "scenes": [
                {
                    "scene_number": 1,
                    "active_roles": ["Role A"],
                    "action": "Cooking potions",
                }
            ],
            "vocal_delivery": "Dynamic studio vocal projection",
            "clip_index": 0,
        },
    )
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["success"] is True
    assert (
        "Voice Style (Role A - Spectacled Wizard Bruv): Melodic autotune trap flow"
        in gen_data["raw_compiled_prompt"]
    )
    assert (
        "Vocal Delivery: Dynamic studio vocal projection"
        in gen_data["raw_compiled_prompt"]
    )

    turn_id = gen_data["turn_id"]
    res_extend = client.post(
        "/api/extend-scene",
        json={
            "session_name": "vocal_session_1",
            "turn_id": turn_id,
            "next_scene_action": "Harry drops mic",
            "vocal_delivery": "Echoing reverberant vocal fadeout",
        },
    )
    assert res_extend.status_code == 200
    assert res_extend.json()["success"] is True


def test_api_save_final_multi_clip_stitching():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    s_name = "api_multi_clip_session"

    g1 = client.post(
        "/api/generate",
        json={
            "user_id": "usr_multi",
            "project_id": "prj_multi",
            "session_name": s_name,
            "prompt": "Clip 1 generation",
            "clip_index": 0,
        },
    )
    assert g1.status_code == 200
    t1_id = g1.json()["turn_id"]

    g2 = client.post(
        "/api/generate",
        json={
            "user_id": "usr_multi",
            "project_id": "prj_multi",
            "session_name": s_name,
            "parent_turn_id": t1_id,
            "prompt": "Clip 2 generation",
            "clip_index": 1,
        },
    )
    assert g2.status_code == 200
    v2_url = g2.json()["video_url"]

    res_save = client.post(
        "/api/save-final",
        json={
            "session_name": s_name,
            "video_url": v2_url,
            "master_title": "api_stitched_master",
        },
    )
    assert res_save.status_code == 200
    data_save = res_save.json()
    assert data_save["success"] is True
    assert "final_masters" in data_save["gcs_uri"]
    assert "api_stitched_master.mp4" in data_save["gcs_uri"]


def test_api_stitch_selected_clips():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res_empty = client.post(
        "/api/stitch-clips",
        json={
            "session_name": "test_stitch_session",
            "clip_urls": [],
            "master_title": "my_stitched_cut",
        },
    )
    assert res_empty.status_code == 400
    assert (
        res_empty.json()["detail"] == "At least one clip URL is required for stitching."
    )

    res_valid = client.post(
        "/api/stitch-clips",
        json={
            "session_name": "test_stitch_session",
            "clip_urls": ["/static/rendered/clip1.mp4", "/static/rendered/clip2.mp4"],
            "master_title": "my_stitched_cut",
        },
    )
    assert res_valid.status_code == 200
    data = res_valid.json()
    assert data["success"] is True
    assert "gcs_uri" in data
    assert "my_stitched_cut.mp4" in data["gcs_uri"]


def test_api_media_proxy():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res_invalid = client.get("/api/media-proxy?uri=https://example.com/image.jpg")
    assert res_invalid.status_code == 400

    res_empty = client.get("/api/media-proxy?uri=gs://bucket_only")
    assert res_empty.status_code == 404

    res_valid = client.get("/api/media-proxy?uri=gs://bucket/test_image.jpg")
    assert res_valid.status_code == 200
    assert res_valid.headers["cache-control"] == "public, max-age=86400"
    assert res_valid.content == b"mock_image_bytes"


def test_api_list_sessions():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.get("/api/sessions")
    assert res.status_code == 200
    data = res.json()
    assert "sessions" in data
    assert "parody_session_1" in data["sessions"]


def test_api_storyboard_expand_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/storyboard/expand",
        json={
            "concept": "Severus Snape in a 90s East Coast boom-bap rap video",
            "style_tone": "Gritty 90s Rap Video",
            "target_duration": 30.0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "shots" in data
    assert len(data["shots"]) == 3
    shot = data["shots"][0]
    assert "shot_index" in shot
    assert "duration_seconds" in shot
    assert "action" in shot
    assert "location" in shot
    assert "style_lighting" in shot
    assert "framing_motion" in shot
    assert "audio" in shot
    assert shot["shot_index"] == 1


def test_api_save_final_with_master_audio():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/save-final",
        json={
            "session_name": "master_audio_session",
            "video_url": "/static/rendered/mock.mp4",
            "master_title": "master_with_audio_track",
            "master_audio_url": "gs://my_bucket/audio_stem.mp3",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "master_with_audio_track.mp4" in data["gcs_uri"]


def test_api_storyboard_expand_with_screenplay_script_and_characters():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/storyboard/expand",
        json={
            "concept": "Wizard battle in Hogwarts classroom",
            "style_tone": "Cinematic Parody",
            "target_duration": 30.0,
            "screenplay_script": "[0-5s] Role A enters the room.\n[5-10s] Role B challenges Role A.",
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Harry",
                    "description": "Young wizard",
                },
                {
                    "role_id": "Role B",
                    "name": "Draco",
                    "description": "Rival wizard",
                },
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "shots" in data
    assert len(data["shots"]) > 0
    shot = data["shots"][0]
    assert "shot_index" in shot
    assert "action" in shot


def test_api_storyboard_keyframe_image_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/storyboard/keyframe-image",
        json={
            "shot_index": 1,
            "action": "Harry casts a levitation spell",
            "location": "Dungeon classroom",
            "style_lighting": "High contrast neon lighting",
            "summary": "Levitation preview",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "keyframe_image_url" in data
    assert data["keyframe_image_url"].startswith("data:image/svg+xml")


def test_api_keyframe_image_with_anchor(monkeypatch):
    captured_kwargs = {}

    def mock_generate_keyframe_image(self, prompt, **kwargs):
        captured_kwargs.update(kwargs)
        captured_kwargs["prompt"] = prompt
        return "https://storage.googleapis.com/test/kf_shot2.png"

    monkeypatch.setattr(
        "omnimash.engine.omni_client.OmniFlashClient.generate_keyframe_image",
        mock_generate_keyframe_image,
    )

    app = create_app(mock_mode=True)
    client = TestClient(app)

    res = client.post(
        "/api/storyboard/keyframe-image",
        json={
            "shot_index": 2,
            "action": "Shot 2 action",
            "anchor_keyframe_url": "https://storage.googleapis.com/test/kf_shot1.png",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["keyframe_image_url"] == "https://storage.googleapis.com/test/kf_shot2.png"
    assert (
        captured_kwargs.get("anchor_keyframe_url")
        == "https://storage.googleapis.com/test/kf_shot1.png"
    )


def test_api_generate_shot_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/generate-shot",
        json={
            "session_name": "shot_test_session",
            "shot_index": 1,
            "shot_directive": "Dramatic close-up of Harry preparing potions",
            "style_lighting": "Gothic neon trap lighting",
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Harry",
                    "description": "Young wizard",
                }
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "video_url" in data
    assert "keyframe_image_url" in data
    assert data["keyframe_image_url"] is not None
    assert "turn_id" in data
    assert data["status"] in ("COMPLETED", "COMMIT_RECOMMENDED")


def test_api_generate_shot_extracts_dialogue_and_voiceover(monkeypatch):
    captured_kwargs = {}
    from omnimash.agent.orchestrator import OmniMashAgent

    original_process_user_turn = OmniMashAgent.process_user_turn

    def mock_process_user_turn(self, *args, **kwargs):
        captured_kwargs.update(kwargs)
        return original_process_user_turn(self, *args, **kwargs)

    monkeypatch.setattr(OmniMashAgent, "process_user_turn", mock_process_user_turn)

    app = create_app(mock_mode=True)
    client = TestClient(app)

    directive_text = (
        "[SHOT DIRECTIVE: Shot 1]\n"
        "- Action / Subject: Arriving at foggy Hogwarts courtyard rapping into microphone wand\n"
        '- Dialogue / Text Overlay: "I been cooking potions since first year. Burrr!"\n'
        "- Audio Soundscape: 140 BPM Heavy 808 Trap"
    )

    res = client.post(
        "/api/generate-shot",
        json={
            "session_name": "dialogue_extract_session",
            "shot_index": 1,
            "shot_directive": directive_text,
            "style_lighting": "Gothic neon trap lighting",
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Harry",
                    "description": "Young wizard",
                }
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["turn_id"] is not None
    assert (
        captured_kwargs.get("voiceover")
        == "I been cooking potions since first year. Burrr!"
    )


def test_generate_shot_preserves_keyframe_image_url(monkeypatch):
    captured_kwargs = {}
    from omnimash.agent.orchestrator import OmniMashAgent

    original_process_user_turn = OmniMashAgent.process_user_turn

    def mock_process_user_turn(self, *args, **kwargs):
        captured_kwargs.update(kwargs)
        return original_process_user_turn(self, *args, **kwargs)

    monkeypatch.setattr(OmniMashAgent, "process_user_turn", mock_process_user_turn)

    app = create_app(mock_mode=True)
    client = TestClient(app)

    res = client.post(
        "/api/generate-shot",
        json={
            "session_name": "keyframe_preserve_session",
            "shot_index": 1,
            "shot_directive": "Test directive",
            "keyframe_image_url": "gs://bucket/keyframe.png",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert captured_kwargs.get("keyframe_image_url") == "gs://bucket/keyframe.png"
    assert data["keyframe_image_url"] == "gs://bucket/keyframe.png"


def test_generate_shot_uses_custom_audio_soundscape(monkeypatch):
    captured_kwargs = {}
    from omnimash.agent.orchestrator import OmniMashAgent

    original_process_user_turn = OmniMashAgent.process_user_turn

    def mock_process_user_turn(self, *args, **kwargs):
        captured_kwargs.update(kwargs)
        return original_process_user_turn(self, *args, **kwargs)

    monkeypatch.setattr(OmniMashAgent, "process_user_turn", mock_process_user_turn)

    app = create_app(mock_mode=True)
    client = TestClient(app)

    directive_text = (
        "[SHOT DIRECTIVE: Shot 2]\n"
        "- Action / Subject: Snape glaring menacingly in potion dungeon\n"
        "- Audio Soundscape: Aggressive 90s boom-bap beat with heavy sub-bass drop and crisp snares"
    )

    res = client.post(
        "/api/generate-shot",
        json={
            "session_name": "audio_soundscape_session",
            "shot_index": 2,
            "shot_directive": directive_text,
            "style_lighting": "Dark dungeon lighting",
            "characters": [
                {
                    "role_id": "Role B",
                    "name": "Snape",
                    "description": "Gothic Potion Master",
                }
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert (
        captured_kwargs.get("audio_stem")
        == "Aggressive 90s boom-bap beat with heavy sub-bass drop and crisp snares"
    )
    assert "Aggressive 90s boom-bap beat" in data.get("raw_compiled_prompt", "")
    assert "90s 808 Trap Beat" not in data.get("raw_compiled_prompt", "")


def test_generate_shot_compiles_four_block_prompt():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/generate-shot",
        json={
            "session_name": "four_block_test_session",
            "shot_index": 1,
            "action": "Harry preparing potions in foggy courtyard",
            "style_lighting": "Gothic neon trap lighting",
            "duration_seconds": 10.0,
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Harry",
                    "description": "Young wizard",
                }
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    compiled = data.get("raw_compiled_prompt", "")
    assert "### SCENE INSTRUCTIONS" in compiled
    assert "### TIMELINE" in compiled
    assert "[0-10s]" in compiled
    assert "[SHOT DIRECTIVE]" not in compiled


def test_generate_shot_keyframe_seed_offsets_prompt_indexes():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/generate-shot",
        json={
            "session_name": "kf_offset_test_session",
            "shot_index": 1,
            "action": "Harry preparing potions in foggy courtyard",
            "keyframe_image_url": "https://example.com/kf.jpg",
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Harry",
                    "description": "Young wizard",
                    "reference_url": "https://example.com/harry.jpg",
                }
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    compiled = data.get("raw_compiled_prompt", "")
    assert "<FIRST_FRAME>@Image1" in compiled
    assert "<IMAGE_REF_0>@Image2" in compiled


def test_ui_html_contains_storyboard_library_controls():
    assert "Save Storyboard" in UI_HTML
    assert "Storyboard Library" in UI_HTML
    assert "/api/storyboards/save" in UI_HTML
    assert "/api/storyboards/load" in UI_HTML
    assert "Remix Styles" in UI_HTML


def test_ui_html_contains_storyboard_workflow_guide():
    assert "Workflow Guide" in UI_HTML
    assert "Stage 1: Concept & Character Roster" in UI_HTML
    assert "Keyframe Chaining" in UI_HTML
    assert "Theatrical Syntax" in UI_HTML


def test_ui_html_contains_safety_sanitization_toggle():
    assert "Safety Sanitization" in UI_HTML
    assert "enableSafetySanitization" in UI_HTML
    assert "enable_safety_sanitization" in UI_HTML


def test_api_generate_with_enable_safety_sanitization_toggle():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res_disabled = client.post(
        "/api/generate",
        json={
            "user_id": "usr_test",
            "project_id": "prj_test",
            "prompt": "Harry Potter casting spells",
            "enable_safety_sanitization": False,
        },
    )
    assert res_disabled.status_code == 200
    assert res_disabled.json()["success"] is True

    res_enabled = client.post(
        "/api/generate",
        json={
            "user_id": "usr_test",
            "project_id": "prj_test",
            "prompt": "Harry Potter casting spells",
            "enable_safety_sanitization": True,
        },
    )
    assert res_enabled.status_code == 200
    assert res_enabled.json()["success"] is True


def test_stitch_master_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/storyboard/stitch_master",
        json={
            "session_id": "test_stitch_master_session",
            "shot_clips": ["/static/rendered/clip1.mp4", "/static/rendered/clip2.mp4"],
            "title_cards": [
                {
                    "title": "Chapter 1",
                    "subtitle": "The Intro",
                    "duration": 3.0,
                    "insert_at": 0,
                }
            ],
            "narrator_audio_paths": ["/static/audio/narrator1.mp3"],
            "background_music_path": "/static/audio/bg_music.mp3",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "master_video_path" in data
    assert "master_video_url" in data


def test_ui_html_contains_simplified_3step_storyboard_workflow():
    assert "Step 1: Visual Concept & Characters" in UI_HTML
    assert "Step 2: Shot Card Workstation" in UI_HTML
    assert "Step 3: Render & Stitch Master Video" in UI_HTML
    assert "Action & Camera" in UI_HTML
    assert "Spoken Dialogue & Voice Style" in UI_HTML
    assert "Title Screen Overlay" in UI_HTML
    assert "Narrator Voiceover" in UI_HTML
    assert "Stitch Master 30–60s Video (With Title Cards & Voiceover)" in UI_HTML
    assert "/api/storyboard/stitch_master" in UI_HTML


def test_api_aspect_ratio_request_models_and_endpoints():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    gen_req = GenerateRequest(prompt="Test", aspect_ratio="9:16")
    assert gen_req.aspect_ratio == "9:16"

    shot_req = GenerateShotRequest(shot_directive="Test", aspect_ratio="1:1")
    assert shot_req.aspect_ratio == "1:1"

    stitch_req = StitchMasterRequest(session_id="test", aspect_ratio="21:9")
    assert stitch_req.aspect_ratio == "21:9"

    res_gen = client.post("/api/generate", json={"prompt": "Aspect Test", "aspect_ratio": "9:16"})
    assert res_gen.status_code == 200

    res_shot = client.post("/api/generate-shot", json={"shot_directive": "Shot aspect test", "aspect_ratio": "1:1"})
    assert res_shot.status_code == 200

    res_stitch = client.post("/api/storyboard/stitch_master", json={"session_id": "test_s", "aspect_ratio": "21:9"})
    assert res_stitch.status_code == 200
    assert res_stitch.json()["status"] == "ok"


def test_journey3_setup_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/journey3/setup",
        json={
            "master_description": "Cyberpunk wizard battle in Tokyo street",
            "aspect_ratio": "16:9",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "shot_cards" in data
    assert len(data["shot_cards"]) > 0
    card = data["shot_cards"][0]
    assert "shot_index" in card
    assert "image_prompt" in card
    assert "action_directive" in card


def test_journey3_keyframe_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/journey3/keyframe",
        json={
            "session_id": "test_j3_session",
            "shot_index": 1,
            "image_prompt": "Wizard stirring cauldrons in neon dungeon",
            "aspect_ratio": "16:9",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "keyframe_image_url" in data
    assert "raw_compiled_prompt" in data
    assert isinstance(data["raw_compiled_prompt"], str)


def test_journey3_generate_shot_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res1 = client.post(
        "/api/journey3/generate-shot",
        json={
            "session_id": "test_j3_session",
            "shot_index": 1,
            "action_directive": "Gaunt wizard puts on a golden velvet blindfold",
            "dialogue_text": "I see all.",
        },
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["success"] is True
    assert "video_url" in data1
    assert "raw_compiled_prompt" in data1
    assert "blindfold" in data1["raw_compiled_prompt"].lower()

    res2 = client.post(
        "/api/journey3/generate-shot",
        json={
            "session_id": "test_j3_session",
            "shot_index": 2,
            "action_directive": "Gaunt wizard raises staff slowly",
            "dialogue_text": "Taste the magic.",
        },
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is True
    assert "raw_compiled_prompt" in data2
    assert "blindfold" in data2["raw_compiled_prompt"].lower()


def test_journey3_stitch_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/journey3/stitch",
        json={
            "session_id": "test_j3_session",
            "shot_clips": ["/static/rendered/clip1.mp4", "/static/rendered/clip2.mp4"],
            "title_cards": [
                {
                    "title": "Journey 3 Master",
                    "subtitle": "Chapter 1",
                    "duration": 3.0,
                    "insert_at": 0,
                }
            ],
            "aspect_ratio": "16:9",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "master_video_path" in data


def test_ui_html_contains_journey3_components():
    assert "Journey 3 - Multi-Shot Continuity Studio" in UI_HTML
    assert "/api/journey3/setup" in UI_HTML
    assert "/api/journey3/keyframe" in UI_HTML
    assert "/api/journey3/generate-shot" in UI_HTML
    assert "/api/journey3/stitch" in UI_HTML
    assert "Cumulative State Inspector" in UI_HTML or "Cumulative Scene State" in UI_HTML


def test_ui_html_syntax_and_tag_balance():
    import re
    match = re.search(r'<script type="text/babel">(.*?)</script>', UI_HTML, re.DOTALL)
    assert match is not None, "UI_HTML must contain a <script type='text/babel'> block"

    babel_js = match.group(1)

    # 1. Remove string content inside double quotes, single quotes, and backticks
    clean_js = re.sub(r'"[^"]*"', '""', babel_js)
    clean_js = re.sub(r"'[^']*'", "''", clean_js)
    clean_js = re.sub(r'`[^`]*`', '``', clean_js, flags=re.DOTALL)
    clean_js = re.sub(r'//.*', '', clean_js)

    # 2. Check JSX tag stack
    tag_pattern = re.compile(r'</?([A-Za-z][A-Za-z0-9.]*)\b[^>]*>')
    lines = clean_js.split("\n")
    stack = []

    for line_idx, line in enumerate(lines, 1):
        for m in tag_pattern.finditer(line):
            full_tag = m.group(0)
            tag_name = m.group(1)

            if full_tag.endswith("/>") or tag_name.lower() in ["img", "input", "br", "hr", "meta", "link"]:
                continue

            if full_tag.startswith("</"):
                if stack and stack[-1][0] == tag_name:
                    stack.pop()
                elif stack:
                    for idx in range(len(stack) - 1, -1, -1):
                        if stack[idx][0] == tag_name:
                            stack = stack[:idx]
                            break
            else:
                stack.append((tag_name, line_idx))

    assert len(stack) == 0, f"Unclosed JSX tags remaining on stack at end of UI_HTML: {stack}"


def test_ui_html_renders_in_browser_without_syntax_error():
    import subprocess
    import os
    skill_dir = "/usr/local/google/home/jordantotten/.gemini/config/skills/playwright-skill"
    test_script = "/usr/local/google/home/jordantotten/.gemini/jetski/brain/3e6e0805-9daf-47da-ae1a-2c3ac07b54e9/scratch/playwright_test_darkblue.js"

    if os.path.exists(skill_dir) and os.path.exists(test_script):
        res = subprocess.run(
            ["node", "run.js", test_script],
            cwd=skill_dir,
            capture_output=True,
            text=True
        )
        output = res.stdout + res.stderr
        assert "BROWSER ERROR:" not in output, f"Browser JavaScript compilation error detected: {output}"


def test_ui_html_journey3_comprehensive_enhancements():
    from omnimash.api.app import UI_HTML
    assert "compileJourney3ShotPromptPreview" in UI_HTML
    assert "lightboxImageUrl" in UI_HTML
    assert "Final Video Generation Prompt (Live 4-Block Compiler)" in UI_HTML
    assert 'const [j3ProductRef, setJ3ProductRef] = useState("");' in UI_HTML
    assert 'const [j3StyleRef, setJ3StyleRef] = useState("");' in UI_HTML
    assert "Storyboard Keyframe Visual Anchor" in UI_HTML
    assert "Click photo to enlarge" in UI_HTML
    assert "j3ImageModel" in UI_HTML
    assert "gemini-3-pro-image" in UI_HTML


def test_ui_html_contains_character_reference_sheet_controls():
    from omnimash.api.app import UI_HTML
    assert "Generate Character Reference Sheet" in UI_HTML
    assert "/api/characters/generate-sheet" in UI_HTML
    assert "/api/characters/save-sheet" in UI_HTML
    assert "Save & Set as Active Character Reference" in UI_HTML
    assert "Character Turnaround Reference Sheet Studio" in UI_HTML


def test_journey3_keyframe_api_accepts_model_style_and_reference_urls():
    from omnimash.api.app import create_app
    from fastapi.testclient import TestClient

    app = create_app(mock_mode=True)
    client = TestClient(app)

    res = client.post(
        "/api/journey3/keyframe",
        json={
            "session_id": "test_j3_session",
            "shot_index": 1,
            "image_prompt": "Wizard in neon dungeon",
            "aspect_ratio": "16:9",
            "reference_image_urls": ["https://storage.googleapis.com/test/char.jpg"],
            "style_preset": "Cinematic Trap Parody",
            "image_model": "gemini-3-pro-image"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "keyframe_image_url" in data
    assert "raw_compiled_prompt" in data
    assert isinstance(data["raw_compiled_prompt"], str)


def test_generate_character_sheet_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res = client.post(
        "/api/characters/generate-sheet",
        json={
            "character_name": "Harry Potter",
            "description": "Young wizard with round glasses",
            "source_image_url": "https://storage.googleapis.com/test-bucket/ref.jpg",
            "aesthetic_tags": ["Red Gucci Tracksuit"],
            "aspect_ratio": "16:9",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "keyframe_image_url" in data
    assert "raw_compiled_prompt" in data
    assert "Harry Potter" in data["raw_compiled_prompt"] or "Red Gucci Tracksuit" in data["raw_compiled_prompt"]
    assert "(Reference Image: @Image1)" in data["raw_compiled_prompt"]


def test_save_character_sheet_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    b64_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    res = client.post(
        "/api/characters/save-sheet",
        json={
            "session_name": "test_sheet_session",
            "image_data": b64_png,
            "custom_name": "Harry Sheet v1.png",
            "set_as_active_reference": True,
            "character_role_id": "Role A",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "gcs_uri" in data
    assert "public_url" in data
    assert "sessions/test_sheet_session/character_sheets/harry_sheet_v1.png" in data["gcs_uri"]
    assert "sessions/test_sheet_session/character_sheets/harry_sheet_v1.png" in data["public_url"]












