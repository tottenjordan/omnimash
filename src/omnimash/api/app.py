from contextlib import asynccontextmanager
import logging
import os
import re
import uuid
from typing import Annotated, Any
from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from omnimash.agent.adk_pipeline import deconstruct_screenplay_with_adk
from omnimash.agent.orchestrator import OmniMashAgent
from omnimash.api.deps import AgentDep
from omnimash.api.helpers import (
    clean_text,
    extract_reference_urls,
    normalize_character_roles,
    parse_shot_directive_if_needed,
    stitch_and_upload_master,
)
from omnimash.api.models import (
    CharacterListResponse,
    CharacterRoleModel,
    CommitRequest,
    ConceptDeconstructRequest,
    CreateProjectRequest,
    CreateProjectResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    DeconstructResponse,
    DeleteStoryboardRequest,
    DraftBatchItem,
    DraftBatchRequest,
    DraftBatchResponse,
    DraftBatchShotItem,
    ExtendSceneRequest,
    ExtractReferenceRequest,
    GenerateCharacterSheetRequest,
    GenerateCharacterSheetResponse,
    GenerateRequest,
    GenerateResponse,
    GenerateShotRequest,
    GenerateShotResponse,
    Journey3KeyframePromptEditRequest,
    Journey3SetupRequest,
    Journey3ShotGenerateRequest,
    Journey3StitchMasterRequest,
    KeyframeImageRequest,
    KeyframeImageResponse,
    LoadCharacterRequest,
    LoadStoryboardRequest,
    MotionReferenceRequest,
    MotionReferenceResponse,
    ProjectListResponse,
    ReferenceSheetListResponse,
    ResearchRequest,
    SaveCharacterRequest,
    SaveCharacterResponse,
    SaveCharacterSheetRequest,
    SaveCharacterSheetResponse,
    SaveFinalRequest,
    SaveFinalResponse,
    SaveRosterRequest,
    SaveStoryboardRequest,
    SaveStoryboardResponse,
    SessionListResponse,
    StitchClipsRequest,
    StitchMasterRequest,
    StoryboardExpandRequest,
    StoryboardExpandResponse,
    StoryboardListResponse,
    StoryboardMetadataModel,
    StoryboardShotModel,
)
from omnimash.engine.omni_client import parse_guardrail_error_guidance
from omnimash.ingestion.media_extractor import (
    ParodyResearchResult,
    ReferenceAnalysisReport,
)
from omnimash.prompts.compiler import (
    CharacterRole,
    SceneDirective,
    compile_journey3_shot_prompt,
    sanitize_real_names,
)

logger = logging.getLogger(__name__)

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "index.html")
_CACHED_UI_HTML: str | None = None


def get_ui_html() -> str:
    """Loads and caches the frontend SPA template."""
    global _CACHED_UI_HTML
    if _CACHED_UI_HTML is None:
        with open(_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            _CACHED_UI_HTML = f.read()
    return _CACHED_UI_HTML


UI_HTML = get_ui_html()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from omnimash.engine.omni_client import ensure_rendered_video

    ensure_rendered_video(
        "/static/rendered/mock.mp4",
        prompt="Trapwarts trailer",
    )
    yield


def create_app(mock_mode: bool | None = None) -> FastAPI:
    app = FastAPI(title="OmniMash API", version="0.1.0", lifespan=lifespan)
    is_mock = (
        mock_mode
        if mock_mode is not None
        else (os.environ.get("MOCK_MODE", "false").lower() in ("true", "1"))
    )
    agent = OmniMashAgent(mock_mode=is_mock)
    agent.session_manager.storage = agent.storage
    app.state.agent = agent

    static_dir = os.path.join(os.getcwd(), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    def get_dashboard() -> HTMLResponse:
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        return HTMLResponse(content=get_ui_html(), headers=headers)

    @app.post("/api/deconstruct-concept", response_model=DeconstructResponse)
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
                    voice_profile=c.voice_profile,
                    wardrobe=getattr(c, "wardrobe", ""),
                    image_role=getattr(c, "image_role", "Character Reference"),
                    is_offscreen_narrator=getattr(c, "is_offscreen_narrator", False),
                )
                for c in tags.characters
            ],
            aesthetic_tags=tags.aesthetic_tags,
            environment_tag=tags.environment_tag,
            camera_lighting_tag=tags.camera_lighting_tag,
            audio_beat=tags.audio_beat,
            vocal_delivery=tags.vocal_delivery,
        )

    @app.post("/api/generate", response_model=GenerateResponse)
    @app.post("/api/diff", response_model=GenerateResponse)
    @app.post("/api/generate_clip", response_model=GenerateResponse)
    @app.post("/api/scenes", response_model=GenerateResponse)
    def generate_video(req: GenerateRequest, request: Request, agent: AgentDep) -> GenerateResponse:
        is_diff_route = bool(request and request.url and request.url.path.endswith("/api/diff"))
        if is_diff_route and not req.parent_turn_id:
            return GenerateResponse(
                success=False,
                status="REJECTED",
                error="Missing parent_turn_id for conversational diff (/api/diff). Generate a base shot first.",
            )
        sanitized_prompt = (
            sanitize_real_names(req.prompt)
            if (req.prompt and req.enable_safety_sanitization)
            else (req.prompt or "")
        )
        base_action = (req.concept or req.shot_directive or "").strip()
        if not base_action and req.scenes:
            first_scene = req.scenes[0]
            if isinstance(first_scene, dict):
                base_action = str(first_scene.get("action", "")).strip()
            elif hasattr(first_scene, "action"):
                base_action = str(first_scene.action or "").strip()
        is_edit = bool(
            req.parent_turn_id
            and (
                is_diff_route
                or not (req.scenes or req.concept or req.shot_directive)
                or (req.prompt and req.prompt.strip() and req.prompt.strip() != base_action)
            )
        )
        compiled_override_val = req.compiled_override

        if req.parent_turn_id and (req.shot_directive or req.scenes):
            char_objs = normalize_character_roles(
                req.characters, sanitize=req.enable_safety_sanitization
            )
            scene_objs: list[SceneDirective] = []
            if req.scenes:
                for s in req.scenes:
                    if isinstance(s, SceneDirective):
                        scene_objs.append(s)
                    elif isinstance(s, dict):
                        sp_script = s.get("screenplay_text") or s.get("screenplay_script")
                        scene_objs.append(
                            SceneDirective(
                                scene_number=s.get("scene_number", 0),
                                active_roles=s.get("active_roles", []),
                                action=s.get("action", ""),
                                dialogue=s.get("dialogue", ""),
                                screenplay_text=sp_script if isinstance(sp_script, str) else None,
                                audio_cues=s.get("audio_cues", ""),
                                title_card_text=s.get("title_card_text"),
                                title_card_subtitle=s.get("title_card_subtitle"),
                                narrator_text=s.get("narrator_text"),
                            )
                        )
            elif req.shot_directive:
                active_roles_list = [c.role_id or c.name for c in char_objs if c.role_id or c.name]
                if not active_roles_list:
                    active_roles_list = ["Role A"]
                scene_objs.append(
                    SceneDirective(
                        scene_number=1,
                        active_roles=active_roles_list,
                        action=clean_text(req.shot_directive, req.enable_safety_sanitization),
                    )
                )

            if not compiled_override_val:
                compiled_override_val = agent.taxonomy.compiler.compile_storyboard(
                    concept=req.concept or sanitized_prompt,
                    characters=char_objs,
                    scenes=scene_objs,
                    aesthetic_tags=req.aesthetic_tags,
                    environment_tag=req.environment_tag,
                    audio_beat=req.audio_stem,
                    vocal_delivery=req.vocal_delivery,
                    edit_instruction=req.prompt if is_edit else None,
                    enable_sanitization=req.enable_safety_sanitization,
                    aspect_ratio=req.aspect_ratio,
                    last_frame_image_url=req.last_frame_image_url,
                )

        agent_turn = agent.process_user_turn(
            user_id=req.user_id,
            project_id=req.project_id,
            prompt=sanitized_prompt,
            clip_index=req.clip_index,
            parent_turn_id=req.parent_turn_id,
            is_conversational_edit=is_edit,
            reference_url=req.reference_url,
            audio_stem=req.audio_stem,
            voiceover=req.voiceover,
            is_silent=req.is_silent,
            on_screen_text=req.on_screen_text,
            compiled_override=compiled_override_val,
            session_name=req.session_name,
            concept=req.concept,
            characters=req.characters,
            scenes=req.scenes,
            aesthetic_tags=req.aesthetic_tags,
            environment_tag=req.environment_tag,
            vocal_delivery=req.vocal_delivery,
            optimize_prompt=req.optimize_prompt,
            enable_sanitization=req.enable_safety_sanitization,
            aspect_ratio=req.aspect_ratio,
            resolution=req.resolution,
        )
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

    @app.post("/api/commit", response_model=GenerateResponse)
    def commit_and_branch(req: CommitRequest, agent: AgentDep) -> GenerateResponse:
        sanitized_prompt = sanitize_real_names(req.next_prompt) if req.next_prompt else ""
        agent_turn = agent.commit_and_branch(
            user_id=req.user_id,
            project_id=req.project_id,
            turn_id=req.turn_id,
            prompt=sanitized_prompt,
            session_name=req.session_name,
        )
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

    @app.post("/api/save-final", response_model=SaveFinalResponse)
    def save_final(req: SaveFinalRequest, agent: AgentDep) -> SaveFinalResponse:
        audio = req.master_audio_path or req.master_audio_url
        if req.is_single_clip:
            pub_url, gcs_uri = agent.storage.save_final_master(
                session_id=req.session_name,
                source_rel_path=req.video_url,
                master_title=req.master_title,
            )
        else:
            pub_url, gcs_uri = agent.save_final_master(
                session_name=req.session_name,
                video_url=req.video_url,
                master_title=req.master_title,
                master_audio_path=audio,
            )
        return SaveFinalResponse(
            success=True,
            gcs_uri=gcs_uri,
            video_url=pub_url,
            message=f"Final master successfully saved to {gcs_uri}",
        )

    @app.post("/api/upload")
    async def upload_media_file(file: Annotated[UploadFile, File()], agent: AgentDep):
        """Uploads a local media file (audio MP3, WAV, image, etc.) to storage and returns accessible URL."""
        try:
            max_upload_bytes = 50 * 1024 * 1024
            content = await file.read(max_upload_bytes + 1)
            if len(content) > max_upload_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "success": False,
                        "error": "File exceeds maximum upload size of 50MB",
                    },
                )
            ext = os.path.splitext(file.filename or "file")[1] or ".bin"
            filename = f"upload_{uuid.uuid4().hex[:8]}{ext}"

            if agent.storage._bucket and not agent.storage.mock_mode:
                gcs_uri = agent.storage.upload_bytes(
                    content,
                    f"uploads/{filename}",
                    content_type=file.content_type or "application/octet-stream",
                )
                return {"success": True, "url": gcs_uri, "filename": file.filename}
            else:
                local_dir = os.path.join(os.getcwd(), "static", "uploads")
                os.makedirs(local_dir, exist_ok=True)
                local_path = os.path.join(local_dir, filename)
                with open(local_path, "wb") as f:
                    f.write(content)
                return {
                    "success": True,
                    "url": f"/static/uploads/{filename}",
                    "filename": file.filename,
                }
        except Exception as exc:
            logger.error("File upload failed: %s", exc)
            return JSONResponse(status_code=500, content={"success": False, "error": str(exc)})

    @app.post("/api/motion-reference/upload", response_model=MotionReferenceResponse)
    def upload_motion_reference(
        req: MotionReferenceRequest, agent: AgentDep
    ) -> MotionReferenceResponse:
        """Crops a 3-second motion reference clip from input_video_path starting at start_sec."""
        raw_path = (req.input_video_path or "").strip()
        if not raw_path:
            raise HTTPException(status_code=400, detail="Missing input_video_path")
        if not (
            raw_path.startswith("gs://") or raw_path.startswith("https://storage.googleapis.com/")
        ):
            import tempfile

            normalized_rel = raw_path.lstrip("/") if raw_path.startswith("/static/") else raw_path
            real_target = os.path.realpath(normalized_rel)
            allowed_roots = (
                os.path.realpath("static"),
                os.path.realpath("/tmp"),
                os.path.realpath(tempfile.gettempdir()),
            )
            if not any(
                real_target == root or real_target.startswith(root + os.sep)
                for root in allowed_roots
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid input_video_path: must reside within static/ or /tmp/ directory",
                )
        try:
            clip_path = agent.media_extractor.crop_3s_motion_reference(
                input_video_path=req.input_video_path,
                start_sec=req.start_sec,
            )
            return MotionReferenceResponse(
                success=True,
                clip_path=clip_path,
                message="Motion reference clip cropped successfully",
            )
        except Exception as exc:
            logger.error("Motion reference cropping failed: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/api/storyboard/expand", response_model=StoryboardExpandResponse)
    def expand_storyboard(req: StoryboardExpandRequest) -> StoryboardExpandResponse:
        char_objs = normalize_character_roles(req.characters, sanitize=False)
        shots = deconstruct_screenplay_with_adk(
            concept=req.concept,
            style_tone=req.style_tone,
            target_duration=req.target_duration,
            characters=char_objs if char_objs else None,
            screenplay_script=req.screenplay_script,
            mock_mode=is_mock,
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

    @app.post("/api/storyboard/keyframe-image", response_model=KeyframeImageResponse)
    def generate_keyframe_image(
        req: KeyframeImageRequest, agent: AgentDep
    ) -> KeyframeImageResponse:
        if req.image_prompt and req.image_prompt.strip():
            prompt = req.image_prompt.strip()
        else:
            prompt_parts = [p for p in [req.action, req.location] if p]
            prompt = (
                ", ".join(prompt_parts)
                if prompt_parts
                else (req.summary or f"Shot {req.shot_index}")
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

    @app.post("/api/generate-shot", response_model=GenerateShotResponse)
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

        char_objs = normalize_character_roles(
            req.characters, sanitize=req.enable_safety_sanitization
        )
        ref_urls = extract_reference_urls(req.characters)

        if req.last_frame_image_url and req.last_frame_image_url.strip():
            has_last = any(
                c.image_role in ("Ending Frame", "Keyframe Last Anchor") for c in char_objs
            )
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
            t
            for t in [style_lighting_val or req.style_lighting, framing_motion_val]
            if t and t.strip()
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

    @app.post("/api/stitch-clips", response_model=SaveFinalResponse)
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

    @app.post("/api/storyboard/stitch_master")
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

    @app.post("/api/journey3/setup")
    def journey3_setup(req: Journey3SetupRequest, agent: AgentDep) -> dict[str, Any]:
        char_objs = normalize_character_roles(req.characters, sanitize=False)
        style_tone = req.style_presets[0] if req.style_presets else "Cinematic Trap Parody"
        shots = agent.storyboard_agent.expand_vision(
            concept=req.master_description,
            style_tone=style_tone,
            target_duration=30.0,
            characters=char_objs if char_objs else None,
        )

        def _is_char_in_text(c: CharacterRole, text: str) -> bool:
            if not text or not text.strip():
                return False
            t_lower = text.lower()
            role = (c.role_id or "").strip().lower()
            if role and role in t_lower:
                return True
            name = (c.name or "").strip().lower()
            if name:
                if name in t_lower:
                    return True
                stop_words = {
                    "the",
                    "and",
                    "fam",
                    "bruv",
                    "chef",
                    "blood",
                    "star",
                    "queen",
                    "king",
                    "master",
                }
                words = [w for w in re.split(r"\W+", name) if len(w) >= 3 and w not in stop_words]
                for w in words:
                    if w in t_lower:
                        return True
            return False

        shot_cards = []
        for s in shots:
            enriched_image_prompt = s.action
            matched_char_ids: list[str] = []
            if char_objs:
                matched_style_strings: list[str] = []
                combined_shot_text = (
                    f"{s.action} {getattr(s, 'dialogue', '')} {getattr(s, 'summary', '')}"
                )
                for c in char_objs:
                    if _is_char_in_text(c, combined_shot_text):
                        matched_char_ids.append(c.role_id)
                        if not c.reference_url or not c.reference_url.strip():
                            tags = []
                            if getattr(c, "wardrobe", ""):
                                tags.append(c.wardrobe.strip())
                            if getattr(c, "aesthetic_tags", None):
                                tags.extend(c.aesthetic_tags)

                            if tags:
                                matched_style_strings.append(
                                    f"{c.name or c.role_id} ({', '.join(tags)})"
                                )

                if matched_style_strings:
                    enriched_image_prompt += (
                        f" | Wardrobe & Style: {' ; '.join(matched_style_strings)}"
                    )

            card = {
                "shot_index": s.shot_index,
                "action_directive": s.action,
                "image_prompt": enriched_image_prompt,
                "duration_seconds": s.duration_seconds,
                "location": s.location,
                "style_lighting": s.style_lighting,
                "framing_motion": s.framing_motion,
                "audio": s.audio,
                "dialogue": getattr(s, "dialogue", ""),
                "summary": getattr(s, "summary", ""),
                "keyframe_image_url": getattr(s, "keyframe_image_url", ""),
                "included_character_ids": matched_char_ids
                if matched_char_ids
                else ([char_objs[0].role_id] if char_objs else []),
            }
            shot_cards.append(card)

        project_id = req.project_id or req.project_name or "default_project"
        session_id = req.session_id or "parody_session_1"
        style_preset = req.style_preset or (
            req.style_presets[0] if req.style_presets else "Gritty 90s Cyberpunk"
        )
        raw_image_model = (req.image_model or "").strip()
        image_model = (
            "gemini-nano-banana-2.1"
            if not raw_image_model or raw_image_model.startswith("gemini-3.1-flash-image")
            else raw_image_model
        )
        aspect_ratio = req.aspect_ratio or "16:9"
        enable_safety = req.enable_safety_sanitization

        session_obj = agent.session_manager.get_or_create_session(
            "usr_default", project_id, session_name=session_id
        )
        session_obj.master_description = req.master_description
        session_obj.style_preset = style_preset
        session_obj.aspect_ratio = aspect_ratio
        session_obj.image_model = image_model
        session_obj.enable_safety_sanitization = enable_safety
        session_obj.characters = req.characters or []
        session_obj.products = req.products or []
        session_obj.shot_cards = shot_cards

        session_dump = session_obj.model_dump()
        manifest_data = {
            **session_dump,
            "project_id": project_id,
            "session_id": session_id,
            "master_description": req.master_description,
            "style_preset": style_preset,
            "aspect_ratio": aspect_ratio,
            "image_model": image_model,
            "enable_safety_sanitization": enable_safety,
            "characters": req.characters or [],
            "products": req.products or [],
            "shot_cards": shot_cards,
        }

        manifest_url = agent.storage.save_session_manifest(
            session_id=session_id,
            manifest_data=manifest_data,
            project_id=project_id,
        )

        return {
            "success": True,
            "master_description": req.master_description,
            "aspect_ratio": aspect_ratio,
            "style_preset": style_preset,
            "image_model": image_model,
            "enable_safety_sanitization": enable_safety,
            "manifest_url": manifest_url,
            "shot_cards": shot_cards,
            "shots": shot_cards,
            "characters": req.characters or [],
        }

    @app.post("/api/journey3/keyframe", response_model=None)
    def journey3_keyframe(
        req: Journey3KeyframePromptEditRequest, agent: AgentDep
    ) -> dict[str, Any] | JSONResponse:
        chars_to_use = req.characters
        if req.characters and req.included_character_ids is not None:
            filtered_chars = [
                c
                for c in req.characters
                if (c.get("role_id") if isinstance(c, dict) else getattr(c, "role_id", ""))
                in req.included_character_ids
            ]
            if filtered_chars:
                chars_to_use = filtered_chars
        char_objs = normalize_character_roles(
            chars_to_use, sanitize=False, default_role_prefix="Role"
        )

        ref_urls = req.reference_image_urls
        if ref_urls and req.characters and char_objs:
            included_ref_urls = {c.reference_url for c in char_objs if c.reference_url}
            all_char_ref_urls = set(extract_reference_urls(req.characters))
            excluded_char_ref_urls = all_char_ref_urls - included_ref_urls
            if excluded_char_ref_urls:
                ref_urls = [u for u in ref_urls if u not in excluded_char_ref_urls]

        raw_kf_model = (req.image_model or "").strip()
        effective_kf_model = (
            "gemini-nano-banana-2.1"
            if not raw_kf_model or raw_kf_model.startswith("gemini-3.1-flash-image")
            else raw_kf_model
        )
        try:
            image_url, compiled_prompt = agent.omni_client.generate_keyframe_image(
                req.image_prompt,
                style_tone=req.style_preset or "",
                reference_image_urls=ref_urls,
                characters=char_objs if char_objs else None,
                aspect_ratio=req.aspect_ratio,
                image_model=effective_kf_model,
                return_compiled_prompt=True,
            )
            return {
                "success": True,
                "session_id": req.session_id,
                "shot_index": req.shot_index,
                "image_prompt": req.image_prompt,
                "keyframe_image_url": image_url,
                "raw_compiled_prompt": compiled_prompt,
            }
        except Exception as exc:
            err_str = str(exc)
            logger.error("Error generating keyframe in journey3_keyframe: %s", exc)
            guardrail_guidance = parse_guardrail_error_guidance(
                err_str, char_objs, req.image_prompt or ""
            )
            return JSONResponse(
                status_code=400,
                content={
                    "detail": err_str,
                    "error": err_str,
                    "guardrail_guidance": guardrail_guidance,
                },
            )

    @app.post("/api/journey3/generate-shot", response_model=None)
    def journey3_generate_shot(
        req: Journey3ShotGenerateRequest, agent: AgentDep
    ) -> dict[str, Any] | JSONResponse:
        session_id = req.session_id or "default_j3_session"

        raw_chars_input = req.characters
        if not raw_chars_input:
            try:
                manifest = agent.storage.get_session_manifest(
                    session_id, project_id=req.project_name
                )
                if isinstance(manifest, dict) and manifest.get("characters"):
                    raw_chars_input = manifest["characters"]
                else:
                    roster = agent.storage.load_session_roster(session_id)
                    if roster:
                        raw_chars_input = roster
            except Exception:
                pass

        chars_to_use = raw_chars_input
        if raw_chars_input and req.included_character_ids is not None:
            filtered_chars = [
                c
                for c in raw_chars_input
                if (c.get("role_id") if isinstance(c, dict) else getattr(c, "role_id", ""))
                in req.included_character_ids
            ]
            if filtered_chars:
                chars_to_use = filtered_chars
        char_objs = normalize_character_roles(
            chars_to_use, sanitize=False, default_role_prefix="Role"
        )

        known_char_names = [c.name for c in char_objs if c.name]
        agent.journey3_tracker.record_shot_directive(
            session_id=session_id,
            shot_index=req.shot_index,
            action_text=req.action_directive,
            dialogue_text=req.dialogue_text,
            known_characters=known_char_names if known_char_names else None,
            project_id=req.project_name,
        )
        cum_state = agent.journey3_tracker.get_cumulative_state(
            session_id, project_id=req.project_name
        )

        keyframe_url = req.keyframe_image_url
        if not keyframe_url and req.action_directive:
            try:
                keyframe_url = agent.omni_client.generate_keyframe_image(
                    req.action_directive,
                    aspect_ratio=req.aspect_ratio,
                    characters=char_objs if char_objs else None,
                )
            except Exception as exc:
                logger.warning(
                    "Keyframe image generation failed in journey3_generate_shot: %s",
                    exc,
                )

        if req.compiled_override:
            compiled_prompt = req.compiled_override
            if keyframe_url and "<FIRST_FRAME>@KeyframeSeed" not in compiled_prompt:
                seed_tags = "<FIRST_FRAME>@KeyframeSeed"
                if req.is_seamless_loop and "<LAST_FRAME>@KeyframeSeed" not in compiled_prompt:
                    seed_tags += " <LAST_FRAME>@KeyframeSeed"
                if "[# Sources" in compiled_prompt:
                    compiled_prompt = compiled_prompt.replace(
                        "[# Sources", f"[# Sources {seed_tags}", 1
                    )
                else:
                    compiled_prompt = f"[# Sources {seed_tags}]\n{compiled_prompt}"
        else:
            compiled_prompt = compile_journey3_shot_prompt(
                shot_number=req.shot_index,
                action_directive=req.action_directive,
                cumulative_state=cum_state,
                aspect_ratio=req.aspect_ratio,
                timeline_dialogue=req.dialogue_text,
                enable_sanitization=req.enable_safety_sanitization,
                characters=char_objs if char_objs else None,
                title_card_text=req.title_card_text,
                title_card_subtitle=req.title_card_subtitle,
                narrator_text=req.narrator_text,
                narrator_voice=req.narrator_voice,
                style_preset=req.style_preset or req.model_style,
                last_frame_image_url=req.last_frame_image_url,
                keyframe_image_url=keyframe_url,
                is_seamless_loop=req.is_seamless_loop,
            )

        try:
            agent_turn = agent.process_user_turn(
                user_id="usr_default",
                project_id=req.project_name or "prj_default",
                prompt=req.action_directive,
                compiled_override=compiled_prompt,
                clip_index=req.shot_index,
                session_name=session_id,
                characters=char_objs if char_objs else None,
                keyframe_image_url=keyframe_url,
                voiceover=req.dialogue_text if req.dialogue_text else None,
                enable_sanitization=req.enable_safety_sanitization,
                aspect_ratio=req.aspect_ratio,
                resolution=req.resolution,
                motion_reference_clip=req.motion_reference_clip,
            )
        except Exception as exc:
            err_str = str(exc)
            logger.error("Error generating shot in journey3_generate_shot: %s", exc)
            guardrail_guidance = parse_guardrail_error_guidance(
                err_str, char_objs, compiled_prompt or req.action_directive or ""
            )
            return JSONResponse(
                status_code=400,
                content={
                    "detail": err_str,
                    "error": err_str,
                    "guardrail_guidance": guardrail_guidance,
                    "session_id": session_id,
                    "shot_index": req.shot_index,
                },
            )

        if not agent_turn.success:
            err_str = agent_turn.error_message or "Shot generation failed"
            guardrail_guidance = parse_guardrail_error_guidance(
                err_str, char_objs, compiled_prompt or req.action_directive or ""
            )
            return JSONResponse(
                status_code=400,
                content={
                    "detail": err_str,
                    "error": err_str,
                    "guardrail_guidance": guardrail_guidance,
                    "session_id": session_id,
                    "shot_index": req.shot_index,
                },
            )

        return {
            "success": agent_turn.success,
            "session_id": session_id,
            "shot_index": req.shot_index,
            "video_url": agent_turn.video_url,
            "keyframe_image_url": keyframe_url,
            "turn_id": agent_turn.turn_id,
            "status": agent_turn.status_event,
            "generation_mode": getattr(agent_turn, "generation_mode", "LIVE_OMNI_FLASH"),
            "error": agent_turn.error_message,
            "raw_compiled_prompt": agent_turn.raw_compiled_prompt or compiled_prompt,
            "cumulative_state": [
                f"{char}: {st}"
                for char, states in cum_state.character_states.items()
                for st in states
            ]
            + cum_state.scene_states,
        }

    @app.post("/api/journey3/stitch")
    def journey3_stitch(req: Journey3StitchMasterRequest, agent: AgentDep) -> dict[str, Any]:
        master_path, master_url = stitch_and_upload_master(
            agent=agent,
            shot_clips=req.shot_clips,
            title_cards=req.title_cards,
            session_id=req.session_id,
            aspect_ratio=req.aspect_ratio,
        )
        return {
            "status": "ok",
            "success": True,
            "session_id": req.session_id,
            "master_video_path": master_path,
            "master_video_url": master_url,
        }

    @app.post("/api/storyboard/draft-batch", response_model=DraftBatchResponse)
    def generate_draft_batch(req: DraftBatchRequest, agent: AgentDep) -> DraftBatchResponse:
        from concurrent.futures import ThreadPoolExecutor

        session_name = req.session_name or "draft_batch_session"
        tasks: list[tuple[DraftBatchShotItem, int]] = [
            (shot, var_idx) for shot in req.shots for var_idx in range(req.variations_per_shot)
        ]

        def _run_draft(item: tuple[DraftBatchShotItem, int]) -> DraftBatchItem:
            shot, var_idx = item
            directive = shot.action
            if shot.style_lighting:
                directive = f"{directive}, style: {shot.style_lighting}"
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

        with ThreadPoolExecutor(max_workers=4) as executor:
            drafts = list(executor.map(_run_draft, tasks))

        return DraftBatchResponse(
            success=True,
            session_name=session_name,
            resolution=req.resolution or "360p",
            total_drafts=len(drafts),
            drafts=drafts,
        )

    @app.post("/api/extend-scene", response_model=GenerateResponse)
    def extend_scene(req: ExtendSceneRequest, agent: AgentDep) -> GenerateResponse:
        agent_turn = agent.extend_scene(
            session_name=req.session_name,
            turn_id=req.turn_id or req.previous_interaction_id,
            next_scene_action=req.next_scene_action,
            dialogue=req.dialogue,
            active_roles=req.active_roles,
            vocal_delivery=req.vocal_delivery,
            resolution=req.resolution,
        )
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

    @app.post("/api/research", response_model=ParodyResearchResult)
    def research_parody(req: ResearchRequest, agent: AgentDep) -> ParodyResearchResult:
        return agent.media_extractor.research_parody_clash(req.subject, req.aesthetic)

    @app.post("/api/extract-reference", response_model=ReferenceAnalysisReport)
    def extract_reference(req: ExtractReferenceRequest, agent: AgentDep) -> ReferenceAnalysisReport:
        return agent.media_extractor.analyze_youtube_reference(
            req.url, session_id=req.session_name or "default"
        )

    @app.post("/api/characters/save", response_model=SaveCharacterResponse)
    def save_character(req: SaveCharacterRequest, agent: AgentDep) -> SaveCharacterResponse:
        _pub_url, gcs_uri = agent.storage.save_character(
            req.character.model_dump(),
            session_id=req.session_name,
            project_id=req.project_name or "default_project",
            is_library=req.is_library,
        )
        return SaveCharacterResponse(
            success=True,
            gcs_uri=gcs_uri,
            message=f"Character saved successfully to {gcs_uri}",
        )

    @app.get("/api/characters", response_model=CharacterListResponse)
    def list_characters(agent: AgentDep, session_name: str | None = None) -> CharacterListResponse:
        raw_chars = agent.storage.list_characters(session_id=session_name)
        characters = [CharacterRoleModel.from_storage_dict(c) for c in (raw_chars or [])]
        return CharacterListResponse(characters=characters)

    @app.get("/api/projects", response_model=ProjectListResponse)
    def list_projects(agent: AgentDep) -> ProjectListResponse:
        return ProjectListResponse(projects=agent.storage.list_projects())

    @app.post("/api/projects/create", response_model=CreateProjectResponse)
    def create_project(req: CreateProjectRequest, agent: AgentDep) -> CreateProjectResponse:
        gcs_uri = agent.storage.create_project(req.project_name)
        return CreateProjectResponse(
            success=True,
            project_name=req.project_name,
            gcs_uri=gcs_uri,
            message=f"Project '{req.project_name}' created successfully",
        )

    @app.get("/api/projects/{project_name}/sessions", response_model=SessionListResponse)
    def list_project_sessions(project_name: str, agent: AgentDep) -> SessionListResponse:
        return SessionListResponse(sessions=agent.storage.list_sessions(project_name))

    @app.post(
        "/api/projects/{project_name}/sessions/create",
        response_model=CreateSessionResponse,
    )
    def create_project_session(
        project_name: str, req: CreateSessionRequest, agent: AgentDep
    ) -> CreateSessionResponse:
        gcs_uri = agent.storage.create_session(req.session_name, project_id=project_name)
        return CreateSessionResponse(
            success=True,
            project_name=project_name,
            session_name=req.session_name,
            gcs_uri=gcs_uri,
            message=f"Session '{req.session_name}' created under project '{project_name}'",
        )

    @app.get("/api/projects/{project_name}/characters", response_model=CharacterListResponse)
    def list_project_characters(project_name: str, agent: AgentDep) -> CharacterListResponse:
        raw_chars = agent.storage.list_project_characters(project_name)
        characters = [CharacterRoleModel.from_storage_dict(c) for c in (raw_chars or [])]
        return CharacterListResponse(characters=characters)

    @app.get(
        "/api/projects/{project_name}/reference-sheets",
        response_model=ReferenceSheetListResponse,
    )
    def list_project_reference_sheets(
        project_name: str, agent: AgentDep
    ) -> ReferenceSheetListResponse:
        sheets = agent.storage.list_project_reference_sheets(project_name)
        return ReferenceSheetListResponse(reference_sheets=sheets or [])

    @app.get("/api/sessions", response_model=SessionListResponse)
    def list_sessions(agent: AgentDep) -> SessionListResponse:
        return SessionListResponse(sessions=agent.storage.list_session_ids())

    @app.post("/api/characters/load", response_model=CharacterRoleModel)
    def load_character(req: LoadCharacterRequest, agent: AgentDep) -> CharacterRoleModel:
        char_data = agent.storage.load_character(req.slug, session_id=req.session_name)
        if not char_data:
            raise HTTPException(
                status_code=404,
                detail=f"Character '{req.slug}' not found",
            )
        return CharacterRoleModel.from_storage_dict(char_data)

    @app.post("/api/characters/save-roster", response_model=SaveCharacterResponse)
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

    @app.get("/api/characters/roster", response_model=CharacterListResponse)
    def get_session_roster(session_name: str, agent: AgentDep) -> CharacterListResponse:
        raw_roster = agent.storage.load_session_roster(session_name)
        characters = [CharacterRoleModel.from_storage_dict(c) for c in (raw_roster or [])]
        return CharacterListResponse(characters=characters)

    @app.post("/api/storyboards/save", response_model=SaveStoryboardResponse)
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

    @app.get("/api/storyboards", response_model=StoryboardListResponse)
    def list_storyboards(
        agent: AgentDep, session_name: str | None = None
    ) -> StoryboardListResponse:
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

    @app.post("/api/storyboards/load", response_model=dict[str, Any])
    def load_storyboard(req: LoadStoryboardRequest, agent: AgentDep) -> dict[str, Any]:
        storyboard_data = agent.storage.load_storyboard(req.slug, session_id=req.session_name)
        if storyboard_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Storyboard '{req.slug}' not found",
            )
        return storyboard_data

    @app.post("/api/storyboards/delete", response_model=dict[str, Any])
    def delete_storyboard(req: DeleteStoryboardRequest, agent: AgentDep) -> dict[str, Any]:
        deleted = agent.storage.delete_storyboard(req.slug, session_id=req.session_name)
        message = (
            f"Storyboard '{req.slug}' deleted successfully"
            if deleted
            else f"Storyboard '{req.slug}' not found"
        )
        return {"success": deleted, "message": message}

    @app.get("/api/media-proxy")
    def media_proxy(uri: str, request: Request, agent: AgentDep) -> Response:
        if not uri:
            raise HTTPException(status_code=400, detail="Missing URI parameter")

        if uri.startswith("https://storage.googleapis.com/"):
            parts = uri.replace("https://storage.googleapis.com/", "").split("/", 1)
            if len(parts) == 2:
                uri = f"gs://{parts[0]}/{parts[1]}"
        elif uri.startswith("https://storage.cloud.google.com/"):
            parts = uri.replace("https://storage.cloud.google.com/", "").split("/", 1)
            if len(parts) == 2:
                uri = f"gs://{parts[0]}/{parts[1]}"

        if not uri.startswith("gs://"):
            raise HTTPException(
                status_code=400,
                detail="Invalid GCS URI. Must start with gs:// or https://storage.googleapis.com/",
            )
        gcs_path = uri[5:]
        if "/" in gcs_path:
            from omnimash.config import settings

            req_bucket = gcs_path.split("/", 1)[0]
            allowed_buckets = {
                agent.storage.bucket_name,
                settings.gcs_bucket_name,
                "reference-images-jt-trend-trawler",
                "omnimash-media-hybrid-vertex",
                "test-omnimash-bucket",
                "bucket",
            }
            if req_bucket not in allowed_buckets:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access to GCS bucket '{req_bucket}' is not permitted",
                )
        data, content_type = agent.storage.download_blob_bytes(uri)
        if not data:
            raise HTTPException(
                status_code=404,
                detail="Media object not found or empty",
            )
        total_len = len(data)
        range_header = (
            request.headers.get("range") if request and hasattr(request, "headers") else None
        )
        if range_header and range_header.strip().lower().startswith("bytes="):
            range_spec = range_header.strip()[6:].split(",")[0].strip()
            if "-" in range_spec:
                start_str, end_str = range_spec.split("-", 1)
                try:
                    if start_str == "":
                        suffix_len = int(end_str)
                        start = max(0, total_len - suffix_len)
                        end = total_len - 1
                    else:
                        start = int(start_str)
                        end = int(end_str) if end_str else total_len - 1
                    if 0 <= start <= end < total_len:
                        chunk = data[start : end + 1]
                        return Response(
                            content=chunk,
                            status_code=206,
                            media_type=content_type,
                            headers={
                                "Cache-Control": "public, max-age=86400",
                                "Accept-Ranges": "bytes",
                                "Content-Range": f"bytes {start}-{end}/{total_len}",
                                "Content-Length": str(len(chunk)),
                            },
                        )
                except ValueError:
                    pass
        return Response(
            content=data,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Accept-Ranges": "bytes",
                "Content-Length": str(total_len),
            },
        )

    @app.post(
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

    @app.post("/api/characters/save-sheet", response_model=SaveCharacterSheetResponse)
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

    return app


_default_app: FastAPI | None = None


def __getattr__(name: str) -> Any:
    global _default_app
    if name == "app":
        if _default_app is None:
            _default_app = create_app()
        return _default_app
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
