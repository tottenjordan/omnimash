import logging
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from omnimash.api.deps import AgentDep
from omnimash.api.helpers import (
    clean_text,
    extract_reference_urls,
    normalize_character_roles,
    stitch_and_upload_master,
)
from omnimash.api.models import (
    CharacterRoleModel,
    CommitRequest,
    ConceptDeconstructRequest,
    DeconstructedSceneModel,
    DeconstructResponse,
    ExtendSceneRequest,
    GenerateRequest,
    GenerateResponse,
    Journey3KeyframePromptEditRequest,
    Journey3SetupRequest,
    Journey3ShotGenerateRequest,
    Journey3StitchMasterRequest,
    SaveFinalRequest,
    SaveFinalResponse,
)
from omnimash.engine.omni_client import parse_guardrail_error_guidance
from omnimash.prompts.compiler import (
    CharacterRole,
    SceneDirective,
    compile_journey3_shot_prompt,
    sanitize_real_names,
)

logger = logging.getLogger(__name__)

router = APIRouter()


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
        keyframe_image_prompt=getattr(tags, "keyframe_image_prompt", ""),
        screenplay_script=getattr(tags, "screenplay_script", ""),
        scenes=[
            DeconstructedSceneModel(
                scene_number=s.scene_number,
                active_roles=list(s.active_roles),
                action=s.action,
                dialogue=s.dialogue,
                audio_cues=getattr(s, "audio_cues", ""),
                timecode=getattr(s, "timecode", "0-10s") or "0-10s",
                duration_seconds=getattr(s, "duration_seconds", 10.0),
            )
            for s in getattr(tags, "scenes", [])
        ],
    )


@router.post("/api/generate", response_model=GenerateResponse)
@router.post("/api/diff", response_model=GenerateResponse)
@router.post("/api/generate_clip", response_model=GenerateResponse)
@router.post("/api/scenes", response_model=GenerateResponse)
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


@router.post("/api/commit", response_model=GenerateResponse)
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


@router.post("/api/save-final", response_model=SaveFinalResponse)
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


@router.post("/api/extend-scene", response_model=GenerateResponse)
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


@router.post("/api/journey3/setup")
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
                enriched_image_prompt += f" | Wardrobe & Style: {' ; '.join(matched_style_strings)}"

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


@router.post("/api/journey3/keyframe", response_model=None)
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
    char_objs = normalize_character_roles(chars_to_use, sanitize=False, default_role_prefix="Role")

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


@router.post("/api/journey3/generate-shot", response_model=None)
def journey3_generate_shot(
    req: Journey3ShotGenerateRequest, agent: AgentDep
) -> dict[str, Any] | JSONResponse:
    session_id = req.session_id or "default_j3_session"

    raw_chars_input = req.characters
    if not raw_chars_input:
        try:
            manifest = agent.storage.get_session_manifest(session_id, project_id=req.project_name)
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
    char_objs = normalize_character_roles(chars_to_use, sanitize=False, default_role_prefix="Role")

    effective_action = req.action_directive or req.prompt or ""
    parent_turn_id = req.turn_id or req.previous_interaction_id
    is_stateful_edit = bool(parent_turn_id and req.prompt)

    known_char_names = [c.name for c in char_objs if c.name]
    if not is_stateful_edit:
        agent.journey3_tracker.record_shot_directive(
            session_id=session_id,
            shot_index=req.shot_index,
            action_text=req.action_directive,
            dialogue_text=req.dialogue_text,
            known_characters=known_char_names if known_char_names else None,
            project_id=req.project_name,
        )
    cum_state = agent.journey3_tracker.get_cumulative_state(session_id, project_id=req.project_name)

    keyframe_url = req.keyframe_image_url
    if not keyframe_url and req.action_directive and not is_stateful_edit:
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
            action_directive=effective_action,
            cumulative_state=cum_state,
            aspect_ratio=req.aspect_ratio,
            timeline_dialogue=req.dialogue_text,
            enable_sanitization=req.enable_safety_sanitization,
            characters=char_objs if char_objs else None,
            audio_mode=req.audio_mode,
            audio_stem=req.audio_stem,
            global_audio_beat=req.global_audio_beat,
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
            prompt=req.prompt if is_stateful_edit and req.prompt else effective_action,
            compiled_override=req.prompt if is_stateful_edit and req.prompt else compiled_prompt,
            parent_turn_id=parent_turn_id,
            is_conversational_edit=is_stateful_edit,
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
            f"{char}: {st}" for char, states in cum_state.character_states.items() for st in states
        ]
        + cum_state.scene_states,
    }


@router.post("/api/journey3/stitch")
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
