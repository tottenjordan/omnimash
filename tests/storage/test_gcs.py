import os
from omnimash.storage.gcs import GcsStorageManager
from omnimash.engine.omni_client import OmniFlashClient


def test_gcs_storage_manager_urls():
    gcs = GcsStorageManager(bucket_name="test-omnimash-bucket", mock_mode=True)
    pub_url = gcs.get_public_url("sessions/s_123/intermediate/clip.mp4")
    assert (
        pub_url
        == "https://storage.googleapis.com/test-omnimash-bucket/sessions/s_123/intermediate/clip.mp4"
    )
    gcs_uri = gcs.get_gcs_uri("sessions/s_123/intermediate/clip.mp4")
    assert gcs_uri == "gs://test-omnimash-bucket/sessions/s_123/intermediate/clip.mp4"


def test_gcs_session_blob_path():
    gcs = GcsStorageManager(bucket_name="test-omnimash-bucket", mock_mode=True)
    path = gcs.build_session_blob_path(
        session_id="session_abc", category="intermediate", filename="clip_0.mp4"
    )
    assert path == "sessions/session_abc/intermediate/clip_0.mp4"


def test_gcs_save_session_prompt():
    gcs = GcsStorageManager(bucket_name="test-omnimash-bucket", mock_mode=True)
    url = gcs.save_session_prompt(
        session_id="session_abc", turn_index=0, prompt_data={"subject": "DumbleDior"}
    )
    assert "sessions/session_abc/prompts/turn_0_prompt.json" in url


def test_gcs_save_and_get_reference_analysis():
    gcs = GcsStorageManager(bucket_name="test-omnimash-bucket", mock_mode=True)
    report_dict = {
        "video_title": "Sample Beat",
        "duration_seconds": 120,
        "detected_bpm": 120,
        "dominant_colors": ["#1B2A4A"],
        "extracted_keyframes": [],
    }
    url = gcs.save_reference_analysis("session_abc", report_dict)
    assert "sessions/session_abc/references/reference_analysis.json" in url
    retrieved = gcs.get_reference_analysis("session_abc")
    assert retrieved == report_dict
    assert gcs.get_reference_analysis("non_existent_session") is None


def test_omni_client_session_gcs_persistence():
    client = OmniFlashClient(mock_mode=True, bucket_name="custom-media-bucket")
    res = client.generate_clip(prompt="DumbleDior in Dior robes", session_id="sess_xyz")
    assert res.video_url is not None
    assert (
        res.gcs_uri
        == f"gs://custom-media-bucket/sessions/sess_xyz/intermediate/{os.path.basename(res.video_url)}"
    )


def test_gcs_ensure_bucket_exists():
    gcs = GcsStorageManager(bucket_name="test-omnimash-bucket", mock_mode=True)
    assert gcs.ensure_bucket_exists() is True
