import logging

from fastapi import APIRouter, HTTPException

from omnimash.api.deps import AgentDep
from omnimash.api.models import (
    CharacterListResponse,
    CharacterRoleModel,
    GenerateCharacterSheetRequest,
    GenerateCharacterSheetResponse,
    LoadCharacterRequest,
    SaveCharacterRequest,
    SaveCharacterResponse,
    SaveCharacterSheetRequest,
    SaveCharacterSheetResponse,
    SaveRosterRequest,
)
from omnimash.api.routers.projects import validate_safe_identifier

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/characters/save", response_model=SaveCharacterResponse)
def save_character(req: SaveCharacterRequest, agent: AgentDep) -> SaveCharacterResponse:
    project_id = (
        validate_safe_identifier(req.project_name, "project_name")
        if req.project_name
        else "default_project"
    )
    if req.session_name:
        validate_safe_identifier(req.session_name, "session_name")
    _pub_url, gcs_uri = agent.storage.save_character(
        req.character.model_dump(),
        session_id=req.session_name,
        project_id=project_id,
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
    characters = [CharacterRoleModel.from_storage_dict(c) for c in (raw_chars or [])]
    return CharacterListResponse(characters=characters)


@router.post("/api/characters/load", response_model=CharacterRoleModel)
def load_character(req: LoadCharacterRequest, agent: AgentDep) -> CharacterRoleModel:
    char_data = agent.storage.load_character(req.slug, session_id=req.session_name)
    if not char_data:
        raise HTTPException(
            status_code=404,
            detail=f"Character '{req.slug}' not found",
        )
    return CharacterRoleModel.from_storage_dict(char_data)


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
    characters = [CharacterRoleModel.from_storage_dict(c) for c in (raw_roster or [])]
    return CharacterListResponse(characters=characters)


@router.post(
    "/api/characters/generate-sheet",
    response_model=GenerateCharacterSheetResponse,
)
def generate_character_sheet_endpoint(req: GenerateCharacterSheetRequest, agent: AgentDep):
    raw_sheet_model = (req.model or "").strip()
    effective_sheet_model = (
        "gemini-nano-banana-2.1"
        if not raw_sheet_model or raw_sheet_model.startswith("gemini-3.1-flash-image")
        else raw_sheet_model
    )
    try:
        res = agent.omni_client.generate_character_reference_sheet(
            source_image_url=req.source_image_url,
            character_name=req.character_name or "",
            description=req.description or "",
            aesthetic_tags=req.aesthetic_tags,
            custom_prompt_override=req.custom_prompt,
            image_model=effective_sheet_model,
            aspect_ratio=req.aspect_ratio,
            return_compiled_prompt=True,
            style_preset=req.style_preset,
        )

        if isinstance(res, tuple) and len(res) == 2:
            url, compiled = res
        elif isinstance(res, dict):
            url = res.get("keyframe_image_url", "")
            compiled = res.get("raw_compiled_prompt", "")
        else:
            url = str(res)
            compiled = ""

        return GenerateCharacterSheetResponse(
            success=True,
            character_name=req.character_name,
            keyframe_image_url=url,
            compiled_prompt=compiled,
            raw_compiled_prompt=compiled,
            aspect_ratio=req.aspect_ratio,
            model=effective_sheet_model,
        )
    except Exception as e:
        logger.error("Error generating character turnaround sheet: %s", e, exc_info=True)
        return GenerateCharacterSheetResponse(
            success=False,
            character_name=req.character_name,
            keyframe_image_url="",
            compiled_prompt="",
            raw_compiled_prompt="",
            aspect_ratio=req.aspect_ratio,
            model=effective_sheet_model,
            details=str(e),
        )


@router.post("/api/characters/save-sheet", response_model=SaveCharacterSheetResponse)
def save_character_sheet_endpoint(req: SaveCharacterSheetRequest, agent: AgentDep):
    try:
        public_url, gcs_uri = agent.storage.save_character_sheet(
            image_data=req.image_data,
            custom_name=req.custom_name,
            session_id=req.session_name,
            project_id=req.project_name,
        )
        return SaveCharacterSheetResponse(
            success=True,
            public_url=public_url,
            gcs_uri=gcs_uri,
            storage_path=gcs_uri,
        )
    except Exception as e:
        logger.error("Error saving character turnaround sheet: %s", e, exc_info=True)
        return SaveCharacterSheetResponse(
            success=False,
            public_url="",
            gcs_uri="",
            storage_path="",
            details=str(e),
        )
