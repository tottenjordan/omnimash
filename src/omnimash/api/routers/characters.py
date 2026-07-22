"""Character and roster persistence endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from omnimash.agent.orchestrator import OmniMashAgent
from omnimash.api.deps import get_agent
from omnimash.api.schemas import (
    CharacterListResponse,
    CharacterRoleModel,
    LoadCharacterRequest,
    SaveCharacterRequest,
    SaveCharacterResponse,
    SaveRosterRequest,
)

router = APIRouter()

AgentDep = Annotated[OmniMashAgent, Depends(get_agent)]


def _to_role_model(data: dict) -> CharacterRoleModel:
    """Build a response model from a stored character dict with safe defaults."""
    return CharacterRoleModel(
        role_id=data.get("role_id", "Role A"),
        name=data.get("name", ""),
        description=data.get("description", ""),
        reference_url=data.get("reference_url"),
        aesthetic_tags=data.get("aesthetic_tags", []),
        voice_style=data.get("voice_style", ""),
    )


@router.post("/api/characters/save", response_model=SaveCharacterResponse)
def save_character(req: SaveCharacterRequest, agent: AgentDep) -> SaveCharacterResponse:
    _pub_url, gcs_uri = agent.storage.save_character(
        req.character.model_dump(),
        session_id=req.session_name,
        is_library=req.is_library,
    )
    return SaveCharacterResponse(
        success=True,
        gcs_uri=gcs_uri,
        message=f"Character saved successfully to {gcs_uri}",
    )


@router.get("/api/characters", response_model=CharacterListResponse)
def list_characters(agent: AgentDep, session_name: str | None = None) -> CharacterListResponse:
    raw_chars = agent.storage.list_characters(session_id=session_name)
    return CharacterListResponse(characters=[_to_role_model(c) for c in (raw_chars or [])])


@router.post("/api/characters/load", response_model=CharacterRoleModel)
def load_character(req: LoadCharacterRequest, agent: AgentDep) -> CharacterRoleModel:
    char_data = agent.storage.load_character(req.slug, session_id=req.session_name)
    if not char_data:
        raise HTTPException(status_code=404, detail=f"Character '{req.slug}' not found")
    return _to_role_model(char_data)


@router.post("/api/characters/save-roster", response_model=SaveCharacterResponse)
def save_roster(req: SaveRosterRequest, agent: AgentDep) -> SaveCharacterResponse:
    _pub_url, gcs_uri = agent.storage.save_session_roster(
        req.session_name,
        [c.model_dump() for c in req.characters],
    )
    return SaveCharacterResponse(
        success=True,
        gcs_uri=gcs_uri,
        message=f"Session roster saved successfully to {gcs_uri}",
    )


@router.get("/api/characters/roster", response_model=CharacterListResponse)
def get_session_roster(session_name: str, agent: AgentDep) -> CharacterListResponse:
    raw_roster = agent.storage.load_session_roster(session_name)
    return CharacterListResponse(characters=[_to_role_model(c) for c in (raw_roster or [])])
