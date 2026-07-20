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
