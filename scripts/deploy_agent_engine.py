"""Deployment script for OmniMash on Vertex AI Agent Engine."""

import os
import sys

# Ensure src/ is in sys.path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

import vertexai
from vertexai import agent_engines
from omnimash.agent.orchestrator import root_agent


def deploy_to_agent_engine(
    project_id: str = "hybrid-vertex",
    location: str = "us-central1",
    display_name: str = "omnimash-agent-production",
) -> None:
    """Deploys the root_agent to Vertex AI Agent Engine."""
    print(
        f"🚀 Initializing Vertex AI client for project '{project_id}' in '{location}'..."
    )
    vertexai.init(project=project_id, location=location)

    app = agent_engines.AdkApp(agent=root_agent)

    print("📦 Deploying OmniMash Agent to Vertex AI Agent Engine...")
    print("   Model: gemini-omni-flash-preview")
    print(f"   Display Name: {display_name}")

    try:
        remote_agent = agent_engines.create(
            agent_engine=app,  # ty: ignore[invalid-argument-type]
            display_name=display_name,
            requirements=[
                "google-cloud-aiplatform[agent_engines,a2a]>=1.112",
                "google-adk>=2.5.0",
                "google-genai",
                "pydantic>=2.0",
            ],
        )
        print("✅ OmniMash successfully deployed to Vertex AI Agent Engine!")
        print(f"   Resource Name: {remote_agent.resource_name}")
    except Exception as e:
        print(f"⚠️ Agent Engine deployment error or simulation note: {e}")
        print(
            "💡 Note: To deploy with full cloud runtime permissions, ensure GCP credentials and Vertex AI APIs are enabled."
        )


if __name__ == "__main__":
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "hybrid-vertex")
    region = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
    deploy_to_agent_engine(project_id=project, location=region)
