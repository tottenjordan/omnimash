from fastapi.testclient import TestClient
from omnimash.api.app import create_app


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






