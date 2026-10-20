from __future__ import annotations

from omnimash.engine.models import GenerationResult
from omnimash.engine.omni_client import GenerationResult as ReexportedResult


def test_generation_result_dataclass():
    """Verify GenerationResult is identical and properly structured."""
    assert GenerationResult is ReexportedResult
    res = GenerationResult(
        interaction_thread_id="th_123",
        video_url="/static/rendered/test.mp4",
        gcs_uri="gs://test-bucket/test.mp4",
        duration_seconds=10,
        synth_id_watermark="SYNTHID_C2PA_VERIFIED",
        error_message=None,
        generation_mode="LIVE_OMNI_FLASH",
    )
    assert res.interaction_thread_id == "th_123"
    assert res.video_url == "/static/rendered/test.mp4"
    assert res.gcs_uri == "gs://test-bucket/test.mp4"
    assert res.duration_seconds == 10
    assert res.generation_mode == "LIVE_OMNI_FLASH"
