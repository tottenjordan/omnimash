from fastapi.testclient import TestClient
from omnimash.api.app import create_app


def test_draft_batch_generates_unique_video_urls_and_gcs_uris_per_variation() -> None:
    """Verify /api/storyboard/draft-batch generates distinct video_url and gcs_uri for each variation of the same shot."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    resp = client.post(
        "/api/storyboard/draft-batch",
        json={
            "session_name": "draft_unique_test_session",
            "variations_per_shot": 3,
            "resolution": "360p",
            "aspect_ratio": "16:9",
            "shots": [
                {
                    "shot_index": 1,
                    "action": "Wizard DJ drops heavy 808 beat in neon dungeon",
                    "style_lighting": "Gritty 90s Cyberpunk",
                }
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["total_drafts"] == 3
    drafts = data["drafts"]
    assert len(drafts) == 3

    video_urls = [d["video_url"] for d in drafts]
    gcs_uris = [d["gcs_uri"] for d in drafts]
    turn_ids = [d["turn_id"] for d in drafts]

    # Every variation must have a non-empty, unique video_url, gcs_uri, and turn_id
    assert all(video_urls)
    assert all(gcs_uris)
    assert len(set(video_urls)) == 3
    assert len(set(gcs_uris)) == 3
    assert len(set(turn_ids)) == 3


def test_generate_shot_auto_keyframe_includes_first_frame_anchor_in_compiled_prompt() -> None:
    """Verify /api/generate-shot and /api/journey3/generate-shot auto-generate the keyframe BEFORE compiling the prompt so <FIRST_FRAME>@KeyframeSeed is present."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    # 1. Test /api/generate-shot with keyframe_image_url=None
    resp1 = client.post(
        "/api/generate-shot",
        json={
            "session_name": "auto_kf_order_session",
            "shot_index": 1,
            "action": "Cyberpunk alchemist stirring glowing cauldron",
            "style_lighting": "Neon Noir",
            "keyframe_image_url": None,
        },
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["success"] is True
    assert data1["keyframe_image_url"]
    assert "<FIRST_FRAME>@KeyframeSeed" in (data1["raw_compiled_prompt"] or "")

    # 2. Test /api/journey3/generate-shot with keyframe_image_url=None
    resp2 = client.post(
        "/api/journey3/generate-shot",
        json={
            "session_id": "auto_kf_j3_session",
            "shot_index": 1,
            "action_directive": "Cyberpunk alchemist stirring glowing cauldron",
            "keyframe_image_url": None,
        },
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["success"] is True
    assert data2["keyframe_image_url"]
    assert "<FIRST_FRAME>@KeyframeSeed" in (data2["raw_compiled_prompt"] or "")
