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


def test_save_and_load_character_gcs():
    storage = GcsStorageManager(bucket_name="test-omnimash-bucket", mock_mode=True)
    char_data = {
        "role_id": "Role A",
        "name": "Harry",
        "description": "Young wizard",
        "reference_url": "gs://bucket/harry.jpg",
        "aesthetic_tags": ["Red Gucci Tracksuit"],
        "voice_style": "Atlanta trap flow",
    }
    pub_url, gcs_uri = storage.save_character(
        char_data, session_id="test_session", is_library=True
    )
    assert "library/characters/harry.json" in gcs_uri
    assert (
        pub_url
        == "https://storage.googleapis.com/test-omnimash-bucket/library/characters/harry.json"
    )

    loaded = storage.load_character("harry")
    assert loaded is not None
    assert loaded["name"] == "Harry"
    assert loaded["voice_style"] == "Atlanta trap flow"

    # Also test session-specific character save
    session_char = {
        "role_id": "Role B",
        "name": "Young Draco",
        "description": "Rival wizard",
        "reference_url": "gs://bucket/draco.jpg",
        "aesthetic_tags": ["Platinum Slicked Hair"],
        "voice_style": "British drawl",
    }
    pub_url_s, gcs_uri_s = storage.save_character(
        session_char, session_id="test_session", is_library=False
    )
    assert "sessions/test_session/characters/young_draco.json" in gcs_uri_s
    loaded_s = storage.load_character("young_draco", session_id="test_session")
    assert loaded_s is not None
    assert loaded_s["name"] == "Young Draco"


def test_list_characters_gcs():
    storage = GcsStorageManager(bucket_name="test-omnimash-bucket", mock_mode=True)
    chars = storage.list_characters()
    assert isinstance(chars, list)
    names = [c["name"] for c in chars]
    assert any('Harry "Gucci"' in n for n in names)
    assert any('Young Draco "Jeezy"' in n for n in names)
    assert any("Cyborg Gordon Ramsay" in n for n in names)
    assert any("Neon Julia Child" in n for n in names)

    custom_char = {
        "role_id": "Role C",
        "name": "Snoop Dogg Wizard",
        "description": "West Coast rap icon",
        "reference_url": "gs://bucket/snoop.jpg",
        "aesthetic_tags": ["Flannel Robe"],
        "voice_style": "West Coast drawl",
    }
    storage.save_character(custom_char)
    updated_chars = storage.list_characters()
    updated_names = [c["name"] for c in updated_chars]
    assert "Snoop Dogg Wizard" in updated_names


def test_save_and_load_session_roster_gcs():
    storage = GcsStorageManager(bucket_name="test-omnimash-bucket", mock_mode=True)
    roster = [
        {
            "role_id": "Role A",
            "name": 'Harry "Gucci"',
            "description": "Young wizard",
            "reference_url": "gs://bucket/harry.jpg",
            "aesthetic_tags": ["Red Gucci Tracksuit"],
            "voice_style": "Atlanta trap flow",
        },
        {
            "role_id": "Role B",
            "name": 'Young Draco "Jeezy"',
            "description": "Rival wizard",
            "reference_url": "gs://bucket/draco.jpg",
            "aesthetic_tags": ["Platinum Slicked Hair"],
            "voice_style": "British drawl",
        },
    ]
    pub_url, gcs_uri = storage.save_session_roster("sess_999", roster)
    assert "sessions/sess_999/characters/roster.json" in gcs_uri
    assert (
        pub_url
        == "https://storage.googleapis.com/test-omnimash-bucket/sessions/sess_999/characters/roster.json"
    )

    loaded = storage.load_session_roster("sess_999")
    assert loaded == roster
    assert storage.load_session_roster("non_existent_session") is None


def test_download_blob_bytes():
    gcs = GcsStorageManager(bucket_name="test-omnimash-bucket", mock_mode=True)
    # Invalid URIs
    assert gcs.download_blob_bytes("http://example.com/image.jpg") == (
        b"",
        "image/jpeg",
    )
    assert gcs.download_blob_bytes("gs://") == (b"", "image/jpeg")
    assert gcs.download_blob_bytes("gs://bucket_only") == (b"", "image/jpeg")
    assert gcs.download_blob_bytes("invalid_uri") == (b"", "image/jpeg")

    # Valid URI in mock_mode
    data, content_type = gcs.download_blob_bytes("gs://test-bucket/path/to/image.jpg")
    assert data == b"mock_image_bytes"
    assert content_type == "image/jpeg"
