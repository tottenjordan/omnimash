import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from omnimash.api.app import create_app


def test_draft_batch_isolates_single_variation_exception():
    """COR-02: Verify an uncaught exception in one variation marks only that item FAILED without crashing the batch."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    orig_process = app.state.agent.process_user_turn
    call_counter = {"count": 0}

    def _flaky_process_user_turn(*args, **kwargs):
        call_counter["count"] += 1
        if kwargs.get("clip_index") == 2:
            raise RuntimeError("Transient Omni Flash rate limit on Shot 2")
        return orig_process(*args, **kwargs)

    with patch.object(app.state.agent, "process_user_turn", side_effect=_flaky_process_user_turn):
        res = client.post(
            "/api/storyboard/draft-batch",
            json={
                "session_name": "resilient_batch_sess",
                "shots": [
                    {"shot_index": 1, "action": "Shot 1 succeeds"},
                    {"shot_index": 2, "action": "Shot 2 raises RuntimeError"},
                    {"shot_index": 3, "action": "Shot 3 succeeds"},
                ],
                "variations_per_shot": 1,
                "resolution": "360p",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["total_drafts"] == 3
        statuses = {d["shot_index"]: d["status"] for d in data["drafts"]}
        assert statuses[1] == "COMPLETED"
        assert statuses[2] == "FAILED"
        assert statuses[3] == "COMPLETED"
        failed_item = next(d for d in data["drafts"] if d["shot_index"] == 2)
        assert failed_item["video_url"] is None


def test_stitch_master_cleans_up_tmp_file_even_on_upload_exception():
    """COR-03: Verify stitch_and_upload_master deletes /tmp/ file inside finally block even if upload raises."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    fd, tmp_video = tempfile.mkstemp(prefix="omnimash_test_master_", suffix=".mp4", dir="/tmp")
    os.write(fd, b"dummy video content")
    os.close(fd)
    assert os.path.exists(tmp_video)

    with (
        patch.object(
            app.state.agent.stitcher,
            "stitch_storyboard_master",
            return_value=tmp_video,
        ),
        patch.object(
            app.state.agent.storage,
            "upload_file",
            side_effect=RuntimeError("Simulated GCS upload outage"),
        ),
    ):
        with pytest.raises(RuntimeError, match="Simulated GCS upload outage"):
            client.post(
                "/api/storyboard/stitch_master",
                json={
                    "session_id": "cleanup_test_session",
                    "shot_clips": ["/static/rendered/clip1.mp4"],
                },
            )

    assert not os.path.exists(tmp_video), (
        "Temporary /tmp/ stitched file leaked after upload failure"
    )


def test_storyboard_expand_forwards_all_taxonomy_fields_and_preserves_temporal_beats():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/storyboard/expand",
        json={
            "concept": "Noir detective interrogating a cybernetic suspect",
            "style_tone": "1940s Classic Film Noir",
            "target_duration": 30.0,
            "camera_lighting": "Dutch-angle chiaroscuro tracking shot with venetian blind shadows",
            "aesthetic_tags": ["Trench Coat", "Cigarette Smoke", "Neon Rain"],
            "audio_beat": "75 BPM Smoky Jazz Saxophone",
            "vocal_delivery": "Weary hard-boiled baritone monologue",
            "environment": "Dimly lit precinct interrogation room at midnight",
        },
    )
    assert res.status_code == 200
    data = res.json()
    shots = data["shots"]
    assert len(shots) == 3
    for s in shots:
        assert "Dimly lit precinct interrogation room at midnight" in s["location"]
        assert "Dutch-angle chiaroscuro tracking shot" in s["framing_motion"]
        assert "Trench Coat" in s["style_lighting"]
        assert "75 BPM Smoky Jazz Saxophone" in s["audio"]
        assert "Weary hard-boiled baritone monologue" in s["audio"]
        assert "[0-3s]" in s["action"]
        assert "[3-6s]" in s["action"]
        assert "[6-10s]" in s["action"]
