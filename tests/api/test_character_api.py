from fastapi.testclient import TestClient

from omnimash.api.app import create_app


def test_save_character_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    payload = {
        "session_name": "test_session_1",
        "character": {
            "role_id": "Role A",
            "name": "Harry Drip",
            "description": "Wizard in designer tracksuit",
            "reference_url": "gs://bucket/harry.jpg",
            "aesthetic_tags": ["Gucci", "Cartier"],
            "voice_style": "Atlanta trap flow",
        },
        "is_library": True,
    }

    res = client.post("/api/characters/save", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "gcs_uri" in data
    assert "gs://" in data["gcs_uri"]
    assert "message" in data


def test_list_characters_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res = client.get("/api/characters")
    assert res.status_code == 200
    data = res.json()
    assert "characters" in data
    assert isinstance(data["characters"], list)
    assert len(data["characters"]) > 0
    first_char = data["characters"][0]
    assert "role_id" in first_char
    assert "name" in first_char

    # Query with session_name
    res_session = client.get("/api/characters?session_name=test_session_1")
    assert res_session.status_code == 200
    assert "characters" in res_session.json()


def test_load_character_endpoint_success_and_not_found():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    # First save a character
    client.post(
        "/api/characters/save",
        json={
            "session_name": "session_load_test",
            "character": {
                "role_id": "Role B",
                "name": "Draco Ice",
                "description": "Blonde rival wizard with iced chain",
                "reference_url": "gs://bucket/draco.jpg",
                "aesthetic_tags": ["Diamond Chain"],
                "voice_style": "British drawl",
            },
            "is_library": False,
        },
    )

    # Load existing character
    res = client.post(
        "/api/characters/load",
        json={"slug": "draco_ice", "session_name": "session_load_test"},
    )
    assert res.status_code == 200
    char_data = res.json()
    assert char_data["name"] == "Draco Ice"
    assert char_data["role_id"] == "Role B"

    # Load non-existent character
    res_404 = client.post(
        "/api/characters/load",
        json={"slug": "completely_unknown_character_xyz"},
    )
    assert res_404.status_code == 404


def test_save_and_load_session_roster_endpoints():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    roster_payload = {
        "session_name": "session_roster_test",
        "characters": [
            {
                "role_id": "Role A",
                "name": "Harry Drip",
                "description": "Wizard with Cartier glasses",
                "reference_url": "gs://bucket/harry.jpg",
                "aesthetic_tags": ["Gucci"],
                "voice_style": "Trap flow",
            },
            {
                "role_id": "Role B",
                "name": "Draco Ice",
                "description": "Blonde wizard with diamond chain",
                "reference_url": "gs://bucket/draco.jpg",
                "aesthetic_tags": ["Ice"],
                "voice_style": "Aggressive cadence",
            },
        ],
    }

    # Save roster
    res_save = client.post("/api/characters/save-roster", json=roster_payload)
    assert res_save.status_code == 200
    data_save = res_save.json()
    assert data_save["success"] is True
    assert "roster.json" in data_save["gcs_uri"]

    # Load roster
    res_load = client.get("/api/characters/roster?session_name=session_roster_test")
    assert res_load.status_code == 200
    data_load = res_load.json()
    assert "characters" in data_load
    assert len(data_load["characters"]) == 2
    assert data_load["characters"][0]["name"] == "Harry Drip"
    assert data_load["characters"][1]["name"] == "Draco Ice"

    # Load empty roster for uninitialized session
    res_empty = client.get("/api/characters/roster?session_name=nonexistent_session")
    assert res_empty.status_code == 200
    assert res_empty.json()["characters"] == []
