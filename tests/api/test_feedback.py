import pytest
from fastapi.testclient import TestClient

from omnimash.api.app import create_app
from omnimash.evaluation.models import DefectCategory


@pytest.fixture
def client():
    app = create_app(mock_mode=True)
    return TestClient(app)


def test_post_and_get_feedback(client: TestClient):
    payload = {
        "session_id": "test_session_doma",
        "turn_id": "turn_0",
        "rating": 4,
        "defects": [DefectCategory.LIKENESS_DRIFT.value],
        "critique_text": "Character hair style changed slightly in shot 2.",
    }
    # Submit feedback
    resp = client.post("/api/feedback", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert "feedback_id" in data

    # Retrieve feedback
    get_resp = client.get("/api/feedback/test_session_doma/turn_0")
    assert get_resp.status_code == 200, get_resp.text
    fb_data = get_resp.json()
    assert fb_data["rating"] == 4
    assert DefectCategory.LIKENESS_DRIFT.value in fb_data["defects"]
    assert fb_data["critique_text"] == "Character hair style changed slightly in shot 2."


def test_get_feedback_not_found(client: TestClient):
    resp = client.get("/api/feedback/non_existent_session/turn_999")
    assert resp.status_code == 404


def test_get_scorecard(client: TestClient):
    # First save a scorecard via storage
    app = client.app
    agent = app.state.agent
    scorecard_payload = {
        "evaluation_id": "eval_test_123",
        "session_id": "test_session_doma",
        "turn_id": "turn_0",
        "overall_rating": 88.0,
        "video_text_adherence": {"score": 90.0, "passed": True, "evidence": "Good adherence"},
        "character_likeness": {"score": 85.0, "passed": True, "evidence": "Consistent actor"},
        "audio_visual_harmony": {"score": 92.0, "passed": True, "evidence": "Music ducks speech"},
        "tag_and_index_integrity": {"score": 100.0, "passed": True, "evidence": "Perfect tags"},
        "detected_defects": [],
        "verbal_critique": "Solid cinematic cut.",
        "suggested_prompt_patch": None,
        "pass_verdict": True,
    }
    agent.storage.save_scorecard("test_session_doma", "turn_0", scorecard_payload)

    # Now query via API
    resp = client.get("/api/eval/scorecard/test_session_doma/turn_0")
    assert resp.status_code == 200, resp.text
    sc_data = resp.json()
    assert sc_data["overall_rating"] == 88.0
    assert sc_data["pass_verdict"] is True
    assert sc_data["evaluation_id"] == "eval_test_123"


def test_get_scorecard_not_found(client: TestClient):
    resp = client.get("/api/eval/scorecard/non_existent/turn_0")
    assert resp.status_code == 404


def test_post_eval_diagnose_endpoint(client: TestClient):
    payload = {
        "session_id": "test_session_diag",
        "turn_id": "turn_0",
        "prompt": """### DIRECTORIAL INTENT
Parody scene.
### CHARACTER PROFILES
[Role A] Host.
### SCREENPLAY
[0-3s] [Role A] speaks words: "Welcome to the grand showdown!"
### AUDIO & ATMOSPHERE
Blaring techno beat at 140bpm with heavy sub-bass.
""",
        "video_uri": "gs://omnimash-media/test/clip.mp4",
        "critique": "Music covers speech completely",
        "defects": [DefectCategory.AUDIO_DROWNED.value],
    }
    resp = client.post("/api/eval/diagnose", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "overall_rating" in data
    assert "audio_visual_harmony" in data
    assert DefectCategory.AUDIO_DROWNED.value in data["detected_defects"]
    assert data["pass_verdict"] is False
    assert data["suggested_prompt_patch"] is not None
    assert "[Instrumental: ducking -18dB under speech]" in data["suggested_prompt_patch"]

    # Verify that scorecard was automatically saved in GCS storage
    stored_scorecard = client.app.state.agent.storage.get_scorecard("test_session_diag", "turn_0")
    assert stored_scorecard is not None
    assert stored_scorecard["overall_rating"] == data["overall_rating"]


def test_feedback_and_diagnose_path_traversal_protection(client: TestClient):
    traversal_ids = [
        "../../etc/passwd",
        "session/../../root",
        "valid_id\x00extra",
        "invalid..name",
        "dir\\traversal",
    ]

    for bad_id in traversal_ids:
        # POST /api/feedback with bad session_id
        res = client.post(
            "/api/feedback",
            json={"session_id": bad_id, "turn_id": "turn_0", "rating": 5},
        )
        assert res.status_code == 400

        # POST /api/feedback with bad project_id
        res_proj = client.post(
            "/api/feedback",
            json={"session_id": "sess_ok", "turn_id": "turn_0", "project_id": bad_id, "rating": 5},
        )
        assert res_proj.status_code == 400

        # GET /api/eval/scorecard with bad project_id
        res_sc = client.get("/api/eval/scorecard/sess_ok/turn_0", params={"project_id": bad_id})
        assert res_sc.status_code == 400

        # GET /api/feedback with bad project_id
        res_fb_proj = client.get("/api/feedback/sess_ok/turn_0", params={"project_id": bad_id})
        assert res_fb_proj.status_code == 400

        # POST /api/eval/diagnose with bad project_id
        res_diag = client.post(
            "/api/eval/diagnose",
            json={"session_id": "sess_ok", "turn_id": "turn_0", "project_id": bad_id},
        )
        assert res_diag.status_code == 400

    # Path parameter invalid ID checks
    assert client.get("/api/feedback/invalid..name/turn_0").status_code == 400
    assert client.get("/api/feedback/dir\\traversal/turn_0").status_code == 400
    assert client.get("/api/eval/scorecard/invalid..name/turn_0").status_code == 400


def test_project_scoped_feedback_and_scorecard_api(client: TestClient):
    # Submit project-scoped feedback
    res = client.post(
        "/api/feedback",
        json={
            "session_id": "scoped_sess",
            "turn_id": "turn_0",
            "project_id": "project_cyber",
            "rating": 5,
            "critique_text": "Cyber project looks great!",
        },
    )
    assert res.status_code == 200
    assert res.json()["success"] is True

    # Retrieve with matching project_id
    get_res = client.get("/api/feedback/scoped_sess/turn_0", params={"project_id": "project_cyber"})
    assert get_res.status_code == 200
    assert get_res.json()["critique_text"] == "Cyber project looks great!"

    # Retrieve with different project_id should be 404
    mismatch_res = client.get(
        "/api/feedback/scoped_sess/turn_0", params={"project_id": "project_other"}
    )
    assert mismatch_res.status_code == 404


def test_post_evaluation_review_endpoint(client: TestClient):
    payload = {
        "session_id": "test_session_review_alias",
        "turn_id": "turn_0",
        "rating": 5,
        "defects": [DefectCategory.LIKENESS_DRIFT.value],
        "critique_text": "Flawless cinematic lighting and framing.",
        "project_id": "project_alpha",
    }
    resp = client.post("/api/evaluation/review", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert "feedback_id" in data
    assert data["message"] == "Feedback saved to GCS storage."

    # Verify retrieval via feedback GET
    get_resp = client.get(
        "/api/feedback/test_session_review_alias/turn_0",
        params={"project_id": "project_alpha"},
    )
    assert get_resp.status_code == 200
    fb_data = get_resp.json()
    assert fb_data["rating"] == 5
    assert fb_data["critique_text"] == "Flawless cinematic lighting and framing."
