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


def test_e2e_commit_and_reanchor_pipeline() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)
    r1 = client.post(
        "/api/generate",
        json={
            "user_id": "u_e2e",
            "project_id": "p_e2e",
            "prompt": "Initial",
            "clip_index": 0,
        },
    )
    t1 = r1.json()["turn_id"]

    t_prev = t1
    for i in range(3):
        r = client.post(
            "/api/generate",
            json={
                "user_id": "u_e2e",
                "project_id": "p_e2e",
                "prompt": f"Edit {i}",
                "clip_index": 0,
                "parent_turn_id": t_prev,
            },
        )
        t_prev = r.json()["turn_id"]
        if i == 2:
            assert r.json()["status"] == "COMMIT_RECOMMENDED"

    rc = client.post(
        "/api/commit",
        json={
            "user_id": "u_e2e",
            "project_id": "p_e2e",
            "turn_id": t_prev,
            "next_prompt": "Reanchored turn",
        },
    )
    assert rc.json()["status"] == "REANCHORED"
    assert rc.json()["depth"] == 0


def test_e2e_compiled_prompt_generation() -> None:
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/generate",
        json={
            "user_id": "u_comp",
            "project_id": "p_comp",
            "prompt": "Snape in 90s rap video",
            "clip_index": 0,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "video_url" in data
