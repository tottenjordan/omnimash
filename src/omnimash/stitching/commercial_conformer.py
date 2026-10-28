"""Mode 5: Commercial Soundstage Post-Production Conformer, Multi-Format Cutdowns & Campaign Packaging.

Implements:
- `SubShotTrimSpec`, `build_default_subshot_specs`, `normalize_subshot_specs`
- `ConformedDeliverables`
- `CommercialConformer` (`render_brand_end_card_clip`, `conform_all_formats`, `reconform_timeline`,
  `build_campaign_package_zip`)
"""

from __future__ import annotations

from collections.abc import Sequence
import logging
import math
import os
import re
import tempfile
from typing import Any, Literal
import uuid
import zipfile

from pydantic import BaseModel, Field, field_validator, model_validator

from omnimash.config import settings
from omnimash.stitching.audio_overlay import apply_dialogue_audio_ducking
from omnimash.stitching.end_card_renderer import (
    _contrast_ratio,
    _parse_hex_rgb,
    _select_end_card_palette,
    concatenate_normalized_av_segments,
    extract_normalized_subshot_segment,
    populate_campaign_zip_archive,
    probe_clip_media_info,
    render_brand_end_card_mp4,
    resolve_confined_media_source,
    serialize_manifest_field as _serialize_manifest_field,
)
from omnimash.stitching.stitcher import VideoStitcher
from omnimash.storage.gcs import GcsStorageManager, validate_safe_identifier

logger = logging.getLogger(__name__)

CANONICAL_SUBSHOT_IDS: tuple[str, ...] = (
    "1.1",
    "1.2",
    "1.3",
    "2.1",
    "2.2",
    "2.3",
    "3.1",
    "3.2",
    "3.3",
)

MIN_SUBSHOT_DURATION_SEC: float = 0.5
MAX_BUMPER_SUBSHOT_DURATION_SEC: float = 2.4
PREFERRED_CUTDOWN_15S_SUBSHOTS: tuple[str, ...] = ("1.1", "2.1", "2.2", "2.3", "3.2")
PREFERRED_BUMPER_6S_SUBSHOTS: tuple[str, ...] = ("2.2", "2.3")

_CANONICAL_BEAT_TIMINGS: dict[str, tuple[float, float]] = {
    "1": (0.0, 3.3),
    "2": (3.3, 3.4),
    "3": (6.7, 3.3),
}

_CANONICAL_SUBSHOT_DEFAULTS: dict[str, tuple[int, float, float]] = {
    shot_id: (
        int(shot_id.split(".")[0]) - 1,
        _CANONICAL_BEAT_TIMINGS[shot_id.split(".")[1]][0],
        _CANONICAL_BEAT_TIMINGS[shot_id.split(".")[1]][1],
    )
    for shot_id in CANONICAL_SUBSHOT_IDS
}


class SubShotTrimSpec(BaseModel):
    """NLE trim and bypass specification for one of the 9 canonical Mode 5 Soundstage sub-shots."""

    shot_id: str
    act_index: int = -1
    default_start_sec: float = -1.0
    default_duration_sec: float = -1.0
    trim_in_sec: float = 0.0
    trim_out_sec: float = 0.0
    bypassed: bool = False

    @model_validator(mode="before")
    @classmethod
    def _populate_canonical_defaults(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        patched = dict(data)
        raw_id = str(patched.get("shot_id", "")).strip()
        if raw_id in _CANONICAL_SUBSHOT_DEFAULTS:
            exp_act, def_start, def_dur = _CANONICAL_SUBSHOT_DEFAULTS[raw_id]
            if "act_index" not in patched or patched["act_index"] is None:
                patched["act_index"] = exp_act
            if "default_start_sec" not in patched or patched["default_start_sec"] is None:
                patched["default_start_sec"] = def_start
            if "default_duration_sec" not in patched or patched["default_duration_sec"] is None:
                patched["default_duration_sec"] = def_dur
        return patched

    @field_validator("act_index", mode="before")
    @classmethod
    def _reject_bool_act_index(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("act_index must be an integer (0, 1, or 2), not bool.")
        return value

    @field_validator("shot_id")
    @classmethod
    def _validate_shot_id(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if cleaned not in CANONICAL_SUBSHOT_IDS:
            raise ValueError(f"Invalid shot_id '{value}': expected one of {CANONICAL_SUBSHOT_IDS}.")
        return cleaned

    @field_validator("default_start_sec", "default_duration_sec", "trim_in_sec", "trim_out_sec")
    @classmethod
    def _validate_finite_float(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError(f"Timing value must be finite, got {value!r}.")
        return float(value)

    @model_validator(mode="after")
    def _validate_act_alignment(self) -> SubShotTrimSpec:
        expected_act = int(self.shot_id.split(".")[0]) - 1
        if self.act_index not in (0, 1, 2) or self.act_index != expected_act:
            raise ValueError(
                f"act_index {self.act_index} does not match shot_id '{self.shot_id}' "
                f"(expected {expected_act})."
            )
        if self.default_start_sec < 0.0:
            raise ValueError("default_start_sec must be >= 0.0.")
        if self.default_duration_sec < MIN_SUBSHOT_DURATION_SEC:
            raise ValueError(f"default_duration_sec must be >= {MIN_SUBSHOT_DURATION_SEC}s.")
        return self

    def effective_window(self, act_duration_sec: float = 10.0) -> tuple[float, float]:
        """Returns `(start_sec, duration_sec)` clamped within `[0.0, act_duration_sec]` (`>= 0.5s`)."""
        if (
            isinstance(act_duration_sec, bool)
            or not isinstance(act_duration_sec, (int, float))
            or not math.isfinite(act_duration_sec)
            or act_duration_sec < MIN_SUBSHOT_DURATION_SEC
        ):
            raise ValueError(
                f"act_duration_sec must be a finite number >= {MIN_SUBSHOT_DURATION_SEC}s, "
                f"got {act_duration_sec!r}."
            )
        max_start = max(0.0, act_duration_sec - MIN_SUBSHOT_DURATION_SEC)
        start = min(max(0.0, self.default_start_sec + self.trim_in_sec), max_start)
        raw_end = self.default_start_sec + self.default_duration_sec - self.trim_out_sec
        end = min(
            max(start + MIN_SUBSHOT_DURATION_SEC, raw_end),
            max(start + MIN_SUBSHOT_DURATION_SEC, act_duration_sec),
        )
        return (round(start, 3), round(end - start, 3))


def build_default_subshot_specs() -> list[SubShotTrimSpec]:
    """Returns the 9 canonical `SubShotTrimSpec` entries (`1.1`..`3.3`) summing to 10.0s per act."""
    return [
        SubShotTrimSpec(
            shot_id=shot_id,
            act_index=_CANONICAL_SUBSHOT_DEFAULTS[shot_id][0],
            default_start_sec=_CANONICAL_SUBSHOT_DEFAULTS[shot_id][1],
            default_duration_sec=_CANONICAL_SUBSHOT_DEFAULTS[shot_id][2],
        )
        for shot_id in CANONICAL_SUBSHOT_IDS
    ]


def normalize_subshot_specs(
    specs: Sequence[SubShotTrimSpec | dict[str, Any]] | None,
) -> list[SubShotTrimSpec]:
    """Merges partial or full NLE overrides onto the 9 canonical `1.1`..`3.3` sub-shot specs."""
    by_id: dict[str, SubShotTrimSpec] = {s.shot_id: s for s in build_default_subshot_specs()}
    if not specs:
        return [by_id[sid] for sid in CANONICAL_SUBSHOT_IDS]

    for item in specs:
        if isinstance(item, SubShotTrimSpec):
            by_id[item.shot_id] = item.model_copy()
        elif isinstance(item, dict):
            raw_id = str(item.get("shot_id", "")).strip()
            if raw_id not in by_id:
                raise ValueError(
                    f"Invalid shot_id '{raw_id}' in subshot_specs: expected one of {CANONICAL_SUBSHOT_IDS}."
                )
            merged = by_id[raw_id].model_dump()
            for key, val in item.items():
                if val is not None:
                    merged[key] = val
            by_id[raw_id] = SubShotTrimSpec(**merged)
        else:
            raise ValueError(
                f"Expected SubShotTrimSpec or dict in subshot_specs, got {type(item).__name__}."
            )

    return [by_id[sid] for sid in CANONICAL_SUBSHOT_IDS]


def _unlink_paths_quietly(paths: Sequence[str | None]) -> None:
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


class ConformedDeliverables(BaseModel):
    """Conformed Mode 5 Commercial Soundstage multi-format video deliverables and timeline metadata."""

    master_30s_16x9_url: str
    cutdown_15s_9x16_url: str
    bumper_6s_9x16_url: str
    end_card_clip_url: str
    end_card_9x16_url: str
    local_paths: dict[str, str] = Field(default_factory=dict)
    gcs_uris: dict[str, str] = Field(default_factory=dict)
    active_subshot_ids: list[str] = Field(default_factory=list)
    active_subshot_count: int
    total_duration_sec: float
    subshot_specs: list[SubShotTrimSpec] = Field(default_factory=list)


class CommercialConformer:
    """Post-production conformer rendering brand end-cards, 30s/15s/6s multi-format cuts, and campaign ZIPs."""

    def __init__(
        self,
        mock_mode: bool | None = None,
        bucket_name: str | None = None,
        storage: GcsStorageManager | None = None,
        stitcher: VideoStitcher | None = None,
    ) -> None:
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self.storage = storage or GcsStorageManager(
            bucket_name=bucket_name, mock_mode=self.mock_mode
        )
        self.stitcher = stitcher or VideoStitcher(
            mock_mode=self.mock_mode, bucket_name=bucket_name, storage=self.storage
        )

    @property
    def _ffmpeg_timeout(self) -> float:
        return float(getattr(settings, "ffmpeg_timeout_seconds", 120.0))

    def render_brand_end_card_clip(
        self,
        display_subject: str,
        display_tagline: str = "",
        primary_hex: str = "#E11D48",
        secondary_hex: str = "#D4C5B0",
        neutral_hex: str = "#111318",
        emblem_path: str | None = None,
        duration_seconds: float = 2.0,
        aspect_ratio: Literal["16:9", "9:16"] = "16:9",
        output_dir: str = "/tmp",
    ) -> str:
        """Renders an editorial brand lockup end-card MP4 clip (`1280x720` or `720x1280`) at 24fps."""
        return render_brand_end_card_mp4(
            display_subject,
            display_tagline,
            primary_hex,
            secondary_hex,
            neutral_hex,
            emblem_path,
            duration_seconds,
            aspect_ratio,
            output_dir,
            self.mock_mode,
            self.storage,
            self._ffmpeg_timeout,
        )

    def _probe_clip_info(self, clip_path: str) -> tuple[bool, float]:
        """Probes `(has_audio_stream, duration_sec)` via ffprobe with safe `(True, 10.0)` fallback."""
        return probe_clip_media_info(clip_path, timeout_sec=self._ffmpeg_timeout)

    def _extract_subshot_segment(
        self,
        source_clip: str,
        start_sec: float,
        duration_sec: float,
        aspect_ratio: Literal["16:9", "9:16"],
        has_audio: bool,
        output_path: str,
    ) -> str:
        """Extracts a normalized 24fps H.264 + stereo 44.1kHz AAC sub-shot segment."""
        return extract_normalized_subshot_segment(
            source_clip,
            start_sec,
            duration_sec,
            aspect_ratio,
            has_audio,
            output_path,
            self._ffmpeg_timeout,
        )

    def _concatenate_normalized_segments(
        self,
        segment_paths: list[str],
        output_path: str,
        temp_dir: str,
        master_audio_path: str | None = None,
    ) -> str:
        """Concatenates normalized video+audio segments via FFmpeg concat demuxer with re-encode fallback."""
        return concatenate_normalized_av_segments(
            segment_paths,
            output_path,
            temp_dir,
            master_audio_path,
            self.storage,
            self.mock_mode,
            self._ffmpeg_timeout,
        )

    def _upload_deliverable(
        self,
        local_path: str,
        session_id: str | None,
        project_id: str | None,
        content_type: str = "video/mp4",
    ) -> tuple[str, str]:
        """Uploads a conformed deliverable to GCS `final_masters` and returns `(public_url, gcs_uri)`."""
        blob_path = self.storage.build_session_blob_path(
            session_id=session_id,
            category="final_masters",
            filename=os.path.basename(local_path),
            project_id=project_id,
        )
        public_url = self.storage.upload_file(
            local_path,
            destination_blob_name=blob_path,
            session_id=session_id,
            category="final_masters",
            content_type=content_type,
            project_id=project_id,
        )
        return (public_url, self.storage.get_gcs_uri(blob_path))

    def _write_zip_media_entry(
        self,
        zf: zipfile.ZipFile,
        source_ref: str,
        arcname: str,
        temp_dir: str,
        output_dir: str,
        mock_fallback_bytes: bytes,
    ) -> bool:
        """Resolves a confined local or GCS media source and writes it into `zf` under `arcname`."""
        resolved = resolve_confined_media_source(
            source_ref, temp_dir, output_dir, self.storage, self.mock_mode
        )
        if resolved and os.path.isfile(resolved):
            zf.write(resolved, arcname=arcname)
            return True
        if self.mock_mode and resolved:
            zf.writestr(arcname, mock_fallback_bytes)
            return True
        return False

    def _has_valid_audio_ref(self, ref: str | None) -> bool:
        return bool(ref and self.stitcher._is_valid_audio_reference(ref))

    def _resolve_confined_audio_ref(
        self, ref: str | None, temp_dir: str, output_dir: str
    ) -> str | None:
        if not self._has_valid_audio_ref(ref):
            return None
        return resolve_confined_media_source(
            ref, temp_dir, output_dir, self.storage, self.mock_mode
        )

    def _resolve_master_audio(
        self,
        safe_bgm: str | None,
        safe_vo: str | None,
        temp_dir: str,
        fallback_dialogue_path: str | None = None,
    ) -> str | None:
        dialogue_src = safe_vo or fallback_dialogue_path
        if safe_bgm and dialogue_src:
            return apply_dialogue_audio_ducking(
                music_path=safe_bgm,
                dialogue_path=dialogue_src,
                output_dir=temp_dir,
                ducking_db=-18.0,
                mock_mode=self.mock_mode,
                storage=self.storage,
            )
        return safe_bgm or safe_vo

    def conform_all_formats(
        self,
        act_clips: list[str],
        display_subject: str,
        display_tagline: str = "",
        primary_hex: str = "#E11D48",
        secondary_hex: str = "#D4C5B0",
        neutral_hex: str = "#111318",
        emblem_path: str | None = None,
        subshot_specs: Sequence[SubShotTrimSpec | dict[str, Any]] | None = None,
        background_music_path: str | None = None,
        narrator_audio_path: str | None = None,
        end_card_duration_sec: float = 2.0,
        output_dir: str = "/tmp",
        session_id: str | None = None,
        project_id: str | None = None,
    ) -> ConformedDeliverables:
        """Conforms 3 continuous act clips into 30s 16:9 Master, 15s 9:16 Cutdown, and 6s 9:16 Bumper."""
        if session_id is not None:
            session_id = validate_safe_identifier(session_id, "session_id")
        if project_id is not None:
            project_id = validate_safe_identifier(project_id, "project_id")
        if (
            isinstance(end_card_duration_sec, bool)
            or not isinstance(end_card_duration_sec, (int, float))
            or not math.isfinite(end_card_duration_sec)
            or end_card_duration_sec <= 0.0
        ):
            raise ValueError(
                f"end_card_duration_sec must be a finite positive number, got {end_card_duration_sec!r}."
            )

        if not act_clips or not any(isinstance(c, str) and c.strip() for c in act_clips):
            raise ValueError("conform_all_formats requires at least one non-empty act clip.")

        normalized_specs = normalize_subshot_specs(subshot_specs)
        active_specs = [
            spec
            for spec in normalized_specs
            if not spec.bypassed
            and 0 <= spec.act_index < len(act_clips)
            and isinstance(act_clips[spec.act_index], str)
            and act_clips[spec.act_index].strip()
        ]
        if not active_specs:
            raise ValueError(
                "At least one sub-shot must remain active (not bypassed) with an available act clip."
            )

        os.makedirs(output_dir, exist_ok=True)
        safe_end_dur = max(0.2, float(end_card_duration_sec))
        cutdown_end_dur = min(safe_end_dur, 1.8)
        bumper_end_dur = min(safe_end_dur, 1.2)

        cutdown_specs = [
            s for s in active_specs if s.shot_id in PREFERRED_CUTDOWN_15S_SUBSHOTS
        ] or active_specs[:5]
        bumper_specs = [
            s for s in active_specs if s.shot_id in PREFERRED_BUMPER_6S_SUBSHOTS
        ] or active_specs[:2]

        uid = uuid.uuid4().hex[:8]
        master_path = os.path.join(output_dir, f"30s_16x9_master_{uid}.mp4")
        cutdown_path = os.path.join(output_dir, f"15s_9x16_cutdown_{uid}.mp4")
        bumper_path = os.path.join(output_dir, f"6s_9x16_bumper_{uid}.mp4")
        created_outputs: list[str] = [master_path, cutdown_path, bumper_path]

        try:
            with tempfile.TemporaryDirectory() as scoped_temp_dir:
                resolved_acts: dict[int, str] = {}
                act_info: dict[int, tuple[bool, float]] = {}
                for act_idx in sorted({s.act_index for s in active_specs}):
                    resolved = resolve_confined_media_source(
                        act_clips[act_idx],
                        temp_dir=scoped_temp_dir,
                        output_dir=output_dir,
                        storage=self.storage,
                        mock_mode=self.mock_mode,
                    )
                    if not resolved or (not self.mock_mode and not os.path.isfile(resolved)):
                        raise ValueError(
                            f"Unable to resolve confined act clip at index {act_idx}: "
                            f"{act_clips[act_idx]!r}"
                        )
                    resolved_acts[act_idx] = resolved
                    if not self.mock_mode:
                        act_info[act_idx] = self._probe_clip_info(resolved)

                resolved_emblem = (
                    resolve_confined_media_source(
                        emblem_path,
                        temp_dir=scoped_temp_dir,
                        output_dir=output_dir,
                        storage=self.storage,
                        mock_mode=self.mock_mode,
                    )
                    if emblem_path and isinstance(emblem_path, str) and emblem_path.strip()
                    else None
                )
                end_card_kwargs: dict[str, Any] = {
                    "display_subject": display_subject,
                    "display_tagline": display_tagline,
                    "primary_hex": primary_hex,
                    "secondary_hex": secondary_hex,
                    "neutral_hex": neutral_hex,
                    "emblem_path": resolved_emblem,
                }
                end_card_16x9 = self.render_brand_end_card_clip(
                    **end_card_kwargs,
                    duration_seconds=safe_end_dur,
                    aspect_ratio="16:9",
                    output_dir=output_dir,
                )
                created_outputs.append(end_card_16x9)
                end_card_9x16 = self.render_brand_end_card_clip(
                    **end_card_kwargs,
                    duration_seconds=cutdown_end_dur,
                    aspect_ratio="9:16",
                    output_dir=output_dir,
                )
                created_outputs.append(end_card_9x16)

                safe_bgm = self._resolve_confined_audio_ref(
                    background_music_path, scoped_temp_dir, output_dir
                )
                safe_vo = self._resolve_confined_audio_ref(
                    narrator_audio_path, scoped_temp_dir, output_dir
                )

                if self.mock_mode:
                    self._resolve_master_audio(
                        safe_bgm,
                        safe_vo,
                        scoped_temp_dir,
                        fallback_dialogue_path=resolved_acts[active_specs[0].act_index],
                    )
                    total_duration = round(
                        sum(s.effective_window(10.0)[1] for s in active_specs) + safe_end_dur,
                        3,
                    )
                    for out_file, label, selected in (
                        (master_path, "30s_16x9_master", active_specs),
                        (cutdown_path, "15s_9x16_cutdown", cutdown_specs),
                        (bumper_path, "6s_9x16_bumper", bumper_specs),
                    ):
                        ids_csv = ",".join(s.shot_id for s in selected)
                        with open(out_file, "w", encoding="utf-8") as f:
                            f.write(f"mock {label} mp4 [{ids_csv}]")
                else:
                    seg_cache: dict[tuple[str, str, float, float], str] = {}

                    def _get_segment(
                        spec: SubShotTrimSpec,
                        aspect: Literal["16:9", "9:16"],
                        max_dur_cap: float | None = None,
                    ) -> tuple[str, float]:
                        has_aud, raw_act_dur = act_info[spec.act_index]
                        act_dur = max(MIN_SUBSHOT_DURATION_SEC, raw_act_dur)
                        start_s, dur_s = spec.effective_window(act_duration_sec=act_dur)
                        if max_dur_cap is not None:
                            dur_s = round(min(dur_s, max_dur_cap), 3)
                        cache_key = (spec.shot_id, aspect, start_s, dur_s)
                        if cache_key not in seg_cache:
                            seg_name = f"seg_{spec.shot_id.replace('.', '_')}_{aspect.replace(':', 'x')}_{uuid.uuid4().hex[:6]}.mp4"
                            seg_out = os.path.join(scoped_temp_dir, seg_name)
                            self._extract_subshot_segment(
                                source_clip=resolved_acts[spec.act_index],
                                start_sec=start_s,
                                duration_sec=dur_s,
                                aspect_ratio=aspect,
                                has_audio=has_aud,
                                output_path=seg_out,
                            )
                            seg_cache[cache_key] = seg_out
                        return (seg_cache[cache_key], dur_s)

                    master_pairs = [_get_segment(spec, "16:9") for spec in active_specs]
                    master_segments = [p for p, _ in master_pairs] + [end_card_16x9]
                    total_duration = round(sum(d for _, d in master_pairs) + safe_end_dur, 3)

                    cutdown_segments = [_get_segment(spec, "9:16")[0] for spec in cutdown_specs] + [
                        end_card_9x16
                    ]

                    bumper_end_card = (
                        end_card_9x16
                        if abs(bumper_end_dur - cutdown_end_dur) < 1e-3
                        else self.render_brand_end_card_clip(
                            **end_card_kwargs,
                            duration_seconds=bumper_end_dur,
                            aspect_ratio="9:16",
                            output_dir=scoped_temp_dir,
                        )
                    )
                    bumper_segments = [
                        _get_segment(spec, "9:16", max_dur_cap=MAX_BUMPER_SUBSHOT_DURATION_SEC)[0]
                        for spec in bumper_specs
                    ] + [bumper_end_card]

                    if safe_bgm and not safe_vo:
                        raw_master_path = os.path.join(scoped_temp_dir, f"raw_master_{uid}.mp4")
                        self._concatenate_normalized_segments(
                            master_segments, raw_master_path, scoped_temp_dir
                        )
                        ducked_master_audio = self._resolve_master_audio(
                            safe_bgm,
                            None,
                            scoped_temp_dir,
                            fallback_dialogue_path=raw_master_path,
                        )
                        self._concatenate_normalized_segments(
                            [raw_master_path], master_path, scoped_temp_dir, ducked_master_audio
                        )
                    else:
                        master_audio = self._resolve_master_audio(
                            safe_bgm, safe_vo, scoped_temp_dir
                        )
                        self._concatenate_normalized_segments(
                            master_segments, master_path, scoped_temp_dir, master_audio
                        )
                    self._concatenate_normalized_segments(
                        cutdown_segments, cutdown_path, scoped_temp_dir
                    )
                    self._concatenate_normalized_segments(
                        bumper_segments, bumper_path, scoped_temp_dir
                    )

            local_paths = {
                "master_30s_16x9": master_path,
                "cutdown_15s_9x16": cutdown_path,
                "bumper_6s_9x16": bumper_path,
                "end_card_16x9": end_card_16x9,
                "end_card_9x16": end_card_9x16,
            }
            urls: dict[str, str] = {}
            gcs_uris: dict[str, str] = {}
            for key, lpath in local_paths.items():
                urls[key], gcs_uris[key] = self._upload_deliverable(
                    local_path=lpath,
                    session_id=session_id,
                    project_id=project_id,
                    content_type="video/mp4",
                )
        except Exception:
            _unlink_paths_quietly(created_outputs)
            raise

        return ConformedDeliverables(
            master_30s_16x9_url=urls["master_30s_16x9"],
            cutdown_15s_9x16_url=urls["cutdown_15s_9x16"],
            bumper_6s_9x16_url=urls["bumper_6s_9x16"],
            end_card_clip_url=urls["end_card_16x9"],
            end_card_9x16_url=urls["end_card_9x16"],
            local_paths=local_paths,
            gcs_uris=gcs_uris,
            active_subshot_ids=[s.shot_id for s in active_specs],
            active_subshot_count=len(active_specs),
            total_duration_sec=total_duration,
            subshot_specs=normalized_specs,
        )

    def reconform_timeline(
        self,
        act_clips: list[str],
        subshot_specs: Sequence[SubShotTrimSpec | dict[str, Any]] | None = None,
        display_subject: str = "Brand",
        display_tagline: str = "",
        primary_hex: str = "#E11D48",
        secondary_hex: str = "#D4C5B0",
        neutral_hex: str = "#111318",
        emblem_path: str | None = None,
        background_music_path: str | None = None,
        narrator_audio_path: str | None = None,
        end_card_duration_sec: float = 2.0,
        output_dir: str = "/tmp",
        session_id: str | None = None,
        project_id: str | None = None,
    ) -> ConformedDeliverables:
        """Re-conforms existing 3 act clips using updated NLE trims and Keep/Bypass overrides without re-filming."""
        return self.conform_all_formats(
            act_clips,
            display_subject,
            display_tagline,
            primary_hex,
            secondary_hex,
            neutral_hex,
            emblem_path,
            subshot_specs,
            background_music_path,
            narrator_audio_path,
            end_card_duration_sec,
            output_dir,
            session_id,
            project_id,
        )

    def build_campaign_package_zip(
        self,
        deliverables: ConformedDeliverables,
        display_subject: str = "",
        display_offering: str = "",
        display_tagline: str = "",
        palette_60_30_10: Any = None,
        territory: Any = None,
        executive_brief: Any = None,
        timed_voiceover: str | Sequence[Any] | dict[str, Any] = "",
        storyboard_frames: dict[str, str] | None = None,
        reference_kit: dict[str, str] | None = None,
        social_copy: dict[str, Any] | None = None,
        plan: Any = None,
        output_dir: str = "/tmp",
        session_id: str | None = None,
        project_id: str | None = None,
    ) -> tuple[str, str]:
        """Bundles conformed deliverables, storyboards, reference kit, and manifest JSON into a GCS-uploaded ZIP."""
        if session_id is not None:
            session_id = validate_safe_identifier(session_id, "session_id")
        if project_id is not None:
            project_id = validate_safe_identifier(project_id, "project_id")

        if plan is not None:
            ident = getattr(plan, "identity", None)
            display_subject = (
                display_subject
                or getattr(ident, "display_subject", "")
                or getattr(plan, "subject", "")
            )
            display_offering = (
                display_offering
                or getattr(ident, "display_offering", "")
                or getattr(plan, "offering", "")
            )
            display_tagline = display_tagline or getattr(ident, "display_tagline", "")
            if palette_60_30_10 is None:
                palette_60_30_10 = getattr(plan, "palette", None)
            if territory is None:
                territory = getattr(plan, "territory", None)
            if executive_brief is None:
                executive_brief = getattr(plan, "brief", None)
            timed_voiceover = timed_voiceover or getattr(plan, "voiceover_full_script", "")

        subj_clean = (display_subject or "Campaign").strip() or "Campaign"
        safe_slug = re.sub(r"[^a-z0-9]+", "_", subj_clean.lower()).strip("_")[:40] or "campaign"
        os.makedirs(output_dir, exist_ok=True)
        local_zip_path = os.path.join(
            output_dir, f"campaign_package_{safe_slug}_{uuid.uuid4().hex[:8]}.zip"
        )

        resolved_social = social_copy or {
            "headline": (
                f"{subj_clean} · {display_offering}".strip(" ·") if display_offering else subj_clean
            ),
            "caption_16x9": display_tagline or f"Introducing {subj_clean}.",
            "caption_9x16": display_tagline or f"{subj_clean} — Commercial Soundstage Cutdown.",
            "bumper_hook": display_tagline or subj_clean,
        }

        fallback_urls = {
            "master_30s_16x9": deliverables.master_30s_16x9_url,
            "cutdown_15s_9x16": deliverables.cutdown_15s_9x16_url,
            "bumper_6s_9x16": deliverables.bumper_6s_9x16_url,
        }
        deliverable_sources = {
            key: (
                arcname,
                deliverables.local_paths.get(key)
                or deliverables.gcs_uris.get(key)
                or fallback_urls[key],
            )
            for key, arcname in (
                ("master_30s_16x9", "deliverables/30s_16x9_master.mp4"),
                ("cutdown_15s_9x16", "deliverables/15s_9x16_cutdown.mp4"),
                ("bumper_6s_9x16", "deliverables/6s_9x16_bumper.mp4"),
            )
        }

        def _build_manifest(written_entries: dict[str, str]) -> dict[str, Any]:
            return {
                "display_subject": subj_clean,
                "display_offering": display_offering,
                "display_tagline": display_tagline,
                "palette_60_30_10": _serialize_manifest_field(palette_60_30_10),
                "territory": _serialize_manifest_field(territory),
                "executive_brief": _serialize_manifest_field(executive_brief),
                "timed_voiceover": (
                    "" if not timed_voiceover else _serialize_manifest_field(timed_voiceover)
                ),
                "subshot_specs": [s.model_dump() for s in deliverables.subshot_specs],
                "deliverables": {
                    **{f"{k}_url": v for k, v in fallback_urls.items()},
                    "end_card_clip_url": deliverables.end_card_clip_url,
                    "end_card_9x16_url": deliverables.end_card_9x16_url,
                    "gcs_uris": dict(deliverables.gcs_uris),
                    "active_subshot_ids": list(deliverables.active_subshot_ids),
                    "active_subshot_count": deliverables.active_subshot_count,
                    "total_duration_sec": deliverables.total_duration_sec,
                    "archive_entries": written_entries,
                },
                "social_copy": _serialize_manifest_field(resolved_social),
            }

        try:
            with tempfile.TemporaryDirectory() as scoped_temp_dir:
                populate_campaign_zip_archive(
                    local_zip_path=local_zip_path,
                    deliverable_sources=deliverable_sources,
                    storyboard_frames=storyboard_frames,
                    reference_kit=reference_kit,
                    canonical_subshot_ids=CANONICAL_SUBSHOT_IDS,
                    write_entry_fn=lambda zf, src, arc, tmp, fb: self._write_zip_media_entry(
                        zf, src, arc, tmp, output_dir, fb
                    ),
                    temp_dir=scoped_temp_dir,
                    build_manifest_fn=_build_manifest,
                )

            _, gcs_uri = self._upload_deliverable(
                local_path=local_zip_path,
                session_id=session_id,
                project_id=project_id,
                content_type="application/zip",
            )
            return (local_zip_path, gcs_uri)
        except Exception:
            _unlink_paths_quietly((local_zip_path,))
            raise


__all__ = [
    "CANONICAL_SUBSHOT_IDS",
    "MAX_BUMPER_SUBSHOT_DURATION_SEC",
    "MIN_SUBSHOT_DURATION_SEC",
    "PREFERRED_BUMPER_6S_SUBSHOTS",
    "PREFERRED_CUTDOWN_15S_SUBSHOTS",
    "CommercialConformer",
    "ConformedDeliverables",
    "SubShotTrimSpec",
    "_contrast_ratio",
    "_parse_hex_rgb",
    "_select_end_card_palette",
    "build_default_subshot_specs",
    "normalize_subshot_specs",
]
