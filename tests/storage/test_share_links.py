"""Tests for GCS V4 signed URL shareable link generation."""

from unittest.mock import MagicMock
import pytest
from omnimash.storage.gcs import GcsStorageManager


def test_create_shareable_link_mock_mode_defaults():
    storage = GcsStorageManager(
        bucket_name="test-bucket", project_id="test-project", mock_mode=True
    )
    res = storage.create_shareable_link(
        blob_path_or_uri="gs://test-bucket/sessions/sess_1/final_masters/battle_master.mp4",
        expiration_days=7,
        master_title="battle_master",
    )
    assert res["success"] is True
    assert (
        "storage.googleapis.com/test-bucket/sessions/sess_1/final_masters/battle_master.mp4"
        in res["share_url"]
    )
    assert "X-Goog-Algorithm=GOOG4-RSA-SHA256" in res["share_url"]
    assert (
        "X-Goog-Credential=omnimash-sa%40test-project.iam.gserviceaccount.com" in res["share_url"]
    )
    assert "X-Goog-Expires=604800" in res["share_url"]
    assert "response-content-disposition=inline" in res["share_url"]
    assert "response-content-type=video%2Fmp4" in res["share_url"]
    assert "download_url" in res
    assert "attachment" in res["download_url"]
    assert "battle_master.mp4" in res["download_url"]
    assert res["lifespan_days"] == 7
    assert res["filename"] == "battle_master.mp4"
    assert "expires_at" in res
    assert res["blob_name"] == "sessions/sess_1/final_masters/battle_master.mp4"
    assert res["gcs_uri"] == "gs://test-bucket/sessions/sess_1/final_masters/battle_master.mp4"
    assert "Valid for 7 days" in res["message"]


def test_create_shareable_link_validates_expiration_bounds():
    storage = GcsStorageManager(mock_mode=True)
    with pytest.raises(ValueError, match="Expiration days must be between 1 and 7"):
        storage.create_shareable_link("test.mp4", expiration_days=0)
    with pytest.raises(ValueError, match="Expiration days must be between 1 and 7"):
        storage.create_shareable_link("test.mp4", expiration_days=8)
    with pytest.raises(ValueError, match="Expiration days must be between 1 and 7"):
        storage.create_shareable_link("test.mp4", expiration_days=-1)


def test_create_shareable_link_resolves_proxy_uri():
    storage = GcsStorageManager(bucket_name="test-bucket", mock_mode=True)
    res = storage.create_shareable_link(
        blob_path_or_uri="/api/media-proxy?uri=gs%3A%2F%2Ftest-bucket%2Fsessions%2Fs1%2Ffinal_masters%2Fcut.mp4"
    )
    assert res["success"] is True
    assert "sessions/s1/final_masters/cut.mp4" in res["share_url"]
    assert res["blob_name"] == "sessions/s1/final_masters/cut.mp4"
    assert res["filename"] == "cut.mp4"


def test_create_shareable_link_custom_master_title():
    storage = GcsStorageManager(bucket_name="test-bucket", mock_mode=True)
    res = storage.create_shareable_link(
        blob_path_or_uri="sessions/s1/final_masters/final_master.mp4",
        expiration_days=3,
        master_title="super_battle_cut",
    )
    assert res["success"] is True
    assert res["lifespan_days"] == 3
    assert res["filename"] == "super_battle_cut.mp4"
    assert "super_battle_cut.mp4" in res["download_url"]
    assert "X-Goog-Expires=259200" in res["share_url"]


def test_create_shareable_link_real_gcs_signing_success():
    storage = GcsStorageManager(bucket_name="test-bucket", mock_mode=False)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.side_effect = [
        "https://storage.googleapis.com/test-bucket/video.mp4?signed_share_token",
        "https://storage.googleapis.com/test-bucket/video.mp4?signed_dl_token",
    ]
    mock_bucket.blob.return_value = mock_blob
    storage._bucket_instance = mock_bucket

    res = storage.create_shareable_link(
        blob_path_or_uri="gs://test-bucket/video.mp4",
        expiration_days=7,
        master_title="epic_master",
    )
    assert res["success"] is True
    assert (
        res["share_url"]
        == "https://storage.googleapis.com/test-bucket/video.mp4?signed_share_token"
    )
    assert (
        res["download_url"]
        == "https://storage.googleapis.com/test-bucket/video.mp4?signed_dl_token"
    )
    assert mock_blob.generate_signed_url.call_count == 2


def test_create_shareable_link_real_gcs_signing_fallback_on_exception():
    storage = GcsStorageManager(
        bucket_name="test-bucket", project_id="test-project", mock_mode=False
    )
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.side_effect = Exception(
        "IAM signBlob permission denied or no private key"
    )
    mock_bucket.blob.return_value = mock_blob
    storage._bucket_instance = mock_bucket

    res = storage.create_shareable_link(
        blob_path_or_uri="gs://test-bucket/video.mp4",
        expiration_days=7,
    )
    assert res["success"] is True
    assert "storage.googleapis.com/test-bucket/video.mp4" in res["share_url"]
    assert "X-Goog-Algorithm=GOOG4-RSA-SHA256" in res["share_url"]
    assert "X-Goog-Expires=604800" in res["share_url"]
