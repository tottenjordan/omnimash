from concurrent.futures import ThreadPoolExecutor
import logging
import os
import tempfile
from typing import Any
from urllib.parse import quote_plus
import uuid

from fastapi import APIRouter, HTTPException

from omnimash.agent.adk_pipeline import deconstruct_screenplay_with_adk
from omnimash.agent.soundstage_store import (
    _unwrap_media_proxy_uri,
    _validate_bucket_and_object_path,
)
from omnimash.api.deps import AgentDep
from omnimash.config import settings
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
from omnimash.api.routers.projects import validate_safe_identifier
from omnimash.api.v2_models import (
    Gate1BatchRequest,
    Gate1BatchResponse,
    Master3StemRequest,
    Master3StemResponse,
    ShotPairPlanRequest,
    ShotPairPlanResponse,
)
from omnimash.audio import (
    CANONICAL_TRAILER_NARRATOR_VOICE_ID,
    AudioGuillotineWindow,
    GeminiTTSClient,
    LyriaClient,
    ThreeStemMasteringEngine,
    resolve_sonic_mix_preset_defaults,
    snap_timestamp_to_bpm_grid,
    synthesize_tuned_808_wav,
)
from omnimash.engine.keyframe_client import KeyframeClient
from omnimash.engine.multimodal import _is_placeholder_image_url
from omnimash.prompts.compiler import CharacterRole, SceneDirective, sanitize_real_names
from omnimash.prompts.preflight_linter import PreFlightGatekeeper
from omnimash.prompts.shot_pair_planner import build_two_shot_hard_cut_plan

logger = logging.getLogger(__name__)

router = APIRouter()


def _screen_prompt_fields(agent: AgentDep, *values: str | None) -> None:
    """Screens user-supplied text fields via Model Armor guardrail."""
    guardrail = getattr(agent, "guardrail", None)
    if guardrail is None:
        return
    for text in values:
        if not text or not text.strip():
            continue
        verdict = guardrail.validate_prompt(text)
        if not verdict.is_approved:
            reason = verdict.rejection_reason or "Blocked by Model Armor security guardrail."
            raise HTTPException(status_code=403, detail=reason)


def _resolve_confined_master_video_path(
    raw_video_path: str,
    *,
    temp_dir: str,
    agent: AgentDep,
) -> str:
    """Confines source video to /static/ or validated gs:// / /api/media-proxy GCS blobs downloaded to temp_dir."""
    cleaned = (raw_video_path or "").strip()
    if ".." in cleaned or "\x00" in cleaned:
        raise HTTPException(
            status_code=400,
            detail="Invalid video_path: path traversal sequences are not permitted.",
        )

    try:
        unwrapped = _unwrap_media_proxy_uri(cleaned, max_hops=3)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if ".." in unwrapped or "\x00" in unwrapped:
        raise HTTPException(
            status_code=400,
            detail="Invalid video_path: path traversal sequences are not permitted.",
        )

    if unwrapped.startswith("https://storage.googleapis.com/"):
        parts = unwrapped.replace("https://storage.googleapis.com/", "", 1).split("/", 1)
        if len(parts) == 2:
            unwrapped = f"gs://{parts[0]}/{parts[1]}"
    elif unwrapped.startswith("https://storage.cloud.google.com/"):
        parts = unwrapped.replace("https://storage.cloud.google.com/", "", 1).split("/", 1)
        if len(parts) == 2:
            unwrapped = f"gs://{parts[0]}/{parts[1]}"

    if unwrapped.startswith("gs://"):
        rest = unwrapped[5:]
        if "/" not in rest:
            raise HTTPException(
                status_code=400,
                detail="Invalid GCS URI: expected gs://<bucket>/<object>.",
            )
        req_bucket, obj_path = rest.split("/", 1)
        try:
            _validate_bucket_and_object_path(req_bucket, obj_path, "video_path")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        allowed_buckets = {
            b
            for b in (
                getattr(agent.storage, "bucket_name", None),
                getattr(settings, "gcs_bucket_name", None),
                "reference-images-jt-trend-trawler",
                "omnimash-media-hybrid-vertex",
                "test-omnimash-bucket",
                "bucket",
            )
            if b
        }
        if req_bucket not in allowed_buckets:
            raise HTTPException(
                status_code=403,
                detail=f"Access to GCS bucket '{req_bucket}' is not permitted",
            )

        if agent.mock_mode:
            mock_input = os.path.join(temp_dir, "mock_source.mp4")
            with open(mock_input, "wb") as f:
                f.write(b"mock_source_mp4")
            return mock_input

        data, _ = agent.storage.download_blob_bytes(unwrapped)
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"Source media not found or empty: {unwrapped}",
            )
        local_src = os.path.join(temp_dir, f"src_{uuid.uuid4().hex[:8]}.mp4")
        with open(local_src, "wb") as f:
            f.write(data)
        return local_src

    if unwrapped.startswith("/static/") and "\\" not in unwrapped:
        rel = unwrapped.lstrip("/")
        candidate = os.path.realpath(os.path.join(os.getcwd(), rel))
        static_root = os.path.realpath(os.path.join(os.getcwd(), "static"))
        if candidate.startswith(static_root + os.sep) and os.path.isfile(candidate):
            return candidate
        if agent.mock_mode:
            mock_input = os.path.join(temp_dir, "mock_source.mp4")
            with open(mock_input, "wb") as f:
                f.write(b"mock_source_mp4")
            return mock_input
        raise HTTPException(
            status_code=404,
            detail="Source static video file not found.",
        )

    raise HTTPException(
        status_code=400,
        detail="Source video_path must reference a confined /static/ file, gs:// URI, or /api/media-proxy URL.",
    )


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
        camera_lighting=req.camera_lighting,
        aesthetic_tags=req.aesthetic_tags,
        audio_beat=req.audio_beat,
        vocal_delivery=req.vocal_delivery,
        environment=req.environment,
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


@router.post("/api/storyboard/gate1-batch", response_model=Gate1BatchResponse)
def generate_gate1_batch(req: Gate1BatchRequest, agent: AgentDep) -> Gate1BatchResponse:
    safe_session = (
        validate_safe_identifier(req.session_name, "session_name")
        if req.session_name and req.session_name.strip()
        else None
    )
    safe_shot_label = validate_safe_identifier(req.shot_label, "shot_label")
    _screen_prompt_fields(agent, req.prompt, req.style_tone, req.wardrobe, req.style_preset)

    ref_urls: list[str] = list(req.reference_image_urls or [])
    for ref in extract_reference_urls(req.characters):
        if ref not in ref_urls:
            ref_urls.append(ref)

    kf_client = getattr(agent.omni_client, "_keyframe_client", None)
    if not isinstance(kf_client, KeyframeClient):
        kf_client = KeyframeClient(mock_mode=agent.mock_mode, storage=agent.storage)

    batch = kf_client.generate_gate1_candidate_batch(
        prompt=req.prompt or "Cinematic establishing keyframe",
        shot_label=safe_shot_label,
        style_tone=req.style_tone,
        reference_image_urls=ref_urls or None,
        characters=req.characters,
        style_preset=req.style_preset,
        wardrobe=req.wardrobe,
        anchor_keyframe_url=req.anchor_keyframe_url,
        aspect_ratio=req.aspect_ratio,
        image_model=req.image_model,
        image_size=req.image_size,
        base_seed=req.base_seed,
        num_candidates=req.num_candidates,
        session_id=safe_session,
    )
    return Gate1BatchResponse(success=True, **batch.model_dump())


@router.post("/api/storyboard/shot-pair-plan", response_model=ShotPairPlanResponse)
def plan_shot_pair(req: ShotPairPlanRequest, agent: AgentDep) -> ShotPairPlanResponse:
    if req.session_name and req.session_name.strip():
        validate_safe_identifier(req.session_name, "session_name")
    safe_scene_id = validate_safe_identifier(req.scene_id, "scene_id")
    _screen_prompt_fields(
        agent,
        req.character_name,
        req.speaker_descriptor,
        req.voice_style,
        req.fixed_character_block,
        req.wetness_lighting_block,
        req.matched_location_block,
        req.wide_action_summary,
        req.mcu_spoken_line,
        req.narrator_text,
        req.ambient_noise,
    )

    plan = build_two_shot_hard_cut_plan(
        scene_id=safe_scene_id,
        character_name=req.character_name,
        speaker_descriptor=req.speaker_descriptor or req.character_name,
        voice_style=req.voice_style,
        fixed_character_block=req.fixed_character_block,
        wetness_lighting_block=req.wetness_lighting_block,
        matched_location_block=req.matched_location_block,
        wide_action_summary=req.wide_action_summary,
        mcu_spoken_line=req.mcu_spoken_line,
        narrator_text=req.narrator_text,
        ambient_noise=req.ambient_noise,
        root_note_808=req.root_note_808,
    )
    shot_a_i2v = PreFlightGatekeeper.lint_and_repair(
        plan.shot_a_i2v_spec.compile(),
        has_dialogue=False,
        shot_seconds=float(plan.shot_a_render_duration_sec),
        strip_offscreen_narrator=True,
    ).repaired_prompt
    shot_b_i2v = PreFlightGatekeeper.lint_and_repair(
        plan.shot_b_i2v_spec.compile(),
        has_dialogue=bool(req.mcu_spoken_line.strip()),
        shot_seconds=float(plan.shot_b_render_duration_sec),
        strip_offscreen_narrator=True,
    ).repaired_prompt

    return ShotPairPlanResponse(
        success=True,
        plan=plan,
        shot_a_keyframe_prompt=plan.shot_a_keyframe_spec.compile(),
        shot_b_keyframe_prompt=plan.shot_b_keyframe_spec.compile(),
        shot_a_i2v_prompt=shot_a_i2v,
        shot_b_i2v_prompt=shot_b_i2v,
    )


@router.post("/api/storyboard/master-3stem", response_model=Master3StemResponse)
def master_3stem_audio(req: Master3StemRequest, agent: AgentDep) -> Master3StemResponse:
    safe_session = validate_safe_identifier(
        req.session_name if req.session_name is not None else "master_3stem_session",
        "session_name",
    )
    _screen_prompt_fields(agent, req.narrator_text, req.narrator_style, req.lyria_prompt)

    try:
        preset_cfg = resolve_sonic_mix_preset_defaults(req.preset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    enable_808 = (
        req.enable_808_drops if req.enable_808_drops is not None else preset_cfg.enable_808_drops
    )
    apply_baritone_dsp = (
        req.apply_narrator_baritone_dsp
        if req.apply_narrator_baritone_dsp is not None
        else preset_cfg.apply_narrator_baritone_dsp
    )
    narrator_delay = (
        req.narrator_delay_sec
        if req.narrator_delay_sec is not None
        else preset_cfg.narrator_delay_sec
    )

    guillotine: AudioGuillotineWindow | None = None
    if preset_cfg.enable_guillotine or (
        req.guillotine_start_sec is not None and req.guillotine_end_sec is not None
    ):
        g_start = req.guillotine_start_sec if req.guillotine_start_sec is not None else 5.50
        g_end = (
            req.guillotine_end_sec
            if req.guillotine_end_sec is not None
            else max(g_start + 0.5, 9.75)
        )
        if g_end <= g_start:
            raise HTTPException(
                status_code=400,
                detail="guillotine_end_sec must be strictly greater than guillotine_start_sec.",
            )
        g_atten = (
            req.guillotine_attenuation_linear
            if req.guillotine_attenuation_linear is not None
            else preset_cfg.guillotine_attenuation_linear
        )
        guillotine = AudioGuillotineWindow(
            start_sec=g_start,
            end_sec=g_end,
            attenuation_linear=g_atten,
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        src_video = _resolve_confined_master_video_path(
            req.video_path,
            temp_dir=tmp_dir,
            agent=agent,
        )

        narrator_wav_path: str | None = None
        narrator_duration_sec: float | None = None
        if req.narrator_text and req.narrator_text.strip():
            tts_client = GeminiTTSClient(mock_mode=agent.mock_mode)
            narrator_wav_path = os.path.join(tmp_dir, "narrator_stem.wav")
            tts_res = tts_client.synthesize_narrator_stem(
                text=req.narrator_text,
                output_path=narrator_wav_path,
                voice_name=req.narrator_voice or CANONICAL_TRAILER_NARRATOR_VOICE_ID,
                style=req.narrator_style,
                target_window_sec=req.narrator_target_window_sec,
                apply_baritone_dsp=apply_baritone_dsp,
            )
            narrator_duration_sec = tts_res.duration_seconds

        lyria_score_path: str | None = None
        lyria_model_id: str | None = None
        if req.lyria_prompt and req.lyria_prompt.strip():
            lyria_client = LyriaClient(mock_mode=agent.mock_mode)
            lyria_score_path = os.path.join(tmp_dir, "lyria_score.wav")
            lyria_res = lyria_client.generate_score(
                prompt=req.lyria_prompt,
                output_path=lyria_score_path,
                duration_sec=req.lyria_duration_sec,
            )
            lyria_model_id = lyria_res.model_id

        sub_bass_808_path: str | None = None
        snapped_808: float | None = None
        if enable_808:
            snapped_808 = snap_timestamp_to_bpm_grid(req.raw_808_timestamp_sec, bpm=req.bpm_808)
            sub_bass_808_path = synthesize_tuned_808_wav(
                os.path.join(tmp_dir, "drop_808.wav"),
                root_note=req.root_note_808,
            )

        out_video_path = os.path.join(
            tmp_dir,
            f"master_3stem_{preset_cfg.preset.value}_{uuid.uuid4().hex[:8]}.mp4",
        )
        mastering_engine = ThreeStemMasteringEngine(mock_mode=agent.mock_mode)
        loudness_report = mastering_engine.mix_and_master_scene(
            video_path=src_video,
            output_video_path=out_video_path,
            narrator_wav_path=narrator_wav_path,
            narrator_delay_sec=narrator_delay,
            lyria_score_path=lyria_score_path,
            score_offset_sec=req.score_offset_sec,
            sub_bass_808_path=sub_bass_808_path,
            sub_bass_808_delay_sec=snapped_808,
            guillotine=guillotine,
            target_lufs=req.target_lufs,
            target_tp=req.target_true_peak_dbtp,
            preset=preset_cfg.preset,
        )

        gcs_dest = f"sessions/{safe_session}/masters/{os.path.basename(out_video_path)}"
        uploaded_ref = agent.storage.upload_file(out_video_path, gcs_dest)
        if not uploaded_ref:
            if not agent.mock_mode:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to upload 3-stem master video to GCS.",
                )
            gcs_uri = None
            master_url = "/static/rendered/mock.mp4"
        else:
            if uploaded_ref.startswith("gs://"):
                gcs_uri = uploaded_ref
            elif hasattr(agent.storage, "get_gcs_uri"):
                gcs_uri = agent.storage.get_gcs_uri(gcs_dest)
            else:
                gcs_uri = uploaded_ref
            master_url = f"/api/media-proxy?uri={quote_plus(gcs_uri)}"

    return Master3StemResponse(
        success=True,
        preset=preset_cfg.preset.value,
        master_video_url=master_url,
        gcs_uri=gcs_uri,
        snapped_808_timestamp_sec=snapped_808,
        loudness_report=loudness_report,
        narrator_duration_sec=narrator_duration_sec,
        lyria_model_id=lyria_model_id,
    )


@router.post("/api/generate-shot", response_model=GenerateShotResponse)
def generate_shot(req: GenerateShotRequest, agent: AgentDep) -> GenerateShotResponse:
    sanitized_directive = (
        sanitize_real_names(req.shot_directive)
        if (req.shot_directive and req.enable_safety_sanitization)
        else (req.shot_directive or "")
    )
    keyframe_url = req.keyframe_image_url
    if _is_placeholder_image_url(keyframe_url):
        keyframe_url = None

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
        compilation_mode=req.compilation_mode,
        shot_seconds=req.duration_seconds,
    )

    agent_turn = agent.process_user_turn(
        user_id="usr_default",
        project_id="prj_default",
        prompt=action_val or sanitized_directive,
        compiled_override=compiled_prompt,
        parent_turn_id=None,
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
