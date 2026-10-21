"""Deployment script for OmniMash on Vertex AI Agent Engine."""

import os
import sys

# Ensure src/ is in sys.path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import vertexai  # noqa: E402
from vertexai import agent_engines  # noqa: E402
from omnimash.agent.orchestrator import root_agent  # noqa: E402

AGENT_ENGINE_REQUIREMENTS: list[str] = [
    "google-cloud-aiplatform[agent_engines,a2a]>=1.112",
    "google-adk>=2.5.0",
    "google-genai",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "google-cloud-storage",
    "google-cloud-modelarmor",
    "pillow",
    "yt-dlp",
    "httpx",
    "numpy",
    "cloudpickle",
]

AGENT_ENGINE_EXTRA_PACKAGES: list[str] = ["omnimash"]


def deploy_to_agent_engine(
    project_id: str = "hybrid-vertex",
    location: str = "us-central1",
    display_name: str = "omnimash-agent-production",
) -> None:
    """Deploys the root_agent to Vertex AI Agent Engine."""
    raw_bucket = (
        os.environ.get("GCS_BUCKET_NAME", "").strip()
        or os.environ.get("OMNIMASH_GCS_BUCKET", "").strip()
    )
    staging_bucket = raw_bucket or f"gs://omnimash-media-{project_id}"
    if not staging_bucket.startswith("gs://"):
        staging_bucket = f"gs://{staging_bucket}"
    bucket_name = staging_bucket.removeprefix("gs://").strip("/")

    print(
        f"🚀 Initializing Vertex AI client for project '{project_id}' in '{location}' with staging bucket '{staging_bucket}'..."
    )
    vertexai.init(project=project_id, location=location, staging_bucket=staging_bucket)

    app = agent_engines.AdkApp(agent=root_agent)

    print("📦 Deploying OmniMash Agent to Vertex AI Agent Engine...")
    print("   Model: gemini-omni-flash-preview")
    print(f"   Display Name: {display_name}")

    original_cwd = os.getcwd()
    try:
        # Vertex AI Agent Engine archives extra_packages relative to cwd into
        # dependencies.tar.gz and extracts it into /code in the container.
        # Switching cwd to src/ ensures `omnimash/` is archived at top level
        # so `import omnimash` resolves directly on sys.path in /code.
        if os.path.isdir(SRC_DIR):
            os.chdir(SRC_DIR)

        remote_agent = agent_engines.create(
            agent_engine=app,  # ty: ignore[invalid-argument-type]
            display_name=display_name,
            requirements=list(AGENT_ENGINE_REQUIREMENTS),
            extra_packages=list(AGENT_ENGINE_EXTRA_PACKAGES),
            env_vars={
                "PYTHONPATH": "/code:/code/src:src:.",
                "GOOGLE_CLOUD_LOCATION": "global",
                "GEMINI_LOCATION": "global",
                "GCP_REGION": location,
                "OMNIMASH_GCS_BUCKET": bucket_name,
            },
        )
        print("✅ OmniMash successfully deployed to Vertex AI Agent Engine!")
        print(f"   Resource Name: {remote_agent.resource_name}")
    except Exception as e:
        print(f"⚠️ Agent Engine deployment error or simulation note: {e}")
        print(
            "💡 Note: To deploy with full cloud runtime permissions, ensure GCP credentials and Vertex AI APIs are enabled."
        )
    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "hybrid-vertex")
    region = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
    deploy_to_agent_engine(project_id=project, location=region)
