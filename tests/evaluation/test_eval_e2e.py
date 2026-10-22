from fastapi.testclient import TestClient

from omnimash.api.app import create_app
from omnimash.evaluation.models import (
    DefectCategory,
    VideoEvaluationScorecard,
)
from omnimash.evaluation.strategy_bank import StrategyBankManager
from omnimash.evaluation.video_critic import VideoCriticAgent


def test_closed_loop_eval_and_prompt_repair_e2e():
    """E2E Test: Exercises the complete Concept -> Video -> Directorial Review ->
    AI Multimodal Critic -> Prompt Repair -> Re-Render closed loop.
    """
    app = create_app(mock_mode=True)
    client = TestClient(app)
    agent = app.state.agent

    # 1. Initial Generation with un-ducked audio defect
    session_id = "sess_e2e_closed_loop"
    turn_id = "turn_0"
    flawed_prompt = """### DIRECTORIAL INTENT
Parody scene at high fashion gala.
### CHARACTER PROFILES
[Role A] DumbleDior: Headmaster archmage in haute couture streetwear. Reference sheet attached.
### SCREENPLAY
[0-3s] [Role A] speaks words: "Welcome to Paris Fashion Week, bruv."
[3-6s] [Role A] struts down runway with glowing wand.
[6-10s] [Role A] poses for flashing cameras.
### AUDIO & ATMOSPHERE
Blaring techno beat at 135bpm with heavy distorted sub-bass throughout.
"""

    gen_resp = client.post(
        "/api/generate",
        json={
            "session_name": session_id,
            "prompt": flawed_prompt,
            "concept": "DumbleDior Paris Fashion Week",
        },
    )
    assert gen_resp.status_code == 200, gen_resp.text
    gen_data = gen_resp.json()
    assert gen_data["success"] is True
    video_url = gen_data["video_url"]
    assert video_url is not None

    # 2. Director reviews the render and flags Audio Drowned defect
    feedback_resp = client.post(
        "/api/feedback",
        json={
            "session_id": session_id,
            "turn_id": turn_id,
            "rating": 2,
            "defects": [DefectCategory.AUDIO_DROWNED.value],
            "critique_text": "Heavy sub-bass completely masked DumbleDior's speech at second 2.",
        },
    )
    assert feedback_resp.status_code == 200
    assert feedback_resp.json()["success"] is True

    # 3. Trigger On-Demand AI Multimodal Critic Diagnosis
    diag_resp = client.post(
        "/api/eval/diagnose",
        json={
            "session_id": session_id,
            "turn_id": turn_id,
            "prompt": flawed_prompt,
            "video_uri": video_url,
            "critique": "Music covers speech completely",
            "defects": [DefectCategory.AUDIO_DROWNED.value],
        },
    )
    assert diag_resp.status_code == 200, diag_resp.text
    scorecard_data = diag_resp.json()
    scorecard = VideoEvaluationScorecard.model_validate(scorecard_data)

    # Assert critic caught the audio defect
    assert DefectCategory.AUDIO_DROWNED in scorecard.detected_defects
    assert scorecard.audio_visual_harmony.score < 70.0
    assert scorecard.pass_verdict is False
    assert scorecard.suggested_prompt_patch is not None

    # 4. Assert PromptRefiner repaired the defect
    repaired_prompt = scorecard.suggested_prompt_patch
    assert "[Instrumental: ducking -18dB under speech]" in repaired_prompt

    # 5. Query Strategy Bank for applicable invariant rules
    strategy_mgr = StrategyBankManager(storage=agent.storage, mock_mode=True)
    rules = strategy_mgr.query_applicable_rules(defect_categories=scorecard.detected_defects)
    assert any(r.rule_id == "RULE-AUDIO-001" for r in rules)

    # 6. Re-Render with the repaired prompt
    re_render_resp = client.post(
        "/api/generate",
        json={
            "session_name": session_id,
            "prompt": repaired_prompt,
            "concept": "DumbleDior Paris Fashion Week",
        },
    )
    assert re_render_resp.status_code == 200
    re_render_data = re_render_resp.json()
    assert re_render_data["success"] is True
    assert re_render_data["video_url"] is not None

    # 7. Post-repair evaluation verifies pass verdict
    critic = VideoCriticAgent(storage=agent.storage, mock_mode=True)
    fixed_scorecard = critic.evaluate_video(
        session_id=session_id,
        turn_id="turn_1",
        prompt=repaired_prompt,
        video_uri=re_render_data["video_url"],
    )
    assert fixed_scorecard.pass_verdict is True
    assert fixed_scorecard.audio_visual_harmony.score >= 80.0
    assert DefectCategory.AUDIO_DROWNED not in fixed_scorecard.detected_defects
