import pytest
from fastapi.testclient import TestClient

from omnimash.api.app import create_app
from omnimash.evaluation.models import DefectCategory, UserFeedbackRecord


@pytest.fixture
def client():
    app = create_app(mock_mode=True)
    return TestClient(app)


def test_induce_rules_endpoint(client: TestClient):
    agent = client.app.state.agent
    project_id = "proj_api_induce"

    # Seed feedback records in mock storage
    agent.storage.save_feedback(
        session_id="sess_1",
        turn_id="turn_0",
        feedback=UserFeedbackRecord(
            session_id="sess_1",
            turn_id="turn_0",
            rating=2,
            defects=[DefectCategory.AUDIO_DROWNED.value],
            project_id=project_id,
        ),
        project_id=project_id,
    )
    agent.storage.save_feedback(
        session_id="sess_2",
        turn_id="turn_0",
        feedback=UserFeedbackRecord(
            session_id="sess_2",
            turn_id="turn_0",
            rating=2,
            defects=[DefectCategory.AUDIO_DROWNED.value],
            project_id=project_id,
        ),
        project_id=project_id,
    )

    resp = client.post(
        "/api/eval/induce-rules",
        json={"project_id": project_id, "min_defect_count": 2},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert "rules_induced" in data
    assert data["count"] == len(data["rules_induced"])
    assert data["count"] >= 1
    assert any(r["category"] == DefectCategory.AUDIO_DROWNED.value for r in data["rules_induced"])


def test_get_rules_endpoint(client: TestClient):
    resp = client.get("/api/eval/rules")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "rules" in data
    assert len(data["rules"]) >= 12
    # Check telemetry fields on rules
    first_rule = data["rules"][0]
    assert "confidence_score" in first_rule
    assert "times_applied" in first_rule
    assert "defect_reduction_rate" in first_rule

    # Scoped project query
    proj_resp = client.get("/api/eval/rules?project_id=test_proj_alpha")
    assert proj_resp.status_code == 200
    assert "rules" in proj_resp.json()


def test_prune_rules_endpoint(client: TestClient):
    resp = client.post(
        "/api/eval/rules/prune",
        json={"project_id": "test_prune_proj", "max_rules": 8},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert "strategy_bank" in data
    bank = data["strategy_bank"]
    assert "rules" in bank
    assert len(bank["rules"]) <= 8


def test_exemplars_post_and_get_endpoints(client: TestClient):
    project_id = "proj_exemplar_api"
    payload = {
        "session_id": "sess_ex_test",
        "concept": "Retro cyberpunk car chase through neon rain",
        "compiled_prompt": "### DIRECTORIAL INTENT\nHigh-octane synthwave pursuit.",
        "user_rating": 5,
        "style_preset": "cyberpunk",
        "project_id": project_id,
    }

    post_resp = client.post("/api/eval/exemplars", json=payload)
    assert post_resp.status_code == 200, post_resp.text
    record = post_resp.json()
    assert record["concept"] == payload["concept"]
    assert record["user_rating"] == 5
    assert record["style_preset"] == "cyberpunk"
    assert record["exemplar_id"].startswith("ex_")

    # Query exemplars back
    get_resp = client.get(
        f"/api/eval/exemplars?project_id={project_id}&style_preset=cyberpunk&limit=10"
    )
    assert get_resp.status_code == 200, get_resp.text
    exemplars = get_resp.json()
    assert isinstance(exemplars, list)
    assert len(exemplars) >= 1
    assert any(e["exemplar_id"] == record["exemplar_id"] for e in exemplars)


def test_path_traversal_protection(client: TestClient):
    traversal_ids = ["../etc/passwd", "..\\system32", "bad/path", "../malicious"]

    for bad_id in traversal_ids:
        # POST /api/eval/induce-rules
        resp1 = client.post("/api/eval/induce-rules", json={"project_id": bad_id})
        assert resp1.status_code == 400, f"Expected 400 for {bad_id}, got {resp1.status_code}"

        # GET /api/eval/rules
        resp2 = client.get(f"/api/eval/rules?project_id={bad_id}")
        assert resp2.status_code == 400, f"Expected 400 for {bad_id}, got {resp2.status_code}"

        # POST /api/eval/rules/prune
        resp3 = client.post("/api/eval/rules/prune", json={"project_id": bad_id})
        assert resp3.status_code == 400, f"Expected 400 for {bad_id}, got {resp3.status_code}"

        # GET /api/eval/exemplars
        resp4 = client.get(f"/api/eval/exemplars?project_id={bad_id}")
        assert resp4.status_code == 400, f"Expected 400 for {bad_id}, got {resp4.status_code}"

        # POST /api/eval/exemplars
        resp5 = client.post(
            "/api/eval/exemplars",
            json={
                "session_id": "valid_sess",
                "concept": "Valid concept",
                "compiled_prompt": "Valid prompt text",
                "project_id": bad_id,
            },
        )
        assert resp5.status_code == 400, f"Expected 400 for {bad_id}, got {resp5.status_code}"

    # Invalid session_id in POST /api/eval/exemplars
    resp_sess = client.post(
        "/api/eval/exemplars",
        json={
            "session_id": "../traversal_sess",
            "concept": "Valid concept",
            "compiled_prompt": "Valid prompt text",
        },
    )
    assert resp_sess.status_code == 400

    # Invalid style_preset with path traversal in GET /api/eval/exemplars
    resp_style = client.get("/api/eval/exemplars?style_preset=../bad_style")
    assert resp_style.status_code == 400


def test_ingest_exemplar_validation_errors(client: TestClient):
    # Rating < 4 must return 400
    resp_rating = client.post(
        "/api/eval/exemplars",
        json={
            "session_id": "sess_valid",
            "concept": "A sci-fi space battle",
            "compiled_prompt": "Prompt details",
            "user_rating": 3,
        },
    )
    assert resp_rating.status_code == 400
    assert "below 4-star minimum threshold" in resp_rating.json()["detail"]

    # Empty concept must return 400
    resp_concept = client.post(
        "/api/eval/exemplars",
        json={
            "session_id": "sess_valid",
            "concept": "   ",
            "compiled_prompt": "Prompt details",
            "user_rating": 5,
        },
    )
    assert resp_concept.status_code == 400
    assert "concept must be a non-empty string" in resp_concept.json()["detail"]

    # Empty compiled_prompt must return 400
    resp_prompt = client.post(
        "/api/eval/exemplars",
        json={
            "session_id": "sess_valid",
            "concept": "A sci-fi space battle",
            "compiled_prompt": "",
            "user_rating": 5,
        },
    )
    assert resp_prompt.status_code == 400
    assert "compiled_prompt must be a non-empty string" in resp_prompt.json()["detail"]


def test_induce_rules_reflected_in_get_rules(client: TestClient):
    agent = client.app.state.agent
    project_id = "proj_reflect_test"

    agent.storage.save_feedback(
        session_id="s1",
        turn_id="t1",
        feedback=UserFeedbackRecord(
            session_id="s1",
            turn_id="t1",
            rating=1,
            defects=[DefectCategory.PHANTOM_KEYFRAME.value],
            project_id=project_id,
        ),
        project_id=project_id,
    )
    agent.storage.save_feedback(
        session_id="s2",
        turn_id="t1",
        feedback=UserFeedbackRecord(
            session_id="s2",
            turn_id="t1",
            rating=1,
            defects=[DefectCategory.PHANTOM_KEYFRAME.value],
            project_id=project_id,
        ),
        project_id=project_id,
    )

    induce_resp = client.post(
        "/api/eval/induce-rules",
        json={"project_id": project_id, "min_defect_count": 2},
    )
    assert induce_resp.status_code == 200
    induced_rules = induce_resp.json()["rules_induced"]
    assert len(induced_rules) >= 1
    induced_id = induced_rules[0]["rule_id"]

    # Verify that GET /api/eval/rules with project_id reflects the newly induced rule
    rules_resp = client.get(f"/api/eval/rules?project_id={project_id}")
    assert rules_resp.status_code == 200
    rules = rules_resp.json()["rules"]
    assert any(r["rule_id"] == induced_id for r in rules)
