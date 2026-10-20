import io
from unittest.mock import MagicMock, patch

import anyio
from fastapi.testclient import TestClient

from omnimash.api.app import create_app


def test_upload_rejects_disallowed_file_extensions_and_mime_types():
    """SEC-03: Verify /api/upload rejects executable/HTML/script extensions and non-media MIME types."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    for bad_name in ("exploit.html", "payload.js", "malware.exe", "run.sh"):
        res = client.post(
            "/api/upload",
            files={"file": (bad_name, io.BytesIO(b"bad content"), "video/mp4")},
        )
        assert res.status_code == 400
        assert res.json()["success"] is False
        assert "Unsupported file extension" in res.json()["error"]

    res_mime = client.post(
        "/api/upload",
        files={"file": ("clip.mp4", io.BytesIO(b"bad mime"), "text/html")},
    )
    assert res_mime.status_code == 400
    assert res_mime.json()["success"] is False
    assert "Unsupported media content-type" in res_mime.json()["error"]


def test_upload_offloads_blocking_io_to_worker_thread(tmp_path, monkeypatch):
    """COR-01: Verify /api/upload offloads local and GCS writes via anyio.to_thread.run_sync."""
    monkeypatch.chdir(tmp_path)
    app = create_app(mock_mode=True)
    client = TestClient(app)

    with patch(
        "omnimash.api.routers.media.anyio.to_thread.run_sync",
        wraps=anyio.to_thread.run_sync,
    ) as mock_run_sync:
        res = client.post(
            "/api/upload",
            files={"file": ("sample.mp4", io.BytesIO(b"video_bytes"), "video/mp4")},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["url"].startswith("/static/uploads/upload_")
        assert data["url"].endswith(".mp4")
        assert mock_run_sync.call_count >= 1


def test_media_proxy_live_range_request_fetches_only_byte_slice():
    """SEC-01: Verify /api/media-proxy uses ranged GCS byte downloads instead of buffering full blob in live mode."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    storage = app.state.agent.storage
    storage.mock_mode = False
    mock_gcs_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.size = 10_000_000
    mock_blob.content_type = "video/mp4"
    mock_blob.download_as_bytes.return_value = b"ABCD"
    mock_bucket.blob.return_value = mock_blob
    mock_gcs_client.bucket.return_value = mock_bucket
    storage._client = mock_gcs_client

    with patch.object(storage, "download_blob_bytes") as mock_full_download:
        res = client.get(
            "/api/media-proxy?uri=gs://bucket/large_video.mp4",
            headers={"Range": "bytes=100-103"},
        )
        assert res.status_code == 206
        assert res.content == b"ABCD"
        assert res.headers["Content-Range"] == "bytes 100-103/10000000"
        mock_blob.download_as_bytes.assert_called_once_with(start=100, end=103)
        mock_full_download.assert_not_called()
