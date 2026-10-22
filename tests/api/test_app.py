from typing import Any
from unittest.mock import patch
import pytest
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
    assert "Voice Style (Role A): Melodic autotune trap flow" in gen_data["raw_compiled_prompt"]
    assert "Vocal Delivery: Dynamic studio vocal projection" in gen_data["raw_compiled_prompt"]

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
    assert res_empty.json()["detail"] == "At least one clip URL is required for stitching."

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
    assert captured_kwargs.get("voiceover") == "I been cooking potions since first year. Burrr!"


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
    assert "<FIRST_FRAME>@KeyframeSeed" in compiled
    assert "<IMAGE_REF_0>@Image1" in compiled


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

    res_shot = client.post(
        "/api/generate-shot", json={"shot_directive": "Shot aspect test", "aspect_ratio": "1:1"}
    )
    assert res_shot.status_code == 200

    res_stitch = client.post(
        "/api/storyboard/stitch_master", json={"session_id": "test_s", "aspect_ratio": "21:9"}
    )
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


def test_ui_html_contains_mode3_turn_history_carousel_and_keyframe_lock():
    assert "TurnHistoryCarousel" in UI_HTML
    assert "Turn History" in UI_HTML
    assert "⏪ Branch" in UI_HTML
    assert "🔒 Lock Visual Continuity" in UI_HTML
    assert "Keyframe Seed" in UI_HTML
    assert "/api/diff" in UI_HTML


def test_ui_html_syntax_and_tag_balance():
    import re

    match = re.search(r'<script type="text/babel">(.*?)</script>', UI_HTML, re.DOTALL)
    assert match is not None, "UI_HTML must contain a <script type='text/babel'> block"

    babel_js = match.group(1)

    # 1. Remove string content inside double quotes, single quotes (excluding prose apostrophes), and backticks
    clean_js = re.sub(r"`[^`]*`", "``", babel_js, flags=re.DOTALL)
    clean_js = re.sub(r'"[^"\n]*"', '""', clean_js)
    clean_js = re.sub(r"(?<![A-Za-z0-9])'[^'\n]*'", "''", clean_js)
    clean_js = re.sub(r"//.*", "", clean_js)
    # Neutralize arrow function '=>' so '>' inside attributes does not truncate multi-line tags
    clean_js = clean_js.replace("=>", "==")

    # 2. Check strict LIFO JSX tag stack across full script (including multi-line tags)
    tag_pattern = re.compile(r"</?([A-Za-z][A-Za-z0-9.]*)\b[^>]*>", re.DOTALL)
    stack = []

    for m in tag_pattern.finditer(clean_js):
        full_tag = m.group(0)
        tag_name = m.group(1)
        line_idx = clean_js.count("\n", 0, m.start()) + 1

        if full_tag.endswith("/>") or tag_name.lower() in [
            "img",
            "input",
            "br",
            "hr",
            "meta",
            "link",
        ]:
            continue

        if full_tag.startswith("</"):
            assert stack and stack[-1][0] == tag_name, (
                f"Mismatched closing tag </{tag_name}> at Babel line {line_idx}; "
                f"expected closing tag for <{stack[-1][0]}> (opened at line {stack[-1][1]})"
                if stack
                else f"Unexpected closing tag </{tag_name}> at Babel line {line_idx} with empty stack"
            )
            stack.pop()
        else:
            stack.append((tag_name, line_idx))

    assert len(stack) == 0, f"Unclosed JSX tags remaining on stack at end of UI_HTML: {stack}"


@pytest.mark.slow
@pytest.mark.browser
def test_ui_html_renders_in_browser_without_syntax_error(tmp_path):
    import os
    import subprocess

    skill_dir = "/usr/local/google/home/jordantotten/.gemini/config/skills/playwright-skill"
    if os.path.exists(skill_dir):
        html_file = tmp_path / "ui_check.html"
        html_file.write_text(UI_HTML, encoding="utf-8")
        inline_js = (
            "const { chromium } = require('playwright');"
            "(async () => {"
            "  const browser = await chromium.launch({ headless: true });"
            "  const page = await browser.newPage();"
            "  page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));"
            f"  await page.goto('file://{html_file}', {{ waitUntil: 'domcontentloaded' }});"
            "  await page.waitForFunction(() => {"
            "    const el = document.querySelector('#__next');"
            "    return el && el.innerHTML.length > 1000;"
            "  }, { timeout: 15000 });"
            "  const html = await page.innerHTML('#__next');"
            "  if (html && html.length > 1000) console.log('INNER_HTML_OK');"
            "  await browser.close();"
            "})();"
        )
        res = subprocess.run(
            ["node", "-e", inline_js],
            cwd=skill_dir,
            capture_output=True,
            text=True,
        )
        output = res.stdout + res.stderr
        assert res.returncode == 0, f"Playwright execution failed: {output}"
        assert "BROWSER ERROR:" not in output, (
            f"Browser JavaScript compilation error detected: {output}"
        )
        assert "INNER_HTML_OK" in output, f"React failed to mount into #__next: {output}"


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
    assert "gemini-nano-banana-2.1" in UI_HTML
    assert "gemini-3-pro-image" in UI_HTML


def test_ui_html_contains_character_reference_sheet_controls():
    from omnimash.api.app import UI_HTML

    assert "Generate Character Reference Sheet" in UI_HTML
    assert "/api/characters/generate-sheet" in UI_HTML
    assert "/api/characters/save-sheet" in UI_HTML
    assert "Save & Set as Active Character Reference" in UI_HTML
    assert "Character Turnaround Reference Sheet Studio" in UI_HTML


def test_ui_html_contains_mode2_batch_render_and_card_controls():
    from omnimash.api.app import UI_HTML

    assert "Render All Shots (Batch)" in UI_HTML
    assert "handleRenderAllShots" in UI_HTML
    assert "➕ Add Shot" in UI_HTML or "Add Shot" in UI_HTML
    assert "📋 Duplicate" in UI_HTML
    assert "🗑️ Delete" in UI_HTML


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
            "image_model": "gemini-3-pro-image",
        },
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
    assert (
        "Harry Potter" in data["raw_compiled_prompt"]
        or "Red Gucci Tracksuit" in data["raw_compiled_prompt"]
    )
    assert "(Reference Image: @Image1)" in data["raw_compiled_prompt"]


def test_generate_character_sheet_endpoint_with_style_preset():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res = client.post(
        "/api/characters/generate-sheet",
        json={
            "character_name": "YoTotti",
            "description": "Young tatted wizard",
            "style_preset": "1930s Rubber Hose Toon",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "1930s Rubber Hose Toon" in data["raw_compiled_prompt"]


def test_ui_html_contains_auto_style_character_controls():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert "handleAutoStyleCharacter" in html
    assert "Auto-Style All Characters" in html
    assert "Auto-Style for" in html


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
    assert "- Role A: (Reference Image: @Image1" in compiled
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
        {
            "role_id": "Role A",
            "name": "Harry",
            "reference_url": "https://storage.googleapis.com/test/refA.jpg",
        },
        {
            "role_id": "Role B",
            "name": "Draco",
            "reference_url": "https://storage.googleapis.com/test/refB.jpg",
        },
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
        assert "Role Y" not in card["included_character_ids"]
        assert len(card["included_character_ids"]) <= 1


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
    assert (
        "projects/default_project/saved_characters/default_hero.json" in res_def.json()["gcs_uri"]
    )

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
        {
            "role_id": "Role B",
            "name": "Trinity",
            "reference_url": "https://example.com/trinity.jpg",
        },
    ]
    res = client.post(
        "/api/journey3/setup",
        json={
            "project_id": "test_cyber_project",
            "session_id": "test_cyber_session",
            "master_description": "Cyberpunk wizard showdown in Tokyo alley",
            "aspect_ratio": "16:9",
            "style_preset": "Gritty 90s Cyberpunk",
            "image_model": "gemini-nano-banana-2.1",
            "enable_safety_sanitization": True,
            "characters": chars,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "manifest_url" in data
    assert data["style_preset"] == "Gritty 90s Cyberpunk"
    assert data["image_model"] == "gemini-nano-banana-2.1"
    assert data["enable_safety_sanitization"] is True

    # Inspect stored manifest in mock storage
    storage = app.state.agent.storage
    manifest = storage.get_session_manifest("test_cyber_session", project_id="test_cyber_project")
    assert manifest is not None
    assert manifest["project_id"] == "test_cyber_project"
    assert manifest["session_id"] == "test_cyber_session"
    assert manifest["style_preset"] == "Gritty 90s Cyberpunk"
    assert manifest["image_model"] == "gemini-nano-banana-2.1"
    assert manifest["aspect_ratio"] == "16:9"
    assert manifest["enable_safety_sanitization"] is True
    assert len(manifest["characters"]) == 2
    assert manifest["characters"][0]["name"] == "Neo"

    # Verify legacy "gemini-3.1-flash-image" in persisted manifest or setup request normalizes to "gemini-nano-banana-2.1"
    storage.save_session_manifest(
        session_id="legacy_session",
        manifest_data={"session_id": "legacy_session", "image_model": "gemini-3.1-flash-image"},
        project_id="test_cyber_project",
    )
    hydrated_session = app.state.agent.session_manager.get_or_create_session(
        "usr_default", "test_cyber_project", session_name="legacy_session"
    )
    assert hydrated_session.image_model == "gemini-nano-banana-2.1"

    res_legacy = client.post(
        "/api/journey3/setup",
        json={
            "project_id": "test_cyber_project",
            "session_id": "legacy_setup_session",
            "master_description": "Cyberpunk wizard showdown",
            "image_model": "gemini-3.1-flash-image-preview",
        },
    )
    assert res_legacy.status_code == 200
    assert res_legacy.json()["image_model"] == "gemini-nano-banana-2.1"


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


def test_ui_html_dual_layer_audio_controls() -> None:
    """Verify UI_HTML contains dual-layer audio controls."""
    from omnimash.api.app import UI_HTML

    assert "audio_mode" in UI_HTML
    assert "🌐 Inherit Global" in UI_HTML
    assert "🎵 Custom Shot Beat" in UI_HTML
    assert "🔇 Silent Shot" in UI_HTML
    assert "audioAmbience" in UI_HTML


def test_ui_html_contains_detach_reference_image_and_anchor_badge() -> None:
    """Verify UI_HTML contains ❌ Detach Reference Image button, handleDetachReferenceUrl, and reference anchor badge."""
    from omnimash.api.app import UI_HTML

    assert "handleDetachReferenceUrl" in UI_HTML
    assert "❌ Detach Reference Image" in UI_HTML
    assert "🖼️ Attached Reference Anchor (" in UI_HTML
    assert "(Click ❌ Detach to clear for fresh visuals)" in UI_HTML


def test_journey3_keyframe_error_returns_guardrail_guidance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify /api/journey3/keyframe returns HTTP 400 and guardrail_guidance dictionary when 400 occurs."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    def mock_generate_keyframe_failing(*args: Any, **kwargs: Any) -> Any:
        raise ValueError(
            "400 Policy violation: Input prompt or reference image violated real_people_likeness safety guidelines."
        )

    monkeypatch.setattr(
        app.state.agent.omni_client, "generate_keyframe_image", mock_generate_keyframe_failing
    )

    res = client.post(
        "/api/journey3/keyframe",
        json={
            "shot_index": 0,
            "image_prompt": "Jordan Totten with a Lightsaber",
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Jordan Totten",
                    "reference_url": "https://example.com/jordan.jpg",
                }
            ],
        },
    )
    assert res.status_code == 400
    data = res.json()
    assert "guardrail_guidance" in data
    guidance = data["guardrail_guidance"]
    assert isinstance(guidance, dict)
    assert "triggers" in guidance
    assert "user_guidance" in guidance
    assert "suggested_actions" in guidance


def test_storyboard_keyframe_image_uses_custom_image_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify /api/storyboard/keyframe-image prioritizes explicit image_prompt parameter over auto-generated string."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    received_prompts: list[str] = []

    def mock_gen_kf(prompt: str, *args: Any, **kwargs: Any) -> Any:
        received_prompts.append(prompt)
        return "gs://test-bucket/mock_keyframe.png"

    monkeypatch.setattr(app.state.agent.omni_client, "generate_keyframe_image", mock_gen_kf)

    res = client.post(
        "/api/storyboard/keyframe-image",
        json={
            "shot_index": 1,
            "image_prompt": "Custom user-crafted keyframe prompt for Shot 1",
            "action": "Legacy action description",
            "location": "Legacy location",
            "style_lighting": "Cinematic",
            "summary": "Legacy summary",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["keyframe_image_url"] == "gs://test-bucket/mock_keyframe.png"
    assert len(received_prompts) == 1
    assert "Custom user-crafted keyframe prompt for Shot 1" in received_prompts[0]


def test_ui_html_contains_editable_keyframe_prompt_box() -> None:
    """Verify UI_HTML contains editable Keyframe Image Generation Prompt box on Step 2 shot cards."""
    from omnimash.api.app import UI_HTML

    assert "Keyframe Image Generation Prompt" in UI_HTML
    assert "image_prompt" in UI_HTML


def test_ui_html_contains_clear_video_and_keyframe_handlers() -> None:
    """Verify UI_HTML contains handleClearShotVideo, handleClearShotKeyframe, and clear buttons on shot cards."""
    from omnimash.api.app import UI_HTML

    assert "handleClearShotVideo" in UI_HTML
    assert "handleClearShotKeyframe" in UI_HTML
    assert "Clear Video Clip" in UI_HTML
    assert "Clear Keyframe" in UI_HTML


def test_ui_html_contains_guardrail_guidance_state_and_alert_banner() -> None:
    """Verify UI_HTML contains guardrailGuidance state hook, policy alert banner, and quick-fix buttons."""
    from omnimash.api.app import UI_HTML

    assert "guardrailGuidance" in UI_HTML
    assert "setGuardrailGuidance" in UI_HTML
    assert "Policy Guardrail Alert Banner" in UI_HTML
    assert "user_guidance" in UI_HTML
    assert "⚡ Auto-Abstract Real Names" in UI_HTML
    assert "❌ Detach Reference Photo" in UI_HTML
    assert "Dismiss ❌" in UI_HTML
    assert "handleAutoAbstractRealNames" in UI_HTML
    assert "handleDetachReferencePhoto" in UI_HTML


def test_ui_html_expand_storyboard_passes_and_applies_vision_defaults() -> None:
    """Verify UI_HTML handleExpandStoryboard passes camera_lighting, aesthetic_tags, audio_beat, vocal_delivery, and environment, and maps defaults onto expanded shot cards."""
    from omnimash.api.app import UI_HTML

    assert "camera_lighting: cameraLightingTag" in UI_HTML
    assert "aesthetic_tags: aestheticTags" in UI_HTML
    assert "audio_beat: audioBeat" in UI_HTML
    assert "vocal_delivery: vocalDelivery" in UI_HTML
    assert "environment: environmentTag" in UI_HTML
    assert "framing_motion: s.framing_motion || cameraLightingTag" in UI_HTML


def test_ui_html_contains_mode1_presets_and_compiled_prompt_preview() -> None:
    """Verify UI_HTML contains QUICK_PRESET_TEMPLATES and live compiled prompt preview box."""
    from omnimash.api.app import UI_HTML

    assert "QUICK_PRESET_TEMPLATES" in UI_HTML
    assert "Quick Concept Presets:" in UI_HTML
    assert "🪄 Hip-Hop Wand Shop" in UI_HTML
    assert "⚡ Neon Cyberpunk Rap Battle" in UI_HTML
    assert "preview-box" in UI_HTML
    assert "Live Compiled Prompt Preview (4-Block Meta-Prompt)" in UI_HTML


def test_ui_html_contains_unified_3mode_switcher_and_headers() -> None:
    """Verify UI_HTML contains unified 3-Mode Studio Switcher tabs and standardized Mode Header Card banners."""
    from omnimash.api.app import UI_HTML

    # Switcher tabs & target output badges
    assert "Mode 1: Guided Fine-Tune" in UI_HTML
    assert "Single Video Target" in UI_HTML
    assert "Mode 2: Screenplay Storyboard" in UI_HTML
    assert "Multi-Scene Master Target" in UI_HTML
    assert "Mode 3: Continuity Studio" in UI_HTML
    assert "Conversational Diff Target" in UI_HTML

    # Mode 1 Header Banner
    assert (
        "Step 1: Set Visual Concept &amp; Cast" in UI_HTML
        or "Step 1: Set Visual Concept & Cast" in UI_HTML
    )
    assert (
        "Step 2: Fine-Tune Audio &amp; Beat" in UI_HTML
        or "Step 2: Fine-Tune Audio & Beat" in UI_HTML
    )
    assert (
        "Step 3: Render &amp; Refine Single Video" in UI_HTML
        or "Step 3: Render & Refine Single Video" in UI_HTML
    )

    # Mode 2 Header Banner
    assert "Step 1: Global Production Context" in UI_HTML
    assert "Step 2: Multi-Scene Storyboard Directing" in UI_HTML
    assert "Step 3: Concatenate Master Screening Room" in UI_HTML

    # Mode 3 Header Banner
    assert (
        "Step 1: Master Setup &amp; Roster" in UI_HTML or "Step 1: Master Setup & Roster" in UI_HTML
    )
    assert (
        "Step 2: Sequential Shot Generation &amp; Keyframe Anchors" in UI_HTML
        or "Step 2: Sequential Shot Generation & Keyframe Anchors" in UI_HTML
    )
    assert (
        "Step 3: Turn History &amp; Conversational Diffing" in UI_HTML
        or "Step 3: Turn History & Conversational Diffing" in UI_HTML
    )


def test_ui_html_contains_symmetric_card_grids_and_controls() -> None:
    """Verify UI_HTML contains balanced 2/3-column card grids, standardized card containers, section headers, and unified button styling."""
    from omnimash.api.app import UI_HTML

    # Balanced Grid Containers across modes
    assert "grid grid-cols-1 md:grid-cols-2 gap-6" in UI_HTML
    assert "grid grid-cols-1 lg:grid-cols-3 gap-4" in UI_HTML

    # Standardized Card Containers & Section Headers
    assert "border-gray-800 bg-gray-900/80 backdrop-blur" in UI_HTML
    assert "p-5 rounded-2xl" in UI_HTML
    assert "border-l-4 border-indigo-500 pl-3" in UI_HTML

    # Unified Button Styling (Primary & Secondary)
    assert (
        "bg-gradient-to-r from-blue-600 to-indigo-600 font-bold text-xs py-2 px-4 rounded-xl shadow-md flex items-center justify-center gap-2"
        in UI_HTML
    )
    assert (
        "bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 text-xs py-2 px-3 rounded-xl flex items-center gap-1.5"
        in UI_HTML
    )


def test_ui_html_contains_vision_prompt_sync_controls_across_modes() -> None:
    """Verify UI_HTML contains vision prompt sync buttons, handlers, and diff defaults across Modes 1, 2, and 3."""
    from omnimash.api.app import UI_HTML

    # Mode 1 Guided Mode Sync Button & Handler
    assert "⚡ Sync Intuitive Defaults from Vision Prompt" in UI_HTML
    assert "handleDeconstructConcept" in UI_HTML

    # Mode 2 Storyboard Sync Button & Handler
    assert "⚡ Re-Sync Storyboard Defaults" in UI_HTML
    assert "handleReSyncStoryboardDefaults" in UI_HTML

    # Mode 3 Continuity Studio Diff Defaults
    assert "Make background darker with glowing blue neon" in UI_HTML
    assert "Add heavy 808 bass drop audio cue" in UI_HTML


def test_ui_html_contains_10s_movie_trailer_studio_controls() -> None:
    """Verify UI_HTML contains 10s Movie Trailer preset template button, handler, title card inputs, and narrator voiceover inputs."""
    from omnimash.api.app import UI_HTML

    assert "handleLoadMovieTrailerTemplate" in UI_HTML
    assert "10s Movie Trailer Preset" in UI_HTML
    assert "title_card_text" in UI_HTML
    assert "title_card_subtitle" in UI_HTML
    assert "narrator_text" in UI_HTML
    assert "narrator_voice" in UI_HTML
    assert "blockbuster_movie_trailer" in UI_HTML


def test_character_voice_profile_propagation_to_voice_style() -> None:
    """Verify incoming character payload with voice_profile or voice_style normalizes and propagates to compiled prompt."""
    from omnimash.api.app import create_app
    from fastapi.testclient import TestClient

    app = create_app(mock_mode=True)
    client = TestClient(app)

    payload = {
        "project_name": "voice_test_project",
        "session_id": "voice_session_1",
        "shot_index": 1,
        "action_directive": "YoTotti enters with heavy accent",
        "characters": [
            {
                "role_id": "Role A",
                "name": "YoTotti",
                "description": "Young wizard",
                "voice_profile": "Scottish accent with rapid delivery",
            }
        ],
        "timeline_dialogue": 'YoTotti: "Hello world!"',
        "keyframe_image_url": "http://example.com/keyframe.png",
    }

    res = client.post("/api/journey3/generate-shot", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    prompt = data.get("raw_compiled_prompt", "")
    assert "Scottish accent with rapid delivery" in prompt
    assert "Voice Style (Role A): Scottish accent with rapid delivery" in prompt


def test_ui_html_contains_mode1_dedicated_keyframe_prompt_and_screenplay_inputs() -> None:
    """Verify UI_HTML contains dedicated Keyframe Image Generation Prompt and Screenplay Script inputs for Mode 1."""
    from omnimash.api.app import UI_HTML

    assert "Keyframe Image Generation Prompt" in UI_HTML
    assert "keyframeImagePrompt" in UI_HTML
    assert "Screenplay Script (10s Shot)" in UI_HTML


def test_api_storyboard_draft_batch_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    req_data = {
        "session_name": "draft_batch_session",
        "shots": [
            {
                "shot_index": 1,
                "action": "Harry preparing potions in foggy courtyard",
                "style_lighting": "Gothic neon trap lighting",
                "keyframe_image_url": "https://example.com/kf_test.png",
            },
            {
                "shot_index": 2,
                "action": "Draco stepping out of shadows with iced out chain",
                "style_lighting": "High contrast neon",
            },
        ],
        "variations_per_shot": 2,
        "resolution": "360p",
    }

    res = client.post("/api/storyboard/draft-batch", json=req_data)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["session_name"] == "draft_batch_session"
    assert data["resolution"] == "360p"
    assert data["total_drafts"] == 4
    assert len(data["drafts"]) == 4

    draft1 = data["drafts"][0]
    assert draft1["shot_index"] == 1
    assert draft1["variation_index"] == 0
    assert draft1["resolution"] == "360p"
    assert draft1["status"] in ("COMPLETED", "COMMIT_RECOMMENDED")
    assert draft1["video_url"] is not None
    assert draft1["keyframe_image_url"] == "https://example.com/kf_test.png"

    draft2 = data["drafts"][1]
    assert draft2["shot_index"] == 1
    assert draft2["variation_index"] == 1

    draft3 = data["drafts"][2]
    assert draft3["shot_index"] == 2
    assert draft3["variation_index"] == 0


def test_ui_html_contains_draft_room_studio_controls() -> None:
    """Verify UI_HTML contains 'The Draft Room' studio controls and 4K Master upscale triggers."""
    from omnimash.api.app import UI_HTML

    assert "⚡ The Draft Room" in UI_HTML
    assert "handleGenerateDraftBatch" in UI_HTML
    assert "handleUpscaleDraftTo4K" in UI_HTML
    assert "🏆 Upgrade to 4K Master" in UI_HTML


def test_api_upload_motion_reference_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/motion-reference/upload",
        json={
            "input_video_path": "static/uploads/sample.mp4",
            "start_sec": 1.5,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "clip_path" in data
    assert data["clip_path"].endswith("_motion_3s.mp4")


def test_api_generate_shot_with_motion_reference_clip():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    with patch.object(
        app.state.agent,
        "process_user_turn",
        wraps=app.state.agent.process_user_turn,
    ) as mock_turn:
        res = client.post(
            "/api/generate-shot",
            json={
                "session_name": "test_motion_ref_session",
                "shot_index": 1,
                "action": "Dancer doing flair spin",
                "motion_reference_clip": "static/uploads/motion_ref_3s.mp4",
            },
        )
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert mock_turn.call_count == 1
        _, kwargs = mock_turn.call_args
        assert kwargs.get("motion_reference_clip") == "static/uploads/motion_ref_3s.mp4"


def test_ui_html_contains_motion_reference_controls() -> None:
    """Verify UI_HTML contains motion reference clip state, upload handler, and motion ref badge elements."""
    from omnimash.api.app import UI_HTML

    assert "motionReferenceClip" in UI_HTML
    assert "handleUploadMotionReference" in UI_HTML
    assert "/api/motion-reference/upload" in UI_HTML
    assert "📹 Motion Reference Clip (3s MP4 Video)" in UI_HTML
    assert "Motion Ref Active" in UI_HTML


def test_ui_html_contains_stage2_dual_keyframe_controls() -> None:
    """Verify UI_HTML contains Stage 2 ending keyframe anchor (<LAST_FRAME>) controls and camera transition presets."""
    from omnimash.api.app import UI_HTML

    assert "last_frame_image_url" in UI_HTML
    assert "<LAST_FRAME>" in UI_HTML
    assert "Whip-Pan" in UI_HTML
    assert "Dolly Zoom" in UI_HTML
    assert "360 Orbit" in UI_HTML
    assert "Seamless Loop" in UI_HTML
    assert "Upload" in UI_HTML and "last_frame_image_url" in UI_HTML
    assert "Clear" in UI_HTML
    assert "Ending Keyframe Image URL" in UI_HTML
    assert "Image #2: Ending Keyframe" in UI_HTML


def test_journey3_generate_shot_seamless_loop():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    with patch.object(
        app.state.agent,
        "process_user_turn",
        wraps=app.state.agent.process_user_turn,
    ) as mock_turn:
        res = client.post(
            "/api/journey3/generate-shot",
            json={
                "session_id": "test_loop_session",
                "shot_index": 1,
                "action_directive": "YoTotti in seamless spell casting loop",
                "keyframe_image_url": "http://example.com/seed_kf.png",
                "is_seamless_loop": True,
            },
        )
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert mock_turn.call_count == 1
        _, kwargs = mock_turn.call_args
        captured_prompt = kwargs.get("compiled_override")
        assert captured_prompt is not None
        assert "<FIRST_FRAME>@KeyframeSeed" in captured_prompt
        assert "<LAST_FRAME>@KeyframeSeed" in captured_prompt
        assert "Seamless Infinite Loop Mode" in captured_prompt


def test_ui_html_contains_1080p_studio_tier_and_seamless_loop_controls() -> None:
    """Verify UI_HTML contains 1080p Studio Full HD resolution option and Seamless Loop toggle."""
    from omnimash.api.app import UI_HTML

    # 1080p Studio Tier in resolution selectors
    assert '<option value="1080p">💎 1080p (Studio Full HD)</option>' in UI_HTML
    assert UI_HTML.count('value="1080p"') >= 5, (
        "Expected 1080p option in all Mode 1, Mode 2, and Draft Room selectors"
    )

    # Seamless loop controls in Stage 2 Workstation and Inspector Drawer
    assert "is_seamless_loop" in UI_HTML
    assert "🔁 Seamless Infinite Loop" in UI_HTML
    assert "checked={!!shot.is_seamless_loop}" in UI_HTML
    assert 'updateStageShot(idx, "is_seamless_loop", e.target.checked)' in UI_HTML
    assert "ACTIVE (Loops to Seed Frame) ✓" in UI_HTML

    # Seamless loop and resolution binding in handleGenerateShotVideo payload
    assert "resolution: omniResolution" in UI_HTML
    assert "is_seamless_loop: !!shot.is_seamless_loop" in UI_HTML


def test_ui_html_act3_screening_room_gated_by_studio_mode() -> None:
    """Verify Act 3 Screening Room only renders and activates when studioMode === 'acts'."""
    from omnimash.api.app import UI_HTML

    assert '{studioMode === "acts" && activeAct === 3 && (' in UI_HTML
    assert "{activeAct === 3 && (" not in UI_HTML
    assert (
        'if (studioMode === "acts") {\n                            setActiveAct(3);\n                        }'
        in UI_HTML
    )


def test_ui_html_authoritative_compilation_and_motion_reference_payloads() -> None:
    """Verify handleJourney3GenerateShot sends compiled_override: null when unmodified, forwards all shot card fields, and both shot handlers forward motion_reference_clip."""
    from omnimash.api.app import UI_HTML

    assert (
        "compiled_override: card.compiled_override !== undefined ? card.compiled_override : null"
        in UI_HTML
    )
    assert (
        "compiled_override: card.compiled_override !== undefined ? card.compiled_override : compileJourney3ShotPromptPreview(card)"
        not in UI_HTML
    )
    assert "title_card_text: card.title_card_text || null," in UI_HTML
    assert "title_card_subtitle: card.title_card_subtitle || null," in UI_HTML
    assert "narrator_text: card.narrator_text || null," in UI_HTML
    assert "narrator_voice: card.narrator_voice || null," in UI_HTML
    assert "style_preset: j3StylePreset || null," in UI_HTML
    assert "is_seamless_loop: !!card.is_seamless_loop," in UI_HTML
    assert UI_HTML.count("motion_reference_clip: motionReferenceClip || null") >= 2


def test_ui_html_stateful_4k_upscale_payload() -> None:
    """Verify handleUpscaleDraftTo4K passes turn_id/previous_interaction_id, explicit stateful upscale prompt, and updates draftBatchShots & j3ShotCards."""
    from omnimash.api.app import UI_HTML

    assert "const sourceTurnId = draftItem.turn_id || draftItem.interaction_id || null;" in UI_HTML
    assert "turn_id: sourceTurnId," in UI_HTML
    assert "previous_interaction_id: sourceTurnId," in UI_HTML
    assert 'prompt: "Upscale to master quality. Keep everything else the same.",' in UI_HTML
    assert 'resolution: "4k", turn_id: data.turn_id || d.turn_id' in UI_HTML


def test_ui_html_standardized_4block_compilers_and_zero_wardrobe_redundancy() -> None:
    """Verify client-side 4-block compilers use canonical headers, zero wardrobe redundancy, instrumental prefix, vocal ducking, and off-screen narrator rules."""
    from omnimash.api.app import UI_HTML

    assert "const buildLivePromptPreview = compileStoryboardPreview;" in UI_HTML
    assert "### CUMULATIVE SHOT STATE" not in UI_HTML
    assert "### VISUAL ACTION & CAMERA" not in UI_HTML
    assert "### TIMELINE & DIALOGUE" not in UI_HTML
    assert "Visual identity anchored via ${alias}." in UI_HTML
    assert "<LAST_FRAME>@EndKeyframe" in UI_HTML
    assert "- On-Screen Displayed Text / Title Card:" in UI_HTML
    assert "@Image${cIdx + 1}" not in UI_HTML
    assert (
        "Ensure the background music ducks under the spoken dialogue so the voice is clear, front-and-center, and intelligible."
        in UI_HTML
    )
    assert "(off-screen) — Do not show a narrator speaking on camera." in UI_HTML


def test_journey3_compiler_4block_alignment_and_stateful_4k_upscale_endpoint() -> None:
    """Verify backend 4-block compiler placement of [# Sources]/[# References], zero wardrobe redundancy in Block 2, audio ducking, narrator off-screen tag, and stateful 4K upscale endpoint."""
    from omnimash.prompts.journey3 import compile_journey3_shot_prompt

    compiled = compile_journey3_shot_prompt(
        shot_number=1,
        action_directive="Harry raises his wand in the neon alley",
        timeline_dialogue="Expelliarmus!",
        global_audio_beat="808 synth trap beat",
        narrator_text="Destiny arrives in the dark.",
        narrator_voice="Deep Trailer Voice",
        keyframe_image_url="https://storage.googleapis.com/test/seed.png",
        characters=[
            {
                "role_id": "Role A",
                "name": "Harry",
                "description": "Young wizard with glasses and cloak",
                "wardrobe": "Emerald Velvet Cloak",
                "aesthetic_tags": ["Cyberpunk Neon"],
                "reference_url": "https://storage.googleapis.com/test/harry.png",
                "voice_style": "British baritone",
            }
        ],
    )

    block1_part, rest = compiled.split("### CHARACTER PROFILES", 1)
    block2_part, rest2 = rest.split("### SCENE INSTRUCTIONS", 1)
    block3_part, block4_part = rest2.split("### TIMELINE", 1)

    assert "### INPUT ROLES & REFERENCES" in block1_part
    assert "[# Sources <FIRST_FRAME>@KeyframeSeed]" in block1_part
    assert "[# References <IMAGE_REF_0>@Image1]" in block1_part
    assert "[Wardrobe: Emerald Velvet Cloak]" in block1_part
    assert "[# Sources" not in block2_part
    assert "[# References" not in block2_part
    assert "Young wizard with glasses and cloak" not in block2_part
    assert "Emerald Velvet Cloak" not in block2_part
    assert "Cyberpunk Neon" not in block2_part
    assert "(Reference Image: @Image1" in block2_part
    assert "instrumental 808 synth trap beat" in block3_part
    assert (
        "Ensure the background music ducks under the spoken dialogue so the voice is clear, front-and-center, and intelligible."
        in block3_part
    )
    assert "(off-screen) — Do not show a narrator speaking on camera." in block4_part

    # Passing both characters and character_roster must not raise UnboundLocalError
    compiled_with_roster = compile_journey3_shot_prompt(
        shot_number=2,
        action_directive="Harry steps forward",
        character_roster="- Role A: Custom Roster Override",
        characters=[{"role_id": "Role A", "name": "Harry", "description": "Wizard"}],
    )
    assert "Custom Roster Override" in compiled_with_roster

    app = create_app(mock_mode=True)
    client = TestClient(app)
    with (
        patch.object(
            app.state.agent,
            "process_user_turn",
            wraps=app.state.agent.process_user_turn,
        ) as mock_turn,
        patch.object(
            app.state.agent.omni_client,
            "generate_keyframe_image",
            wraps=app.state.agent.omni_client.generate_keyframe_image,
        ) as mock_kf,
    ):
        res = client.post(
            "/api/journey3/generate-shot",
            json={
                "session_id": "test_upscale_session",
                "shot_index": 1,
                "turn_id": "turn_draft_360p",
                "previous_interaction_id": "turn_draft_360p",
                "prompt": "Upscale to master quality. Keep everything else the same.",
                "action_directive": "Gaunt wizard puts on a golden velvet blindfold",
                "keyframe_image_url": None,
                "resolution": "4k",
                "motion_reference_clip": "static/uploads/motion_3s.mp4",
            },
        )
        assert res.status_code == 200
        assert res.json()["success"] is True
        mock_kf.assert_not_called()
        _, kwargs = mock_turn.call_args
        assert kwargs.get("parent_turn_id") == "turn_draft_360p"
        assert kwargs.get("is_conversational_edit") is True
        assert kwargs.get("prompt") == "Upscale to master quality. Keep everything else the same."
        assert kwargs.get("keyframe_image_url") is None
        assert kwargs.get("resolution") == "4k"
        assert kwargs.get("motion_reference_clip") == "static/uploads/motion_3s.mp4"


def test_ui_html_shared_character_roster_and_turnaround_studio_component() -> None:
    """Verify CharacterRosterAndTurnaroundStudio is extracted above OmniMashApp, deduplicates the 3x roster JSX, syncs characters/j3Characters, and renders the Visual Anchor Active badge."""
    from omnimash.api.app import UI_HTML

    comp_pos = UI_HTML.find("function CharacterRosterAndTurnaroundStudio(")
    app_pos = UI_HTML.find("function OmniMashApp()")
    assert comp_pos != -1, "CharacterRosterAndTurnaroundStudio component must be defined"
    assert comp_pos < app_pos, (
        "CharacterRosterAndTurnaroundStudio must be defined above OmniMashApp"
    )

    assert UI_HTML.count("<CharacterRosterAndTurnaroundStudio") >= 3
    assert UI_HTML.count("<span>Character Turnaround Reference Sheet Studio</span>") == 1
    assert "⚓ Visual Anchor Active" in UI_HTML
    assert (
        "useEffect(() => {\n                setJ3Characters(characters);\n            }, [characters]);"
        in UI_HTML
    )


def test_ui_html_mode1_stage3_inline_conversational_diffs_and_turn_branching() -> None:
    """Verify Mode 1 Stage 3 embeds Conversational Diff (POST /api/diff), Guided Diff Category Pills, Turn Depth Meter, and TurnHistoryCarousel."""
    from omnimash.api.app import UI_HTML

    stage3_start = UI_HTML.find("{activeStage === 3 && (")
    stage4_start = UI_HTML.find("{activeStage === 4 && (")
    assert stage3_start != -1 and stage4_start != -1 and stage3_start < stage4_start
    stage3_block = UI_HTML[stage3_start:stage4_start]

    for pill in [
        "🌧️ Lighting/Weather",
        "🎥 Camera Angle",
        "🎵 Audio Beat",
        "🗣️ Dialogue Line",
        "⏱️ Pacing",
    ]:
        assert pill in UI_HTML
    assert "GUIDED_DIFF_CATEGORY_PILLS" in stage3_block
    assert "POST /api/diff" in stage3_block
    assert "TurnHistoryCarousel" in stage3_block
    assert "⏪ Branch from Turn" in stage3_block
    assert "/ 4 — Re-anchor recommended at 4+ turns" in stage3_block
    assert "Depth: N / 4 — Re-anchor recommended at 4+ turns" in stage3_block
    assert "const shotTurnId = parentTurnId || selectedShotObj?.turn_id || null;" in UI_HTML
    assert "keyframe_seed: isVisualContinuityLocked ? keyframeSeedAnchor : null" in UI_HTML
    assert "? { ...s, turn_id: tId, video_url: turn.videoUrl || s.video_url }" in stage3_block


def test_ui_html_mode3_shot_card_speaker_role_and_duration_sweet_spot() -> None:
    """Verify Mode 3 shot cards include Speaker Role selector (Role A / Role B / Off-Screen Narrator) and duration sweet-spot indicator (4s–15s • 10s optimal)."""
    from omnimash.api.app import UI_HTML

    assert "4s–15s • 10s optimal" in UI_HTML
    assert "speaker_role" in UI_HTML
    assert '<option value="Role A">Role A</option>' in UI_HTML
    assert '<option value="Role B">Role B</option>' in UI_HTML
    assert (
        '<option value="🎙️ Off-Screen Narrator (off-screen)">🎙️ Off-Screen Narrator (off-screen)</option>'
        in UI_HTML
    )
    assert "const speakerRole = (card && card.speaker_role) ||" in UI_HTML
    assert 'speaker_role: card.speaker_role || "Role A",' in UI_HTML
    assert (
        'speakerRole !== "Role A" ? `${speakerRole}: "${trimmedDialogue}"` : rawDialogue' in UI_HTML
    )


@pytest.mark.slow
@pytest.mark.browser
def test_ui_html_pr2_browser_dom_interactions(tmp_path) -> None:
    """Verify in a real headless Chromium browser that CharacterRosterAndTurnaroundStudio, Mode 1 Stage 3 Guided Diff Pills, Turn Depth Meter (4+ turn warning), TurnHistoryCarousel branching, and Mode 3 Speaker Role selector + payload work interactively."""
    import os
    import subprocess
    from omnimash.api.app import UI_HTML

    skill_dir = "/usr/local/google/home/jordantotten/.gemini/config/skills/playwright-skill"
    if not os.path.exists(skill_dir):
        pytest.skip("Playwright skill directory not installed")

    html_file = tmp_path / "ui_pr2_check.html"
    html_file.write_text(UI_HTML, encoding="utf-8")
    inline_js = (
        "const { chromium } = require('playwright');"
        "(async () => {"
        "  const browser = await chromium.launch({ headless: true });"
        "  const page = await browser.newPage();"
        "  page.on('pageerror', err => { console.error('BROWSER ERROR:', err.message); process.exit(2); });"
        f"  await page.goto('file://{html_file}', {{ waitUntil: 'domcontentloaded' }});"
        "  await page.waitForFunction(() => {"
        "    const el = document.querySelector('#__next');"
        "    return el && el.innerHTML.length > 1000;"
        "  }, { timeout: 15000 });"
        "  await page.evaluate(() => {"
        "    window.__capturedRequests = [];"
        "    let turnCounter = 0;"
        "    window.fetch = async (url, opts) => {"
        "      const body = opts && opts.body ? JSON.parse(opts.body) : null;"
        "      window.__capturedRequests.push({ url: String(url), body });"
        "      if (String(url).includes('/api/journey3/generate-shot')) {"
        "        return { ok: true, status: 200, json: async () => ({ video_url: 'https://example.com/j3.mp4', turn_id: 'j3_turn_1' }) };"
        "      }"
        "      if (String(url).includes('/api/generate') || String(url).includes('/api/diff')) {"
        "        const tId = `turn_0${turnCounter++}`;"
        "        return { ok: true, status: 200, json: async () => ({ success: true, status: 'OK', turn_id: tId, video_url: `https://example.com/${tId}.mp4`, raw_compiled_prompt: 'compiled' }) };"
        "      }"
        "      return { ok: true, status: 200, json: async () => ({}) };"
        "    };"
        "  });"
        "  const mode3Text = await page.innerText('#__next');"
        "  if (!mode3Text.includes('4s–15s • 10s optimal')) throw new Error('Missing duration sweet-spot badge in Mode 3');"
        "  if (!mode3Text.includes('⚓ Visual Anchor Active')) throw new Error('Missing Visual Anchor Active badge in Mode 3');"
        "  const speakerSelect = page.locator('select').filter({ hasText: '🎙️ Off-Screen Narrator (off-screen)' }).first();"
        "  await speakerSelect.selectOption('Role B');"
        "  await page.getByRole('button', { name: /Render 10s Shot Video/i }).first().click();"
        "  await page.waitForTimeout(100);"
        "  const j3ReqRoleB = await page.evaluate(() => window.__capturedRequests.find(r => r.url.includes('/api/journey3/generate-shot')));"
        "  if (!j3ReqRoleB || j3ReqRoleB.body.speaker_role !== 'Role B' || !j3ReqRoleB.body.dialogue_text.startsWith('Role B:')) {"
        "    throw new Error('Mode 3 Role B speaker_role not normalized in generate-shot payload: ' + JSON.stringify(j3ReqRoleB));"
        "  }"
        "  await page.evaluate(() => { window.__capturedRequests = []; });"
        "  await speakerSelect.selectOption('🎙️ Off-Screen Narrator (off-screen)');"
        "  await page.getByRole('button', { name: /Render 10s Shot Video/i }).first().click();"
        "  await page.waitForTimeout(100);"
        "  const j3ReqNarr = await page.evaluate(() => window.__capturedRequests.find(r => r.url.includes('/api/journey3/generate-shot')));"
        "  if (!j3ReqNarr || j3ReqNarr.body.dialogue_text !== '' || !String(j3ReqNarr.body.narrator_text || '').includes('I see all.')) {"
        "    throw new Error('Mode 3 Off-Screen Narrator speaker_role not routed to narrator_text: ' + JSON.stringify(j3ReqNarr));"
        "  }"
        "  await page.getByRole('button', { name: /Mode 1: Guided Fine-Tune/i }).first().click();"
        "  const stage1Text = await page.innerText('#__next');"
        "  if (!stage1Text.includes('⚓ Visual Anchor Active')) throw new Error('Missing Visual Anchor Active badge in Stage 1');"
        "  await page.getByRole('button', { name: /Step 3: Render & Stitch Master Video/i }).click();"
        "  const stage3Text = await page.innerText('#__next');"
        "  if (!stage3Text.includes('Depth: 0 / 4 — Re-anchor recommended at 4+ turns')) throw new Error('Missing Turn Depth Meter in Stage 3');"
        "  if (!stage3Text.includes('🌧️ Lighting/Weather')) throw new Error('Missing Guided Diff Category Pills in Stage 3');"
        "  if (!stage3Text.toUpperCase().includes('TURNHISTORYCAROUSEL')) throw new Error('Missing TurnHistoryCarousel in Stage 3');"
        "  const carouselCount = await page.locator('.TurnHistoryCarousel').count();"
        "  if (carouselCount < 1) throw new Error('Expected .TurnHistoryCarousel element in Stage 3 DOM');"
        "  await page.getByRole('button', { name: /🌧️ Lighting\\/Weather/i }).click();"
        "  const diffVal = await page.locator('input[placeholder*=\"gold metallic sunglasses\"]').inputValue();"
        "  if (!diffVal.includes('Shift scene lighting to dramatic neon rain')) throw new Error('Guided Diff Pill did not populate deltaPrompt: ' + diffVal);"
        "  for (let i = 0; i < 4; i++) {"
        "    await page.getByRole('button', { name: /Apply Diff & Render/i }).click();"
        "    await page.waitForTimeout(50);"
        "  }"
        "  const stage3After4 = await page.innerText('#__next');"
        "  if (!stage3After4.includes('Depth: 4 / 4 — Re-anchor recommended at 4+ turns')) {"
        "    throw new Error('Turn Depth Meter did not update to 4 / 4 after 4 turns');"
        "  }"
        "  const meterClasses = await page.locator('div[title*=\"Turn Depth Meter\"]').getAttribute('class');"
        "  if (!meterClasses || !meterClasses.includes('border-red-500')) {"
        "    throw new Error('Turn Depth Meter did not switch to red warning state at 4+ turns: ' + meterClasses);"
        "  }"
        "  await page.getByRole('button', { name: /⏪ Branch from Turn 1/i }).click();"
        "  await page.evaluate(() => { window.__capturedRequests = []; });"
        "  await page.getByRole('button', { name: /🎥 Camera Angle/i }).click();"
        "  await page.getByRole('button', { name: /Apply Diff & Render/i }).click();"
        "  await page.waitForTimeout(50);"
        "  const branchedDiffReq = await page.evaluate(() => window.__capturedRequests.find(r => r.url.includes('/api/diff')));"
        "  if (!branchedDiffReq || branchedDiffReq.body.parent_turn_id !== 'turn_01') {"
        "    throw new Error('Branching from Turn 1 in Stage 3 TurnHistoryCarousel did not send parent_turn_id=turn_01: ' + JSON.stringify(branchedDiffReq));"
        "  }"
        "  console.log('PR2_BROWSER_INTERACTIONS_OK');"
        "  await browser.close();"
        "})();"
    )
    res = subprocess.run(
        ["node", "-e", inline_js],
        cwd=skill_dir,
        capture_output=True,
        text=True,
    )
    output = res.stdout + res.stderr
    assert res.returncode == 0, f"Playwright PR2 interaction test failed: {output}"
    assert "PR2_BROWSER_INTERACTIONS_OK" in output


def test_ui_html_omni11_7card_production_playbook_and_workflow_guide() -> None:
    """Verify showBestPracticesModal renders the 7-card Omni Flash 1.1 Production Playbook and showWorkflowGuideModal alias is wired."""
    from omnimash.api.app import UI_HTML

    assert "💡 Gemini Omni Prompting Guide" in UI_HTML
    assert "gemini-omni-1.1-flash-preview" in UI_HTML
    for card_title in [
        "Card 1: Canonical 4-Block Prompt Architecture",
        "Card 2: Character Consistency &amp; Zero Wardrobe Redundancy",
        "Card 3: Dual-Keyframe Transitions",
        'Card 4: Theatrical Dialogue &amp; "instrumental" Audio Ducking',
        "Card 5: Conversational Diffs &amp; Re-Anchoring at 4–6 Turns",
        "Card 6: 360p Draft-First → 4K Stateful Upscale",
        "Card 7: Real-Person Likeness &amp; Trademark Safety Policy",
    ]:
        assert card_title in UI_HTML, f"Missing playbook card: {card_title}"

    assert "const showWorkflowGuideModal = showStoryboardGuideModal;" in UI_HTML
    assert "const setShowWorkflowGuideModal = setShowStoryboardGuideModal;" in UI_HTML
    assert "Unified 3-Mode Studio Architecture" in UI_HTML


def test_ui_html_safety_compliant_presets_and_parody_mappings() -> None:
    """Verify UI_HTML presets/rosters/placeholders avoid real celebrity and luxury brand names and REAL_NAME_MAPPINGS covers culinary/luxury terms."""
    from omnimash.api.app import UI_HTML
    from omnimash.prompts.compiler import (
        GEMINI_OMNI_FLASH_INSTR,
        REAL_NAME_MAPPINGS,
        sanitize_real_names,
    )

    assert (
        "Fiery Executive Chef vs Classic French Pastry Master in a cyberpunk iron chef battle"
        in UI_HTML
    )
    assert "Gothic Potion Master in a 90s East Coast boom-bap rap video" in UI_HTML
    assert "Crimson Velvet Tracksuit, Gold Wire-Rim Glasses" in UI_HTML
    assert "Headmaster Archmage: (Casual, adjusting his spectacles)" in UI_HTML
    assert "Red Gucci Tracksuit" not in UI_HTML
    assert "Cartier Glasses" not in UI_HTML
    assert "Gothic Hogwarts courtyard" not in UI_HTML
    assert "This is Trap or Die, Potter!" not in UI_HTML
    assert 'placeholder="e.g. Harry"' not in UI_HTML
    assert 'placeholder="e.g. harry_potter_sheet_v1"' not in UI_HTML
    assert "Dumble Dior: (Casual" not in UI_HTML

    assert "gemini-omni-1.1-flash-preview" in GEMINI_OMNI_FLASH_INSTR
    assert "Zero Wardrobe Redundancy" in GEMINI_OMNI_FLASH_INSTR
    assert len(REAL_NAME_MAPPINGS) >= 60

    sample = "Guy Fieri and Anthony Bourdain wearing Hermes and Patek Philippe with Audemars Piguet at Hogwarts with Potter"
    sanitized = sanitize_real_names(sample)
    assert "Guy Fieri" not in sanitized
    assert "Anthony Bourdain" not in sanitized
    assert "Hermes" not in sanitized
    assert "Patek Philippe" not in sanitized
    assert "Audemars Piguet" not in sanitized
    assert "Hogwarts" not in sanitized
    assert "Potter" not in sanitized
    assert "Spiky Blonde Flavortown Chef" in sanitized
    assert "World-Weary Culinary Traveler" in sanitized
    assert "Gothic Academy" in sanitized


def test_ui_html_wcag_aa_polish_toast_region_and_modal_a11y() -> None:
    """Verify UI_HTML has zero blocking alert() calls, mounts ToastNotificationRegion, defines CSS tokens & focus-visible, eliminates text-[9px]/text-[10px]/text-gray-500/text-gray-600, and adds ARIA dialog attributes + Escape dismissal + Tab focus trap."""
    from omnimash.api.app import UI_HTML

    assert "alert(" not in UI_HTML
    assert "function ToastNotificationRegion(" in UI_HTML
    assert "<ToastNotificationRegion toasts={toasts} onDismiss={dismissToast} />" in UI_HTML
    assert "toasts.slice(-4)" in UI_HTML
    assert "const pushToast = addToast;" in UI_HTML
    assert 'role="status"' in UI_HTML
    assert 'aria-live="polite"' in UI_HTML

    # CSS tokens & focus-visible outlines
    for token in [
        "--bg-primary:",
        "--bg-surface:",
        "--text-primary:",
        "--text-secondary:",
        "--accent-primary:",
        "--focus-ring:",
        ":focus-visible",
    ]:
        assert token in UI_HTML

    # No sub-11px or low-contrast gray-500/gray-600 text classes remaining
    assert "text-[9px]" not in UI_HTML
    assert "text-[10px]" not in UI_HTML
    assert "text-gray-500" not in UI_HTML
    assert "text-gray-600" not in UI_HTML

    # Modal ARIA dialog attributes, Escape listener, and Tab focus trap
    assert UI_HTML.count('role="dialog"') >= 10
    assert UI_HTML.count('aria-modal="true"') >= 10
    for label_id in [
        "modal-title-new-project",
        "modal-title-new-session",
        "modal-title-best-practices",
        "modal-title-workflow-guide",
        "modal-title-save-storyboard",
        "modal-title-lightbox",
    ]:
        assert f'aria-labelledby="{label_id}"' in UI_HTML
        assert f'id="{label_id}"' in UI_HTML
    assert 'if (e.key === "Escape")' in UI_HTML
    assert 'else if (e.key === "Tab")' in UI_HTML


@pytest.mark.slow
@pytest.mark.browser
def test_ui_html_pr3_browser_dom_interactions(tmp_path) -> None:
    """Verify in a real headless Chromium browser that ToastNotificationRegion, 7-card Omni 1.1 Prompting Guide modal, ARIA dialog attributes, Escape-key modal dismissal, Tab focus trapping, and capped non-blocking toast validation work interactively."""
    import os
    import subprocess
    from omnimash.api.app import UI_HTML

    skill_dir = "/usr/local/google/home/jordantotten/.gemini/config/skills/playwright-skill"
    if not os.path.exists(skill_dir):
        pytest.skip("Playwright skill directory not installed")

    html_file = tmp_path / "ui_pr3_check.html"
    html_file.write_text(UI_HTML, encoding="utf-8")
    inline_js = (
        "const { chromium } = require('playwright');"
        "(async () => {"
        "  const browser = await chromium.launch({ headless: true });"
        "  const page = await browser.newPage();"
        "  page.on('pageerror', err => { console.error('BROWSER ERROR:', err.message); process.exit(2); });"
        f"  await page.goto('file://{html_file}', {{ waitUntil: 'domcontentloaded' }});"
        "  await page.waitForFunction(() => {"
        "    const el = document.querySelector('#__next');"
        "    return el && el.innerHTML.length > 1000;"
        "  }, { timeout: 15000 });"
        '  const toastRegion = page.locator(\'.ToastNotificationRegion[role="status"][aria-live="polite"]\');'
        "  if (await toastRegion.count() !== 1) throw new Error('Expected ToastNotificationRegion with role=status and aria-live=polite');"
        "  await page.getByRole('button', { name: /Mode 1: Guided Fine-Tune/i }).first().click();"
        "  await page.getByRole('button', { name: /Gemini Omni Prompting Guide/i }).first().click();"
        '  const dialog = page.locator(\'[role="dialog"][aria-modal="true"]\');'
        "  if (await dialog.count() < 1) throw new Error('Expected Best Practices modal with role=dialog and aria-modal=true');"
        "  const dialogText = (await dialog.first().innerText()).toUpperCase();"
        "  if (!dialogText.includes('CARD 1: CANONICAL 4-BLOCK PROMPT ARCHITECTURE') || !dialogText.includes('CARD 7: REAL-PERSON LIKENESS')) {"
        "    throw new Error('7-card playbook content missing from modal: ' + dialogText);"
        "  }"
        "  for (let t = 0; t < 4; t++) {"
        "    await page.keyboard.press('Tab');"
        "    const insideDialog = await page.evaluate(() => {"
        '      const dlg = document.querySelector(\'[role="dialog"][aria-modal="true"]\');'
        "      return dlg && dlg.contains(document.activeElement);"
        "    });"
        "    if (!insideDialog) throw new Error('Tab focus escaped open aria-modal dialog on press ' + t);"
        "  }"
        "  await page.keyboard.press('Escape');"
        "  await page.waitForTimeout(50);"
        "  if (await dialog.count() !== 0) throw new Error('Escape key did not dismiss Best Practices modal');"
        "  await page.getByRole('button', { name: /\\+ New Project/i }).first().click();"
        "  if (await dialog.count() < 1) throw new Error('Expected New Project modal to open');"
        "  for (let i = 0; i < 6; i++) {"
        "    await page.getByRole('button', { name: /Create Project/i }).click();"
        "  }"
        "  await page.waitForTimeout(50);"
        "  const toastText = await toastRegion.innerText();"
        "  if (!toastText.includes('Please enter a valid project name.')) {"
        "    throw new Error('Expected non-blocking toast notification on empty project name, got: ' + toastText);"
        "  }"
        "  const renderedToasts = await toastRegion.locator('button[aria-label=\"Dismiss notification\"]').count();"
        "  if (renderedToasts !== 4) {"
        "    throw new Error('Expected toast stack to cap at 4 items, got: ' + renderedToasts);"
        "  }"
        "  await page.keyboard.press('Escape');"
        "  await page.waitForTimeout(50);"
        "  if (await dialog.count() !== 0) throw new Error('Escape key did not dismiss New Project modal');"
        "  console.log('PR3_BROWSER_INTERACTIONS_OK');"
        "  await browser.close();"
        "})();"
    )
    res = subprocess.run(
        ["node", "-e", inline_js],
        cwd=skill_dir,
        capture_output=True,
        text=True,
    )
    output = res.stdout + res.stderr
    assert res.returncode == 0, f"Playwright PR3 interaction test failed: {output}"
    assert "PR3_BROWSER_INTERACTIONS_OK" in output


def test_minimal_intent_prompt_engine_end_to_end():
    """Verify minimal 1-sentence intent produces optimal [0-3s]/[3-6s]/[6-10s] beats and 4-Block prompts across deconstruct, expand, and generate."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    # 1. /api/deconstruct-concept
    res_deconstruct = client.post(
        "/api/deconstruct-concept",
        json={"concept": "Gordon Ramsay vs Julia Child in a cyberpunk iron chef battle"},
    )
    assert res_deconstruct.status_code == 200
    dec_data = res_deconstruct.json()
    assert dec_data["keyframe_image_prompt"] != ""
    assert "[0-3s]" in dec_data["screenplay_script"]
    assert "[3-6s]" in dec_data["screenplay_script"]
    assert "[6-10s]" in dec_data["screenplay_script"]
    assert len(dec_data["scenes"]) >= 1
    assert "[0-3s]" in dec_data["scenes"][0]["action"]
    assert "[3-6s]" in dec_data["scenes"][0]["action"]
    assert "[6-10s]" in dec_data["scenes"][0]["action"]
    assert dec_data["scenes"][0]["dialogue"] != ""

    # 2. /api/storyboard/expand forwarding taxonomy fields
    res_expand = client.post(
        "/api/storyboard/expand",
        json={
            "concept": "Gordon Ramsay vs Julia Child in a cyberpunk iron chef battle",
            "style_tone": "Cyberpunk Glow",
            "target_duration": 30.0,
            "camera_lighting": dec_data["camera_lighting_tag"],
            "aesthetic_tags": dec_data["aesthetic_tags"],
            "audio_beat": dec_data["audio_beat"],
            "vocal_delivery": dec_data["vocal_delivery"],
            "environment": dec_data["environment_tag"],
        },
    )
    assert res_expand.status_code == 200
    exp_shots = res_expand.json()["shots"]
    assert len(exp_shots) == 3
    for s in exp_shots:
        assert "[0-3s]" in s["action"]
        assert "[3-6s]" in s["action"]
        assert "[6-10s]" in s["action"]
        assert dec_data["environment_tag"] in s["location"]
        assert dec_data["audio_beat"] in s["audio"]

    # 3. /api/generate with bare minimal prompt
    res_gen = client.post(
        "/api/generate",
        json={
            "user_id": "usr_min",
            "project_id": "prj_min",
            "prompt": "A neon samurai vs a cyborg ninja in an arcade showdown",
            "clip_index": 0,
        },
    )
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    assert gen_data["success"] is True
    raw_prompt = gen_data["raw_compiled_prompt"]
    assert "### INPUT ROLES & REFERENCES" in raw_prompt
    assert "### CHARACTER PROFILES" in raw_prompt
    assert "### SCENE INSTRUCTIONS" in raw_prompt
    assert "### TIMELINE" in raw_prompt
    assert "[0-3s]" in raw_prompt
    assert "[3-6s]" in raw_prompt
    assert "[6-10s]" in raw_prompt


def test_ui_html_pr2_user_journeys_express_flow_and_cross_mode_sync() -> None:
    """Verify PR 2 frontend user journey refactoring, simultaneous Mode 1+3 render fix, Express 1-Click Flow, Mode 2 Act 3 colocation, cross-mode sync, and Mode 3 Step Filter bar."""
    from omnimash.api.app import UI_HTML

    # 1. Simultaneous Mode 1 + Mode 3 render bug fixed via activeTab !== "journey3"
    assert '{studioMode === "acts" && activeTab !== "journey3" && (' in UI_HTML
    assert '{studioMode === "stages" && activeTab !== "journey3" && (' in UI_HTML
    assert "🏆 Stage 4: The Final Cut" not in UI_HTML
    assert "Proceed to Stage 4" not in UI_HTML
    assert "setActiveStage(4)" not in UI_HTML

    # 2. handleDeconstructConcept populates scenes from data.scenes without dummy overwrite
    assert "in action sequence" not in UI_HTML
    assert "Array.isArray(data.scenes) && data.scenes.length > 0" in UI_HTML
    assert (
        "if (data.keyframe_image_prompt) setKeyframeImagePrompt(data.keyframe_image_prompt);"
        in UI_HTML
    )
    assert "if (data.screenplay_script) setScreenplayScript(data.screenplay_script);" in UI_HTML

    # 3. Mode 1 Stage 1 Express Render 10s Video Now CTA & Generate Keyframe Anchor button
    assert "🎬 Express Render 10s Video Now →" in UI_HTML
    assert "handleExpressRenderSingleVideo" in UI_HTML
    assert "🖼️ Generate Keyframe Anchor" in UI_HTML
    assert "handleStage1GenerateKeyframeAnchor" in UI_HTML
    assert "Deconstruct & Extract Cast (AI)" not in UI_HTML

    # 4. Mode 2 handleReSyncStoryboardDefaults updates setScenes and Act 3 is colocated inside Mode 2 before Mode 1
    mode2_start = UI_HTML.find(
        '{studioMode === "acts" && activeTab !== "journey3" && (', UI_HTML.find("<main")
    )
    mode1_start = UI_HTML.find(
        '{studioMode === "stages" && activeTab !== "journey3" && (', UI_HTML.find("<main")
    )
    act3_pos = UI_HTML.find('{studioMode === "acts" && activeAct === 3 && (')
    assert mode2_start != -1 and mode1_start != -1 and act3_pos != -1
    assert mode2_start < act3_pos < mode1_start

    # 5. Cross-mode state sync & Mode 3 Step Filter bar
    assert 'const [j3StepFilter, setJ3StepFilter] = useState("all");' in UI_HTML
    assert "const visualConcept = concept;" in UI_HTML
    assert "1. Master Setup & Cast" in UI_HTML
    assert "2. Keyframes & Shots" in UI_HTML
    assert "3. Master Stitch" in UI_HTML


@pytest.mark.slow
@pytest.mark.browser
def test_ui_html_pr2_express_flow_and_mode3_step_filter_browser_dom(tmp_path) -> None:
    """Verify in headless Chromium that startup only renders Mode 3 (not Mode 1+3 simultaneously), Mode 3 Step Filter works, bidirectional cross-mode sync works, Stage 2->3 navigation works, and Mode 1 Express CTA auto-deconstructs and renders."""
    import os
    import subprocess
    from omnimash.api.app import UI_HTML

    skill_dir = "/usr/local/google/home/jordantotten/.gemini/config/skills/playwright-skill"
    if not os.path.exists(skill_dir):
        pytest.skip("Playwright skill dir not available")

    html_file = tmp_path / "ui_pr2_journey_check.html"
    html_file.write_text(UI_HTML, encoding="utf-8")
    inline_js = (
        "const { chromium } = require('playwright');"
        "(async () => {"
        "  const browser = await chromium.launch({ headless: true });"
        "  const page = await browser.newPage();"
        "  page.on('pageerror', err => { console.error('BROWSER ERROR:', err.message); process.exit(2); });"
        f"  await page.goto('file://{html_file}', {{ waitUntil: 'domcontentloaded' }});"
        "  await page.waitForFunction(() => {"
        "    const el = document.querySelector('#__next');"
        "    return el && el.innerHTML.length > 1000;"
        "  }, { timeout: 15000 });"
        "  await page.evaluate(() => {"
        "    window.__capturedGeneratePayload = null;"
        "    const origFetch = window.fetch;"
        "    window.fetch = async (url, opts) => {"
        "      const u = String(url);"
        "      if (u.includes('/api/deconstruct-concept')) {"
        "        const body = JSON.parse(opts.body || '{}');"
        "        return new Response(JSON.stringify({"
        "          characters: [{ role_id: 'Role A', name: 'Mars Grandmaster', description: 'Astronaut in chrome suit', aesthetic_tags: ['Sci-Fi'], voice_style: 'Calm', wardrobe: 'Spacesuit' }],"
        "          aesthetic_tags: ['Retro Sci-Fi Cinema'],"
        "          environment_tag: 'Red cratered Mars plateau',"
        "          camera_lighting_tag: 'Anamorphic lens with warm Martian rim lighting',"
        "          audio_beat: '120 BPM Synthwave Pulse',"
        "          vocal_delivery: 'Deadpan astronaut commentary',"
        "          keyframe_image_prompt: 'Wide establishing frame: ' + (body.concept || ''),"
        "          screenplay_script: '[0-3s] Action: Opening move on Mars.\\n[3-6s] Action: Tension rises.\\n[6-10s] Action: Checkmate.',"
        "          scenes: [{ scene_number: 1, active_roles: ['Role A'], action: '[0-3s] Action: Mars Grandmaster moves rook. [3-6s] Action: Zero-G dust swirls. [6-10s] Action: Triumphant checkmate.', dialogue: 'Mars Grandmaster: \"Checkmate on Olympus Mons.\"' }]"
        "        }), { status: 200, headers: { 'Content-Type': 'application/json' } });"
        "      }"
        "      if (u.includes('/api/generate')) {"
        "        window.__capturedGeneratePayload = JSON.parse(opts.body || '{}');"
        "        return new Response(JSON.stringify({"
        "          success: true,"
        "          status: 'OK',"
        "          turn_id: 'turn_express_01',"
        "          video_url: 'https://storage.googleapis.com/mock/express_10s.mp4',"
        "          raw_compiled_prompt: '### INPUT ROLES & REFERENCES\\nNone.\\n\\n### CHARACTER PROFILES\\n- Role A (Mars Grandmaster)\\n\\n### SCENE INSTRUCTIONS\\nMars\\n\\n### TIMELINE\\n- [0-3s] [3-6s] [6-10s]'"
        "        }), { status: 200, headers: { 'Content-Type': 'application/json' } });"
        "      }"
        "      return origFetch(url, opts);"
        "    };"
        "  });"
        "  const mainTextOnStartup = await page.locator('main').textContent();"
        "  if (!mainTextOnStartup.includes('Mode 3: Continuity Studio')) {"
        "    throw new Error('Expected Mode 3 to be rendered on startup');"
        "  }"
        "  if (mainTextOnStartup.includes('Expand Vision into 5-Part Storyboard Grid')) {"
        "    throw new Error('Simultaneous Mode 1 + Mode 3 render bug detected on startup!');"
        "  }"
        "  await page.getByRole('button', { name: '2. Keyframes & Shots' }).click();"
        "  const step2Text = await page.locator('main').textContent();"
        "  if (step2Text.includes('Step 1: Master Concept & Character Roles Manager') || !step2Text.includes('Step 2: Shot Card Workstation')) {"
        "    throw new Error('Mode 3 Step Filter (2. Keyframes & Shots) did not filter sections properly');"
        "  }"
        "  await page.getByRole('button', { name: 'All Sections' }).click();"
        "  const j3Textarea = page.locator('textarea[placeholder*=\"Describe the multi-shot continuous scene\"]');"
        "  await j3Textarea.fill('Synced Cross-Mode Dragon Chef Showdown');"
        "  await page.getByRole('button', { name: /Mode 1: Guided Fine-Tune/i }).first().click();"
        "  const mode1Textarea = page.locator('textarea[placeholder*=\"Specify the exact keyframe frame visual setup\"]');"
        "  const mode1ValAfterJ3 = await mode1Textarea.inputValue();"
        "  if (mode1ValAfterJ3 !== 'Synced Cross-Mode Dragon Chef Showdown') {"
        "    throw new Error('Expected Mode 3 -> Mode 1 concept sync, got: ' + mode1ValAfterJ3);"
        "  }"
        "  await mode1Textarea.fill('');"
        "  if ((await mode1Textarea.inputValue()) !== '') {"
        "    throw new Error('Expected Mode 1 textarea to clear cleanly to empty string without snapping back');"
        "  }"
        "  await mode1Textarea.fill('Mode 1 Updated Mars Chess Battle');"
        "  await page.getByRole('button', { name: /Mode 2: Screenplay Storyboard/i }).first().click();"
        "  const mode2Textarea = page.locator('textarea[placeholder*=\"Fiery Executive Chef\"]');"
        "  if ((await mode2Textarea.inputValue()) !== 'Mode 1 Updated Mars Chess Battle') {"
        "    throw new Error('Expected Mode 1 -> Mode 2 concept sync, got: ' + (await mode2Textarea.inputValue()));"
        "  }"
        "  await page.getByRole('button', { name: /Mode 1: Guided Fine-Tune/i }).first().click();"
        "  await page.getByRole('button', { name: /Step 2: Shot Card Workstation/i }).click();"
        "  await page.getByRole('button', { name: /Proceed to Step 3: Render & Stitch Master Video/i }).click();"
        "  const stage3NavText = await page.locator('main').textContent();"
        "  if (!stage3NavText.includes('Select Shot Card to Inspect & Diff') || !stage3NavText.includes('Master Audio Overlay & GCS Export Settings')) {"
        "    throw new Error('Stage 2 Proceed to Step 3 button did not render Stage 3 properly');"
        "  }"
        "  await page.getByRole('button', { name: /Step 1: Visual Concept & Characters/i }).click();"
        "  await page.getByRole('button', { name: /Express Render 10s Video Now/i }).click();"
        "  await page.waitForFunction(() => !!window.__capturedGeneratePayload, { timeout: 5000 });"
        "  const genPayload = await page.evaluate(() => window.__capturedGeneratePayload);"
        "  if (!genPayload || !genPayload.scenes || !genPayload.scenes[0].action.includes('[0-3s] Action: Mars Grandmaster moves rook.')) {"
        "    throw new Error('Expected Express Render to auto-deconstruct new concept before /api/generate, got: ' + JSON.stringify(genPayload));"
        "  }"
        "  const afterExpressText = await page.locator('main').textContent();"
        "  if (!afterExpressText.includes('Checkmate on Olympus Mons') || !afterExpressText.includes('Red cratered Mars plateau')) {"
        "    throw new Error('Expected Stage 3 Shot #1 prompt preview to show newly deconstructed scene metadata');"
        "  }"
        "  const bodyText = await page.locator('body').textContent();"
        "  if (bodyText.includes('Stage 4: The Final Cut')) {"
        "    throw new Error('Expected dead Stage 4 tab to be removed');"
        "  }"
        "  console.log('PR2_JOURNEY_BROWSER_OK');"
        "  await browser.close();"
        "})();"
    )
    res = subprocess.run(
        ["node", "-e", inline_js],
        cwd=skill_dir,
        capture_output=True,
        text=True,
    )
    output = res.stdout + res.stderr
    assert res.returncode == 0, f"Playwright PR2 journey test failed: {output}"
    assert "PR2_JOURNEY_BROWSER_OK" in output


def test_ui_html_contains_trapwarts_vault_audit_default_preset() -> None:
    """Verify UI_HTML includes the Trapwarts Vault Audit default preset with saved characters and reference sheets."""
    from omnimash.api.app import UI_HTML

    assert "TRAPWARTS_VAULT_AUDIT_PRESET" in UI_HTML
    assert "handleLoadTrapwartsVaultDefault" in UI_HTML
    assert "Load Trapwarts Vault Default" in UI_HTML
    assert "dumble_dior_office_sheet_v13.png" in UI_HTML
    assert "yototti_office_sheet_v13.png" in UI_HTML
    assert "accountant_elves_office_sheet_v13.png" in UI_HTML


def test_ui_html_contains_shareable_video_link_controls() -> None:
    """Verify UI_HTML contains 7-day shareable video link controls, modal, and API wiring."""
    from omnimash.api.app import UI_HTML

    assert "Share Video (7 Days)" in UI_HTML
    assert "handleOpenShareModal" in UI_HTML
    assert "modal-title-share" in UI_HTML
    assert "/api/share/create" in UI_HTML
    assert "Privacy & Infrastructure Protected" in UI_HTML
    assert "Direct Streaming Link" in UI_HTML
    assert "Valid for 7 Days" in UI_HTML
    assert "Preview in New Tab" in UI_HTML
    assert "Copy Download URL" in UI_HTML
    assert "Copy Embed Code" in UI_HTML
    assert "Get Shareable Link (7 Days)" in UI_HTML


def test_ui_html_contains_mode4_directors_copilot_workspace() -> None:
    """Verify UI_HTML contains Mode 4 Director's Co-Pilot studio, intent inputs, auto-filler, and ubiquitous contextual assist."""
    from omnimash.api.app import UI_HTML

    # 1. Mode Switcher & Header
    assert "Mode 4: Director's Co-Pilot" in UI_HTML
    assert "Zero-Friction Intent Target" in UI_HTML

    # 2. Intent Intake Card & Actions
    assert "intent-input" in UI_HTML
    assert "Ask Me Questions (Clarify Gaps)" in UI_HTML
    assert "Surprise Me (Auto-Fill Gaps Cohesively)" in UI_HTML

    # 2b. Character Vault Dropdown with Reference Image Thumbnails & Dialogue Direction
    assert "mode4-vault-dropdown-btn" in UI_HTML
    assert "Select Saved Character(s) with Reference Image Thumbnail" in UI_HTML
    assert "mode4-dialogue-direction-input" in UI_HTML
    assert "Dialogue Direction (Guidance for Gemini)" in UI_HTML

    # 3. API Endpoints
    assert "/api/intent/analyze-gaps" in UI_HTML
    assert "/api/intent/auto-fill" in UI_HTML
    assert "/api/intent/render-direct" in UI_HTML

    # 4. Clarification Flow & Promotion
    assert "Directorial Clarification" in UI_HTML
    assert "Direct & Render 10s Video Now" in UI_HTML
    assert "Open in Mode 1 (Guided Fine-Tune)" in UI_HTML
    assert "Open in Mode 2 (Screenplay Storyboard)" in UI_HTML
    assert "Open in Mode 3 (Continuity Studio)" in UI_HTML

    # 5. Screening Room & Share
    assert "Mode 4 Screening Room (Direct Render)" in UI_HTML
    assert 'handleOpenShareModal(mode4VideoUrl, "mode4_intent_cut")' in UI_HTML

    # 6. Ubiquitous Contextual Assist Modal & Buttons
    assert "modal-title-intent-assist" in UI_HTML
    assert "handleOpenIntentAssist" in UI_HTML
    assert "handleApplyIntentAssistToTarget" in UI_HTML
    assert "Co-Pilot Gap Filler" in UI_HTML
    assert "Co-Pilot Script & Shot Generator" in UI_HTML
    assert "Co-Pilot Master Setup" in UI_HTML

    # 7. AST Layout Position verification: Mode 4 is placed strictly after Mode 1
    mode1_start = UI_HTML.find(
        '{studioMode === "stages" && activeTab !== "journey3" && (', UI_HTML.find("<main")
    )
    mode4_start = UI_HTML.find(
        '{studioMode === "intent" && activeTab !== "journey3" && (', UI_HTML.find("<main")
    )
    assert mode1_start != -1 and mode4_start != -1
    assert mode1_start < mode4_start
