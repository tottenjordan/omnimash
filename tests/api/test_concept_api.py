from fastapi.testclient import TestClient

from omnimash.api.app import create_app


def test_deconstruct_concept_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/deconstruct-concept",
        json={"concept": "Harry vs Draco trap battle"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "characters" in data
    assert len(data["characters"]) >= 2
    assert "aesthetic_tags" in data
    assert "environment_tag" in data
    assert "camera_lighting_tag" in data
    assert "audio_beat" in data
    assert "vocal_delivery" in data
    assert data["vocal_delivery"] != ""
    for char in data["characters"]:
        assert "voice_style" in char
    assert any(c["voice_style"] != "" for c in data["characters"])


def test_generate_endpoint_accepts_vocal_delivery_and_character_voice_style():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/generate",
        json={
            "user_id": "usr_test",
            "project_id": "prj_test",
            "concept": "Harry vs Draco trap battle",
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Harry",
                    "description": "Young wizard with round glasses",
                    "reference_url": "https://example.com/harry.jpg",
                    "aesthetic_tags": ["Red Gucci Tracksuit"],
                    "voice_style": "Fast-paced Atlanta trap flow",
                }
            ],
            "scenes": [
                {
                    "scene_number": 1,
                    "active_roles": ["Role A"],
                    "action": "Rapping into microphone wand",
                    "dialogue": "I been cooking potions!",
                }
            ],
            "vocal_delivery": "Punchy synchronized rap cadence",
            "clip_index": 0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["raw_compiled_prompt"] is not None
    assert "Voice Style (Role A): Fast-paced Atlanta trap flow" in data["raw_compiled_prompt"]
    assert "Vocal Delivery: Punchy synchronized rap cadence" in data["raw_compiled_prompt"]


def test_generate_with_character_roles_and_scenes():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/generate",
        json={
            "user_id": "usr_test",
            "project_id": "prj_test",
            "concept": "Harry vs Draco trap battle",
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Harry",
                    "description": "Young wizard with round glasses and lightning scar",
                    "reference_url": "https://example.com/harry.jpg",
                },
                {
                    "role_id": "Role B",
                    "name": "Draco",
                    "description": "Blonde rival wizard in silver-trimmed robes",
                    "reference_url": "https://example.com/draco.jpg",
                },
            ],
            "scenes": [
                {
                    "scene_number": 1,
                    "active_roles": ["Role A"],
                    "action": "Arriving at foggy courtyard rapping into microphone wand",
                    "dialogue": "I been cooking potions since first year!",
                },
                {
                    "scene_number": 2,
                    "active_roles": ["Role B"],
                    "action": "Stepping from shadows in high-gloss neon lighting",
                    "dialogue": "This is Trap or Die, Potter!",
                },
            ],
            "aesthetic_tags": ["2000s Atlanta Trap", "Fisheye lens", "Heavy 808 bass"],
            "environment_tag": "Gothic Hogwarts courtyard with neon stage lights",
            "clip_index": 0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["video_url"] is not None
    assert "generation_mode" in data
    assert data["generation_mode"] in ["LIVE_OMNI_FLASH", "LOCAL_PROCEDURAL_ANIMATION"]
    assert "error" in data


def test_generate_and_diff_endpoints_surface_error_and_generation_mode():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res_gen = client.post(
        "/api/generate",
        json={
            "user_id": "usr_test",
            "project_id": "prj_test",
            "prompt": "Snape 90s rap video",
        },
    )
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    assert gen_data["success"] is True
    assert "generation_mode" in gen_data
    assert gen_data["generation_mode"] in [
        "LIVE_OMNI_FLASH",
        "LOCAL_PROCEDURAL_ANIMATION",
    ]
    assert "error" in gen_data

    turn_id = gen_data["turn_id"]
    res_diff = client.post(
        "/api/diff",
        json={
            "user_id": "usr_test",
            "project_id": "prj_test",
            "prompt": "Add gold chains",
            "parent_turn_id": turn_id,
        },
    )
    assert res_diff.status_code == 200
    diff_data = res_diff.json()
    assert diff_data["success"] is True
    assert "generation_mode" in diff_data
    assert diff_data["generation_mode"] in [
        "LIVE_OMNI_FLASH",
        "LOCAL_PROCEDURAL_ANIMATION",
    ]
    assert "error" in diff_data
