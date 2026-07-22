"""Generation, editing, stitching, and research/reference endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from omnimash.agent.orchestrator import OmniMashAgent
from omnimash.api.deps import get_agent
from omnimash.api.schemas import (
    CharacterRoleModel,
    CommitRequest,
    ConceptDeconstructRequest,
    DeconstructResponse,
    ExtendSceneRequest,
    ExtractReferenceRequest,
    GenerateRequest,
    GenerateResponse,
    ResearchRequest,
    SaveFinalRequest,
    SaveFinalResponse,
    StitchClipsRequest,
)
from omnimash.ingestion.media_extractor import (
    ParodyResearchResult,
    ReferenceAnalysisReport,
)

router = APIRouter()

AgentDep = Annotated[OmniMashAgent, Depends(get_agent)]


def _to_generate_response(agent_turn) -> GenerateResponse:
    """Map an orchestrator turn result onto the API response model."""
    return GenerateResponse(
        success=agent_turn.success,
        status=agent_turn.status_event,
        video_url=agent_turn.video_url,
        turn_id=agent_turn.turn_id,
        depth=agent_turn.depth,
        error=agent_turn.error_message,
        generation_mode=agent_turn.generation_mode,
        raw_compiled_prompt=agent_turn.raw_compiled_prompt,
        reference_analysis=agent_turn.reference_analysis,
    )


@router.post("/api/deconstruct-concept", response_model=DeconstructResponse)
def deconstruct_concept(req: ConceptDeconstructRequest, agent: AgentDep) -> DeconstructResponse:
    tags = agent.deconstruct_concept(req.concept)
    return DeconstructResponse(
        characters=[
            CharacterRoleModel(
                role_id=c.role_id,
                name=c.name,
                description=c.description,
                reference_url=c.reference_url,
                aesthetic_tags=c.aesthetic_tags,
                voice_style=c.voice_style,
            )
            for c in tags.characters
        ],
        aesthetic_tags=tags.aesthetic_tags,
        environment_tag=tags.environment_tag,
        camera_lighting_tag=tags.camera_lighting_tag,
        audio_beat=tags.audio_beat,
        vocal_delivery=tags.vocal_delivery,
    )


@router.post("/api/generate", response_model=GenerateResponse)
@router.post("/api/diff", response_model=GenerateResponse)
def generate_video(req: GenerateRequest, agent: AgentDep) -> GenerateResponse:
    agent_turn = agent.process_user_turn(
        user_id=req.user_id,
        project_id=req.project_id,
        prompt=req.prompt,
        clip_index=req.clip_index,
        parent_turn_id=req.parent_turn_id,
        reference_url=req.reference_url,
        audio_stem=req.audio_stem,
        voiceover=req.voiceover,
        is_silent=req.is_silent,
        on_screen_text=req.on_screen_text,
        compiled_override=req.compiled_override,
        session_name=req.session_name,
        concept=req.concept,
        characters=req.characters,
        scenes=req.scenes,
        aesthetic_tags=req.aesthetic_tags,
        environment_tag=req.environment_tag,
        vocal_delivery=req.vocal_delivery,
        optimize_prompt=req.optimize_prompt,
    )
    return _to_generate_response(agent_turn)


@router.post("/api/commit", response_model=GenerateResponse)
def commit_and_branch(req: CommitRequest, agent: AgentDep) -> GenerateResponse:
    agent_turn = agent.commit_and_branch(
        user_id=req.user_id,
        project_id=req.project_id,
        turn_id=req.turn_id,
        prompt=req.next_prompt,
        session_name=req.session_name,
    )
    return _to_generate_response(agent_turn)


@router.post("/api/save-final", response_model=SaveFinalResponse)
def save_final(req: SaveFinalRequest, agent: AgentDep) -> SaveFinalResponse:
    _pub_url, gcs_uri = agent.save_final_master(
        session_name=req.session_name,
        video_url=req.video_url,
        master_title=req.master_title,
    )
    if not gcs_uri:
        raise HTTPException(
            status_code=502,
            detail="Save produced no artifact; the master was not persisted.",
        )
    return SaveFinalResponse(
        success=True,
        gcs_uri=gcs_uri,
        message=f"Final master successfully saved to {gcs_uri}",
    )


@router.post("/api/stitch-clips", response_model=SaveFinalResponse)
def stitch_clips(req: StitchClipsRequest, agent: AgentDep) -> SaveFinalResponse:
    if not req.clip_urls:
        raise HTTPException(
            status_code=400,
            detail="At least one clip URL is required for stitching.",
        )
    stitched_path = agent.stitcher.concatenate_clips(req.clip_urls, session_id=req.session_name)
    _pub_url, gcs_uri = agent.storage.save_final_master(
        session_id=req.session_name,
        source_rel_path=stitched_path,
        master_title=req.master_title,
    )
    if not gcs_uri:
        raise HTTPException(
            status_code=502,
            detail="Stitching produced no artifact; the master was not persisted.",
        )
    return SaveFinalResponse(
        success=True,
        gcs_uri=gcs_uri,
        message=f"Custom stitched master successfully saved to {gcs_uri}",
    )


@router.post("/api/extend-scene", response_model=GenerateResponse)
def extend_scene(req: ExtendSceneRequest, agent: AgentDep) -> GenerateResponse:
    agent_turn = agent.extend_scene(
        session_name=req.session_name,
        turn_id=req.turn_id,
        next_scene_action=req.next_scene_action,
        dialogue=req.dialogue,
        active_roles=req.active_roles,
        vocal_delivery=req.vocal_delivery,
    )
    return _to_generate_response(agent_turn)


@router.post("/api/research", response_model=ParodyResearchResult)
def research_parody(req: ResearchRequest, agent: AgentDep) -> ParodyResearchResult:
    return agent.media_extractor.research_parody_clash(req.subject, req.aesthetic)


@router.post("/api/extract-reference", response_model=ReferenceAnalysisReport)
def extract_reference(req: ExtractReferenceRequest, agent: AgentDep) -> ReferenceAnalysisReport:
    return agent.media_extractor.analyze_youtube_reference(
        req.url, session_id=req.session_name or "default"
    )
