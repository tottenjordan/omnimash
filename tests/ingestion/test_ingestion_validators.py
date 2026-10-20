import pytest

from omnimash.ingestion.validators import (
    normalize_and_validate_clip_paths,
    sanitize_clip_timing,
    sanitize_ingestion_session_id,
    validate_youtube_reference_url,
)


def test_validate_youtube_reference_url_allows_youtube_and_blocks_ssrf(monkeypatch):
    import socket

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("142.250.190.46", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    assert (
        validate_youtube_reference_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )
    assert (
        validate_youtube_reference_url("https://youtu.be/dQw4w9WgXcQ")
        == "https://youtu.be/dQw4w9WgXcQ"
    )

    for bad_url in [
        "file:///etc/passwd",
        "http://169.254.169.254/latest/meta-data/",
        "https://evil.example.com/watch?v=123",
        "ytsearch:secret",
    ]:
        with pytest.raises(ValueError):
            validate_youtube_reference_url(bad_url)


def test_sanitize_ingestion_session_id_blocks_path_traversal():
    assert sanitize_ingestion_session_id(None) == "default"
    assert sanitize_ingestion_session_id("") == "default"
    assert sanitize_ingestion_session_id("sess_123-abc") == "sess_123-abc"

    for malicious in ["../etc", "../../tmp/pwn", "sess/../../root", "bad\x00id"]:
        with pytest.raises(ValueError, match="Invalid session_id"):
            sanitize_ingestion_session_id(malicious)


def test_normalize_and_validate_clip_paths_strips_leading_static_slash():
    src, out = normalize_and_validate_clip_paths("/static/uploads/dance.mp4")
    assert src == "static/uploads/dance.mp4"
    assert out == "static/uploads/dance_motion_3s.mp4"

    for bad_path in ["-i /etc/passwd", "/etc/passwd", "../../etc/shadow"]:
        with pytest.raises(ValueError):
            normalize_and_validate_clip_paths(bad_path)


def test_sanitize_clip_timing_handles_nan_inf_and_negative_values():
    start, dur = sanitize_clip_timing(-4.5, -10.0)
    assert start == 0.0
    assert dur == 3.0

    start_nan, dur_inf = sanitize_clip_timing(float("nan"), float("inf"))
    assert start_nan == 0.0
    assert dur_inf == 3.0

    start_ok, dur_ok = sanitize_clip_timing(2.5, 4.0)
    assert start_ok == 2.5
    assert dur_ok == 4.0
