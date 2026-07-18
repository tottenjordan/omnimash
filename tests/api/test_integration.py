from fastapi.testclient import TestClient
from omnimash.api.app import create_app


def test_full_e2e_flow() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)

    # 1. Initial clip generation
    resp1 = client.post(
        "/api/generate",
        json={
            "user_id": "usr_prod",
            "project_id": "prj_mashup",
            "prompt": "Severus Snape in 90s rap video",
            "clip_index": 0,
        },
    )
    assert resp1.status_code == 200
    turn1 = resp1.json()
    assert turn1["success"] is True
    turn_id_1 = turn1["turn_id"]

    # 2. Conversational diff branching
    resp2 = client.post(
        "/api/generate",
        json={
            "user_id": "usr_prod",
            "project_id": "prj_mashup",
            "prompt": "Add diamond chains and green neon lights",
            "clip_index": 0,
            "parent_turn_id": turn_id_1,
        },
    )
    assert resp2.status_code == 200
    turn2 = resp2.json()
    assert turn2["success"] is True
    assert turn2["turn_id"] != turn_id_1

    # 3. Test UI static / dashboard endpoint
    resp_ui = client.get("/")
    assert resp_ui.status_code == 200
    assert "OmniMash" in resp_ui.text
