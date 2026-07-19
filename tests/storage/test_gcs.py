import os
from omnimash.storage.gcs import GcsStorageManager
from omnimash.engine.omni_client import OmniFlashClient


def test_gcs_storage_manager_urls():
    gcs = GcsStorageManager(bucket_name="test-omnimash-bucket", mock_mode=True)
    pub_url = gcs.get_public_url("rendered/clip_123.mp4")
    assert (
        pub_url
        == "https://storage.googleapis.com/test-omnimash-bucket/rendered/clip_123.mp4"
    )
    gcs_uri = gcs.get_gcs_uri("rendered/clip_123.mp4")
    assert gcs_uri == "gs://test-omnimash-bucket/rendered/clip_123.mp4"


def test_gcs_storage_manager_upload_file(tmp_path):
    gcs = GcsStorageManager(bucket_name="test-omnimash-bucket", mock_mode=True)
    test_file = tmp_path / "sample_video.mp4"
    test_file.write_bytes(b"dummy mp4 binary data")

    url = gcs.upload_file(
        str(test_file), destination_blob_name="rendered/sample_video.mp4"
    )
    assert (
        "https://storage.googleapis.com/test-omnimash-bucket/rendered/sample_video.mp4"
        in url
    )


def test_gcs_storage_manager_upload_bytes():
    gcs = GcsStorageManager(bucket_name="test-omnimash-bucket", mock_mode=True)
    url = gcs.upload_bytes(
        b"raw bytes", destination_blob_name="audio/beat.wav", content_type="audio/wav"
    )
    assert url == "https://storage.googleapis.com/test-omnimash-bucket/audio/beat.wav"


def test_omni_client_gcs_persistence():
    client = OmniFlashClient(mock_mode=True, bucket_name="custom-media-bucket")
    res = client.generate_clip(prompt="DumbleDior in Dior robes")
    assert res.video_url is not None
    assert (
        res.gcs_uri
        == f"gs://custom-media-bucket/rendered/{os.path.basename(res.video_url)}"
    )
