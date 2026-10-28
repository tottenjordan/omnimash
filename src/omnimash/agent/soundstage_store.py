"""Persistent run store, media confinement, and kit/board synthesis helpers for Mode 5: Commercial Soundstage."""

from __future__ import annotations

import base64
import binascii
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
import re
import threading
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
import uuid

from omnimash.api.models import CharacterRoleModel
from omnimash.api.soundstage_models import (
    SoundstageBoardCheck,
    SoundstageBoardsRequest,
    SoundstageCastRequest,
    SoundstageProgressEvent,
    SoundstageStatusResponse,
)
from omnimash.engine.keyframe_client import KeyframeClient
from omnimash.engine.media_loader import (
    fetch_media_bytes,
    validate_local_media_path,
    validate_remote_media_url,
)
from omnimash.prompts.commercial_planner import (
    DualLayerIdentityAbstractor,
    Palette603010,
    SoundstageCommercialPlan,
    SoundstageThreeActPlanner,
    StoryboardTileSpec,
)
from omnimash.prompts.offering_physics import (
    sanitize_single_line_field,
    scrub_offering_trademarks,
)
from omnimash.prompts.parody import sanitize_real_names
from omnimash.stitching.commercial_conformer import CANONICAL_SUBSHOT_IDS
from omnimash.storage.gcs import GcsStorageManager, validate_safe_identifier

MAX_DATA_URI_BYTES = 10 * 1024 * 1024
MAX_DATA_URI_CHARS = 14 * 1024 * 1024
_ALLOWED_DATA_IMAGE_SUBTYPES = frozenset({"png", "jpeg", "jpg", "webp", "svg+xml"})
_GCS_BUCKET_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

_THIRD_PARTY_BRAND_RE = re.compile(
    r"\b(?:Nike|Adidas|Porsche|Ferrari|Lamborghini|Tesla|Apple|Samsung|Rolex|Omega|"
    r"Gucci|Prada|Dior|Chanel|Hermes|Starbucks|Nespresso|Coca-Cola|Pepsi|Red\s+Bull|"
    r"Netflix|Spotify|Uber|Airbnb|Amazon)\b",
    re.IGNORECASE,
)


class SoundstageNotFoundError(KeyError):
    """Raised when a requested Mode 5 Soundstage `run_id` or vault asset does not exist."""


class SoundstageGuardrailBlockedError(PermissionError):
    """Raised when Model Armor security guardrails reject an adversarial prompt or note."""


class SoundstageConflictError(RuntimeError):
    """Raised when an operation conflicts with run state or an active job on `run_id`."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def scrub_commercial_note(text: str, subject: str, offering: str) -> str:
    """Scrubs offering trademarks, real human names, and third-party brand tokens from director notes."""
    cleaned = sanitize_single_line_field(text)
    if not cleaned:
        return ""
    cleaned = scrub_offering_trademarks(cleaned, subject=subject, offering=offering)
    cleaned = sanitize_real_names(cleaned)
    cleaned = _THIRD_PARTY_BRAND_RE.sub("", cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip(" ,;-")


def _validate_and_decode_data_image_uri(uri: str) -> bytes:
    """Validates `data:image/(png|jpeg|jpg|webp|svg+xml);base64,<payload>` within 10 MiB decoded cap."""
    if len(uri) > MAX_DATA_URI_CHARS:
        raise ValueError(f"data:image URI exceeds maximum {MAX_DATA_URI_BYTES} byte limit.")
    header, sep, b64_body = uri.partition(",")
    header_low = header.strip().lower()
    if sep != "," or not header_low.startswith("data:image/") or not header_low.endswith(";base64"):
        raise ValueError("Invalid data:image URI format; expected base64-encoded image.")
    subtype = header_low[len("data:image/") : -len(";base64")]
    if subtype not in _ALLOWED_DATA_IMAGE_SUBTYPES:
        raise ValueError(f"Unsupported data:image subtype '{subtype}'.")
    compact = "".join(b64_body.split())
    if not compact:
        raise ValueError("Empty base64 payload in data:image URI.")
    try:
        decoded = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Malformed base64 payload in data:image URI.") from exc
    if not decoded or len(decoded) > MAX_DATA_URI_BYTES:
        raise ValueError(f"Decoded data:image payload exceeds {MAX_DATA_URI_BYTES} byte limit.")
    return decoded


def _unwrap_media_proxy_uri(url: str, max_hops: int = 3) -> str:
    """Unwraps `/api/media-proxy?uri=...` up to `max_hops` hops, rejecting deeper nesting or empty URIs."""
    current = url.strip()
    for _ in range(max_hops):
        parsed = urlparse(current)
        if parsed.path != "/api/media-proxy" and not current.startswith("/api/media-proxy"):
            break
        qs = parse_qs(parsed.query)
        inner = unquote((qs.get("uri") or [""])[0]).strip()
        if not inner:
            raise ValueError("Missing or empty 'uri' parameter in /api/media-proxy URL.")
        current = inner
    parsed_final = urlparse(current)
    if parsed_final.path == "/api/media-proxy" or current.startswith("/api/media-proxy"):
        raise ValueError(f"Exceeded maximum {max_hops}-hop /api/media-proxy unwrap depth.")
    return current


def _validate_bucket_and_object_path(bucket: str, obj_path: str, field_name: str) -> None:
    clean_bucket = bucket.strip()
    clean_obj = obj_path.split("?", 1)[0].strip("/")
    if (
        not clean_bucket
        or clean_bucket in {".", ".."}
        or not _GCS_BUCKET_NAME_RE.match(clean_bucket)
        or not clean_obj
        or "\x00" in clean_obj
        or "\\" in clean_obj
        or ".." in clean_obj.split("/")
    ):
        raise ValueError(
            f"Invalid storage URI in {field_name}: expected <bucket>/<object> without '..'."
        )


def _validate_unwrapped_media_target(unwrapped: str, field_name: str) -> None:
    if unwrapped.lower().startswith("data:"):
        raise ValueError(f"data: URIs are not permitted in {field_name}.")
    if unwrapped.startswith("gs://"):
        rest = unwrapped[5:]
        if "/" not in rest:
            raise ValueError(f"Invalid GCS URI in {field_name}: expected gs://<bucket>/<object>.")
        bucket, obj_path = rest.split("/", 1)
        _validate_bucket_and_object_path(bucket, obj_path, field_name)
        return
    if unwrapped.startswith("https://storage.googleapis.com/"):
        rest = unwrapped[len("https://storage.googleapis.com/") :]
        if "/" not in rest:
            raise ValueError(f"Invalid storage URL in {field_name}: expected bucket and object.")
        bucket, obj_path = rest.split("/", 1)
        _validate_bucket_and_object_path(bucket, obj_path, field_name)
        return
    if unwrapped.startswith(("http://", "https://")):
        if not validate_remote_media_url(unwrapped):
            raise ValueError(f"Disallowed or internal remote host in {field_name}.")
        return
    if validate_local_media_path(unwrapped) is not None:
        return
    raise ValueError(f"Disallowed or unconfined local path in {field_name}.")


def validate_confined_custom_image_url(url: str) -> str:
    """Validates custom image references across bounded `data:image/`, 3-hop media-proxy, GCS, HTTPS, and local roots."""
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("custom_image_url must not be empty.")
    if cleaned.lower().startswith("data:"):
        _validate_and_decode_data_image_uri(cleaned)
        return cleaned
    unwrapped = _unwrap_media_proxy_uri(cleaned, max_hops=3)
    _validate_unwrapped_media_target(unwrapped, "custom_image_url")
    return cleaned


def validate_confined_audio_url(url: str) -> str:
    """Validates `background_music_path` rejecting `data:` URIs, SSRF URLs, out-of-root paths, and proxy bypasses."""
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("background_music_path must not be empty.")
    if cleaned.lower().startswith("data:"):
        raise ValueError("data: URIs are not permitted for background_music_path.")
    unwrapped = _unwrap_media_proxy_uri(cleaned, max_hops=3)
    _validate_unwrapped_media_target(unwrapped, "background_music_path")
    return cleaned


def normalize_optional_confined_audio_url(url: str | None) -> str | None:
    """Normalizes whitespace-only audio path to `None` and validates non-empty paths."""
    if url is None:
        return None
    cleaned = url.strip()
    if not cleaned:
        return None
    return validate_confined_audio_url(cleaned)


def default_reference_kit(
    emblem_url: str | None = None,
    packshot_url: str | None = None,
) -> dict[str, Any]:
    return {
        "lead_cast_url": None,
        "lead_cast_candidates": [],
        "emblem_url": emblem_url,
        "emblem_candidates": [emblem_url] if emblem_url else [],
        "packshot_url": packshot_url,
        "packshot_candidates": [packshot_url] if packshot_url else [],
        "cast_locked": False,
    }


def coerce_palette_inputs(raw_palette: Any) -> tuple[list[str] | None, Palette603010 | None]:
    """Coerces `[primary, secondary, neutral]` lists, tuples, dicts, or `Palette603010` inputs."""
    if raw_palette is None:
        return None, None
    if isinstance(raw_palette, Palette603010):
        return None, raw_palette
    if isinstance(raw_palette, (list, tuple)):
        hexes = [str(item).strip() for item in raw_palette if str(item).strip()]
        if len(hexes) != 3:
            raise ValueError(
                "palette_hexes must contain exactly 3 #RRGGBB hex strings [primary, secondary, neutral]."
            )
        return hexes, None
    if isinstance(raw_palette, dict):
        if {"primary_hex", "secondary_hex", "neutral_hex"} <= set(raw_palette.keys()):
            if {"primary_name", "secondary_name", "neutral_name"} <= set(raw_palette.keys()):
                return None, Palette603010.model_validate(raw_palette)
            return [
                str(raw_palette["primary_hex"]),
                str(raw_palette["secondary_hex"]),
                str(raw_palette["neutral_hex"]),
            ], None
        raise ValueError("Invalid palette_hexes mapping.")
    raise ValueError("Unsupported palette_hexes format.")


def materialize_media_ref_if_data_uri(
    ref: str | None,
    temp_dir: str,
    stem: str,
    storage: GcsStorageManager,
) -> str | None:
    """Validates bounded `data:image/...` URIs and writes them to confined `/tmp` PNG files."""
    if not ref or not isinstance(ref, str):
        return None
    cleaned = ref.strip()
    if not cleaned.lower().startswith("data:"):
        return cleaned
    _validate_and_decode_data_image_uri(cleaned)
    img_bytes, _ = fetch_media_bytes(cleaned, storage=storage)
    if not img_bytes:
        return None
    target_path = os.path.join(temp_dir, f"{stem}.png")
    with open(target_path, "wb") as handle:
        handle.write(img_bytes)
    return target_path


def evaluate_board_check(
    tile: StoryboardTileSpec,
    effective_prompt: str,
    image_url: str,
    cast_handle: str,
) -> SoundstageBoardCheck:
    """Runs DOMA pre-filming continuity & human-free reference isolation check on a storyboard plate."""
    if not image_url or not image_url.strip():
        return SoundstageBoardCheck(
            shot_id=tile.shot_id,
            image_url="",
            has_person_expected=tile.has_person,
            passed=False,
            flagged_reason="Empty storyboard image URL returned.",
        )
    if not tile.has_person:
        cast_leak_re = re.compile(
            rf"(?<![^\W_]){re.escape(cast_handle)}(?![^\W_])",
            re.IGNORECASE,
        )
        if cast_leak_re.search(effective_prompt):
            return SoundstageBoardCheck(
                shot_id=tile.shot_id,
                image_url=image_url,
                has_person_expected=False,
                passed=False,
                flagged_reason=f"Cast handle '{cast_handle}' leaked into human-free shot {tile.shot_id}.",
            )
    return SoundstageBoardCheck(
        shot_id=tile.shot_id,
        image_url=image_url,
        has_person_expected=tile.has_person,
        passed=True,
        flagged_reason=None,
    )


def inject_surgical_director_directive(prompt_text: str, scrubbed_note: str) -> str:
    """Injects trademark-scrubbed surgical Director Note into Block 3 SCENE INSTRUCTIONS."""
    if not scrubbed_note:
        return prompt_text
    directive_line = f"- Director Revision Note: {scrubbed_note}."
    if "### TIMELINE" in prompt_text:
        head, tail = prompt_text.split("### TIMELINE", 1)
        return f"{head.rstrip()}\n{directive_line}\n\n### TIMELINE{tail}"
    return f"{prompt_text.rstrip()}\n{directive_line}"


class SoundstageRunStore:
    """Thread-safe in-memory + GCS JSON persistence store for Mode 5 Soundstage runs."""

    def __init__(self, storage: GcsStorageManager) -> None:
        self.storage = storage
        self._lock = threading.RLock()
        self._gcs_locks: dict[str, threading.RLock] = {}
        self._runs: dict[str, SoundstageStatusResponse] = {}
        if not hasattr(self.storage, "_mock_soundstage_runs"):
            setattr(self.storage, "_mock_soundstage_runs", {})

    @property
    def _mock_cache(self) -> dict[str, Any]:
        cache = getattr(self.storage, "_mock_soundstage_runs", None)
        if not isinstance(cache, dict):
            cache = {}
            setattr(self.storage, "_mock_soundstage_runs", cache)
        return cache

    def _gcs_lock_for(self, safe_run_id: str) -> threading.RLock:
        with self._lock:
            lock = self._gcs_locks.get(safe_run_id)
            if lock is None:
                lock = threading.RLock()
                self._gcs_locks[safe_run_id] = lock
            return lock

    def save(self, status: SoundstageStatusResponse) -> SoundstageStatusResponse:
        """Snapshots state in memory under `_lock`, then performs GCS uploads under per-run I/O lock."""
        safe_run_id = validate_safe_identifier(status.run_id, "run_id")
        safe_session = validate_safe_identifier(status.session_name, "session_name")
        safe_project = validate_safe_identifier(status.project_name, "project_name")

        with self._lock:
            payload = status.model_dump(mode="json")
            snapshot = SoundstageStatusResponse.model_validate(payload)
            self._runs[safe_run_id] = snapshot
            gcs_lock = self._gcs_lock_for(safe_run_id)
            returned = snapshot.model_copy(deep=True)

        with gcs_lock:
            for blob_path, cache_key in (
                (
                    f"sessions/{safe_session}/soundstage/{safe_run_id}.json",
                    f"session:{safe_session}:{safe_run_id}",
                ),
                (
                    f"projects/{safe_project}/sessions/{safe_session}/soundstage/{safe_run_id}.json",
                    f"project:{safe_project}:{safe_session}:{safe_run_id}",
                ),
                (f"soundstage_runs/{safe_run_id}.json", f"index:{safe_run_id}"),
            ):
                self.storage._upload_json_payload(
                    blob_path,
                    payload,
                    mock_cache_dict=self._mock_cache,
                    mock_cache_key=cache_key,
                )
        return returned

    def get(
        self,
        run_id: str,
        session_name: str | None = None,
        project_name: str | None = None,
    ) -> SoundstageStatusResponse:
        """Retrieves run snapshot from memory or reloads from GCS JSON persistence."""
        safe_run_id = validate_safe_identifier(run_id, "run_id")
        safe_session = (
            validate_safe_identifier(session_name, "session_name") if session_name else None
        )
        safe_project = (
            validate_safe_identifier(project_name, "project_name") if project_name else None
        )

        with self._lock:
            cached = self._runs.get(safe_run_id)
            if cached is not None:
                return cached.model_copy(deep=True)
            gcs_lock = self._gcs_lock_for(safe_run_id)

        with gcs_lock:
            with self._lock:
                cached = self._runs.get(safe_run_id)
                if cached is not None:
                    return cached.model_copy(deep=True)

            lookup_targets: list[tuple[str, str]] = []
            if safe_project and safe_session:
                lookup_targets.append(
                    (
                        f"projects/{safe_project}/sessions/{safe_session}/soundstage/{safe_run_id}.json",
                        f"project:{safe_project}:{safe_session}:{safe_run_id}",
                    )
                )
            if safe_session:
                lookup_targets.append(
                    (
                        f"sessions/{safe_session}/soundstage/{safe_run_id}.json",
                        f"session:{safe_session}:{safe_run_id}",
                    )
                )
            lookup_targets.append((f"soundstage_runs/{safe_run_id}.json", f"index:{safe_run_id}"))

            for blob_path, cache_key in lookup_targets:
                loaded = self.storage._download_json_payload(
                    blob_path,
                    mock_cache_dict=self._mock_cache,
                    mock_cache_key=cache_key,
                )
                if isinstance(loaded, dict):
                    restored = SoundstageStatusResponse.model_validate(loaded)
                    with self._lock:
                        self._runs[safe_run_id] = restored
                    return restored.model_copy(deep=True)

        raise SoundstageNotFoundError(f"Soundstage run '{safe_run_id}' not found.")

    def append_event(
        self,
        status: SoundstageStatusResponse,
        *,
        stage: str,
        progress_pct: int,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> SoundstageStatusResponse:
        """Appends a monotonic progress event, updates stage/progress, and persists to GCS."""
        with self._lock:
            monotonic_pct = min(100, max(status.progress_pct, max(0, int(progress_pct))))
            next_event_id = (status.events[-1].event_id + 1) if status.events else 1
            status.stage = stage
            status.progress_pct = monotonic_pct
            status.events.append(
                SoundstageProgressEvent(
                    event_id=next_event_id,
                    stage=stage,
                    progress_pct=monotonic_pct,
                    message=message,
                    timestamp=utc_now_iso(),
                    data=dict(data or {}),
                )
            )
        return self.save(status)


def rebuild_plan_preserving_state(
    planner: SoundstageThreeActPlanner,
    plan: SoundstageCommercialPlan,
    *,
    lead_override: CharacterRoleModel | None = None,
    packshot_url: str | None = None,
    emblem_url: str | None = None,
) -> SoundstageCommercialPlan:
    """Recompiles plan so identity descriptors and 4-block prompts stay synchronized after cast/kit updates."""
    return planner.build_plan(
        subject=plan.subject,
        offering=plan.offering,
        territory=plan.territory.place_name,
        moment=plan.moment,
        language=plan.language,
        tagline=plan.identity.display_tagline,
        lead_character_override=lead_override or plan.lead_character,
        packshot_url=packshot_url or plan.hero_offering_role.reference_url,
        emblem_url=emblem_url,
        territory_override=plan.territory,
        palette_override=plan.palette,
    )


def _invalidate_prefilming_boards(run: SoundstageStatusResponse) -> None:
    if run.deliverables is None and not run.acts:
        run.boards.clear()
        run.board_checks.clear()
        run.flagged_shot_ids.clear()
        run.auto_advance_filming = False


def execute_cast_and_kit_update(
    run: SoundstageStatusResponse,
    req: SoundstageCastRequest,
    *,
    planner: SoundstageThreeActPlanner,
    keyframe_client: KeyframeClient,
    storage: GcsStorageManager,
    store: SoundstageRunStore,
) -> SoundstageStatusResponse:
    """Executes lead cast turnaround generation, vault hydration, or emblem/packshot synthesis."""
    plan = run.plan
    subj, off = plan.identity.display_subject, plan.identity.display_offering
    next_stage = "completed" if run.deliverables is not None else "cast_ready"
    target_pct = 100 if run.deliverables is not None else 20

    if req.action in ("generate", "recast", "older", "younger", "tweak"):
        wardrobe_delta = (
            scrub_commercial_note(req.wardrobe_note, subj, off)
            if req.wardrobe_note
            else plan.lead_character.wardrobe
        )
        tweak_delta = scrub_commercial_note(req.tweak_note, subj, off) if req.tweak_note else ""
        age_modifier = {
            "older": "distinguished mature editorial poise (+12 years seasoned presence)",
            "younger": "fresh contemporary rising-talent energy (younger editorial presence)",
            "recast": f"distinctive fresh casting silhouette variation {uuid.uuid4().hex[:6]}",
        }.get(req.action, "")

        updated_lead = plan.lead_character.model_copy(
            update={"wardrobe": wardrobe_delta or plan.lead_character.wardrobe}
        )
        plan = rebuild_plan_preserving_state(
            planner,
            plan,
            lead_override=updated_lead,
            packshot_url=run.reference_kit.get("packshot_url"),
            emblem_url=run.reference_kit.get("emblem_url"),
        )

        extra_clauses = [c for c in (age_modifier, tweak_delta) if c]
        enriched_desc = (
            f"{plan.identity.omni_safe_cast_description}; {', '.join(extra_clauses)}"
            if extra_clauses
            else plan.identity.omni_safe_cast_description
        )
        enriched_desc = scrub_commercial_note(enriched_desc, subj, off)
        plan.identity.omni_safe_cast_description = enriched_desc
        plan.lead_character.description = enriched_desc

        candidates = [
            str(
                keyframe_client.generate_character_reference_sheet(
                    character_name=plan.identity.omni_safe_cast_handle,
                    description=(
                        enriched_desc
                        if req.candidate_count == 1
                        else f"{enriched_desc} (casting take {idx + 1})"
                    ),
                    aesthetic_tags=list(plan.lead_character.aesthetic_tags),
                    session_id=run.session_name,
                    style_preset="2K photorealistic commercial cinema turnaround",
                )
            )
            for idx in range(req.candidate_count)
        ]
        plan.lead_character.reference_url = candidates[0]
        run.plan = plan
        run.reference_kit.update(
            lead_cast_url=candidates[0],
            lead_cast_candidates=candidates,
            cast_locked=True,
        )
        _invalidate_prefilming_boards(run)
        return store.append_event(
            run,
            stage=next_stage,
            progress_pct=target_pct,
            message=f"Updated lead cast reference sheet ({req.action}) for {plan.identity.omni_safe_cast_handle}.",
            data={"action": req.action, "candidate_count": len(candidates)},
        )

    if req.action == "vault":
        slug = (req.vault_character_slug or "").strip()
        if not slug:
            raise ValueError("vault_character_slug is required when action='vault'.")
        vault_char = storage.load_character(slug, session_id=run.session_name)
        if not isinstance(vault_char, dict):
            target_slug = storage._slugify(slug)
            project_chars = storage.list_project_characters(project_id=run.project_name)
            vault_char = next(
                (
                    c
                    for c in (project_chars or [])
                    if isinstance(c, dict)
                    and (
                        storage._slugify(str(c.get("name", ""))) == target_slug
                        or storage._slugify(str(c.get("role_id", ""))) == target_slug
                    )
                ),
                None,
            )
        if not isinstance(vault_char, dict):
            raise SoundstageNotFoundError(
                f"Vault character '{slug}' not found in session or library."
            )

        raw_name = str(vault_char.get("name", "") or "Vanguard")
        raw_wardrobe = scrub_commercial_note(
            str(vault_char.get("wardrobe", "") or plan.lead_character.wardrobe), subj, off
        )
        raw_voice = sanitize_single_line_field(
            str(vault_char.get("voice_style", "") or plan.lead_character.voice_style)
        )
        raw_ref_url = str(vault_char.get("reference_url", "") or "").strip()
        if not raw_ref_url:
            safe_identity = DualLayerIdentityAbstractor.abstract(
                subject=subj,
                offering=off,
                physics=plan.physics,
                palette=plan.palette,
                lead_name=raw_name,
                lead_wardrobe=raw_wardrobe,
                tagline=plan.identity.display_tagline,
            )
            raw_ref_url = str(
                keyframe_client.generate_character_reference_sheet(
                    character_name=safe_identity.omni_safe_cast_handle,
                    description=safe_identity.omni_safe_cast_description,
                    session_id=run.session_name,
                )
            )

        plan = rebuild_plan_preserving_state(
            planner,
            plan,
            lead_override=CharacterRoleModel(
                role_id="Role A",
                name=raw_name,
                description="",
                reference_url=raw_ref_url,
                wardrobe=raw_wardrobe,
                voice_style=raw_voice,
            ),
            packshot_url=run.reference_kit.get("packshot_url"),
            emblem_url=run.reference_kit.get("emblem_url"),
        )
        plan.lead_character.reference_url = raw_ref_url
        run.plan = plan
        run.reference_kit.update(
            lead_cast_url=raw_ref_url,
            lead_cast_candidates=[raw_ref_url],
            cast_locked=True,
        )
        _invalidate_prefilming_boards(run)
        return store.append_event(
            run,
            stage=next_stage,
            progress_pct=target_pct,
            message=f"Hydrated vault character as safe cast handle '{plan.identity.omni_safe_cast_handle}'.",
            data={"action": "vault", "cast_handle": plan.identity.omni_safe_cast_handle},
        )

    if req.custom_image_url:
        kit_candidates = [validate_confined_custom_image_url(req.custom_image_url)]
    else:
        base_prompt = (
            f"Minimalist geometric sculptural studio emblem mark on matte "
            f"{plan.palette.neutral_name} ({plan.palette.neutral_hex}) surface with "
            f"{plan.palette.primary_name} ({plan.palette.primary_hex}) metallic inlay, "
            "clean centered graphic composition, zero printed letters, zero text."
            if req.action == "emblem"
            else (
                f"Studio hero commercial packshot of {plan.identity.omni_safe_offering_descriptor} "
                f"resting centered on {plan.palette.neutral_name} ({plan.palette.neutral_hex}) plinth, "
                f"60% {plan.palette.primary_name} ({plan.palette.primary_hex}) architectural backdrop, "
                "8k commercial macro photography, zero people, zero text."
            )
        )
        if req.tweak_note:
            base_prompt = f"{base_prompt} {scrub_commercial_note(req.tweak_note, subj, off)}"
        kit_candidates = [
            str(
                keyframe_client.generate_keyframe_image(
                    prompt=(
                        base_prompt
                        if req.candidate_count == 1
                        else f"{base_prompt} (variation {idx + 1})"
                    ),
                    aspect_ratio="16:9",
                    session_id=run.session_name,
                )
            )
            for idx in range(req.candidate_count)
        ]

    chosen = kit_candidates[0]
    run.reference_kit[f"{req.action}_url"] = chosen
    run.reference_kit[f"{req.action}_candidates"] = kit_candidates
    if req.action == "packshot":
        run.plan.hero_offering_role.reference_url = chosen
        _invalidate_prefilming_boards(run)
    return store.append_event(
        run,
        stage=next_stage,
        progress_pct=target_pct,
        message=f"Prepared {req.action} reference asset ({len(kit_candidates)} candidate(s)).",
        data={"action": req.action, "candidate_count": len(kit_candidates)},
    )


def ensure_reference_kit_anchors(
    run: SoundstageStatusResponse,
    keyframe_client: KeyframeClient,
) -> None:
    """Auto-populates stylized lead cast and hero packshot anchors if not yet present."""
    plan = run.plan
    if not run.reference_kit.get("lead_cast_url"):
        lead_url = str(
            keyframe_client.generate_character_reference_sheet(
                character_name=plan.identity.omni_safe_cast_handle,
                description=plan.identity.omni_safe_cast_description,
                aesthetic_tags=list(plan.lead_character.aesthetic_tags),
                session_id=run.session_name,
                style_preset="2K photorealistic commercial cinema turnaround",
            )
        )
        run.reference_kit.update(
            lead_cast_url=lead_url,
            lead_cast_candidates=[lead_url],
            cast_locked=True,
        )
        plan.lead_character.reference_url = lead_url

    if not run.reference_kit.get("packshot_url"):
        pack_url = str(
            keyframe_client.generate_keyframe_image(
                prompt=(
                    f"Studio hero commercial packshot of {plan.identity.omni_safe_offering_descriptor} "
                    f"on {plan.palette.neutral_name} ({plan.palette.neutral_hex}) hero plinth, "
                    "zero people, zero hands, zero text."
                ),
                aspect_ratio="16:9",
                session_id=run.session_name,
            )
        )
        run.reference_kit.update(packshot_url=pack_url, packshot_candidates=[pack_url])
        plan.hero_offering_role.reference_url = pack_url


def execute_boards_synthesis(
    run: SoundstageStatusResponse,
    req: SoundstageBoardsRequest,
    *,
    keyframe_client: KeyframeClient,
    store: SoundstageRunStore,
) -> SoundstageStatusResponse:
    """Synthesizes 9 storyboard plates (or 1 target shot_id) with strict person-free reference isolation."""
    if req.manual_board_gate is not None:
        run.manual_board_gate = req.manual_board_gate

    ensure_reference_kit_anchors(run, keyframe_client)
    plan = run.plan
    lead_cast_url = str(run.reference_kit["lead_cast_url"])
    packshot_url = str(run.reference_kit["packshot_url"])
    subj, off = plan.identity.display_subject, plan.identity.display_offering
    scrubbed_note = scrub_commercial_note(req.director_note, subj, off) if req.director_note else ""

    tiles_by_id = {tile.shot_id: tile for tile in plan.boards}
    target_tiles = (
        [tiles_by_id[req.shot_id]]
        if req.shot_id is not None
        else [tiles_by_id[sid] for sid in CANONICAL_SUBSHOT_IDS]
    )

    def _render_tile(tile: StoryboardTileSpec) -> tuple[str, str, SoundstageBoardCheck]:
        prompt_text = (
            f"{tile.image_prompt} Director visual refinement: {scrubbed_note}."
            if scrubbed_note
            else tile.image_prompt
        )
        prompt_text = scrub_offering_trademarks(prompt_text, subject=subj, offering=off)
        if tile.has_person:
            refs = [
                lead_cast_url,
                *([packshot_url] if tile.act_number in (2, 3) and packshot_url else []),
            ]
            chars: list[Any] | None = [plan.lead_character]
        else:
            refs = [packshot_url] if packshot_url else []
            chars = None

        img_url = str(
            keyframe_client.generate_keyframe_image(
                prompt=prompt_text,
                reference_image_urls=refs,
                characters=chars,
                aspect_ratio="16:9",
                session_id=run.session_name,
            )
        )
        return (
            tile.shot_id,
            img_url,
            evaluate_board_check(
                tile=tile,
                effective_prompt=prompt_text,
                image_url=img_url,
                cast_handle=plan.identity.omni_safe_cast_handle,
            ),
        )

    with ThreadPoolExecutor(max_workers=min(4, max(1, len(target_tiles)))) as pool:
        rendered_results = list(pool.map(_render_tile, target_tiles))

    for shot_id, img_url, check in rendered_results:
        run.boards[shot_id] = img_url
        run.board_checks[shot_id] = check

    run.flagged_shot_ids = [
        sid
        for sid in CANONICAL_SUBSHOT_IDS
        if sid in run.board_checks and not run.board_checks[sid].passed
    ]
    run.auto_advance_filming = (len(run.flagged_shot_ids) == 0) and (not run.manual_board_gate)
    if run.deliverables is not None:
        next_stage = "completed"
        target_pct = 100
    elif run.stage == "filming_acts":
        next_stage = "filming_acts"
        target_pct = max(run.progress_pct, 34)
    else:
        next_stage = "boards_ready"
        target_pct = 30
    return store.append_event(
        run,
        stage=next_stage,
        progress_pct=target_pct,
        message=(
            f"Generated {len(rendered_results)} storyboard plate(s); "
            f"{len(run.flagged_shot_ids)} continuity flag(s)."
        ),
        data={
            "boards_rendered": [sid for sid, _, _ in rendered_results],
            "flagged_shot_ids": list(run.flagged_shot_ids),
            "auto_advance_filming": run.auto_advance_filming,
        },
    )
