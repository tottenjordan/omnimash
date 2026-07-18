"""ADK Agent entrypoint for OmniMash."""

from omnimash.agent.orchestrator import build_adk_agent, root_agent

agent = root_agent

__all__ = ["agent", "build_adk_agent", "root_agent"]
