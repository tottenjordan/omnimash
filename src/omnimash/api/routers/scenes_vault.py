"""Router for Saved Scenes Vault CRUD and Final-Stage 3-Scene Cohesive Harmony Stitcher."""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from omnimash.api.deps import AgentDep
from omnimash.prompts.scene_harmony import (
    SavedSceneSpec,
    SceneHarmonyProducer,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory vault store indexed by scene_id (backed by GCS projects/{project_id}/saved_scenes/{scene_id}.json)
_SAVED_SCENES_MEMORY: dict[str, SavedSceneSpec] = {}


class SaveSceneRequest(BaseModel):
    scene_id: str | None = None
    title: str = "Saved Scene"
    project_id: str = "prj_default"
    session_id: str = "default_session"
    prompt: str = ""
    action: str = ""
    dialogue: str = ""
    dialogue_direction: str = ""
    screenplay_script: str = ""
    environment: str = ""
    style_tone: str = "90s_rap_video"
    audio_beat: str = "140 BPM Heavy 808 Trap"
    vocal_delivery: str = ""
    characters: list[dict[str, Any]] = Field(default_factory=list)
    keyframe_image_url: str | None = None
    video_url: str | None = None
    gcs_uri: str | None = None
    aspect_ratio: str = "16:9"
    is_locked_video: bool = True


class HarmonizePreviewRequest(BaseModel):
    project_id: str = "prj_default"
    scene_ids: list[str] = Field(default_factory=list)
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    bridging_direction: str = ""


class HarmonizeAndStitchRequest(BaseModel):
    project_id: str = "prj_default"
    session_name: str = "harmonized_master_session"
    scene_ids: list[str] = Field(default_factory=list)
    scenes: list[dict[str, Any]] = Field(default_factory=list)
    bridging_direction: str = ""
    respect_locked_videos: bool = True
    re_render_harmonized: bool = False
    aspect_ratio: str = "16:9"
    resolution: str = "720p"
    master_title: str | None = None


def _hydrate_saved_scenes_from_gcs(
    agent: Any,
    project_id: str | None = None,
) -> None:
    """Hydrates saved scene specs from projects/{project_id}/saved_scenes/*.json in GCS into _SAVED_SCENES_MEMORY and evicts deleted scenes."""
    if (
        agent is None
        or getattr(agent.storage, "mock_mode", True)
        or not getattr(agent.storage, "bucket", None)
    ):
        return
    try:
        bucket = agent.storage.bucket
        prefix = f"projects/{project_id}/saved_scenes/" if project_id else "projects/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        live_scene_ids: set[str] = set()
        for blob in blobs:
            name = getattr(blob, "name", "") or ""
            if not name.endswith(".json") or "/saved_scenes/" not in name:
                continue
            raw = (
                blob.download_as_text()
                if hasattr(blob, "download_as_text")
                else blob.download_as_bytes().decode("utf-8")
            )
            spec = SavedSceneSpec.model_validate_json(raw)
            _SAVED_SCENES_MEMORY[spec.scene_id] = spec
            live_scene_ids.add(spec.scene_id)
        for sid, existing in list(_SAVED_SCENES_MEMORY.items()):
            if (
                project_id is None or existing.project_id == project_id
            ) and sid not in live_scene_ids:
                _SAVED_SCENES_MEMORY.pop(sid, None)
    except Exception as exc:
        logger.debug("Saved scene GCS hydration skipped/failed: %s", exc)


def _resolve_scenes_for_request(
    scene_ids: list[str],
    inline_scenes: list[dict[str, Any]],
    agent: Any = None,
    project_id: str | None = None,
) -> list[SavedSceneSpec]:
    resolved: list[SavedSceneSpec] = []
    if inline_scenes:
        for item in inline_scenes:
            resolved.append(SavedSceneSpec.model_validate(item))
        return resolved

    _hydrate_saved_scenes_from_gcs(agent=agent, project_id=project_id)
    if project_id and any(sid not in _SAVED_SCENES_MEMORY for sid in scene_ids):
        _hydrate_saved_scenes_from_gcs(agent=agent, project_id=None)

    for sid in scene_ids:
        spec = _SAVED_SCENES_MEMORY.get(sid)
        if spec is not None:
            resolved.append(spec)
    return resolved


@router.post("/api/scenes/save")
def save_scene_to_vault(req: SaveSceneRequest, agent: AgentDep) -> dict[str, Any]:
    scene_id = (req.scene_id or "").strip() or f"scn_{uuid.uuid4().hex[:10]}"
    spec = SavedSceneSpec(
        scene_id=scene_id,
        title=req.title or "Saved Scene",
        created_at=datetime.now(UTC).isoformat(),
        project_id=req.project_id or "prj_default",
        session_id=req.session_id or "default_session",
        prompt=req.prompt,
        action=req.action or req.prompt,
        dialogue=req.dialogue,
        dialogue_direction=req.dialogue_direction,
        screenplay_script=req.screenplay_script,
        environment=req.environment,
        style_tone=req.style_tone,
        audio_beat=req.audio_beat,
        vocal_delivery=req.vocal_delivery,
        characters=req.characters,  # type: ignore[arg-type]
        keyframe_image_url=req.keyframe_image_url,
        video_url=req.video_url,
        gcs_uri=req.gcs_uri,
        aspect_ratio=req.aspect_ratio or "16:9",
        is_locked_video=req.is_locked_video,
    )
    _SAVED_SCENES_MEMORY[scene_id] = spec

    # Persist to GCS if live storage is available
    try:
        blob_path = f"projects/{spec.project_id}/saved_scenes/{scene_id}.json"
        if not getattr(agent.storage, "mock_mode", True) and getattr(agent.storage, "bucket", None):
            bucket = agent.storage.bucket
            if bucket is not None:
                blob = bucket.blob(blob_path)
                blob.upload_from_string(
                    spec.model_dump_json(indent=2),
                    content_type="application/json",
                )
    except Exception as exc:
        logger.debug("Saved scene GCS persistence skipped/failed: %s", exc)

    return {
        "success": True,
        "scene": spec.model_dump(),
    }


@router.get("/api/scenes")
def list_saved_scenes(
    agent: AgentDep,
    project_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    _hydrate_saved_scenes_from_gcs(agent=agent, project_id=project_id)
    items = list(_SAVED_SCENES_MEMORY.values())
    if project_id:
        items = [s for s in items if s.project_id == project_id]
    if session_id:
        items = [s for s in items if s.session_id == session_id]
    items.sort(key=lambda s: s.created_at)
    return {
        "success": True,
        "scenes": [s.model_dump() for s in items],
    }


@router.delete("/api/scenes/{scene_id}")
def delete_saved_scene(
    scene_id: str,
    agent: AgentDep,
    project_id: str | None = None,
) -> dict[str, Any]:
    popped = _SAVED_SCENES_MEMORY.pop(scene_id, None)
    existed = popped is not None
    eff_project_id = project_id or (popped.project_id if popped else None)

    if not getattr(agent.storage, "mock_mode", True) and getattr(agent.storage, "bucket", None):
        try:
            bucket = agent.storage.bucket
            if bucket is not None:
                deleted_in_gcs = False
                if eff_project_id:
                    blob_path = f"projects/{eff_project_id}/saved_scenes/{scene_id}.json"
                    blob = bucket.blob(blob_path)
                    if blob.exists():
                        blob.delete()
                        deleted_in_gcs = True
                        existed = True
                if not deleted_in_gcs:
                    suffix = f"/saved_scenes/{scene_id}.json"
                    for b in list(bucket.list_blobs(prefix="projects/")):
                        b_name = getattr(b, "name", "") or ""
                        if b_name.endswith(suffix):
                            b.delete()
                            deleted_in_gcs = True
                            existed = True
                if not deleted_in_gcs and not eff_project_id:
                    for fallback_proj in ("prj_director", "prj_default"):
                        blob = bucket.blob(f"projects/{fallback_proj}/saved_scenes/{scene_id}.json")
                        if blob.exists():
                            blob.delete()
                            existed = True
                            break
        except Exception as exc:
            logger.debug("Saved scene GCS delete skipped/failed for %s: %s", scene_id, exc)

    return {
        "success": True,
        "deleted": existed,
        "scene_id": scene_id,
    }


@router.post("/api/scenes/harmonize-preview")
def harmonize_preview(req: HarmonizePreviewRequest, agent: AgentDep) -> dict[str, Any]:
    scenes = _resolve_scenes_for_request(
        req.scene_ids,
        req.scenes,
        agent=agent,
        project_id=req.project_id,
    )
    if not scenes:
        raise HTTPException(
            status_code=400,
            detail="No saved scenes found for harmonization preview. Provide scene_ids or scenes.",
        )

    producer = SceneHarmonyProducer(
        mock_mode=getattr(agent, "mock_mode", False),
        compiler=agent.taxonomy.compiler,
    )
    plan = producer.harmonize_three_scenes(
        scenes=scenes,
        bridging_direction=req.bridging_direction,
    )
    return {
        "success": True,
        "unified_characters": [asdict(c) for c in plan.unified_characters],
        "harmonized_scenes": plan.harmonized_scenes,
        "compiled_prompts": plan.compiled_prompts,
        "audio_beat": plan.audio_beat,
        "style_tone": plan.style_tone,
        "environment": plan.environment,
        "harmony_notes": plan.harmony_notes,
    }


@router.post("/api/scenes/harmonize-and-stitch")
def harmonize_and_stitch(req: HarmonizeAndStitchRequest, agent: AgentDep) -> dict[str, Any]:
    scenes = _resolve_scenes_for_request(
        req.scene_ids,
        req.scenes,
        agent=agent,
        project_id=req.project_id,
    )
    if not scenes:
        raise HTTPException(
            status_code=400,
            detail="No saved scenes found for harmonize-and-stitch. Select up to 3 scenes first.",
        )

    producer = SceneHarmonyProducer(
        mock_mode=getattr(agent, "mock_mode", False),
        compiler=agent.taxonomy.compiler,
    )
    plan = producer.harmonize_three_scenes(
        scenes=scenes,
        bridging_direction=req.bridging_direction,
    )

    scene_video_urls: list[str] = []
    for idx, (scene_spec, compiled_prompt) in enumerate(zip(scenes, plan.compiled_prompts)):
        can_reuse = (
            req.respect_locked_videos
            and not req.re_render_harmonized
            and bool(scene_spec.video_url and scene_spec.video_url.strip())
        )
        if can_reuse and scene_spec.video_url:
            scene_video_urls.append(scene_spec.video_url)
        else:
            # Render a fresh Turn-0 video (parent_turn_id=None, is_conversational_edit=False)
            turn_res = agent.process_user_turn(
                user_id="usr_studio",
                project_id=req.project_id or scene_spec.project_id or "prj_default",
                prompt=scene_spec.action or scene_spec.prompt or f"Harmonized Scene {idx + 1}",
                clip_index=idx,
                parent_turn_id=None,
                is_conversational_edit=False,
                compiled_override=compiled_prompt,
                session_name=req.session_name or "harmonized_master_session",
                concept=scene_spec.prompt or scene_spec.title,
                characters=plan.unified_characters,
                keyframe_image_url=scene_spec.keyframe_image_url,
                audio_stem=plan.audio_beat,
                voiceover=scene_spec.dialogue or None,
                environment_tag=plan.environment,
                aspect_ratio=req.aspect_ratio or scene_spec.aspect_ratio or "16:9",
                resolution=req.resolution or "720p",
            )
            if not turn_res.success or not turn_res.video_url:
                raise HTTPException(
                    status_code=400,
                    detail=turn_res.error_message or f"Failed to render harmonized Scene {idx + 1}",
                )
            scene_video_urls.append(turn_res.video_url)

    # Concatenate the 3 clips into a seamless master MP4
    target_aspect = (req.aspect_ratio or "16:9").strip() or "16:9"
    has_mixed_aspect_ratios = any(
        (s.aspect_ratio or "16:9").strip() != target_aspect for s in scenes
    )
    stitched_local_path = agent.stitcher.concatenate_clips(
        clip_paths=scene_video_urls,
        session_id=req.session_name,
        aspect_ratio=target_aspect,
        force_normalize=has_mixed_aspect_ratios,
    )
    master_url, gcs_uri = agent.storage.save_final_master(
        session_id=req.session_name,
        source_rel_path=stitched_local_path,
        master_title=req.master_title or "harmonized_3scene_master",
    )

    return {
        "success": True,
        "master_video_url": master_url,
        "master_video_path": stitched_local_path,
        "gcs_uri": gcs_uri,
        "scene_video_urls": scene_video_urls,
        "compiled_prompts": plan.compiled_prompts,
        "unified_characters": [asdict(c) for c in plan.unified_characters],
        "harmonized_scenes": plan.harmonized_scenes,
        "harmony_notes": plan.harmony_notes,
    }
