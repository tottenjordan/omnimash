from omnimash.config import OmniMashSettings


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
