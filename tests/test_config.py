import pytest

from omnimash.config import OmniMashSettings


def test_real_mode_requires_credentials():
    # No API keys and no project => fail fast at settings load.
    with pytest.raises(ValueError):
        OmniMashSettings(
            mock_mode=False,
            google_api_key=None,
            gemini_api_key=None,
            omnimash_gcs_bucket=None,
            google_cloud_project="",
        )


def test_real_mode_ok_with_project():
    s = OmniMashSettings(
        mock_mode=False,
        google_api_key=None,
        gemini_api_key=None,
        google_cloud_project="hybrid-vertex",
    )
    assert s.mock_mode is False


def test_mock_mode_skips_credential_check():
    s = OmniMashSettings(
        mock_mode=True,
        google_api_key=None,
        gemini_api_key=None,
        google_cloud_project="",
    )
    assert s.mock_mode is True


def test_omnimash_settings_defaults():
    s = OmniMashSettings(mock_mode=True, omnimash_gcs_bucket=None)
    assert s.google_cloud_region in ("global", "us-central1")
    assert s.gcs_bucket_name == f"omnimash-media-{s.google_cloud_project}"


def test_omnimash_settings_custom_project():
    s = OmniMashSettings(google_cloud_project="custom-corp-ai", omnimash_gcs_bucket=None)
    assert s.gcs_bucket_name == "omnimash-media-custom-corp-ai"


def test_omnimash_settings_explicit_bucket():
    s = OmniMashSettings(omnimash_gcs_bucket="my-custom-bucket")
    assert s.gcs_bucket_name == "my-custom-bucket"
