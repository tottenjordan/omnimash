from fastapi import APIRouter, HTTPException

from omnimash.api.deps import AgentDep
from omnimash.api.models import (
    CharacterListResponse,
    CharacterRoleModel,
    CreateProjectRequest,
    CreateProjectResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    ProjectListResponse,
    ReferenceSheetListResponse,
    SessionListResponse,
)
from omnimash.storage.gcs import validate_safe_identifier as _storage_validate_safe_identifier

router = APIRouter()


def validate_safe_identifier(value: str, label: str = "identifier") -> str:
    """SEC-02: Validates project_name / session_name against path traversal and unsafe characters."""
    try:
        return _storage_validate_safe_identifier(value, label)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.get("/api/projects", response_model=ProjectListResponse)
def list_projects(agent: AgentDep) -> ProjectListResponse:
    return ProjectListResponse(projects=agent.storage.list_projects())


@router.post("/api/projects/create", response_model=CreateProjectResponse)
def create_project(req: CreateProjectRequest, agent: AgentDep) -> CreateProjectResponse:
    safe_project = validate_safe_identifier(req.project_name, "project_name")
    gcs_uri = agent.storage.create_project(safe_project)
    return CreateProjectResponse(
        success=True,
        project_name=safe_project,
        gcs_uri=gcs_uri,
        message=f"Project '{safe_project}' created successfully",
    )


@router.get("/api/projects/{project_name}/sessions", response_model=SessionListResponse)
def list_project_sessions(project_name: str, agent: AgentDep) -> SessionListResponse:
    safe_project = validate_safe_identifier(project_name, "project_name")
    return SessionListResponse(sessions=agent.storage.list_sessions(safe_project))


@router.post(
    "/api/projects/{project_name}/sessions/create",
    response_model=CreateSessionResponse,
)
def create_project_session(
    project_name: str, req: CreateSessionRequest, agent: AgentDep
) -> CreateSessionResponse:
    safe_project = validate_safe_identifier(project_name, "project_name")
    safe_session = validate_safe_identifier(req.session_name, "session_name")
    gcs_uri = agent.storage.create_session(safe_session, project_id=safe_project)
    return CreateSessionResponse(
        success=True,
        project_name=safe_project,
        session_name=safe_session,
        gcs_uri=gcs_uri,
        message=f"Session '{safe_session}' created under project '{safe_project}'",
    )


@router.get("/api/projects/{project_name}/characters", response_model=CharacterListResponse)
def list_project_characters(project_name: str, agent: AgentDep) -> CharacterListResponse:
    safe_project = validate_safe_identifier(project_name, "project_name")
    raw_chars = agent.storage.list_project_characters(safe_project)
    characters = [CharacterRoleModel.from_storage_dict(c) for c in (raw_chars or [])]
    return CharacterListResponse(characters=characters)


@router.get(
    "/api/projects/{project_name}/reference-sheets",
    response_model=ReferenceSheetListResponse,
)
def list_project_reference_sheets(project_name: str, agent: AgentDep) -> ReferenceSheetListResponse:
    safe_project = validate_safe_identifier(project_name, "project_name")
    sheets = agent.storage.list_project_reference_sheets(safe_project)
    return ReferenceSheetListResponse(reference_sheets=sheets or [])


@router.get("/api/sessions", response_model=SessionListResponse)
def list_sessions(agent: AgentDep) -> SessionListResponse:
    return SessionListResponse(sessions=agent.storage.list_session_ids())
