from __future__ import annotations

from urllib.parse import unquote
import pytest
from fastapi.testclient import TestClient

from omnimash.api.app import create_app
from omnimash.evaluation.models import DefectCategory


@pytest.fixture
def client() -> TestClient:
    app = create_app(mock_mode=True)
    return TestClient(app)


def test_session_fork_and_turn0_regeneration_lifecycle(client: TestClient) -> None:
    """End-to-end verification of session forking and fresh Turn-0 regeneration.

    1. Initial generation in session 1 (`orbit_duel_v1`), verifying Turn-0 baseline.
    2. Fork session to `orbit_duel_v2` via POST /api/projects/prj_default/sessions/fork.
    3. Verify response has session_name == 'orbit_duel_v2' and parent_session_name == 'orbit_duel_v1'.
    4. Generate in `orbit_duel_v2` with parent_turn_id: None and a tweaked prompt/action.
    5. Assert generation succeeds with turn_id / Turn-0 video, verifying it was rendered
       from scratch rather than being an edit diff, and verify the video url points
       to the orbit_duel_v2 session path.
    """
    # 1. Initial generation in session 1 (orbit_duel_v1)
    gen_payload_1 = {
        "user_id": "usr_pilot",
        "project_id": "prj_default",
        "session_name": "orbit_duel_v1",
        "prompt": "Two starfighters dogfighting in low orbit around a neon gas giant with planetary rings",
        "clip_index": 0,
        "parent_turn_id": None,
    }
    res1 = client.post("/api/generate", json=gen_payload_1)
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert data1["success"] is True
    assert data1["depth"] == 0

    # Verify Turn-0 baseline generation from scratch in session 1
    turn_id_1 = data1["turn_id"]
    assert turn_id_1 is not None
    assert "turn_0_video.mp4" in data1["video_url"]
    decoded_url_1 = unquote(data1["video_url"])
    assert "projects/prj_default/sessions/orbit_duel_v1" in decoded_url_1
    assert "turn_0" in data1["video_url"] or turn_id_1 == "turn_0"

    # 2. Fork session to orbit_duel_v2 via POST /api/projects/prj_default/sessions/fork
    fork_payload = {
        "source_session_name": "orbit_duel_v1",
        "new_session_name": "orbit_duel_v2",
        "copy_roster": True,
    }
    fork_res = client.post("/api/projects/prj_default/sessions/fork", json=fork_payload)
    assert fork_res.status_code == 200, fork_res.text
    fork_data = fork_res.json()

    # 3. Verify response metadata
    assert fork_data["success"] is True
    assert fork_data["project_name"] == "prj_default"
    assert fork_data["session_name"] == "orbit_duel_v2"
    assert fork_data["parent_session_name"] == "orbit_duel_v1"
    assert "orbit_duel_v2" in fork_data["gcs_uri"]
    assert fork_data["iteration_number"] >= 2

    # 4. Generate in orbit_duel_v2 with parent_turn_id: None and a tweaked prompt/action
    tweaked_prompt = (
        "Two starfighters engaging laser cannons in low orbit around a neon gas giant "
        "with dynamic particle shield explosions and lens flare"
    )
    gen_payload_2 = {
        "user_id": "usr_pilot",
        "project_id": "prj_default",
        "session_name": "orbit_duel_v2",
        "prompt": tweaked_prompt,
        "clip_index": 0,
        "parent_turn_id": None,
    }
    res2 = client.post("/api/generate", json=gen_payload_2)
    assert res2.status_code == 200, res2.text
    data2 = res2.json()

    # 5. Assert generation succeeds with turn_id / Turn-0 video, verifying it was rendered from scratch
    # rather than being an edit diff, and verify the video url points to orbit_duel_v2 session path
    assert data2["success"] is True
    assert (
        data2["depth"] == 0
    )  # 0 indicates fresh Turn-0 generation from scratch, NOT an edit diff (depth >= 1)
    assert "turn_0_video.mp4" in data2["video_url"]
    decoded_url_2 = unquote(data2["video_url"])
    assert "projects/prj_default/sessions/orbit_duel_v2" in decoded_url_2
    assert "turn_diff" not in data2["video_url"]

    turn_id_2 = data2["turn_id"]
    assert turn_id_2 is not None
    assert turn_id_2 != turn_id_1
    assert "turn_0" in data2["video_url"] or turn_id_2 == "turn_0"


def test_mode4_critic_and_prompt_patch_e2e(client: TestClient) -> None:
    """End-to-end verification of Mode 4 AI critic review, diagnosis, and patched re-render.

    1. Generate intent plan / render direct in Mode 4.
    2. Post directorial review to /api/evaluation/review with rating=2 and defects=['likeness_drift'].
    3. Diagnose with critic via POST /api/eval/diagnose.
    4. Re-render direct with compiled_override containing the patched prompt. Assert the
       rendered result uses the patched prompt and succeeds with HTTP 200.
    """
    session_name = "mode4_critic_patch_sess"

    # 1. Generate intent plan / render direct in Mode 4
    render_payload = {
        "intent": "Two cyberpunk bounty hunters dueling with energy blades in a rain-soaked neon alley",
        "optional_inputs": {
            "audio_beat": "130 BPM Gritty Cyberpunk Synthwave Beat",
        },
        "session_name": session_name,
        "resolution": "720p",
        "aspect_ratio": "16:9",
    }
    render_res = client.post("/api/intent/render-direct", json=render_payload)
    assert render_res.status_code == 200, render_res.text
    render_data = render_res.json()
    assert render_data["success"] is True
    assert render_data["video_url"] is not None
    initial_compiled_prompt = render_data["raw_compiled_prompt"]
    assert initial_compiled_prompt is not None

    # 2. Post directorial review to /api/evaluation/review with rating=2 and defects=['likeness_drift']
    review_payload = {
        "session_id": session_name,
        "turn_id": "turn_0",
        "rating": 2,
        "defects": ["likeness_drift"],
        "critique_text": "Character facial features and cybernetic eye implants drift across camera angles.",
    }
    review_res = client.post("/api/evaluation/review", json=review_payload)
    assert review_res.status_code == 200, review_res.text
    review_data = review_res.json()
    assert review_data["success"] is True
    assert "feedback_id" in review_data

    # Also verify feedback can be fetched from storage
    get_fb_res = client.get(f"/api/feedback/{session_name}/turn_0")
    assert get_fb_res.status_code == 200
    assert get_fb_res.json()["rating"] == 2
    assert DefectCategory.LIKENESS_DRIFT.value in get_fb_res.json()["defects"]

    # 3. Diagnose with critic via POST /api/eval/diagnose
    diagnose_payload = {
        "session_id": session_name,
        "turn_id": "turn_0",
        "prompt": initial_compiled_prompt,
        "defects": ["likeness_drift"],
        "critique": "Character facial features and cybernetic eye implants drift across camera angles.",
    }
    diag_res = client.post("/api/eval/diagnose", json=diagnose_payload)
    assert diag_res.status_code == 200, diag_res.text
    diag_data = diag_res.json()
    assert DefectCategory.LIKENESS_DRIFT.value in diag_data["detected_defects"]

    suggested_patch = diag_data.get("suggested_prompt_patch")
    assert suggested_patch is not None, "Critic failed to generate a suggested_prompt_patch"
    assert len(suggested_patch.strip()) > 0

    # 4. Re-render direct with compiled_override containing the patched prompt.
    # Assert the rendered result uses the patched prompt and succeeds with HTTP 200.
    rerender_payload = {
        "intent": "Two cyberpunk bounty hunters dueling with energy blades in a rain-soaked neon alley",
        "session_name": session_name,
        "resolution": "720p",
        "aspect_ratio": "16:9",
        "compiled_override": suggested_patch,
    }
    rerender_res = client.post("/api/intent/render-direct", json=rerender_payload)
    assert rerender_res.status_code == 200, rerender_res.text
    rerender_data = rerender_res.json()
    assert rerender_data["success"] is True
    assert rerender_data["video_url"] is not None
    assert rerender_data["raw_compiled_prompt"] == suggested_patch
