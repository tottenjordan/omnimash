"""Tests for the shareable video link API router."""

import pytest
from fastapi.testclient import TestClient
from omnimash.api.app import create_app


@pytest.fixture
def client():
    app = create_app(mock_mode=True)
    with TestClient(app) as c:
        yield c


def test_create_share_link_valid_payload_defaults(client):
    payload = {
        "session_name": "rap_battle_session",
        "video_url": "gs://test-bucket/sessions/rap_battle_session/final_masters/master.mp4",
        "master_title": "master",
        "expiration_days": 7,
    }
    res = client.post("/api/share/create", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "share_url" in data
    assert "storage.googleapis.com" in data["share_url"]
    assert "download_url" in data
    assert "attachment" in data["download_url"]
    assert "embed_snippet" in data
    assert "<video controls" in data["embed_snippet"]
    assert data["lifespan_days"] == 7
    assert data["filename"] == "master.mp4"
    assert "expires_at" in data
    assert "gcs_uri" in data
    assert "message" in data


@pytest.mark.parametrize("invalid_days", [0, 8, 10, -1])
def test_create_share_link_rejects_invalid_lifespan(client, invalid_days):
    payload = {
        "session_name": "test_session",
        "video_url": "gs://test-bucket/video.mp4",
        "expiration_days": invalid_days,
    }
    res = client.post("/api/share/create", json=payload)
    assert res.status_code == 422  # Pydantic validation error for ge=1, le=7


def test_create_share_link_rejects_empty_video_url(client):
    # Empty string
    payload = {
        "session_name": "test_session",
        "video_url": "",
        "expiration_days": 7,
    }
    res = client.post("/api/share/create", json=payload)
    assert res.status_code == 400
    data = res.json()
    assert data["detail"] == "Missing video_url"

    # Whitespace only
    payload_whitespace = {
        "session_name": "test_session",
        "video_url": "   ",
        "expiration_days": 7,
    }
    res_ws = client.post("/api/share/create", json=payload_whitespace)
    assert res_ws.status_code == 400
    assert res_ws.json()["detail"] == "Missing video_url"


def test_create_share_link_custom_master_title(client):
    payload = {
        "session_name": "test_session",
        "video_url": "gs://test-bucket/sessions/test_session/final_masters/output.mp4",
        "master_title": "Grand_Finale_Cut",
        "expiration_days": 5,
    }
    res = client.post("/api/share/create", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["lifespan_days"] == 5
    assert data["filename"] == "Grand_Finale_Cut.mp4"
    assert "Grand_Finale_Cut.mp4" in data["download_url"]
    assert "storage.googleapis.com" in data["share_url"]


def test_create_share_link_media_proxy_url(client):
    payload = {
        "session_name": "test_session",
        "video_url": "/api/media-proxy?uri=gs%3A%2F%2Ftest-bucket%2Fsessions%2Fs1%2Ffinal_masters%2Fpromo.mp4",
        "expiration_days": 3,
    }
    res = client.post("/api/share/create", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["lifespan_days"] == 3
    assert data["filename"] == "promo.mp4"
    assert "sessions/s1/final_masters/promo.mp4" in data["share_url"]


def test_create_share_link_value_error_handling(client, monkeypatch):
    app = create_app(mock_mode=True)

    def mock_create_shareable_link(*args, **kwargs):
        raise ValueError("Invalid storage URI format")

    monkeypatch.setattr(
        app.state.agent.storage, "create_shareable_link", mock_create_shareable_link
    )
    with TestClient(app) as c:
        res = c.post(
            "/api/share/create",
            json={
                "session_name": "s1",
                "video_url": "invalid://not-supported",
            },
        )
        assert res.status_code == 400
        assert "Invalid storage URI format" in res.json()["detail"]


def test_build_snapshot_strips_private_fields():
    """Verify build_share_snapshot allowlists only public fields and strips prompts, session_id, user_id, gcs_uri."""
    from omnimash.storage.share_snapshot import build_share_snapshot, new_share_token

    token = new_share_token()
    snap = build_share_snapshot(
        token=token,
        scope="video",
        title="Trapwarts Finale",
        aspect_ratio="16:9",
        duration_seconds=30,
        prompt="SECRET INTERNAL PROMPT",
        raw_compiled_prompt="### INPUT ROLES & REFERENCES SECRET",
        session_id="secret_session_id",
        user_id="secret_user",
        user_email="director@example.com",
        gcs_uri="gs://private-bucket/secret.mp4",
    )
    assert snap["token"] == token
    assert snap["title"] == "Trapwarts Finale"
    assert snap["scope"] == "video"
    assert "prompt" not in snap
    assert "raw_compiled_prompt" not in snap
    assert "session_id" not in snap
    assert "user_id" not in snap
    assert "user_email" not in snap
    assert "gcs_uri" not in snap


def test_frozen_share_lifecycle_viewer_range_streaming_and_revocation(client):
    """Verify POST /api/shares -> GET /api/shares -> GET /s/{token} -> GET /s/{token}/video (200 & 206 Range) -> DELETE /api/shares/{token} (410 Gone)."""
    create_res = client.post(
        "/api/shares",
        json={
            "session_id": "share_lifecycle_sess",
            "video_url": "gs://test-bucket/sessions/share_lifecycle_sess/final_masters/master.mp4",
            "title": "Gothic Trap Act 1-3 Master",
            "scope": "video",
            "aspect_ratio": "16:9",
            "duration_seconds": 30.0,
        },
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["success"] is True
    token = created["token"]
    assert len(token) >= 16
    assert created["url"].endswith(f"/s/{token}")

    # List active shares
    list_res = client.get("/api/shares", params={"session_id": "share_lifecycle_sess"})
    assert list_res.status_code == 200
    shares_list = list_res.json()["shares"]
    assert any(s["token"] == token for s in shares_list)

    # Fetch public HTML viewer /s/{token}
    viewer_res = client.get(f"/s/{token}")
    assert viewer_res.status_code == 200
    assert viewer_res.headers.get("x-robots-tag") == "noindex, nofollow"
    assert viewer_res.headers.get("referrer-policy") == "no-referrer"
    html_body = viewer_res.text
    assert "Gothic Trap Act 1-3 Master" in html_body
    assert f"/s/{token}/video" in html_body
    assert "Card View" in html_body
    assert "Social Feed View" in html_body
    assert "9:16 Story Frame" in html_body

    # Stream full video
    vid_res = client.get(f"/s/{token}/video")
    assert vid_res.status_code == 200
    assert vid_res.headers.get("accept-ranges") == "bytes"
    assert len(vid_res.content) > 10

    # Stream partial content with HTTP Range header
    range_res = client.get(f"/s/{token}/video", headers={"Range": "bytes=0-15"})
    assert range_res.status_code == 206
    assert range_res.headers.get("content-range", "").startswith("bytes 0-15/")
    assert len(range_res.content) == 16

    # Download mode (?download=1)
    dl_res = client.get(f"/s/{token}/video?download=1")
    assert dl_res.status_code == 200
    assert "attachment" in dl_res.headers.get("content-disposition", "")

    # Revoke share
    del_res = client.delete(f"/s/{token}" if False else f"/api/shares/{token}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Subsequent viewer & video requests must return 410 Gone
    assert client.get(f"/s/{token}").status_code == 410
    assert client.get(f"/s/{token}/video").status_code == 410


def test_share_mode_lockdown_middleware(monkeypatch):
    """Verify SHARE_MODE=1 blocks studio/API routes with 404 while keeping /s/{token} accessible."""
    app = create_app(mock_mode=True)
    with TestClient(app) as c:
        res = c.post(
            "/api/shares",
            json={
                "session_id": "lockdown_sess",
                "video_url": "gs://test-bucket/master.mp4",
                "title": "Lockdown Test Video",
            },
        )
        token = res.json()["token"]

        monkeypatch.setenv("SHARE_MODE", "1")
        # Studio root and API routes must be blocked (404)
        assert c.get("/").status_code == 404
        assert c.get("/api/shares").status_code == 404
        assert c.post("/api/generate", json={"prompt": "test"}).status_code == 404

        # Public share viewer and video stream remain accessible (200)
        assert c.get(f"/s/{token}").status_code == 200
        assert c.get(f"/s/{token}/video").status_code == 200


def test_create_share_link_live_mode_never_returns_mockv4signature_and_falls_back_to_public_token_url():
    """Verify when mock_mode=False, /api/share/create never returns mockv4signature and falls back to /s/<token> when V4 signing is unavailable."""
    from unittest.mock import MagicMock

    app = create_app(mock_mode=True)
    storage = app.state.agent.storage
    storage.mock_mode = False

    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.exists.return_value = False
    mock_blob.generate_signed_url.side_effect = Exception(
        "No private key and IAM signBlob unavailable"
    )
    mock_bucket.blob.return_value = mock_blob
    storage._bucket_instance = mock_bucket

    with TestClient(app) as c:
        res = c.post(
            "/api/share/create",
            json={
                "session_name": "live_prod_session",
                "video_url": "gs://test-bucket/sessions/live_prod_session/final_masters/master.mp4",
                "master_title": "Prod_Master",
                "expiration_days": 7,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        token = data["token"]
        assert "mockv4signature" not in data["share_url"]
        assert "mockv4signature" not in data["download_url"]
        assert "mockv4signature" not in data["embed_snippet"]
        assert data["share_url"].endswith(f"/s/{token}")
        assert data["download_url"].endswith(f"/s/{token}/video?download=1")


def test_list_active_shares_hydrates_from_gcs_snapshots_across_instances():
    """Verify GET /api/shares hydrates ShareRecords from shares/*/snapshot.json in GCS and evicts shares deleted on another instance."""
    import json
    from unittest.mock import MagicMock
    from omnimash.storage.share_snapshot import new_share_token

    app = create_app(mock_mode=True)
    storage = app.state.agent.storage
    storage.mock_mode = False

    remote_token = new_share_token()
    snap_payload = {
        "token": remote_token,
        "scope": "video",
        "title": "Hydrated Cloud Run Share",
        "aspect_ratio": "9:16",
        "duration_seconds": 15.0,
        "created_at": "2026-10-22T06:00:00+00:00",
    }
    mock_snap_blob = MagicMock()
    mock_snap_blob.name = f"shares/{remote_token}/snapshot.json"
    mock_snap_blob.download_as_text.return_value = json.dumps(snap_payload)

    mock_bucket = MagicMock()
    mock_bucket.list_blobs.return_value = [mock_snap_blob]
    storage._bucket_instance = mock_bucket

    with TestClient(app) as c:
        res = c.get("/api/shares", params={"session_id": "any_session"})
        assert res.status_code == 200
        shares = res.json()["shares"]
        matched = [s for s in shares if s["token"] == remote_token]
        assert len(matched) == 1
        assert matched[0]["title"] == "Hydrated Cloud Run Share"
        assert matched[0]["aspect_ratio"] == "9:16"
        assert matched[0]["url"].endswith(f"/s/{remote_token}")

        # Simulate another Cloud Run instance revoking/deleting the share in GCS
        mock_bucket.list_blobs.return_value = []
        res_after = c.get("/api/shares", params={"session_id": "any_session"})
        assert res_after.status_code == 200
        assert not any(s["token"] == remote_token for s in res_after.json()["shares"])

        # Simulate stale _mock_shares entry on Instance A when GCS blob was deleted on Instance B
        storage._mock_shares[remote_token] = {
            "snapshot": snap_payload,
            "video_bytes": b"stale_video_bytes",
        }
        missing_blob = MagicMock()
        missing_blob.exists.return_value = False
        mock_bucket.blob.return_value = missing_blob
        assert c.get(f"/s/{remote_token}").status_code == 404
        assert c.get(f"/s/{remote_token}/video").status_code == 404
        assert remote_token not in storage._mock_shares
