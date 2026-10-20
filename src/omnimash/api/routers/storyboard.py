from concurrent.futures import ThreadPoolExecutor
import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException

from omnimash.agent.adk_pipeline import deconstruct_screenplay_with_adk
from omnimash.api.deps import AgentDep
from omnimash.api.helpers import (
    extract_reference_urls,
    normalize_character_roles,
    parse_shot_directive_if_needed,
    stitch_and_upload_master,
)
from omnimash.api.models import (
    DeleteStoryboardRequest,
    DraftBatchItem,
    DraftBatchRequest,
    DraftBatchResponse,
    DraftBatchShotItem,
    GenerateShotRequest,
    GenerateShotResponse,
    KeyframeImageRequest,
    KeyframeImageResponse,
    LoadStoryboardRequest,
    SaveFinalResponse,
    SaveStoryboardRequest,
    SaveStoryboardResponse,
    StitchClipsRequest,
    StitchMasterRequest,
    StoryboardExpandRequest,
    StoryboardExpandResponse,
    StoryboardListResponse,
    StoryboardMetadataModel,
    StoryboardShotModel,
)
from omnimash.prompts.compiler import CharacterRole, SceneDirective, sanitize_real_names

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/storyboard/expand", response_model=StoryboardExpandResponse)
def expand_storyboard(req: StoryboardExpandRequest, agent: AgentDep) -> StoryboardExpandResponse:
    char_objs = normalize_character_roles(req.characters, sanitize=False)
    shots = deconstruct_screenplay_with_adk(
        concept=req.concept,
        style_tone=req.style_tone,
        target_duration=req.target_duration,
        characters=char_objs if char_objs else None,
        screenplay_script=req.screenplay_script,
        mock_mode=agent.mock_mode,
    )
    return StoryboardExpandResponse(
        shots=[
            StoryboardShotModel(
                shot_index=s.shot_index,
                duration_seconds=s.duration_seconds,
                action=s.action,
                location=s.location,
                style_lighting=s.style_lighting,
                framing_motion=s.framing_motion,
                audio=s.audio,
                dialogue=getattr(s, "dialogue", ""),
                summary=s.summary,
                keyframe_image_url=getattr(s, "keyframe_image_url", ""),
                video_url=getattr(s, "video_url", ""),
                narrative_stage=getattr(s, "narrative_stage", "Rising Action"),
                preceding_context=getattr(s, "preceding_context", ""),
                camera_transition=getattr(s, "camera_transition", "Continuous match cut"),
                character_continuity=getattr(
                    s,
                    "character_continuity",
                    "Maintain subject outfit, posture, and facial expression from preceding shot",
                ),
            )
            for s in shots
        ]
    )


@router.post("/api/storyboard/keyframe-image", response_model=KeyframeImageResponse)
def generate_keyframe_image(req: KeyframeImageRequest, agent: AgentDep) -> KeyframeImageResponse:
    if req.image_prompt and req.image_prompt.strip():
        prompt = req.image_prompt.strip()
    else:
        prompt_parts = [p for p in [req.action, req.location] if p]
        prompt = (
            ", ".join(prompt_parts) if prompt_parts else (req.summary or f"Shot {req.shot_index}")
        )
    ref_urls: list[str] = list(req.reference_image_urls or [])
    for ref in extract_reference_urls(req.characters):
        if ref not in ref_urls:
            ref_urls.append(ref)

    image_url = agent.omni_client.generate_keyframe_image(
        prompt,
        style_tone=req.style_lighting,
        reference_image_urls=ref_urls,
        characters=req.characters,
        anchor_keyframe_url=req.anchor_keyframe_url,
        aspect_ratio=req.aspect_ratio,
    )
    return KeyframeImageResponse(success=True, keyframe_image_url=image_url)


@router.post("/api/generate-shot", response_model=GenerateShotResponse)
def generate_shot(req: GenerateShotRequest, agent: AgentDep) -> GenerateShotResponse:
    sanitized_directive = (
        sanitize_real_names(req.shot_directive)
        if (req.shot_directive and req.enable_safety_sanitization)
        else (req.shot_directive or "")
    )
    keyframe_url = req.keyframe_image_url

    (
        action_val,
        dialogue_val,
        audio_val,
        location_val,
        style_lighting_val,
        framing_motion_val,
    ) = parse_shot_directive_if_needed(req)
    audio_stem_val = audio_val or req.audio_stem

    char_objs = normalize_character_roles(req.characters, sanitize=req.enable_safety_sanitization)
    ref_urls = extract_reference_urls(req.characters)

    if req.last_frame_image_url and req.last_frame_image_url.strip():
        has_last = any(c.image_role in ("Ending Frame", "Keyframe Last Anchor") for c in char_objs)
        if not has_last:
            char_objs.append(
                CharacterRole(
                    role_id="Ending Frame",
                    name="Ending Frame Anchor",
                    description="Ending Frame Anchor concept image",
                    reference_url=req.last_frame_image_url.strip(),
                    image_role="Ending Frame",
                )
            )

    active_roles: list[str] = []
    if char_objs:
        active_roles = [c.role_id or c.name for c in char_objs if c.role_id or c.name]
    if not active_roles:
        active_roles = ["Role A"]

    scene_directive = SceneDirective(
        scene_number=req.shot_index,
        active_roles=active_roles,
        action=action_val,
        dialogue=dialogue_val,
        duration_seconds=req.duration_seconds,
    )

    aesthetic_tags = [
        t for t in [style_lighting_val or req.style_lighting, framing_motion_val] if t and t.strip()
    ]

    if not keyframe_url and (action_val or sanitized_directive):
        try:
            keyframe_url = agent.omni_client.generate_keyframe_image(
                action_val or sanitized_directive,
                style_tone=req.style_lighting or style_lighting_val,
                reference_image_urls=ref_urls,
                characters=req.characters,
                aspect_ratio=req.aspect_ratio,
            )
        except Exception as exc:
            logger.warning(
                "Auto keyframe image generation before video generation failed: %s",
                exc,
            )

    compiled_prompt = agent.taxonomy.compiler.compile_storyboard(
        concept=action_val,
        characters=char_objs,
        scenes=[scene_directive],
        aesthetic_tags=aesthetic_tags if aesthetic_tags else None,
        environment_tag=location_val if location_val.strip() else None,
        audio_beat=audio_stem_val,
        has_keyframe_seed=bool(keyframe_url),
        keyframe_image_url=keyframe_url,
        last_frame_image_url=req.last_frame_image_url,
        enable_sanitization=req.enable_safety_sanitization,
        aspect_ratio=req.aspect_ratio,
        style_preset=req.style_lighting or style_lighting_val,
        is_seamless_loop=req.is_seamless_loop,
    )

    agent_turn = agent.process_user_turn(
        user_id="usr_default",
        project_id="prj_default",
        prompt=action_val or sanitized_directive,
        compiled_override=compiled_prompt,
        parent_turn_id=req.parent_turn_id,
        clip_index=req.shot_index,
        duration_seconds=req.duration_seconds,
        is_conversational_edit=False,
        session_name=req.session_name,
        characters=req.characters,
        scenes=[scene_directive],
        keyframe_image_url=keyframe_url,
        voiceover=dialogue_val if dialogue_val else None,
        audio_stem=audio_stem_val,
        enable_sanitization=req.enable_safety_sanitization,
        aspect_ratio=req.aspect_ratio,
        resolution=req.resolution,
        motion_reference_clip=req.motion_reference_clip,
    )
    return GenerateShotResponse(
        success=agent_turn.success,
        video_url=agent_turn.video_url,
        keyframe_image_url=keyframe_url,
        turn_id=agent_turn.turn_id,
        status=agent_turn.status_event,
        generation_mode=getattr(agent_turn, "generation_mode", "LIVE_OMNI_FLASH"),
        error=agent_turn.error_message,
        raw_compiled_prompt=agent_turn.raw_compiled_prompt or compiled_prompt,
    )


@router.post("/api/stitch-clips", response_model=SaveFinalResponse)
def stitch_clips(req: StitchClipsRequest, agent: AgentDep) -> SaveFinalResponse:
    if not req.clip_urls:
        raise HTTPException(
            status_code=400,
            detail="At least one clip URL is required for stitching.",
        )
    stitched_path = agent.stitcher.concatenate_clips(req.clip_urls, session_id=req.session_name)
    try:
        _pub_url, gcs_uri = agent.storage.save_final_master(
            session_id=req.session_name,
            source_rel_path=stitched_path,
            master_title=req.master_title,
        )
    finally:
        if stitched_path.startswith("/tmp/") and os.path.exists(stitched_path):
            try:
                os.remove(stitched_path)
            except OSError:
                pass
    return SaveFinalResponse(
        success=True,
        gcs_uri=gcs_uri,
        message=f"Custom stitched master successfully saved to {gcs_uri}",
    )


@router.post("/api/storyboard/stitch_master")
def stitch_storyboard_master(req: StitchMasterRequest, agent: AgentDep) -> dict[str, Any]:
    master_path, master_url = stitch_and_upload_master(
        agent=agent,
        shot_clips=req.shot_clips,
        title_cards=req.title_cards,
        narrator_audio_paths=req.narrator_audio_paths,
        background_music_path=req.background_music_path,
        session_id=req.session_id,
        aspect_ratio=req.aspect_ratio,
    )
    return {
        "status": "ok",
        "master_video_path": master_path,
        "master_video_url": master_url,
    }


@router.post("/api/storyboard/draft-batch", response_model=DraftBatchResponse)
def generate_draft_batch(req: DraftBatchRequest, agent: AgentDep) -> DraftBatchResponse:
    session_name = req.session_name or "draft_batch_session"
    tasks: list[tuple[DraftBatchShotItem, int]] = [
        (shot, var_idx) for shot in req.shots for var_idx in range(req.variations_per_shot)
    ]

    def _run_draft(item: tuple[DraftBatchShotItem, int]) -> DraftBatchItem:
        shot, var_idx = item
        directive = shot.action
        if shot.style_lighting:
            directive = f"{directive}, style: {shot.style_lighting}"
        try:
            turn = agent.process_user_turn(
                user_id="usr_default",
                project_id="prj_draft_room",
                prompt=directive,
                keyframe_image_url=shot.keyframe_image_url,
                audio_stem=shot.audio,
                resolution=req.resolution or "360p",
                aspect_ratio=req.aspect_ratio,
                clip_index=shot.shot_index,
                session_name=session_name,
            )
            return DraftBatchItem(
                shot_index=shot.shot_index,
                variation_index=var_idx,
                action=shot.action,
                resolution=req.resolution or "360p",
                status="COMPLETED" if turn.success else "FAILED",
                video_url=turn.video_url,
                gcs_uri=getattr(turn, "gcs_uri", None),
                turn_id=turn.turn_id,
                keyframe_image_url=shot.keyframe_image_url,
            )
        except Exception as exc:
            logger.error(
                "Draft batch variation failed (shot=%s, var=%s): %s",
                shot.shot_index,
                var_idx,
                exc,
            )
            return DraftBatchItem(
                shot_index=shot.shot_index,
                variation_index=var_idx,
                action=shot.action,
                resolution=req.resolution or "360p",
                status="FAILED",
                video_url=None,
                gcs_uri=None,
                turn_id=None,
                keyframe_image_url=shot.keyframe_image_url,
            )

    with ThreadPoolExecutor(max_workers=4) as executor:
        drafts = list(executor.map(_run_draft, tasks))

    return DraftBatchResponse(
        success=True,
        session_name=session_name,
        resolution=req.resolution or "360p",
        total_drafts=len(drafts),
        drafts=drafts,
    )


@router.post("/api/storyboards/save", response_model=SaveStoryboardResponse)
def save_storyboard(req: SaveStoryboardRequest, agent: AgentDep) -> SaveStoryboardResponse:
    _pub_url, gcs_uri = agent.storage.save_storyboard(
        req.name,
        req.storyboard_data,
        session_id=req.session_name,
    )
    return SaveStoryboardResponse(
        success=True,
        gcs_uri=gcs_uri,
        message=f"Storyboard saved successfully to {gcs_uri}",
    )


@router.get("/api/storyboards", response_model=StoryboardListResponse)
def list_storyboards(agent: AgentDep, session_name: str | None = None) -> StoryboardListResponse:
    raw_storyboards = agent.storage.list_storyboards(session_id=session_name)
    storyboards = [
        StoryboardMetadataModel(
            name=sb.get("name", ""),
            slug=sb.get("slug", ""),
            concept=sb.get("concept", ""),
            shot_count=sb.get("shot_count", 0),
            updated_at=sb.get("updated_at", ""),
        )
        for sb in (raw_storyboards or [])
    ]
    return StoryboardListResponse(storyboards=storyboards)


@router.post("/api/storyboards/load", response_model=dict[str, Any])
def load_storyboard(req: LoadStoryboardRequest, agent: AgentDep) -> dict[str, Any]:
    storyboard_data = agent.storage.load_storyboard(req.slug, session_id=req.session_name)
    if storyboard_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Storyboard '{req.slug}' not found",
        )
    return storyboard_data


@router.post("/api/storyboards/delete", response_model=dict[str, Any])
def delete_storyboard(req: DeleteStoryboardRequest, agent: AgentDep) -> dict[str, Any]:
    deleted = agent.storage.delete_storyboard(req.slug, session_id=req.session_name)
    message = (
        f"Storyboard '{req.slug}' deleted successfully"
        if deleted
        else f"Storyboard '{req.slug}' not found"
    )
    return {"success": deleted, "message": message}
