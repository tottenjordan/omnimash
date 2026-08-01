from fastapi.testclient import TestClient
from omnimash.api.app import create_app


def test_save_storyboard_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    payload = {
        "name": "Test Storyboard Save",
        "storyboard_data": {
            "concept": "Cyberpunk cooking battle",
            "scenes": [
                {
                    "shot_index": 1,
                    "action": "Gordon slicing neon tuna",
                }
            ],
        },
        "session_name": "test_session_sb",
        "is_library": True,
    }
    res = client.post("/api/storyboards/save", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "gcs_uri" in data
    assert "message" in data


def test_list_storyboards_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    client.post(
        "/api/storyboards/save",
        json={
            "name": "Listed Storyboard",
            "storyboard_data": {
                "concept": "Rap battle scene",
                "scenes": [
                    {"shot_index": 1, "action": "Shot 1"},
                    {"shot_index": 2, "action": "Shot 2"},
                ],
            },
            "session_name": "list_session_test",
            "is_library": True,
        },
    )

    res = client.get("/api/storyboards")
    assert res.status_code == 200
    data = res.json()
    assert "storyboards" in data
    assert isinstance(data["storyboards"], list)

    slugs = [sb["slug"] for sb in data["storyboards"]]
    assert "listed_storyboard" in slugs

    res_session = client.get("/api/storyboards?session_name=list_session_test")
    assert res_session.status_code == 200
    assert "storyboards" in res_session.json()


def test_load_storyboard_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    client.post(
        "/api/storyboards/save",
        json={
            "name": "Load Me Storyboard",
            "storyboard_data": {
                "concept": "Trap Rap Showdown",
                "scenes": [
                    {"shot_index": 1, "action": "Shot 1 Action"},
                ],
            },
            "session_name": "load_session_test",
            "is_library": True,
        },
    )

    res = client.post(
        "/api/storyboards/load",
        json={"slug": "load_me_storyboard", "session_name": "load_session_test"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Load Me Storyboard"
    assert data["slug"] == "load_me_storyboard"
    assert data["concept"] == "Trap Rap Showdown"
    assert len(data["scenes"]) == 1

    res_404 = client.post(
        "/api/storyboards/load",
        json={"slug": "non_existent_storyboard_xyz"},
    )
    assert res_404.status_code == 404


def test_delete_storyboard_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    client.post(
        "/api/storyboards/save",
        json={
            "name": "Delete Me Storyboard",
            "storyboard_data": {
                "concept": "To be deleted",
                "scenes": [],
            },
            "session_name": "delete_session_test",
            "is_library": True,
        },
    )

    res_list = client.get("/api/storyboards?session_name=delete_session_test")
    assert res_list.status_code == 200
    slugs = [sb["slug"] for sb in res_list.json()["storyboards"]]
    assert "delete_me_storyboard" in slugs

    res_delete = client.post(
        "/api/storyboards/delete",
        json={"slug": "delete_me_storyboard", "session_name": "delete_session_test"},
    )
    assert res_delete.status_code == 200
    delete_data = res_delete.json()
    assert delete_data["success"] is True

    res_load_after = client.post(
        "/api/storyboards/load",
        json={"slug": "delete_me_storyboard", "session_name": "delete_session_test"},
    )
    assert res_load_after.status_code == 404

    res_delete_again = client.post(
        "/api/storyboards/delete",
        json={"slug": "delete_me_storyboard", "session_name": "delete_session_test"},
    )
    assert res_delete_again.status_code == 200
    assert res_delete_again.json()["success"] is False
