from typing import Annotated
from fastapi import Depends, Request
from omnimash.agent.orchestrator import OmniMashAgent


def get_agent(request: Request) -> OmniMashAgent:
    """Dependency provider for accessing the active OmniMashAgent instance."""
    return request.app.state.agent


AgentDep = Annotated[OmniMashAgent, Depends(get_agent)]
