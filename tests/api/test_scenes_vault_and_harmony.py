"""Tests for Saved Scenes Vault CRUD, SceneHarmonyProducer, and Final-Stage 3-Scene Cohesive Stitcher."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from omnimash.api.app import create_app
from omnimash.prompts.character_roles import CharacterRole
from omnimash.prompts.scene_harmony import (
    SavedSceneSpec,
    SceneHarmonyProducer,
)


def test_scene_harmony_producer_unifies_cast_and_preserves_scene_likeness():
    """Verify SceneHarmonyProducer deduplicates characters across 3 scenes,
    assigns canonical Role A/B/C with <IMAGE_REF_0>/<IMAGE_REF_1>, preserves
    user-finalized action & dialogue, and adds smooth entry/exit bridges."""
    producer = SceneHarmonyProducer(mock_mode=True)

    scenes = [
        SavedSceneSpec(
            scene_id="scn_001",
            title="Act 1: The Vintage Elixir",
            project_id="prj_director",
            session_id="revamp_v3",
            prompt="Gothic office introduction",
            action="[0-3s] Role B steps forward in white gloves. [3-6s] Role A inspects the crystal vial. [6-10s] Role A smirks.",
            dialogue='Role B: "The vintage elixir, Master." / Role A: "Bottle it."',
            dialogue_direction="Polished British vs East London cadence",
            environment="Grand vaulted gothic stone office",
            style_tone="Cinematic Dark Fantasy Trap",
            audio_beat="140 BPM Heavy 808 Trap",
            characters=[
                CharacterRole(
                    role_id="Role A",
                    name="YoTotti",
                    description="Young tatted wizard radiating zen energy",
                    reference_url="gs://bucket/yototti_sheet.png",
                    voice_style="British, East London accent",
                ),
                CharacterRole(
                    role_id="Role C",
                    name="Bee Allison",
                    description="Gritty, thin-faced, high-energy trap wizard",
                    reference_url="gs://bucket/bee_allison_sheet.png",
                    voice_style="Polished British accent",
                ),
            ],
            video_url="/api/clips/mock_scene_1.mp4",
        ),
        SavedSceneSpec(
            scene_id="scn_002",
            title="Act 2: The Golden Scale",
            project_id="prj_director",
            session_id="revamp_v3",
            prompt="Weighing the elixir on the golden scale",
            action="[0-3s] YoTotti places the vial on the golden scale. [3-6s] Bee Allison nods in approval. [6-10s] Steam rises from the goblet.",
            dialogue='YoTotti: "Pure magic on the scale."',
            environment="Grand vaulted gothic stone office",
            style_tone="Cinematic Dark Fantasy Trap",
            audio_beat="140 BPM Heavy 808 Trap",
            characters=[
                CharacterRole(
                    role_id="Role A",
                    name="YoTotti",
                    description="Young tatted wizard radiating zen energy",
                    reference_url="gs://bucket/yototti_sheet.png",
                    voice_style="British, East London accent",
                ),
            ],
            video_url="/api/clips/mock_scene_2.mp4",
        ),
        SavedSceneSpec(
            scene_id="scn_003",
            title="Act 3: The Runway Toast",
            project_id="prj_director",
            session_id="revamp_v3",
            prompt="Raising the golden goblets in triumph",
            action="[0-3s] Both wizards step toward the arched window. [3-6s] They raise golden goblets. [6-10s] Camera pulls back in a triumphant finish.",
            dialogue='Bee Allison: "To the empire." / YoTotti: "The runway awaits."',
            environment="Grand vaulted gothic stone office",
            style_tone="Cinematic Dark Fantasy Trap",
            audio_beat="140 BPM Heavy 808 Trap",
            characters=[
                CharacterRole(
                    role_id="Role B",
                    name="Bee Allison",
                    description="Gritty, thin-faced, high-energy trap wizard",
                    reference_url="gs://bucket/bee_allison_sheet.png",
                    voice_style="Polished British accent",
                ),
                CharacterRole(
                    role_id="Role A",
                    name="YoTotti",
                    description="Young tatted wizard radiating zen energy",
                    reference_url="gs://bucket/yototti_sheet.png",
                    voice_style="British, East London accent",
                ),
            ],
            video_url="/api/clips/mock_scene_3.mp4",
        ),
    ]

    plan = producer.harmonize_three_scenes(
        scenes=scenes,
        bridging_direction="Keep gothic stone candlelit continuity and 140 BPM trap beat across all 3 acts.",
    )

    # 1. Unified cast must deduplicate YoTotti and Bee Allison into canonical Role A & Role B
    assert len(plan.unified_characters) == 2
    role_ids = [c.role_id for c in plan.unified_characters]
    assert role_ids == ["Role A", "Role B"]
    names = {c.name for c in plan.unified_characters}
    assert names == {"YoTotti", "Bee Allison"}

    # 2. All 3 scenes must have compiled 4-block prompts with <IMAGE_REF_0> and <IMAGE_REF_1>
    assert len(plan.compiled_prompts) == 3
    for cp in plan.compiled_prompts:
        assert "### INPUT ROLES & REFERENCES" in cp
        assert "### CHARACTER PROFILES" in cp
        assert "### SCENE INSTRUCTIONS" in cp
        assert "### TIMELINE" in cp
        assert "<IMAGE_REF_0>" in cp
        assert "<IMAGE_REF_1>" in cp
        assert "- Scene 1 []:" not in cp

    # 3. Likeness preservation: original dialogue lines must remain intact
    assert "The vintage elixir" in plan.compiled_prompts[0]
    assert "Pure magic on the scale" in plan.compiled_prompts[1]
    assert "The runway awaits" in plan.compiled_prompts[2]

    # 4. Harmony notes must document cast unification and transition bridges
    assert len(plan.harmony_notes) >= 3


def test_saved_scenes_vault_crud_and_final_stage_harmonize_stitch_endpoints():
    """Verify POST /api/scenes/save, GET /api/scenes, DELETE /api/scenes/{id},
    POST /api/scenes/harmonize-preview, and POST /api/scenes/harmonize-and-stitch."""
    app = create_app(mock_mode=True)
    client = TestClient(app)

    saved_ids: list[str] = []
    for idx in range(1, 4):
        res = client.post(
            "/api/scenes/save",
            json={
                "title": f"Saved Scene {idx}",
                "project_id": "prj_vault_test",
                "session_id": "sess_vault_test",
                "prompt": f"Scene {idx} prompt concept",
                "action": f"[0-3s] Role A enters scene {idx}. [3-6s] Role A performs action {idx}. [6-10s] Role A finishes pose {idx}.",
                "dialogue": f'Role A: "Line from scene {idx}!"',
                "dialogue_direction": "Confident delivery",
                "environment": "Neon Gothic Studio",
                "style_tone": "90s_rap_video",
                "audio_beat": "140 BPM Heavy 808 Trap",
                "characters": [
                    {
                        "role_id": "Role A",
                        "name": "YoTotti",
                        "description": "Young tatted wizard",
                        "reference_url": "gs://bucket/yototti.png",
                        "voice_style": "East London accent",
                    },
                    {
                        "role_id": "Role B",
                        "name": "Bee Allison",
                        "description": "High-energy trap wizard",
                        "reference_url": "gs://bucket/bee.png",
                        "voice_style": "Polished British accent",
                    },
                ],
                "keyframe_image_url": f"https://storage.googleapis.com/mock/kf_{idx}.png",
                "video_url": f"/api/clips/mock_vault_clip_{idx}.mp4",
                "is_locked_video": True,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["scene"]["scene_id"]
        saved_ids.append(body["scene"]["scene_id"])

    # List saved scenes
    list_res = client.get("/api/scenes", params={"project_id": "prj_vault_test"})
    assert list_res.status_code == 200
    listed = list_res.json()
    assert listed["success"] is True
    assert len(listed["scenes"]) == 3

    # Preview harmonization
    preview_res = client.post(
        "/api/scenes/harmonize-preview",
        json={
            "project_id": "prj_vault_test",
            "scene_ids": saved_ids,
            "bridging_direction": "Seamless candlelit transitions and unified 140 BPM beat",
        },
    )
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    assert preview_data["success"] is True
    assert len(preview_data["compiled_prompts"]) == 3
    assert len(preview_data["unified_characters"]) == 2
    assert len(preview_data["harmony_notes"]) >= 3

    # Harmonize and stitch (Mode 1: respect_locked_videos=True -> reuses finalized MP4s without re-generating)
    with patch.object(
        app.state.agent,
        "process_user_turn",
        wraps=app.state.agent.process_user_turn,
    ) as spy_turn:
        stitch_res = client.post(
            "/api/scenes/harmonize-and-stitch",
            json={
                "project_id": "prj_vault_test",
                "session_name": "sess_vault_test",
                "scene_ids": saved_ids,
                "respect_locked_videos": True,
                "re_render_harmonized": False,
                "bridging_direction": "Maintain exact finalized clips and stitch into master",
            },
        )
        assert stitch_res.status_code == 200
        stitch_data = stitch_res.json()
        assert stitch_data["success"] is True
        assert stitch_data["master_video_url"]
        assert len(stitch_data["scene_video_urls"]) == 3
        assert spy_turn.call_count == 0

    # Harmonize and stitch (Mode 2: re_render_harmonized=True -> renders 3 fresh Turn-0 clips with parent_turn_id=None)
    with patch.object(
        app.state.agent,
        "process_user_turn",
        wraps=app.state.agent.process_user_turn,
    ) as spy_turn_rerender:
        rerender_res = client.post(
            "/api/scenes/harmonize-and-stitch",
            json={
                "project_id": "prj_vault_test",
                "session_name": "sess_vault_test",
                "scene_ids": saved_ids,
                "respect_locked_videos": False,
                "re_render_harmonized": True,
                "bridging_direction": "Re-render with unified cast and continuity bridges",
            },
        )
        assert rerender_res.status_code == 200
        rerender_data = rerender_res.json()
        assert rerender_data["success"] is True
        assert rerender_data["master_video_url"]
        assert spy_turn_rerender.call_count == 3
        for call in spy_turn_rerender.call_args_list:
            assert call.kwargs.get("parent_turn_id") is None
            assert call.kwargs.get("is_conversational_edit") is False

    # Delete one scene
    del_res = client.delete(f"/api/scenes/{saved_ids[0]}", params={"project_id": "prj_vault_test"})
    assert del_res.status_code == 200
    list_after = client.get("/api/scenes", params={"project_id": "prj_vault_test"}).json()
    assert len(list_after["scenes"]) == 2


def test_harmonize_and_stitch_mixed_aspect_ratios_forces_ffmpeg_normalization_reencode(tmp_path):
    """Verify POST /api/scenes/harmonize-and-stitch with mixed aspect ratios (9:16 + 16:9)
    passes force_normalize=True to VideoStitcher.concatenate_clips and invokes FFmpeg scale/pad re-encoding."""
    from unittest.mock import MagicMock
    from omnimash.stitching.stitcher import VideoStitcher

    app = create_app(mock_mode=True)
    client = TestClient(app)

    s1 = client.post(
        "/api/scenes/save",
        json={
            "title": "Vertical Scene 1",
            "project_id": "prj_mixed_ar",
            "action": "[0-3s] Role A enters. [3-6s] Role A raps. [6-10s] Role A poses.",
            "aspect_ratio": "9:16",
            "video_url": "/api/clips/mock_v1.mp4",
        },
    ).json()["scene"]["scene_id"]
    s2 = client.post(
        "/api/scenes/save",
        json={
            "title": "Horizontal Scene 2",
            "project_id": "prj_mixed_ar",
            "action": "[0-3s] Role A walks. [3-6s] Role A turns. [6-10s] Role A smiles.",
            "aspect_ratio": "16:9",
            "video_url": "/api/clips/mock_v2.mp4",
        },
    ).json()["scene"]["scene_id"]

    with patch.object(
        app.state.agent.stitcher,
        "concatenate_clips",
        wraps=app.state.agent.stitcher.concatenate_clips,
    ) as spy_concat:
        res = client.post(
            "/api/scenes/harmonize-and-stitch",
            json={
                "project_id": "prj_mixed_ar",
                "session_name": "sess_mixed_ar",
                "scene_ids": [s1, s2],
                "aspect_ratio": "16:9",
                "respect_locked_videos": True,
            },
        )
        assert res.status_code == 200
        assert spy_concat.call_count == 1
        assert spy_concat.call_args.kwargs.get("force_normalize") is True

    # Also verify live VideoStitcher.concatenate_clips with force_normalize=True skips -c copy and runs scale/pad re-encode
    stitcher = VideoStitcher(mock_mode=False)
    clip_a = tmp_path / "clip_a.mp4"
    clip_b = tmp_path / "clip_b.mp4"
    clip_a.write_bytes(b"fake_mp4_a")
    clip_b.write_bytes(b"fake_mp4_b")

    ok_res = MagicMock()
    ok_res.returncode = 0
    with (
        patch("subprocess.run", return_value=ok_res) as mock_run,
        patch.object(stitcher.storage, "upload_file"),
    ):
        stitcher.concatenate_clips(
            [str(clip_a), str(clip_b)],
            output_dir=str(tmp_path),
            aspect_ratio="16:9",
            force_normalize=True,
        )
        assert mock_run.call_count == 1
        cmd = mock_run.call_args[0][0]
        assert "-vf" in cmd
        assert "libx264" in cmd
        assert "copy" not in cmd


def test_saved_scenes_vault_gcs_hydration_and_deletion_across_instances():
    """Verify list_saved_scenes, _resolve_scenes_for_request, and delete_saved_scene hydrate from
    and delete projects/{project_id}/saved_scenes/*.json blobs in GCS when storage has a live bucket."""
    from unittest.mock import MagicMock
    from omnimash.api.routers.scenes_vault import _SAVED_SCENES_MEMORY

    app = create_app(mock_mode=True)
    storage = app.state.agent.storage
    storage.mock_mode = False

    remote_spec = SavedSceneSpec(
        scene_id="scn_remote_hydrated_1",
        title="Remote Hydrated Act 1",
        created_at="2026-10-22T06:00:00+00:00",
        project_id="prj_cloudrun_sync",
        session_id="sess_cloudrun_sync",
        prompt="Gothic office remote scene",
        action="[0-3s] Role A enters. [3-6s] Role A speaks. [6-10s] Role A nods.",
        dialogue='Role A: "Hydrated from GCS!"',
        environment="Vaulted Gothic Office",
        style_tone="Cinematic Dark Fantasy Trap",
        audio_beat="140 BPM Heavy 808 Trap",
        video_url="/api/clips/mock_hydrated.mp4",
    )
    _SAVED_SCENES_MEMORY.pop(remote_spec.scene_id, None)

    mock_blob = MagicMock()
    mock_blob.name = "projects/prj_cloudrun_sync/saved_scenes/scn_remote_hydrated_1.json"
    mock_blob.download_as_text.return_value = remote_spec.model_dump_json()
    mock_blob.exists.return_value = True

    mock_bucket = MagicMock()
    mock_bucket.list_blobs.return_value = [mock_blob]
    mock_bucket.blob.return_value = mock_blob
    storage._bucket_instance = mock_bucket

    client = TestClient(app)

    # 1. GET /api/scenes hydrates from GCS into _SAVED_SCENES_MEMORY
    list_res = client.get("/api/scenes", params={"project_id": "prj_cloudrun_sync"})
    assert list_res.status_code == 200
    scenes = list_res.json()["scenes"]
    assert any(s["scene_id"] == "scn_remote_hydrated_1" for s in scenes)

    # 2. Clear memory and verify harmonize-preview (_resolve_scenes_for_request) also hydrates from GCS
    _SAVED_SCENES_MEMORY.pop("scn_remote_hydrated_1", None)
    preview_res = client.post(
        "/api/scenes/harmonize-preview",
        json={
            "project_id": "prj_cloudrun_sync",
            "scene_ids": ["scn_remote_hydrated_1"],
            "bridging_direction": "Keep gothic continuity",
        },
    )
    assert preview_res.status_code == 200
    assert len(preview_res.json()["compiled_prompts"]) == 1

    # 3. DELETE /api/scenes/{scene_id} deletes blob from GCS as well as memory
    del_res = client.delete(
        "/api/scenes/scn_remote_hydrated_1",
        params={"project_id": "prj_cloudrun_sync"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True
    mock_bucket.blob.assert_called_with(
        "projects/prj_cloudrun_sync/saved_scenes/scn_remote_hydrated_1.json"
    )
    assert mock_blob.delete.call_count == 1
