import os
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from omnimash.api.app import create_app
from omnimash.api.deps import get_agent


def test_projects_and_sessions_reject_path_traversal_sequences():
    """SEC-02: Verify project_name and session_name reject '../', '/', '\\', and invalid characters with HTTP 400."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    malicious_identifiers = [
        "../other_project",
        "..\\windows_traversal",
        "proj/subpath",
        "proj..escape",
        "bad name with spaces!",
        "   ",
    ]

    for bad_id in malicious_identifiers:
        res_proj = client.post("/api/projects/create", json={"project_name": bad_id})
        assert res_proj.status_code == 400, f"Expected 400 for project_name={bad_id!r}"

        res_sess = client.post(
            "/api/projects/valid_project/sessions/create",
            json={"session_name": bad_id},
        )
        assert res_sess.status_code == 400, f"Expected 400 for session_name={bad_id!r}"

    res_path_proj = client.get("/api/projects/..%5Cescape/sessions")
    assert res_path_proj.status_code == 400

    res_char_save = client.post(
        "/api/characters/save",
        json={
            "project_name": "../escaped_project",
            "character": {"role_id": "Role A", "name": "Test"},
        },
    )
    assert res_char_save.status_code == 400


def test_app_factory_is_thin_and_supports_dependency_overrides():
    """ARC-01 & ARC-02: Verify src/omnimash/api/app.py is <120 lines and supports FastAPI dependency_overrides."""
    app_py_path = os.path.join(os.getcwd(), "src", "omnimash", "api", "app.py")
    with open(app_py_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) < 120, f"Expected app.py to be <120 lines, found {len(lines)}"

    app = create_app(mock_mode=True)
    mock_agent = MagicMock()
    mock_agent.storage.list_projects.return_value = ["overridden_project_1"]
    app.dependency_overrides[get_agent] = lambda: mock_agent

    client = TestClient(app)
    res = client.get("/api/projects")
    assert res.status_code == 200
    assert res.json()["projects"] == ["overridden_project_1"]
    app.dependency_overrides.clear()
