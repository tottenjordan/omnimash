"""ADK Agent entrypoint for OmniMash."""

from omnimash.agent.orchestrator import build_adk_agent, get_root_agent, root_agent

agent = get_root_agent()

__all__ = ["agent", "build_adk_agent", "get_root_agent", "root_agent"]
