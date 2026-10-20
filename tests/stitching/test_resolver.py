import os
from unittest.mock import MagicMock, patch

from omnimash.stitching.resolver import resolve_media_source_to_local_path


def test_resolve_local_file(tmp_path):
    local_file = tmp_path / "clip.mp4"
    local_file.write_bytes(b"local clip content")
    mock_storage = MagicMock()

    resolved = resolve_media_source_to_local_path(
        str(local_file),
        temp_dir=str(tmp_path),
        storage=mock_storage,
    )
    assert resolved == os.path.abspath(str(local_file))


def test_resolve_empty_or_invalid():
    mock_storage = MagicMock()
    assert resolve_media_source_to_local_path("", temp_dir="/tmp", storage=mock_storage) is None
    assert resolve_media_source_to_local_path(None, temp_dir="/tmp", storage=mock_storage) is None  # type: ignore
    assert resolve_media_source_to_local_path("   ", temp_dir="/tmp", storage=mock_storage) is None


def test_resolve_static_path_confined(tmp_path):
    mock_storage = MagicMock()
    static_file = tmp_path / "test.mp4"
    static_file.write_bytes(b"static clip")

    with patch("omnimash.stitching.resolver.validate_local_media_path", return_value=str(static_file)):
        resolved = resolve_media_source_to_local_path(
            "/static/test.mp4",
            temp_dir=str(tmp_path),
            storage=mock_storage,
        )
        assert resolved == str(static_file)


def test_resolve_static_path_traversal_blocked(tmp_path):
    mock_storage = MagicMock()
    with patch("omnimash.stitching.resolver.validate_local_media_path", return_value=None):
        resolved = resolve_media_source_to_local_path(
            "/static/../../etc/passwd",
            temp_dir=str(tmp_path),
            storage=mock_storage,
        )
        assert resolved is None


def test_resolve_media_proxy_uri(tmp_path):
    mock_storage = MagicMock()
    mock_storage.download_blob_bytes.return_value = (b"proxy clip bytes", "video/mp4")

    proxy_url = "/api/media-proxy?uri=gs%3A%2F%2Fmy-bucket%2Fvideos%2Fclip1.mp4"
    resolved = resolve_media_source_to_local_path(
        proxy_url,
        temp_dir=str(tmp_path),
        storage=mock_storage,
    )
    assert resolved is not None
    assert os.path.exists(resolved)
    mock_storage.download_blob_bytes.assert_called_once_with("gs://my-bucket/videos/clip1.mp4")
    with open(resolved, "rb") as f:
        assert f.read() == b"proxy clip bytes"


def test_resolve_gcs_uri_mock_mode(tmp_path):
    mock_storage = MagicMock()
    resolved = resolve_media_source_to_local_path(
        "gs://my-bucket/session/clip.mp4",
        temp_dir=str(tmp_path),
        storage=mock_storage,
        mock_mode=True,
    )
    assert resolved is not None
    assert os.path.exists(resolved)
    with open(resolved, "rb") as f:
        assert b"mock gcs" in f.read()


def test_resolve_remote_http_url_ssrf_blocked(tmp_path):
    mock_storage = MagicMock()
    resolved = resolve_media_source_to_local_path(
        "http://169.254.169.254/latest/meta-data/",
        temp_dir=str(tmp_path),
        storage=mock_storage,
    )
    assert resolved is None
