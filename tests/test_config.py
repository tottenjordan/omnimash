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


def test_omnimash_settings_ffmpeg_timeout():
    s = OmniMashSettings()
    assert s.ffmpeg_timeout_seconds == 120.0


def test_omnimash_settings_gcs_timeout():
    s = OmniMashSettings(gcs_timeout_seconds=45.0)
    assert s.gcs_timeout_seconds == 45.0
    default_s = OmniMashSettings()
    assert default_s.gcs_timeout_seconds == 30.0


def test_omnimash_v2_model_and_mastering_defaults() -> None:
    s = OmniMashSettings(_env_file=None)
    assert s.omni_model_id == "gemini-omni-1.2-flash"
    assert s.pro_model_id == "gemini-4-argon"
    assert s.flash_model_id == "gemini-3.8-flash"
    assert s.image_model_id == "gemini-3-pro-image"
    assert s.fast_image_model_id == "gemini-nano-banana-2.1"
    assert s.lite_image_model_id == "gemini-3.1-flash-lite-image"
    assert s.tts_model_id == "gemini-3.8-flash-tts"
    assert s.tts_lite_model_id == "gemini-3.8-flash-lite-tts"
    assert s.lyria_pro_model_id == "lyria-3-pro-preview"
    assert s.lyria_clip_model_id == "lyria-3-clip-preview"
    assert s.default_image_size == "2K"
    assert s.default_resolution == "1080p"
    assert s.target_lufs == -14.0
    assert s.target_true_peak_dbtp == -1.0
    assert s.audio_sample_rate_hz == 48000
