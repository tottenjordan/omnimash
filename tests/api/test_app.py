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
        "Voice Style (Spectacled Wizard Bruv): Melodic autotune trap flow"
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


def test_journey3_setup_included_character_ids_and_prompt_deduplication():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    chars = [
        {
            "role_id": "char_1",
            "name": "Wizard Harry",
            "reference_url": "gs://bucket/harry.png",
            "wardrobe": "Blue Robe",
            "aesthetic_tags": ["Glasses"],
        },
        {
            "role_id": "char_2",
            "name": "Ron",
            "reference_url": None,
            "wardrobe": "Red Sweater",
            "aesthetic_tags": ["Freckles"],
        },
    ]
    res = client.post(
        "/api/journey3/setup",
        json={
            "master_description": "Wizard Harry and Ron cast spells together in the dungeon",
            "aspect_ratio": "16:9",
            "characters": chars,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    cards = data["shot_cards"]
    assert len(cards) > 0
    card = cards[0]
    assert "included_character_ids" in card
    assert isinstance(card["included_character_ids"], list)
    if "char_1" in card["included_character_ids"]:
        assert "Blue Robe" not in card["image_prompt"]


def test_journey3_keyframe_character_filtering():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    chars = [
        {"role_id": "char_1", "name": "Harry", "description": "Wizard"},
        {"role_id": "char_2", "name": "Ron", "description": "Sidekick"},
    ]
    res = client.post(
        "/api/journey3/keyframe",
        json={
            "session_id": "test_j3_filter",
            "shot_index": 1,
            "image_prompt": "Harry in potions class",
            "characters": chars,
            "included_character_ids": ["char_1"],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    raw_prompt = data["raw_compiled_prompt"]
    assert "Harry" in raw_prompt
    assert "Ron" not in raw_prompt


def test_journey3_generate_shot_character_filtering():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    chars = [
        {"role_id": "char_1", "name": "Harry", "description": "Wizard"},
        {"role_id": "char_2", "name": "Ron", "description": "Sidekick"},
    ]
    res = client.post(
        "/api/journey3/generate-shot",
        json={
            "session_id": "test_j3_gen_filter",
            "shot_index": 1,
            "action_directive": "Harry raises staff",
            "characters": chars,
            "included_character_ids": ["char_1"],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True


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
    assert "j3ProductRef" in UI_HTML
    assert "j3StyleRef" in UI_HTML
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


def test_ui_html_contains_continuation_link_button():
    from omnimash.api.app import UI_HTML

    assert "handleLinkToPrevShot" in UI_HTML
    assert "Continue From Shot #" in UI_HTML
    assert "Inherit previous shot's keyframe image as starting frame anchor" in UI_HTML


def test_journey3_clean_names_and_in_text_image_tag_replacement():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res = client.post(
        "/api/journey3/generate-shot",
        json={
            "session_id": "test_j3_tags",
            "shot_index": 1,
            "action_directive": "Swagrid Tha Plug glides out of the forest",
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Swagrid Tha Plug",
                    "description": "Legendary supplier wizard",
                    "reference_url": "https://storage.googleapis.com/test-bucket/swagrid.jpg",
                }
            ],
            "included_character_ids": ["Role A"],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    compiled = data.get("raw_compiled_prompt", "")
    assert "- Swagrid Tha Plug: (Reference Image: @Image1)" in compiled
    assert "Role A - Swagrid Tha Plug" not in compiled
    assert "Swagrid Tha Plug (@Image1) glides out of the forest" in compiled


def test_journey3_keyframe_excluded_character_reference_url_filtering(monkeypatch):
    from omnimash.api.app import create_app
    from fastapi.testclient import TestClient

    app = create_app(mock_mode=True)
    client = TestClient(app)

    captured_kwargs = {}

    def mock_generate_keyframe_image(self, prompt, **kwargs):
        captured_kwargs.update(kwargs)
        return "https://storage.googleapis.com/test-bucket/keyframe.jpg", "Compiled Keyframe Prompt"

    monkeypatch.setattr(
        "omnimash.engine.omni_client.OmniFlashClient.generate_keyframe_image",
        mock_generate_keyframe_image,
    )

    chars = [
        {"role_id": "Role A", "name": "Harry", "reference_url": "https://storage.googleapis.com/test/refA.jpg"},
        {"role_id": "Role B", "name": "Draco", "reference_url": "https://storage.googleapis.com/test/refB.jpg"},
    ]

    res = client.post(
        "/api/journey3/keyframe",
        json={
            "session_id": "test_j3_ref_filter",
            "shot_index": 1,
            "image_prompt": "Harry and Draco wizard duel",
            "characters": chars,
            "included_character_ids": ["Role A"],
            "reference_image_urls": [
                "https://storage.googleapis.com/test/refA.jpg",
                "https://storage.googleapis.com/test/refB.jpg",
                "https://storage.googleapis.com/test/style.jpg",
            ],
        },
    )

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    passed_ref_urls = captured_kwargs.get("reference_image_urls", [])
    assert "https://storage.googleapis.com/test/refA.jpg" in passed_ref_urls
    assert "https://storage.googleapis.com/test/style.jpg" in passed_ref_urls
    assert "https://storage.googleapis.com/test/refB.jpg" not in passed_ref_urls


def test_journey3_keyframe_fallback_for_stale_included_character_ids():
    from omnimash.api.app import create_app
    from fastapi.testclient import TestClient

    app = create_app(mock_mode=True)
    client = TestClient(app)

    chars = [
        {"role_id": "Role A", "name": "Harry", "description": "Wizard A"},
        {"role_id": "Role B", "name": "Draco", "description": "Wizard B"},
    ]

    res = client.post(
        "/api/journey3/keyframe",
        json={
            "session_id": "test_j3_stale_fallback",
            "shot_index": 1,
            "image_prompt": "Harry and Draco battle in neon alley",
            "characters": chars,
            "included_character_ids": ["Stale_Role_X"],
        },
    )

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    compiled = data.get("raw_compiled_prompt", "")
    assert "Harry" in compiled
    assert "Draco" in compiled or "Rival Wizard" in compiled


def test_journey3_setup_defaults_included_characters_when_action_text_is_generic(monkeypatch):
    from omnimash.prompts.storyboard_agent import StoryboardAgent, StoryboardShot

    def mock_expand_vision(*args, **kwargs):
        return [
            StoryboardShot(
                shot_index=1,
                action="Generic cinematic landscape with misty mountains and rolling fog",
                duration_seconds=5.0,
                start_seconds=0.0,
                end_seconds=5.0,
                summary="Generic Landscape Shot",
                location="Mist Mountains",
                style_lighting="Cinematic 16:9",
                framing_motion="Wide pan",
                audio="Wind blowing",
            )
        ]

    monkeypatch.setattr(StoryboardAgent, "expand_vision", mock_expand_vision)

    app = create_app(mock_mode=True)
    client = TestClient(app)
    chars = [
        {"role_id": "Role X", "name": "Voldemort"},
        {"role_id": "Role Y", "name": "Dumbledore"},
    ]
    res = client.post(
        "/api/journey3/setup",
        json={
            "master_description": "Generic action without explicit names",
            "aspect_ratio": "16:9",
            "characters": chars,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    cards = data["shot_cards"]
    assert len(cards) > 0
    for card in cards:
        assert "included_character_ids" in card
        assert "Role X" in card["included_character_ids"]
        assert "Role Y" in card["included_character_ids"]


def test_ui_html_journey3_character_selection_and_sync_patterns():
    from omnimash.api.app import UI_HTML

    assert "validIncludedChars" in UI_HTML
    assert "characters: j3Characters" in UI_HTML
    assert "updatedRoleIds" in UI_HTML
    assert "selectAllCharactersInShot" in UI_HTML
    assert "Select All" in UI_HTML
    assert "char.name || char.role_id" in UI_HTML
    assert "Character {idx + 1}:" in UI_HTML


def test_project_and_session_management_api_endpoints():
    import base64
    from fastapi.testclient import TestClient
    from omnimash.api.app import create_app

    app = create_app(mock_mode=True)
    client = TestClient(app)

    # 1. GET /api/projects
    res = client.get("/api/projects")
    assert res.status_code == 200
    data = res.json()
    assert "projects" in data
    assert "default_project" in data["projects"]

    # 2. POST /api/projects/create
    res = client.post("/api/projects/create", json={"project_name": "alpha_project"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["project_name"] == "alpha_project"
    assert "projects/alpha_project/.keep" in data["gcs_uri"]

    # Verify project listing includes newly created project
    res = client.get("/api/projects")
    assert "alpha_project" in res.json()["projects"]

    # 3. GET /api/projects/alpha_project/sessions
    res = client.get("/api/projects/alpha_project/sessions")
    assert res.status_code == 200
    data = res.json()
    assert "sessions" in data

    # 4. POST /api/projects/alpha_project/sessions/create
    res = client.post(
        "/api/projects/alpha_project/sessions/create",
        json={"session_name": "alpha_session_1"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["project_name"] == "alpha_project"
    assert data["session_name"] == "alpha_session_1"
    assert "projects/alpha_project/sessions/alpha_session_1/.keep" in data["gcs_uri"]

    # Verify session listing for alpha_project
    res = client.get("/api/projects/alpha_project/sessions")
    assert "alpha_session_1" in res.json()["sessions"]

    # 5. POST /api/characters/save with project_name & GET /api/projects/alpha_project/characters
    char_payload = {
        "project_name": "alpha_project",
        "character": {
            "role_id": "Role Alpha",
            "name": "Alpha Wizard",
            "description": "Powerful wizard in alpha project",
        },
        "is_library": False,
    }
    res = client.post("/api/characters/save", json=char_payload)
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert "projects/alpha_project/saved_characters/alpha_wizard.json" in res.json()["gcs_uri"]

    res = client.get("/api/projects/alpha_project/characters")
    assert res.status_code == 200
    chars = res.json()["characters"]
    assert len(chars) >= 1
    assert any(c["name"] == "Alpha Wizard" for c in chars)

    # Test POST /api/characters/save without project_name defaults to default_project
    char_default_payload = {
        "character": {
            "role_id": "Role Default",
            "name": "Default Hero",
            "description": "Hero in default project",
        },
        "is_library": False,
    }
    res_def = client.post("/api/characters/save", json=char_default_payload)
    assert res_def.status_code == 200
    assert res_def.json()["success"] is True
    assert "projects/default_project/saved_characters/default_hero.json" in res_def.json()["gcs_uri"]

    # 6. POST /api/characters/save-sheet with project_name & GET /api/projects/alpha_project/reference-sheets
    dummy_img = base64.b64encode(b"fake_image_bytes").decode("utf-8")
    sheet_payload = {
        "project_name": "alpha_project",
        "image_data": dummy_img,
        "custom_name": "alpha_turnaround",
    }
    res = client.post("/api/characters/save-sheet", json=sheet_payload)
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert "projects/alpha_project" in res.json()["gcs_uri"]

    res = client.get("/api/projects/alpha_project/reference-sheets")
    assert res.status_code == 200
    sheets = res.json()["reference_sheets"]
    assert len(sheets) >= 1
    assert any(s["name"] == "alpha_turnaround" for s in sheets)

    # 7. Test /api/journey3/keyframe & /api/journey3/generate-shot with project_name
    res = client.post(
        "/api/journey3/keyframe",
        json={
            "project_name": "alpha_project",
            "session_id": "alpha_session_1",
            "shot_index": 1,
            "image_prompt": "Wizard casting spell",
        },
    )
    assert res.status_code == 200
    assert res.json()["success"] is True

    res = client.post(
        "/api/journey3/generate-shot",
        json={
            "project_name": "alpha_project",
            "session_id": "alpha_session_1",
            "shot_index": 1,
            "action_directive": "Wizard casting lightning",
        },
    )
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_ui_html_contains_project_and_session_tier_architecture() -> None:
    """Verify UI_HTML contains 2-tier project & session controls and modal elements."""
    assert "activeProject" in UI_HTML
    assert "omnimash_active_project" in UI_HTML
    assert "projectsList" in UI_HTML
    assert "showNewProjectModal" in UI_HTML
    assert "showNewSessionModal" in UI_HTML
    assert "isCreatingProject" in UI_HTML
    assert "isCreatingSession" in UI_HTML
    assert "⏳ Creating Project..." in UI_HTML
    assert "⏳ Creating Session..." in UI_HTML
    assert "disabled={isCreatingProject}" in UI_HTML
    assert "disabled={isCreatingSession}" in UI_HTML
    assert "+ New Project" in UI_HTML
    assert "+ New Session" in UI_HTML
    assert "/api/projects" in UI_HTML
    assert "/api/projects/create" in UI_HTML


def test_journey3_setup_session_manifest_persistence() -> None:
    """Verify /api/journey3/setup saves session manifest to GCS containing presets and characters."""
    app = create_app(mock_mode=True)
    client = TestClient(app)
    chars = [
        {"role_id": "Role A", "name": "Neo", "reference_url": "https://example.com/neo.jpg"},
        {"role_id": "Role B", "name": "Trinity", "reference_url": "https://example.com/trinity.jpg"},
    ]
    res = client.post(
        "/api/journey3/setup",
        json={
            "project_id": "test_cyber_project",
            "session_id": "test_cyber_session",
            "master_description": "Cyberpunk wizard showdown in Tokyo alley",
            "aspect_ratio": "16:9",
            "style_preset": "Gritty 90s Cyberpunk",
            "image_model": "gemini-3.1-flash-image",
            "enable_safety_sanitization": True,
            "characters": chars,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "manifest_url" in data
    assert data["style_preset"] == "Gritty 90s Cyberpunk"
    assert data["image_model"] == "gemini-3.1-flash-image"
    assert data["enable_safety_sanitization"] is True

    # Inspect stored manifest in mock storage
    storage = app.state.agent.storage
    manifest = storage.get_session_manifest("test_cyber_session", project_id="test_cyber_project")
    assert manifest is not None
    assert manifest["project_id"] == "test_cyber_project"
    assert manifest["session_id"] == "test_cyber_session"
    assert manifest["style_preset"] == "Gritty 90s Cyberpunk"
    assert manifest["image_model"] == "gemini-3.1-flash-image"
    assert manifest["aspect_ratio"] == "16:9"
    assert manifest["enable_safety_sanitization"] is True
    assert len(manifest["characters"]) == 2
    assert manifest["characters"][0]["name"] == "Neo"


def test_ui_html_session_preset_and_character_restoration_hooks() -> None:
    """Verify UI_HTML contains localStorage preset hooks and character auto-restoration setters."""
    assert "omnimash_j3_style_preset" in UI_HTML
    assert "omnimash_aspect_ratio" in UI_HTML
    assert "omnimash_j3_image_model" in UI_HTML
    assert "omnimash_enable_safety_sanitization" in UI_HTML
    assert "omnimash_j3_master_description" in UI_HTML
    assert "omnimash_j3_product_ref" in UI_HTML
    assert "omnimash_j3_style_ref" in UI_HTML

    # Verify project character auto-restoration into Continuity Studio in activeProject useEffect
    assert "setSavedVaultCharacters(data.characters);" in UI_HTML
    assert "setJ3Characters(data.characters);" in UI_HTML
    assert "setCharacters(data.characters);" in UI_HTML


def test_ui_html_saved_character_turnaround_sheets_and_quick_select() -> None:
    """Verify UI_HTML contains turnaround sheet quick-select dropdown and vault gallery section."""
    assert "savedVaultReferenceSheets" in UI_HTML
    assert "Select from Saved Turnaround Sheets..." in UI_HTML
    assert "Saved Character Turnaround Sheets" in UI_HTML
    assert "➕ Apply to Character..." in UI_HTML


def test_ui_html_reset_roster_button_and_cleanup_handlers() -> None:
    """Verify UI_HTML contains the Reset Roster button and roster cleanup handlers."""
    assert "Reset Roster" in UI_HTML
    assert "handleResetRoster" in UI_HTML
    assert "handleCreateProject" in UI_HTML
    assert "handleCreateNewSession" in UI_HTML
    assert "setJ3Characters([])" in UI_HTML
    assert "setCharacters([])" in UI_HTML


