"""Session listing and the dashboard entry point."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from omnimash.agent.orchestrator import OmniMashAgent
from omnimash.api.deps import get_agent, load_ui_html
from omnimash.api.schemas import SessionListResponse

router = APIRouter()

AgentDep = Annotated[OmniMashAgent, Depends(get_agent)]


@router.get("/", response_class=HTMLResponse)
def get_dashboard() -> HTMLResponse:
    return HTMLResponse(content=load_ui_html())


@router.get("/api/sessions", response_model=SessionListResponse)
def list_sessions(agent: AgentDep) -> SessionListResponse:
    return SessionListResponse(sessions=agent.storage.list_session_ids())
