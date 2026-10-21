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


def prune_orphan_agent_engines(
    project_id: str = "hybrid-vertex",
    location: str = "us-central1",
    display_name: str = "omnimash-agent-production",
    keep_resource_name: str | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Finds and deletes superseded reasoning engines with matching display_name.

    Args:
        project_id: GCP project ID.
        location: GCP region location.
        display_name: The display name to match (exact match for safety).
        keep_resource_name: Specific resource_name to spare (e.g. newly deployed engine).
            If None and multiple exist, keeps only the newest by create_time.
        dry_run: If True, only lists candidates without deleting.

    Returns:
        List of deleted (or candidate) resource names.
    """
    vertexai.init(project=project_id, location=location)
    try:
        matching_engines = [
            eng
            for eng in agent_engines.list()
            if getattr(eng, "display_name", None) == display_name
        ]
    except Exception as e:
        print(f"⚠️ Failed to list reasoning engines for orphan pruning: {e}")
        return []

    if not matching_engines:
        print(f"ℹ️ No reasoning engines found with display name '{display_name}'.")
        return []

    # Sort matching engines by create_time descending (newest first)
    matching_engines.sort(
        key=lambda eng: str(getattr(eng, "create_time", "") or ""),
        reverse=True,
    )

    # Determine which engine to keep
    target_to_keep = keep_resource_name or getattr(matching_engines[0], "resource_name", None)

    orphans = [
        eng for eng in matching_engines if getattr(eng, "resource_name", None) != target_to_keep
    ]

    print(f"🔍 Found {len(matching_engines)} instance(s) matching '{display_name}'.")
    print(f"   Active / Preserved: {target_to_keep}")
    print(f"   Orphans identified: {len(orphans)}")

    deleted: list[str] = []
    for orphan in orphans:
        r_name = getattr(orphan, "resource_name", str(orphan))
        c_time = getattr(orphan, "create_time", "unknown")
        if dry_run:
            print(f"   [DRY-RUN] Would delete orphan: {r_name} (created {c_time})")
            deleted.append(r_name)
        else:
            print(f"   🗑️ Deleting orphan: {r_name} (created {c_time})...")
            try:
                orphan.delete(force=True)
                print(f"   ✅ Successfully deleted orphan: {r_name}")
                deleted.append(r_name)
            except Exception as e:
                print(f"   ⚠️ Failed to delete {r_name}: {e}")

    return deleted


def deploy_to_agent_engine(
    project_id: str = "hybrid-vertex",
    location: str = "us-central1",
    display_name: str = "omnimash-agent-production",
    auto_prune_orphans: bool = True,
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

        if auto_prune_orphans:
            print("🧹 Automatically pruning superseded orphan instances of this agent engine...")
            prune_orphan_agent_engines(
                project_id=project_id,
                location=location,
                display_name=display_name,
                keep_resource_name=remote_agent.resource_name,
            )
    except Exception as e:
        print(f"⚠️ Agent Engine deployment error or simulation note: {e}")
        print(
            "💡 Note: To deploy with full cloud runtime permissions, ensure GCP credentials and Vertex AI APIs are enabled."
        )
    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Deploy or prune Vertex AI Agent Engines for OmniMash."
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT", "hybrid-vertex"),
        help="GCP Project ID (default: hybrid-vertex).",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("GOOGLE_CLOUD_REGION", "us-central1"),
        help="GCP Region (default: us-central1).",
    )
    parser.add_argument(
        "--display-name",
        default="omnimash-agent-production",
        help="Display name of the agent engine (default: omnimash-agent-production).",
    )
    parser.add_argument(
        "--prune-orphans-only",
        action="store_true",
        help="Only prune older orphan instances without deploying a new agent engine.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview orphans to be pruned without deleting.",
    )
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="Deploy without pruning superseded instances.",
    )

    args = parser.parse_args()

    if args.prune_orphans_only:
        prune_orphan_agent_engines(
            project_id=args.project,
            location=args.region,
            display_name=args.display_name,
            dry_run=args.dry_run,
        )
    else:
        deploy_to_agent_engine(
            project_id=args.project,
            location=args.region,
            display_name=args.display_name,
            auto_prune_orphans=not args.no_prune,
        )
