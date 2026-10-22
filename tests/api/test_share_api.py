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
