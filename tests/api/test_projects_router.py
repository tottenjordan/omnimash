from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from omnimash.api.app import create_app
from omnimash.storage.gcs import GcsStorageManager


@pytest.fixture(autouse=True)
def _reset_shared_clients():
    GcsStorageManager._SHARED_CLIENTS.clear()
    yield
    GcsStorageManager._SHARED_CLIENTS.clear()


@pytest.fixture
def client():
    app = create_app(mock_mode=True)
    return TestClient(app)


def test_fork_project_session_endpoint_success(client: TestClient):
    """Verifies creating a session under a project, forking it, and checking response and listing."""
    # 1. Create base project and session
    create_sess_res = client.post(
        "/api/projects/prj_alpha/sessions/create",
        json={"session_name": "shot_v1"},
    )
    assert create_sess_res.status_code == 200

    # 2. Fork session
    res = client.post(
        "/api/projects/prj_alpha/sessions/fork",
        json={"source_session_name": "shot_v1", "new_session_name": "shot_v2"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["project_name"] == "prj_alpha"
    assert data["session_name"] == "shot_v2"
    assert data["parent_session_name"] == "shot_v1"
    assert data["iteration_number"] == 2
    assert "message" in data and len(data["message"]) > 0
    assert "gs://" in data["gcs_uri"]

    # 3. Verify both sessions appear in list_project_sessions
    list_res = client.get("/api/projects/prj_alpha/sessions")
    assert list_res.status_code == 200
    sessions = list_res.json()["sessions"]
    assert "shot_v1" in sessions
    assert "shot_v2" in sessions


def test_fork_project_session_same_name_fails(client: TestClient):
    """Verifies HTTP 400 when target session is identical to source session."""
    client.post(
        "/api/projects/prj_alpha/sessions/create",
        json={"session_name": "shot_same"},
    )
    res = client.post(
        "/api/projects/prj_alpha/sessions/fork",
        json={"source_session_name": "shot_same", "new_session_name": "shot_same"},
    )
    assert res.status_code == 400
    assert "identical" in res.json()["detail"].lower()


def test_fork_project_session_invalid_identifier(client: TestClient):
    """Verifies HTTP 400 for path traversal sequences and invalid characters."""
    # Path traversal in new_session_name
    res_traversal_new = client.post(
        "/api/projects/prj_alpha/sessions/fork",
        json={"source_session_name": "shot_v1", "new_session_name": "../escape"},
    )
    assert res_traversal_new.status_code == 400

    # Path traversal in source_session_name
    res_traversal_src = client.post(
        "/api/projects/prj_alpha/sessions/fork",
        json={"source_session_name": "../escape", "new_session_name": "shot_v2"},
    )
    assert res_traversal_src.status_code == 400

    # Path traversal in project_name URL parameter
    res_traversal_prj = client.post(
        "/api/projects/..%5Cescape/sessions/fork",
        json={"source_session_name": "shot_v1", "new_session_name": "shot_v2"},
    )
    assert res_traversal_prj.status_code == 400

    # Illegal characters (spaces)
    res_invalid_chars = client.post(
        "/api/projects/prj_alpha/sessions/fork",
        json={"source_session_name": "shot_v1", "new_session_name": "has space"},
    )
    assert res_invalid_chars.status_code == 400


def test_fork_project_session_with_roster(client: TestClient):
    """Saves character in source session, forks with copy_roster=True, and verifies child session has roster."""
    client.post(
        "/api/projects/prj_roster/sessions/create",
        json={"session_name": "parent_shot"},
    )
    char_payload = {
        "session_name": "parent_shot",
        "characters": [
            {
                "role_id": "Role A",
                "name": "Wizard Hero",
                "description": "Powerful sorcerer",
                "reference_url": "gs://bucket/hero.png",
            }
        ],
    }
    save_roster_res = client.post("/api/characters/save-roster", json=char_payload)
    assert save_roster_res.status_code == 200

    # Fork with copy_roster=True
    fork_res = client.post(
        "/api/projects/prj_roster/sessions/fork",
        json={
            "source_session_name": "parent_shot",
            "new_session_name": "child_shot",
            "copy_roster": True,
        },
    )
    assert fork_res.status_code == 200

    # Verify child session has roster
    roster_res = client.get("/api/characters/roster?session_name=child_shot")
    assert roster_res.status_code == 200
    roster_chars = roster_res.json()["characters"]
    assert len(roster_chars) == 1
    assert roster_chars[0]["name"] == "Wizard Hero"
    assert roster_chars[0]["role_id"] == "Role A"


def test_fork_project_session_copy_roster_false(client: TestClient):
    """Verifies that fork with copy_roster=False does not copy the roster to child session."""
    client.post(
        "/api/projects/prj_no_roster/sessions/create",
        json={"session_name": "parent_shot_nr"},
    )
    char_payload = {
        "session_name": "parent_shot_nr",
        "characters": [
            {
                "role_id": "Role B",
                "name": "Knight",
            }
        ],
    }
    save_roster_res = client.post("/api/characters/save-roster", json=char_payload)
    assert save_roster_res.status_code == 200

    # Fork with copy_roster=False
    fork_res = client.post(
        "/api/projects/prj_no_roster/sessions/fork",
        json={
            "source_session_name": "parent_shot_nr",
            "new_session_name": "child_shot_nr",
            "copy_roster": False,
        },
    )
    assert fork_res.status_code == 200

    # Verify child session has no characters
    roster_res = client.get("/api/characters/roster?session_name=child_shot_nr")
    assert roster_res.status_code == 200
    assert len(roster_res.json()["characters"]) == 0
