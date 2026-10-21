"""Unit tests for Vertex AI Agent Engine deployment script."""

import importlib.util
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "deploy_agent_engine.py"


def _load_deploy_module():
    spec = importlib.util.spec_from_file_location("deploy_agent_engine", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deploy_to_agent_engine_packages_omnimash_and_dependencies(monkeypatch):
    """Verifies deploy_to_agent_engine passes extra_packages and required runtime dependencies."""
    monkeypatch.delenv("GCS_BUCKET_NAME", raising=False)
    monkeypatch.delenv("OMNIMASH_GCS_BUCKET", raising=False)
    deploy_mod = _load_deploy_module()

    original_cwd = os.getcwd()
    captured_cwd_during_create: list[str] = []

    def _fake_create(**kwargs):
        captured_cwd_during_create.append(os.getcwd())
        for pkg in kwargs.get("extra_packages", []):
            assert os.path.exists(pkg), f"extra_package {pkg!r} must exist relative to cwd"
        mock_remote = MagicMock()
        mock_remote.resource_name = "projects/123/locations/us-central1/reasoningEngines/456"
        return mock_remote

    with (
        patch.object(deploy_mod.vertexai, "init") as mock_init,
        patch.object(deploy_mod.agent_engines, "AdkApp") as mock_adk_app,
        patch.object(deploy_mod.agent_engines, "create", side_effect=_fake_create) as mock_create,
    ):
        deploy_mod.deploy_to_agent_engine(
            project_id="hybrid-vertex",
            location="us-central1",
            display_name="omnimash-test-agent",
        )

    assert os.getcwd() == original_cwd
    assert captured_cwd_during_create == [str(REPO_ROOT / "src")]

    mock_init.assert_called_once_with(
        project="hybrid-vertex",
        location="us-central1",
        staging_bucket="gs://omnimash-media-hybrid-vertex",
    )
    mock_adk_app.assert_called_once_with(agent=deploy_mod.root_agent)
    mock_create.assert_called_once()

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["display_name"] == "omnimash-test-agent"
    assert call_kwargs["extra_packages"] == ["omnimash"]

    reqs = call_kwargs["requirements"]
    required_prefixes = [
        "google-cloud-aiplatform",
        "google-adk",
        "google-genai",
        "pydantic>=",
        "pydantic-settings",
        "google-cloud-storage",
        "google-cloud-modelarmor",
        "pillow",
        "yt-dlp",
        "httpx",
        "numpy",
        "cloudpickle",
    ]
    for prefix in required_prefixes:
        assert any(r.startswith(prefix) for r in reqs), (
            f"Expected dependency starting with {prefix!r} in requirements: {reqs}"
        )

    env_vars = call_kwargs["env_vars"]
    assert env_vars["GOOGLE_CLOUD_LOCATION"] == "global"
    assert env_vars["GEMINI_LOCATION"] == "global"
    assert env_vars["GCP_REGION"] == "us-central1"
    assert env_vars["OMNIMASH_GCS_BUCKET"] == "omnimash-media-hybrid-vertex"
    assert "/code" in env_vars["PYTHONPATH"]
    assert "GOOGLE_CLOUD_PROJECT" not in env_vars


def test_deploy_to_agent_engine_normalizes_bucket_and_restores_cwd_on_error(monkeypatch):
    """Verifies GCS_BUCKET_NAME without gs:// is normalized, passed to env_vars, and cwd is restored on error."""
    monkeypatch.setenv("GCS_BUCKET_NAME", "custom-staging-bucket")
    deploy_mod = _load_deploy_module()

    original_cwd = os.getcwd()

    with (
        patch.object(deploy_mod.vertexai, "init") as mock_init,
        patch.object(deploy_mod.agent_engines, "AdkApp"),
        patch.object(
            deploy_mod.agent_engines,
            "create",
            side_effect=RuntimeError("simulated deployment failure"),
        ) as mock_create,
    ):
        deploy_mod.deploy_to_agent_engine(
            project_id="hybrid-vertex",
            location="us-central1",
        )

    assert os.getcwd() == original_cwd
    mock_init.assert_called_once_with(
        project="hybrid-vertex",
        location="us-central1",
        staging_bucket="gs://custom-staging-bucket",
    )
    assert (
        mock_create.call_args.kwargs["env_vars"]["OMNIMASH_GCS_BUCKET"] == "custom-staging-bucket"
    )


def test_deploy_to_agent_engine_handles_whitespace_bucket_and_omnimash_gcs_bucket_fallback(
    monkeypatch,
):
    """Verifies empty/whitespace GCS_BUCKET_NAME falls back to OMNIMASH_GCS_BUCKET or default bucket."""
    monkeypatch.setenv("GCS_BUCKET_NAME", "   ")
    monkeypatch.setenv("OMNIMASH_GCS_BUCKET", "gs://fallback-omnimash-bucket/")
    deploy_mod = _load_deploy_module()

    with (
        patch.object(deploy_mod.vertexai, "init") as mock_init,
        patch.object(deploy_mod.agent_engines, "AdkApp"),
        patch.object(deploy_mod.agent_engines, "create") as mock_create,
    ):
        deploy_mod.deploy_to_agent_engine(
            project_id="hybrid-vertex",
            location="us-central1",
        )

    mock_init.assert_called_once_with(
        project="hybrid-vertex",
        location="us-central1",
        staging_bucket="gs://fallback-omnimash-bucket/",
    )
    assert (
        mock_create.call_args.kwargs["env_vars"]["OMNIMASH_GCS_BUCKET"]
        == "fallback-omnimash-bucket"
    )
