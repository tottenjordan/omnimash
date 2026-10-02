import inspect
from fastapi.testclient import TestClient
from omnimash.api.app import create_app
from omnimash.engine.omni_client import OmniFlashClient


def test_media_proxy_rejects_disallowed_gcs_buckets():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    # Allowed buckets should succeed
    res_ok = client.get(
        "/api/media-proxy",
        params={"uri": "gs://reference-images-jt-trend-trawler/harry_drip.jpeg"},
    )
    assert res_ok.status_code == 200

    # Disallowed arbitrary GCS bucket should be rejected with 403
    res_forbidden = client.get(
        "/api/media-proxy",
        params={"uri": "gs://some-other-private-project-bucket/secrets.json"},
    )
    assert res_forbidden.status_code == 403


def test_omni_client_fetch_image_bytes_blocks_private_ips_and_unauthorized_local_paths(
    tmp_path,
):
    client = OmniFlashClient(mock_mode=True)

    # SSRF metadata & loopback URLs must be blocked
    data_meta, _ = client._fetch_image_bytes(
        "http://169.254.169.254/computeMetadata/v1/"
    )
    assert data_meta == b""

    data_local, _ = client._fetch_image_bytes("http://127.0.0.1:8000/secret")
    assert data_local == b""

    # Arbitrary system files outside static/ or /tmp/ must be blocked
    data_etc, _ = client._fetch_image_bytes("/etc/hosts")
    assert data_etc == b""


def test_motion_reference_upload_rejects_arbitrary_system_paths():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res = client.post(
        "/api/motion-reference/upload",
        json={"input_video_path": "/etc/passwd", "start_sec": 0.0},
    )
    assert res.status_code == 400


def test_character_sheet_endpoints_are_sync_def_for_threadpool_execution():
    app = create_app(mock_mode=True)
    target_paths = {"/api/characters/generate-sheet", "/api/characters/save-sheet"}
    matched = 0
    for route in app.routes:
        path = getattr(route, "path", "")
        if path in target_paths:
            matched += 1
            endpoint = getattr(route, "endpoint", None)
            assert endpoint is not None
            assert not inspect.iscoroutinefunction(endpoint), (
                f"Route {path} uses blocking I/O and must be defined with sync 'def' "
                "so FastAPI executes it in the worker threadpool."
            )
    assert matched == 2
