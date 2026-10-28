"""Production orchestration service for Mode 5: Commercial Soundstage."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os
import tempfile
import threading
from typing import Literal
import uuid

from omnimash.agent.orchestrator import OmniMashAgent
from omnimash.agent.soundstage_store import (
    SoundstageConflictError,
    SoundstageGuardrailBlockedError,
    SoundstageNotFoundError,
    SoundstageRunStore,
    coerce_palette_inputs,
    default_reference_kit,
    execute_boards_synthesis,
    execute_cast_and_kit_update,
    inject_surgical_director_directive,
    materialize_media_ref_if_data_uri,
    normalize_optional_confined_audio_url,
    scrub_commercial_note,
    validate_confined_audio_url,
    validate_confined_custom_image_url,
)
from omnimash.api.models import CharacterRoleModel
from omnimash.api.soundstage_models import (
    SoundstageActRenderRecord,
    SoundstageBoardsRequest,
    SoundstageCastRequest,
    SoundstageDiscoverRequest,
    SoundstageDiscoverResponse,
    SoundstagePlanRequest,
    SoundstageReconformRequest,
    SoundstageReviseRequest,
    SoundstageRunRequest,
    SoundstageStatusResponse,
    SoundstageVariationRequest,
    infer_target_act_from_note,
)
from omnimash.config import settings
from omnimash.engine.keyframe_client import KeyframeClient
from omnimash.engine.media_loader import coerce_character_roles
from omnimash.evaluation.models import UserFeedbackRecord, VideoEvaluationScorecard
from omnimash.evaluation.prompt_refiner import PromptRefiner
from omnimash.evaluation.video_critic import VideoCriticAgent
from omnimash.prompts.commercial_planner import (
    SoundstageActPlan,
    SoundstageDiscoveryEngine,
    SoundstageThreeActPlanner,
)
from omnimash.prompts.offering_physics import scrub_offering_trademarks
from omnimash.prompts.preflight_linter import PreFlightGatekeeper
from omnimash.stitching.commercial_conformer import (
    CANONICAL_SUBSHOT_IDS,
    CommercialConformer,
    build_default_subshot_specs,
    normalize_subshot_specs,
)
from omnimash.storage.gcs import validate_safe_identifier

logger = logging.getLogger(__name__)


def _unlink_confined_temp_file(path: str | None, allowed_roots: tuple[str, ...]) -> None:
    if not path or not os.path.isfile(path):
        return
    real_target = os.path.realpath(path)
    if any(
        real_target.startswith(os.path.realpath(root) + os.sep) for root in allowed_roots if root
    ):
        try:
            os.remove(real_target)
        except OSError:
            pass


class SoundstageProductionService:
    """End-to-end production orchestrator for Mode 5: Commercial Soundstage."""

    def __init__(
        self,
        agent: OmniMashAgent,
        store: SoundstageRunStore | None = None,
        output_dir: str | None = None,
    ) -> None:
        self.agent = agent
        self.mock_mode = bool(getattr(agent, "mock_mode", False))
        self.storage = agent.storage
        self.output_dir = output_dir or tempfile.gettempdir()
        self.store = store or SoundstageRunStore(storage=self.storage)
        self.discovery_engine = SoundstageDiscoveryEngine(mock_mode=self.mock_mode)
        self.planner = SoundstageThreeActPlanner(mock_mode=self.mock_mode)
        omni_client = getattr(agent, "omni_client", None)
        existing_kf = getattr(omni_client, "_keyframe_client", None)
        if isinstance(existing_kf, KeyframeClient) and existing_kf.storage is self.storage:
            self.keyframe_client = existing_kf
        else:
            default_proj = getattr(settings, "google_cloud_project", "hybrid-vertex")
            self.keyframe_client = KeyframeClient(
                mock_mode=self.mock_mode,
                storage=self.storage,
                api_key=getattr(omni_client, "api_key", None),
                project=getattr(omni_client, "project", default_proj),
                genai_client=getattr(omni_client, "_genai_client", None),
                log_inference_fn=getattr(omni_client, "_log_multimodal_inference", None),
                storage_getter=lambda: self.storage,
                api_key_getter=lambda: getattr(omni_client, "api_key", None),
                project_getter=lambda: getattr(omni_client, "project", default_proj),
            )
        self.conformer = CommercialConformer(
            mock_mode=self.mock_mode,
            storage=self.storage,
        )
        self.video_critic = VideoCriticAgent(
            mock_mode=self.mock_mode,
            storage=self.storage,
        )
        self.prompt_refiner = PromptRefiner(mock_mode=self.mock_mode)
        self._run_locks: dict[str, threading.RLock] = {}
        self._active_jobs: set[str] = set()
        self._locks_guard = threading.Lock()

    def is_actively_running(self, run_id: str) -> bool:
        """Returns True while a synchronous or background filming/revision/conform job is in flight."""
        with self._locks_guard:
            return run_id in self._active_jobs

    def _try_claim_active_job(self, run_id: str) -> bool:
        """Atomically claims `run_id` as active; returns False if another job is already running."""
        with self._locks_guard:
            if run_id in self._active_jobs:
                return False
            self._active_jobs.add(run_id)
            return True

    def _claim_active_job_or_raise(self, run_id: str) -> None:
        if not self._try_claim_active_job(run_id):
            raise SoundstageConflictError(
                f"Soundstage run '{run_id}' already has an active filming or conform job in progress."
            )

    def _set_job_active(self, run_id: str, active: bool) -> None:
        with self._locks_guard:
            if active:
                self._active_jobs.add(run_id)
            else:
                self._active_jobs.discard(run_id)

    def _lock_for_run(self, run_id: str) -> threading.RLock:
        with self._locks_guard:
            lock = self._run_locks.get(run_id)
            if lock is None:
                lock = threading.RLock()
                self._run_locks[run_id] = lock
            return lock

    def _screen_text_fields(self, *values: str | None) -> None:
        """Screens all user-supplied free-text prompts and notes via ModelArmorGuardrail."""
        guardrail = getattr(self.agent, "guardrail", None)
        if guardrail is None:
            return
        for text in values:
            if not text or not text.strip():
                continue
            verdict = guardrail.validate_prompt(text)
            if not verdict.is_approved:
                reason = verdict.rejection_reason or "Blocked by Model Armor security guardrail."
                raise SoundstageGuardrailBlockedError(reason)

    def get_status(self, run_id: str) -> SoundstageStatusResponse:
        return self.store.get(run_id)

    def discover(self, req: SoundstageDiscoverRequest) -> SoundstageDiscoverResponse:
        """Runs 10-step intake discovery and first-principles offering physics deduction."""
        self._screen_text_fields(req.subject, req.offering, req.territory, req.custom_dna)
        result = self.discovery_engine.discover(
            subject=req.subject,
            offering_hint=req.offering or "",
            territory_hint=req.territory or "",
            custom_dna=req.custom_dna or "",
        )
        return SoundstageDiscoverResponse.from_discovery_result(result)

    def create_plan(self, req: SoundstagePlanRequest) -> SoundstageStatusResponse:
        """Validates identifiers, compiles 3-Act x 3-Beat commercial plan, and persists run at 14%."""
        safe_project = validate_safe_identifier(req.project_name, "project_name")
        safe_session = validate_safe_identifier(req.session_name, "session_name")
        self._screen_text_fields(
            req.subject,
            req.offering,
            req.territory,
            req.weather_condition,
            req.tagline,
            req.moment,
            req.language,
            req.vocal_cadence,
            req.lead_name,
            req.lead_wardrobe,
            req.custom_dna,
        )

        safe_emblem = validate_confined_custom_image_url(req.emblem_url) if req.emblem_url else None
        safe_packshot = (
            validate_confined_custom_image_url(req.packshot_url) if req.packshot_url else None
        )
        custom_hexes, palette_override = coerce_palette_inputs(req.palette_hexes)

        clean_lead_name = (req.lead_name or "").strip()
        clean_lead_wardrobe = (req.lead_wardrobe or "").strip()
        clean_vocal_cadence = (req.vocal_cadence or "").strip()
        lead_override: CharacterRoleModel | None = None
        if clean_lead_name or clean_lead_wardrobe or clean_vocal_cadence:
            lead_override = CharacterRoleModel(
                role_id="Role A",
                name=clean_lead_name,
                description="",
                reference_url=None,
                wardrobe=clean_lead_wardrobe,
                voice_style=clean_vocal_cadence,
            )

        self.storage.create_session(safe_session, project_id=safe_project)
        plan = self.planner.build_plan(
            subject=req.subject,
            offering=req.offering or "",
            territory=req.territory or "",
            weather_condition=req.weather_condition or "",
            palette_hexes=custom_hexes,
            moment=req.moment or "",
            language=req.language,
            tagline=req.tagline or "",
            custom_dna=req.custom_dna or "",
            lead_character_override=lead_override,
            packshot_url=safe_packshot,
            emblem_url=safe_emblem,
            palette_override=palette_override,
        )

        status = SoundstageStatusResponse(
            run_id=f"sstage_{uuid.uuid4().hex[:12]}",
            project_name=safe_project,
            session_name=safe_session,
            stage="planned",
            progress_pct=0,
            resolution=req.resolution,
            manual_board_gate=req.manual_board_gate,
            auto_advance_filming=False,
            plan=plan,
            reference_kit=default_reference_kit(
                emblem_url=safe_emblem,
                packshot_url=safe_packshot,
            ),
            subshot_specs=build_default_subshot_specs(),
        )
        return self.store.append_event(
            status,
            stage="planned",
            progress_pct=14,
            message=(
                f"Compiled 3-Act x 3-Beat commercial plan for {plan.identity.display_subject} "
                f"({plan.physics.archetype})."
            ),
            data={"archetype": plan.physics.archetype},
        )

    def manage_cast_and_kit(self, req: SoundstageCastRequest) -> SoundstageStatusResponse:
        """Generates or hydrates lead cast turnaround sheets, brand emblems, and hero offering packshots."""
        self._screen_text_fields(req.tweak_note, req.wardrobe_note, req.vault_character_slug)
        run = self.store.get(req.run_id)
        if self.is_actively_running(run.run_id):
            raise SoundstageConflictError(
                f"Soundstage run '{run.run_id}' already has an active filming or conform job in progress."
            )
        with self._lock_for_run(run.run_id):
            if self.is_actively_running(run.run_id):
                raise SoundstageConflictError(
                    f"Soundstage run '{run.run_id}' already has an active filming or conform job in progress."
                )
            latest = self.store.get(req.run_id)
            return execute_cast_and_kit_update(
                latest,
                req,
                planner=self.planner,
                keyframe_client=self.keyframe_client,
                storage=self.storage,
                store=self.store,
            )

    def _generate_boards_locked(self, req: SoundstageBoardsRequest) -> SoundstageStatusResponse:
        latest = self.store.get(req.run_id)
        return execute_boards_synthesis(
            latest,
            req,
            keyframe_client=self.keyframe_client,
            store=self.store,
        )

    def generate_boards(self, req: SoundstageBoardsRequest) -> SoundstageStatusResponse:
        """Synthesizes all 9 storyboard plates (or 1 target shot_id) with strict person-free reference isolation."""
        self._screen_text_fields(req.director_note)
        run = self.store.get(req.run_id)
        if self.is_actively_running(run.run_id):
            raise SoundstageConflictError(
                f"Soundstage run '{run.run_id}' already has an active filming or conform job in progress."
            )
        with self._lock_for_run(run.run_id):
            if self.is_actively_running(run.run_id):
                raise SoundstageConflictError(
                    f"Soundstage run '{run.run_id}' already has an active filming or conform job in progress."
                )
            return self._generate_boards_locked(req)

    def _film_single_act(
        self,
        run: SoundstageStatusResponse,
        act: SoundstageActPlan,
        resolution: str,
        prompt_override: str | None = None,
        revision_count: int = 0,
        last_director_note: str | None = None,
    ) -> SoundstageActRenderRecord:
        """Lints an act's 4-Block Meta-Prompt and renders its 10s continuous clip via Gemini Omni Flash."""
        plan = run.plan
        first_frame_url = run.boards[act.first_frame_shot_id]
        last_frame_url = run.boards[act.last_frame_shot_id]

        lead_role = plan.lead_character.model_copy(
            update={
                "reference_url": run.reference_kit.get("lead_cast_url")
                or plan.lead_character.reference_url
            }
        )
        hero_role = plan.hero_offering_role.model_copy(
            update={
                "reference_url": run.reference_kit.get("packshot_url")
                or plan.hero_offering_role.reference_url
            }
        )
        linted = PreFlightGatekeeper.lint_and_repair(
            prompt_override or act.compiled_omni_prompt,
            characters=[lead_role, hero_role],
            keyframe_image_url=first_frame_url,
            last_frame_image_url=last_frame_url,
            has_dialogue=bool(act.voiceover_line),
            offering_physics=plan.physics.model_dump(),
            palette_60_30_10=plan.palette.model_dump(),
            act_number=act.act_number,
        )
        gen_res = self.agent.omni_client.generate_clip(
            prompt=linted.repaired_prompt,
            session_id=run.session_name,
            project_id=run.project_name,
            voiceover=act.voiceover_line,
            turn_index=None,
            characters=coerce_character_roles([lead_role, hero_role]),
            keyframe_image_url=first_frame_url,
            last_frame_image_url=last_frame_url,
            resolution=resolution,
            aspect_ratio="16:9",
        )
        if not gen_res.video_url:
            raise RuntimeError(
                gen_res.error_message
                or f"Gemini Omni Flash returned an empty video_url for Act {act.act_number}."
            )
        return SoundstageActRenderRecord(
            act_number=act.act_number,
            video_url=gen_res.video_url,
            gcs_uri=gen_res.gcs_uri,
            resolution=resolution,
            generation_mode=gen_res.generation_mode,
            compiled_prompt=linted.repaired_prompt,
            revision_count=revision_count,
            last_director_note=last_director_note,
        )

    def _conform_run_deliverables(
        self,
        run: SoundstageStatusResponse,
        *,
        use_reconform: bool = False,
    ) -> None:
        """Conforms 30s/15s/6s deliverables, unlinks superseded temp MP4s, and resets stale ZIP URLs."""
        prev_paths = (
            set((run.deliverables.local_paths or {}).values())
            if run.deliverables is not None
            else set()
        )
        act_clips = [rec.video_url for rec in sorted(run.acts, key=lambda rec: rec.act_number)]
        plan = run.plan
        with tempfile.TemporaryDirectory() as temp_dir:
            emblem_source = materialize_media_ref_if_data_uri(
                run.reference_kit.get("emblem_url"),
                temp_dir=temp_dir,
                stem="emblem_lockup",
                storage=self.storage,
            )
            conform_fn = (
                self.conformer.reconform_timeline
                if use_reconform
                else self.conformer.conform_all_formats
            )
            new_deliverables = conform_fn(
                act_clips=act_clips,
                display_subject=plan.identity.display_subject,
                display_tagline=plan.identity.display_tagline,
                primary_hex=plan.palette.primary_hex,
                secondary_hex=plan.palette.secondary_hex,
                neutral_hex=plan.palette.neutral_hex,
                emblem_path=emblem_source,
                subshot_specs=run.subshot_specs,
                background_music_path=run.background_music_path,
                end_card_duration_sec=run.end_card_duration_sec,
                output_dir=self.output_dir,
                session_id=run.session_name,
                project_id=run.project_name,
            )

        run.deliverables = new_deliverables
        run.package_zip_url = None
        new_paths = set((new_deliverables.local_paths or {}).values())
        allowed_roots = (self.output_dir, tempfile.gettempdir())
        for old_path in prev_paths - new_paths:
            _unlink_confined_temp_file(old_path, allowed_roots)

    def _execute_filming_pipeline(
        self,
        run_id: str,
        effective_resolution: str,
        background_music_path: str | None,
        update_bgm: bool,
        end_card_duration_sec: float,
    ) -> SoundstageStatusResponse:
        with self._lock_for_run(run_id):
            try:
                run = self.store.get(run_id)
                run.error = None
                reset_cap = 32 if (run.stage == "filming_acts" and run.progress_pct == 32) else 30
                run.progress_pct = min(run.progress_pct, reset_cap)
                run.resolution = effective_resolution
                run.end_card_duration_sec = end_card_duration_sec
                if update_bgm:
                    run.background_music_path = background_music_path

                if set(run.boards.keys()) != set(CANONICAL_SUBSHOT_IDS):
                    run = self._generate_boards_locked(SoundstageBoardsRequest(run_id=run_id))
                    run.error = None
                    run.resolution = effective_resolution
                    run.end_card_duration_sec = end_card_duration_sec
                    if update_bgm:
                        run.background_music_path = background_music_path

                run = self.store.append_event(
                    run,
                    stage="filming_acts",
                    progress_pct=36,
                    message=(
                        f"Filming 3 parallel 10-second continuous Soundstage acts at {effective_resolution} "
                        f"via {settings.omni_model_id}."
                    ),
                    data={"resolution": effective_resolution},
                )

                milestones = {1: 54, 2: 72, 3: 88}
                rendered_by_act: dict[int, SoundstageActRenderRecord] = {}
                ordered_act_plans = sorted(run.plan.acts, key=lambda a: a.act_number)
                pool = ThreadPoolExecutor(max_workers=3)
                try:
                    future_to_act = {
                        pool.submit(
                            self._film_single_act, run, act_plan, effective_resolution
                        ): act_plan.act_number
                        for act_plan in ordered_act_plans
                    }
                    completed_count = 0
                    for fut in as_completed(future_to_act):
                        act_num = future_to_act[fut]
                        record = fut.result()
                        completed_count += 1
                        rendered_by_act[act_num] = record
                        run = self.store.append_event(
                            run,
                            stage="filming_acts",
                            progress_pct=milestones.get(completed_count, 88),
                            message=f"Rendered Act {act_num} continuous 10s master clip ({effective_resolution}).",
                            data={"act_number": act_num, "video_url": record.video_url},
                        )
                except Exception:
                    pool.shutdown(wait=True, cancel_futures=True)
                    raise
                else:
                    pool.shutdown(wait=True)

                run.acts = [rendered_by_act[idx] for idx in sorted(rendered_by_act)]
                for idx, record in enumerate(run.acts):
                    run.plan.acts[idx].compiled_omni_prompt = record.compiled_prompt

                run = self.store.append_event(
                    run,
                    stage="conforming",
                    progress_pct=90,
                    message="Conforming 30s 16:9 Master, 15s 9:16 Cutdown, and 6s 9:16 Bumper with brand lockup.",
                )
                self._conform_run_deliverables(run, use_reconform=False)

                if run.deliverables is None:
                    raise RuntimeError("CommercialConformer returned no deliverables.")
                deliverables = run.deliverables
                scorecard = self.video_critic.evaluate_video(
                    session_id=run.session_name,
                    turn_id=f"{run.run_id}_master",
                    prompt="\n\n".join(rec.compiled_prompt for rec in run.acts),
                    video_uri=deliverables.gcs_uris.get("master_30s_16x9")
                    or deliverables.master_30s_16x9_url,
                )
                run.critic_scorecards["master"] = scorecard.model_dump(mode="json")
                run = self.store.append_event(
                    run,
                    stage="critic_evaluated",
                    progress_pct=96,
                    message=f"DOMA commercial critic evaluated master deliverable ({scorecard.overall_rating:.1f}/100).",
                    data={"overall_rating": scorecard.overall_rating},
                )
                run.error = None
                return self.store.append_event(
                    run,
                    stage="completed",
                    progress_pct=100,
                    message="Commercial Soundstage 30s Master, 15s Cutdown, and 6s Bumper completed.",
                    data={
                        "master_30s_16x9_url": deliverables.master_30s_16x9_url,
                        "cutdown_15s_9x16_url": deliverables.cutdown_15s_9x16_url,
                        "bumper_6s_9x16_url": deliverables.bumper_6s_9x16_url,
                    },
                )
            except Exception as exc:
                failed_run = self.store.get(run_id)
                failed_run.error = str(exc)
                self.store.append_event(
                    failed_run,
                    stage="failed",
                    progress_pct=failed_run.progress_pct,
                    message=f"Soundstage filming failed: {exc}",
                    data={"error": str(exc)},
                )
                raise

    def execute_filming_and_conform(self, req: SoundstageRunRequest) -> SoundstageStatusResponse:
        """Executes 3-act parallel Omni Flash filming, multi-format conform, and DOMA critic evaluation."""
        run = self.store.get(req.run_id)
        has_bgm_field = req.background_music_path is not None
        validated_bgm = normalize_optional_confined_audio_url(req.background_music_path)
        effective_res = req.resolution or run.resolution or "720p"

        self._claim_active_job_or_raise(run.run_id)
        if not req.async_execution:
            try:
                return self._execute_filming_pipeline(
                    run_id=run.run_id,
                    effective_resolution=effective_res,
                    background_music_path=validated_bgm,
                    update_bgm=has_bgm_field,
                    end_card_duration_sec=req.end_card_duration_sec,
                )
            finally:
                self._set_job_active(run.run_id, False)

        def _bg_runner() -> None:
            try:
                self._execute_filming_pipeline(
                    run_id=run.run_id,
                    effective_resolution=effective_res,
                    background_music_path=validated_bgm,
                    update_bgm=has_bgm_field,
                    end_card_duration_sec=req.end_card_duration_sec,
                )
            except Exception as exc:
                logger.exception("Async Soundstage run %s failed: %s", run.run_id, exc)
                with self._lock_for_run(run.run_id):
                    try:
                        cur = self.store.get(run.run_id)
                        if cur.stage != "failed":
                            cur.error = str(exc)
                            self.store.append_event(
                                cur,
                                stage="failed",
                                progress_pct=cur.progress_pct,
                                message=f"Soundstage filming failed: {exc}",
                                data={"error": str(exc)},
                            )
                    except Exception:
                        pass
            finally:
                self._set_job_active(run.run_id, False)

        try:
            with self._lock_for_run(run.run_id):
                run = self.store.get(req.run_id)
                run.error = None
                run.progress_pct = min(run.progress_pct, 30)
                run.resolution = effective_res
                run.end_card_duration_sec = req.end_card_duration_sec
                if has_bgm_field:
                    run.background_music_path = validated_bgm
                queued = self.store.append_event(
                    run,
                    stage="filming_acts",
                    progress_pct=32,
                    message=f"Queued asynchronous Commercial Soundstage filming at {effective_res}.",
                    data={"async_execution": True, "resolution": effective_res},
                )
            worker = threading.Thread(
                target=_bg_runner,
                name=f"soundstage-run-{run.run_id}",
                daemon=True,
            )
            worker.start()
        except Exception:
            self._set_job_active(run.run_id, False)
            raise
        return queued

    def revise_act(self, run_id: str, req: SoundstageReviseRequest) -> SoundstageStatusResponse:
        """Applies a trademark-scrubbed Director Note to re-film ONLY the target act (Lock & Isolate)."""
        self._screen_text_fields(req.director_note)
        run = self.store.get(run_id)
        self._claim_active_job_or_raise(run.run_id)
        try:
            with self._lock_for_run(run.run_id):
                run = self.store.get(run_id)
                if len(run.acts) < 3:
                    raise SoundstageConflictError(
                        "Cannot revise an act before initial 3-act filming has completed."
                    )

                target_act: Literal[1, 2, 3] = (
                    req.target_act
                    if req.target_act is not None
                    else infer_target_act_from_note(req.director_note)
                )
                act_idx = target_act - 1
                plan = run.plan
                subj, off = plan.identity.display_subject, plan.identity.display_offering
                scrubbed_note = scrub_commercial_note(req.director_note, subj, off)
                effective_res = req.resolution or run.resolution or "720p"

                existing_record = run.acts[act_idx]
                master_raw = run.critic_scorecards.get("master")
                scorecard = (
                    VideoEvaluationScorecard.model_validate(master_raw)
                    if isinstance(master_raw, dict)
                    else self.video_critic.evaluate_video(
                        session_id=run.session_name,
                        turn_id=f"{run.run_id}_act_{target_act}",
                        prompt=existing_record.compiled_prompt,
                        video_uri=existing_record.gcs_uri or existing_record.video_url,
                    )
                )
                refinement = self.prompt_refiner.refine_prompt(
                    original_prompt=existing_record.compiled_prompt,
                    scorecard=scorecard,
                    user_feedback=UserFeedbackRecord(
                        feedback_id=f"fb_{uuid.uuid4().hex[:10]}",
                        session_id=run.session_name,
                        turn_id=f"act_{target_act}",
                        rating=4,
                        critique_text=scrubbed_note,
                    ),
                )
                patched_prompt = scrub_offering_trademarks(
                    inject_surgical_director_directive(refinement.repaired_prompt, scrubbed_note),
                    subject=subj,
                    offering=off,
                )
                revised_record = self._film_single_act(
                    run=run,
                    act=plan.acts[act_idx],
                    resolution=effective_res,
                    prompt_override=patched_prompt,
                    revision_count=existing_record.revision_count + 1,
                    last_director_note=scrubbed_note,
                )

                run.acts[act_idx] = revised_record
                run.plan.acts[act_idx].compiled_omni_prompt = revised_record.compiled_prompt
                self._conform_run_deliverables(run, use_reconform=False)

                return self.store.append_event(
                    run,
                    stage="completed",
                    progress_pct=100,
                    message=f"Surgically re-filmed Act {target_act} and re-conformed 30s/15s/6s deliverables.",
                    data={
                        "target_act": target_act,
                        "revision_count": revised_record.revision_count,
                    },
                )
        finally:
            self._set_job_active(run.run_id, False)

    def reconform(self, run_id: str, req: SoundstageReconformRequest) -> SoundstageStatusResponse:
        """Applies NLE sub-shot trim/bypass adjustments and re-conforms deliverables with zero re-filming."""
        run = self.store.get(run_id)
        has_bgm_field = req.background_music_path is not None
        validated_bgm = normalize_optional_confined_audio_url(req.background_music_path)

        self._claim_active_job_or_raise(run.run_id)
        try:
            with self._lock_for_run(run.run_id):
                run = self.store.get(run_id)
                if len(run.acts) < 3:
                    raise SoundstageConflictError(
                        "Cannot reconform timeline before 3-act video clips have been filmed."
                    )

                run.subshot_specs = normalize_subshot_specs(
                    [*run.subshot_specs, *req.subshot_specs]
                )
                if req.end_card_duration_sec is not None:
                    run.end_card_duration_sec = req.end_card_duration_sec
                if has_bgm_field:
                    run.background_music_path = validated_bgm

                self._conform_run_deliverables(run, use_reconform=True)
                if run.deliverables is None:
                    raise RuntimeError("CommercialConformer returned no deliverables.")
                return self.store.append_event(
                    run,
                    stage="completed",
                    progress_pct=100,
                    message=(
                        f"Re-conformed timeline with {run.deliverables.active_subshot_count} active sub-shot(s) "
                        "and zero Omni Flash re-filming."
                    ),
                    data={
                        "active_subshot_count": run.deliverables.active_subshot_count,
                        "active_subshot_ids": list(run.deliverables.active_subshot_ids),
                    },
                )
        finally:
            self._set_job_active(run.run_id, False)

    def fork_variation(
        self,
        run_id: str,
        req: SoundstageVariationRequest,
    ) -> SoundstageStatusResponse:
        """Forks a session-isolated commercial variation across `place`, `cast`, or `offering`."""
        self._screen_text_fields(req.new_value)
        source_run = self.store.get(run_id)

        raw_new_session = (
            req.new_session_name.strip()
            if req.new_session_name and req.new_session_name.strip()
            else f"{source_run.session_name}_{req.axis}_{uuid.uuid4().hex[:6]}"
        )
        safe_new_session = validate_safe_identifier(raw_new_session, "new_session_name")

        self.storage.fork_session(
            source_session=source_run.session_name,
            new_session=safe_new_session,
            project_id=source_run.project_name,
            copy_roster=(req.axis != "cast"),
        )
        repointed_plan = self.planner.repoint_plan_for_variation(
            source_run.plan,
            axis=req.axis,
            new_value=req.new_value,
        )

        src_kit = source_run.reference_kit
        forked_kit = default_reference_kit(
            emblem_url=src_kit.get("emblem_url"),
            packshot_url=src_kit.get("packshot_url") if req.axis != "offering" else None,
        )
        forked_kit["emblem_candidates"] = list(src_kit.get("emblem_candidates") or [])
        if req.axis != "offering":
            forked_kit["packshot_candidates"] = list(src_kit.get("packshot_candidates") or [])
        if req.axis != "cast":
            forked_kit["lead_cast_url"] = src_kit.get("lead_cast_url")
            forked_kit["lead_cast_candidates"] = list(src_kit.get("lead_cast_candidates") or [])
            forked_kit["cast_locked"] = bool(src_kit.get("cast_locked", False))
            if forked_kit["lead_cast_url"]:
                repointed_plan.lead_character.reference_url = forked_kit["lead_cast_url"]
        if forked_kit["packshot_url"]:
            repointed_plan.hero_offering_role.reference_url = forked_kit["packshot_url"]

        forked_run_id = f"sstage_{uuid.uuid4().hex[:12]}"
        forked_status = SoundstageStatusResponse(
            run_id=forked_run_id,
            parent_run_id=source_run.run_id,
            variation_axis=req.axis,
            project_name=source_run.project_name,
            session_name=safe_new_session,
            stage="planned",
            progress_pct=0,
            resolution=source_run.resolution,
            manual_board_gate=source_run.manual_board_gate,
            auto_advance_filming=False,
            end_card_duration_sec=source_run.end_card_duration_sec,
            background_music_path=source_run.background_music_path,
            plan=repointed_plan,
            reference_kit=forked_kit,
            subshot_specs=[spec.model_copy() for spec in source_run.subshot_specs],
        )
        forked_status = self.store.append_event(
            forked_status,
            stage="planned",
            progress_pct=14,
            message=f"Forked '{req.axis}' variation into session '{safe_new_session}'.",
            data={"axis": req.axis, "parent_run_id": source_run.run_id},
        )
        if req.auto_film:
            return self.execute_filming_and_conform(SoundstageRunRequest(run_id=forked_run_id))
        if req.auto_generate_boards:
            return self.generate_boards(SoundstageBoardsRequest(run_id=forked_run_id))
        return forked_status

    def export_package_zip(self, run_id: str) -> tuple[str, str]:
        """Builds a campaign `.zip` archive bundling deliverables, 9 storyboards, kit, and manifest JSON."""
        run = self.store.get(run_id)
        with self._lock_for_run(run.run_id):
            run = self.store.get(run_id)
            if run.deliverables is None:
                raise SoundstageConflictError(
                    "Cannot export campaign package.zip before deliverables have been conformed."
                )

            with tempfile.TemporaryDirectory() as temp_dir:
                materialized_boards = {
                    shot_id: mat
                    for shot_id, board_ref in run.boards.items()
                    if (
                        mat := materialize_media_ref_if_data_uri(
                            board_ref,
                            temp_dir=temp_dir,
                            stem=f"board_{shot_id.replace('.', '_')}",
                            storage=self.storage,
                        )
                    )
                }
                materialized_kit: dict[str, str] = {
                    str(kit_key.removesuffix("_url")): mat
                    for kit_key in ("lead_cast_url", "emblem_url", "packshot_url")
                    if isinstance(run.reference_kit.get(kit_key), str)
                    and (
                        mat := materialize_media_ref_if_data_uri(
                            run.reference_kit.get(kit_key),
                            temp_dir=temp_dir,
                            stem=f"kit_{kit_key}",
                            storage=self.storage,
                        )
                    )
                }
                local_zip_path, gcs_uri = self.conformer.build_campaign_package_zip(
                    deliverables=run.deliverables,
                    plan=run.plan,
                    storyboard_frames=materialized_boards,
                    reference_kit=materialized_kit,
                    output_dir=self.output_dir,
                    session_id=run.session_name,
                    project_id=run.project_name,
                )

            try:
                run.package_zip_url = gcs_uri
                self.store.save(run)
            except Exception:
                _unlink_confined_temp_file(local_zip_path, (self.output_dir, tempfile.gettempdir()))
                raise
            return local_zip_path, gcs_uri


def get_soundstage_service(agent: OmniMashAgent) -> SoundstageProductionService:
    """Returns the singleton SoundstageProductionService attached to `agent` (refreshing if storage changed)."""
    existing = getattr(agent, "_soundstage_service", None)
    if isinstance(existing, SoundstageProductionService) and existing.storage is agent.storage:
        return existing
    service = SoundstageProductionService(agent=agent)
    setattr(agent, "_soundstage_service", service)
    return service


__all__ = [
    "SoundstageConflictError",
    "SoundstageGuardrailBlockedError",
    "SoundstageNotFoundError",
    "SoundstageProductionService",
    "SoundstageRunStore",
    "get_soundstage_service",
    "validate_confined_audio_url",
    "validate_confined_custom_image_url",
]
