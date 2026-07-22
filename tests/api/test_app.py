from fastapi.testclient import TestClient

from omnimash.api.app import (
    GenerateRequest,
    SaveFinalRequest,
    StitchClipsRequest,
    create_app,
)


def test_identifier_fields_are_sanitized():
    # Traversal payloads in identifier fields collapse to safe segments.
    gen = GenerateRequest(session_name="../../x", prompt="Snape spicy rap")
    assert gen.session_name is not None
    assert "/" not in gen.session_name
    assert ".." not in gen.session_name
    # Free-text creative fields are left untouched (guardrails stay relaxed).
    assert gen.prompt == "Snape spicy rap"

    final = SaveFinalRequest(
        session_name="../evil", video_url="/static/x.mp4", master_title="../../boom"
    )
    assert ".." not in final.master_title
    assert "/" not in final.master_title

    stitch = StitchClipsRequest(session_name="ok", clip_urls=[])
    assert stitch.master_title == "custom_stitched_cut"


def test_dashboard_served_from_static_asset():
    # The UI now lives as a packaged asset; GET / reads and returns it.
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert "<!DOCTYPE html>" in res.text
    assert "OmniMash" in res.text


def test_ui_html_asset_file_exists_and_loads():
    from omnimash.api.app import _load_ui_html

    html = _load_ui_html()
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html


def test_api_generate_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    response = client.post(
        "/api/generate",
        json={
            "user_id": "usr_test",
            "project_id": "prj_test",
            "prompt": "Snape 90s rap video",
            "clip_index": 0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "video_url" in data


def test_api_commit_endpoint():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    gen_res = client.post(
        "/api/generate",
        json={
            "user_id": "usr_c",
            "project_id": "prj_c",
            "prompt": "Snape rap",
            "clip_index": 0,
        },
    )
    turn_id = gen_res.json()["turn_id"]

    commit_res = client.post(
        "/api/commit",
        json={
            "user_id": "usr_c",
            "project_id": "prj_c",
            "turn_id": turn_id,
            "next_prompt": "Continue with lasers",
        },
    )
    assert commit_res.status_code == 200
    data = commit_res.json()
    assert data["success"] is True
    assert data["status"] == "REANCHORED"
    assert data["depth"] == 0


def test_save_final_master_and_extend_scene_endpoints():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res_save = client.post(
        "/api/save-final",
        json={
            "session_name": "trap_or_die_v1",
            "video_url": "/static/rendered/mock.mp4",
            "master_title": "official_rap_battle_master",
        },
    )
    assert res_save.status_code == 200
    data_save = res_save.json()
    assert data_save["success"] is True
    assert "final_masters" in data_save["gcs_uri"]
    assert "official_rap_battle_master.mp4" in data_save["gcs_uri"]

    gen_res = client.post(
        "/api/generate",
        json={
            "user_id": "usr_ext",
            "project_id": "prj_ext",
            "session_name": "trap_or_die_v1",
            "prompt": "Harry rap battle",
            "clip_index": 0,
        },
    )
    turn_id = gen_res.json()["turn_id"]

    res_extend = client.post(
        "/api/extend-scene",
        json={
            "session_name": "trap_or_die_v1",
            "turn_id": turn_id,
            "next_scene_action": "Harry drops the mic and walks away",
            "dialogue": "I'm out!",
            "active_roles": ["Role A"],
        },
    )
    assert res_extend.status_code == 200
    data_extend = res_extend.json()
    assert data_extend["success"] is True
    assert data_extend["video_url"] is not None


def test_api_generate_and_extend_scene_with_vocal_delivery_and_voice_style():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    gen_res = client.post(
        "/api/generate",
        json={
            "user_id": "usr_vocal",
            "project_id": "prj_vocal",
            "concept": "Harry rap battle",
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Harry",
                    "description": "Young wizard",
                    "voice_style": "Melodic autotune trap flow",
                }
            ],
            "scenes": [
                {
                    "scene_number": 1,
                    "active_roles": ["Role A"],
                    "action": "Cooking potions",
                }
            ],
            "vocal_delivery": "Dynamic studio vocal projection",
            "clip_index": 0,
        },
    )
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["success"] is True
    assert "Voice Style (Role A): Melodic autotune trap flow" in gen_data["raw_compiled_prompt"]
    assert "Vocal Delivery: Dynamic studio vocal projection" in gen_data["raw_compiled_prompt"]

    turn_id = gen_data["turn_id"]
    res_extend = client.post(
        "/api/extend-scene",
        json={
            "session_name": "vocal_session_1",
            "turn_id": turn_id,
            "next_scene_action": "Harry drops mic",
            "vocal_delivery": "Echoing reverberant vocal fadeout",
        },
    )
    assert res_extend.status_code == 200
    assert res_extend.json()["success"] is True


def test_api_save_final_multi_clip_stitching():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    s_name = "api_multi_clip_session"

    g1 = client.post(
        "/api/generate",
        json={
            "user_id": "usr_multi",
            "project_id": "prj_multi",
            "session_name": s_name,
            "prompt": "Clip 1 generation",
            "clip_index": 0,
        },
    )
    assert g1.status_code == 200
    t1_id = g1.json()["turn_id"]

    g2 = client.post(
        "/api/generate",
        json={
            "user_id": "usr_multi",
            "project_id": "prj_multi",
            "session_name": s_name,
            "parent_turn_id": t1_id,
            "prompt": "Clip 2 generation",
            "clip_index": 1,
        },
    )
    assert g2.status_code == 200
    v2_url = g2.json()["video_url"]

    res_save = client.post(
        "/api/save-final",
        json={
            "session_name": s_name,
            "video_url": v2_url,
            "master_title": "api_stitched_master",
        },
    )
    assert res_save.status_code == 200
    data_save = res_save.json()
    assert data_save["success"] is True
    assert "final_masters" in data_save["gcs_uri"]
    assert "api_stitched_master.mp4" in data_save["gcs_uri"]


def test_api_stitch_selected_clips():
    app = create_app(mock_mode=True)
    client = TestClient(app)

    res_empty = client.post(
        "/api/stitch-clips",
        json={
            "session_name": "test_stitch_session",
            "clip_urls": [],
            "master_title": "my_stitched_cut",
        },
    )
    assert res_empty.status_code == 400
    assert res_empty.json()["detail"] == "At least one clip URL is required for stitching."

    res_valid = client.post(
        "/api/stitch-clips",
        json={
            "session_name": "test_stitch_session",
            "clip_urls": ["/static/rendered/clip1.mp4", "/static/rendered/clip2.mp4"],
            "master_title": "my_stitched_cut",
        },
    )
    assert res_valid.status_code == 200
    data = res_valid.json()
    assert data["success"] is True
    assert "gcs_uri" in data
    assert "my_stitched_cut.mp4" in data["gcs_uri"]


def test_api_media_proxy():
    from omnimash.config import settings

    app = create_app(mock_mode=True)
    client = TestClient(app)
    bucket = settings.gcs_bucket_name

    res_invalid = client.get("/api/media-proxy?uri=https://example.com/image.jpg")
    assert res_invalid.status_code == 400

    res_empty = client.get("/api/media-proxy?uri=gs://bucket_only")
    assert res_empty.status_code == 404

    res_valid = client.get(f"/api/media-proxy?uri=gs://{bucket}/test_image.jpg")
    assert res_valid.status_code == 200
    assert res_valid.headers["cache-control"] == "public, max-age=86400"
    assert res_valid.content == b"mock_image_bytes"


def test_api_media_proxy_rejects_foreign_bucket():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    # A bucket outside the app bucket + allow-list must not be proxied.
    res = client.get("/api/media-proxy?uri=gs://some-other-bucket/secret.mp4")
    assert res.status_code == 404


def test_media_proxy_full_get_advertises_range_support():
    from omnimash.config import settings

    app = create_app(mock_mode=True)
    client = TestClient(app)
    bucket = settings.gcs_bucket_name
    res = client.get(f"/api/media-proxy?uri=gs://{bucket}/clip.mp4")
    assert res.status_code == 200
    assert res.headers["accept-ranges"] == "bytes"
    assert res.headers["content-length"] == str(len(b"mock_image_bytes"))
    assert res.content == b"mock_image_bytes"


def test_media_proxy_serves_partial_content_for_range():
    from omnimash.config import settings

    app = create_app(mock_mode=True)
    client = TestClient(app)
    bucket = settings.gcs_bucket_name
    res = client.get(
        f"/api/media-proxy?uri=gs://{bucket}/clip.mp4",
        headers={"Range": "bytes=0-3"},
    )
    assert res.status_code == 206
    assert res.headers["content-range"] == f"bytes 0-3/{len(b'mock_image_bytes')}"
    assert res.headers["content-length"] == "4"
    assert res.headers["accept-ranges"] == "bytes"
    assert res.content == b"mock"


def test_media_proxy_rejects_unsatisfiable_range():
    from omnimash.config import settings

    app = create_app(mock_mode=True)
    client = TestClient(app)
    bucket = settings.gcs_bucket_name
    res = client.get(
        f"/api/media-proxy?uri=gs://{bucket}/clip.mp4",
        headers={"Range": "bytes=9999-"},
    )
    assert res.status_code == 416
    assert res.headers["content-range"] == f"bytes */{len(b'mock_image_bytes')}"


def test_parse_range_header_variants():
    from omnimash.api.app import _parse_range_header

    # No / unparseable header -> serve full (None).
    assert _parse_range_header(None, 100) is None
    assert _parse_range_header("items=0-10", 100) is None
    assert _parse_range_header("bytes=0-10,20-30", 100) is None
    # Closed range, clamped to size.
    assert _parse_range_header("bytes=0-49", 100) == (0, 49)
    assert _parse_range_header("bytes=10-", 100) == (10, 99)
    assert _parse_range_header("bytes=50-9999", 100) == (50, 99)
    # Suffix range: last N bytes.
    assert _parse_range_header("bytes=-20", 100) == (80, 99)
    assert _parse_range_header("bytes=-500", 100) == (0, 99)
    # Unsatisfiable -> sentinel for a 416.
    assert _parse_range_header("bytes=100-", 100) == "invalid"
    assert _parse_range_header("bytes=-0", 100) == "invalid"


def test_extract_reference_rejects_bad_urls():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    for bad in (
        "file:///etc/passwd",
        "http://169.254.169.254/latest/meta-data/",
        "https://evil.example.com/watch?v=abc",
        "not-a-url",
    ):
        res = client.post("/api/extract-reference", json={"url": bad})
        assert res.status_code == 422, bad


def test_extract_reference_allows_youtube():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.post(
        "/api/extract-reference",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert res.status_code == 200


def test_api_list_sessions():
    app = create_app(mock_mode=True)
    client = TestClient(app)
    res = client.get("/api/sessions")
    assert res.status_code == 200
    data = res.json()
    assert "sessions" in data
    assert "parody_session_1" in data["sessions"]


def test_save_final_returns_502_when_no_uri(monkeypatch):
    # An empty save result must not be reported as success.
    from omnimash.agent.orchestrator import OmniMashAgent

    monkeypatch.setattr(OmniMashAgent, "save_final_master", lambda self, **kw: ("", ""))
    app = create_app(mock_mode=True)
    client = TestClient(app)
    resp = client.post(
        "/api/save-final",
        json={"session_name": "s1", "video_url": "/static/x.mp4", "master_title": "m1"},
    )
    assert resp.status_code == 502


def test_external_service_error_maps_to_sanitized_502(monkeypatch):
    from omnimash.agent.orchestrator import OmniMashAgent
    from omnimash.engine.media_utils import FfmpegError

    def boom(self, **kwargs):
        raise FfmpegError("ffmpeg failed on /tmp/secret_path.mp4", stderr="gs://bucket/leak")

    monkeypatch.setattr(OmniMashAgent, "save_final_master", boom)
    app = create_app(mock_mode=True)
    client = TestClient(app)
    resp = client.post(
        "/api/save-final",
        json={"session_name": "s1", "video_url": "/static/x.mp4", "master_title": "m1"},
    )
    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert "secret_path" not in detail
    assert "/tmp" not in detail
    assert "gs://" not in detail


def test_generate_endpoint_success_unaffected_by_error_handling():
    # Regression: happy path still returns 200/success with error handling wired in.
    app = create_app(mock_mode=True)
    client = TestClient(app)
    resp = client.post(
        "/api/generate",
        json={
            "user_id": "usr_ok",
            "project_id": "prj_ok",
            "prompt": "Snape spicy 90s rap video",
            "clip_index": 0,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_import_and_create_app_do_not_run_ffmpeg_warmup(monkeypatch):
    # The ffmpeg warm-up must only run inside the FastAPI lifespan (on startup),
    # never at import time or during plain create_app()/TestClient construction.
    import importlib

    from omnimash.engine import omni_client

    calls: list[str] = []
    monkeypatch.setattr(
        omni_client, "ensure_rendered_video", lambda *a, **k: calls.append("called")
    )
    # The module-level ``app = create_app()`` runs on reload; keep it in mock mode.
    monkeypatch.setenv("MOCK_MODE", "true")

    # Re-importing the app module must not trigger the warm-up.
    import omnimash.api.app as app_module

    importlib.reload(app_module)
    assert calls == []

    # Building the app (without entering its lifespan) must not either.
    app_module.create_app(mock_mode=True)
    assert calls == []

    # Entering the lifespan via the TestClient context manager runs it exactly once.
    with TestClient(app_module.create_app(mock_mode=True)):
        pass
    assert calls == ["called"]
