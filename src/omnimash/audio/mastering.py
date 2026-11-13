"""3-Stem Audio Mastering Engine with Audio Guillotine, SonicMixPreset, Tuned 808s, and 2-Pass -14 LUFS Loudnorm."""

from __future__ import annotations

from enum import Enum
import json
import logging
import math
import os
import re
import subprocess
from typing import Any

from pydantic import BaseModel, Field

from omnimash.config import settings

logger = logging.getLogger(__name__)


class SonicMixPreset(str, Enum):
    """Canonical OmniMash v2.0 sonic mix profiles for trailer, commercial, and diegetic scenes."""

    TRAILER = "trailer"
    COMMERCIAL = "commercial"
    DIEGETIC = "diegetic"


class SonicMixPresetConfig(BaseModel):
    """Resolved mastering and stem-balance parameters for a SonicMixPreset."""

    preset: SonicMixPreset
    target_lufs: float = -14.0
    target_true_peak_dbtp: float = -1.0
    target_lra: float = 7.0
    sample_rate_hz: int = 48000
    music_gain: float = 0.32
    consonant_carve_freq_hz: int = 2450
    consonant_carve_gain_db: float = -4.5
    guillotine_attenuation_linear: float = 0.10
    apply_narrator_baritone_dsp: bool = True
    enable_808_drops: bool = True
    enable_guillotine: bool = True
    narrator_delay_sec: float = 0.30
    description: str = ""


_SONIC_MIX_PRESET_TABLE: dict[SonicMixPreset, SonicMixPresetConfig] = {
    SonicMixPreset.TRAILER: SonicMixPresetConfig(
        preset=SonicMixPreset.TRAILER,
        target_lufs=-14.0,
        target_true_peak_dbtp=-1.0,
        target_lra=7.0,
        sample_rate_hz=48000,
        music_gain=0.32,
        consonant_carve_freq_hz=2450,
        consonant_carve_gain_db=-4.5,
        guillotine_attenuation_linear=0.10,
        apply_narrator_baritone_dsp=True,
        enable_808_drops=True,
        enable_guillotine=True,
        narrator_delay_sec=0.30,
        description="Trailer baritone narrator DSP, key-locked 808 drops, and -20 dB dry punchline guillotine.",
    ),
    SonicMixPreset.COMMERCIAL: SonicMixPresetConfig(
        preset=SonicMixPreset.COMMERCIAL,
        target_lufs=-14.0,
        target_true_peak_dbtp=-1.0,
        target_lra=6.0,
        sample_rate_hz=48000,
        music_gain=0.28,
        consonant_carve_freq_hz=2450,
        consonant_carve_gain_db=-4.5,
        guillotine_attenuation_linear=0.12,
        apply_narrator_baritone_dsp=False,
        enable_808_drops=False,
        enable_guillotine=True,
        narrator_delay_sec=0.20,
        description="Broadcast commercial soundstage balance with crisp 2450 Hz consonant pocket and tight LRA.",
    ),
    SonicMixPreset.DIEGETIC: SonicMixPresetConfig(
        preset=SonicMixPreset.DIEGETIC,
        target_lufs=-14.0,
        target_true_peak_dbtp=-1.0,
        target_lra=8.0,
        sample_rate_hz=48000,
        music_gain=0.20,
        consonant_carve_freq_hz=2450,
        consonant_carve_gain_db=-3.0,
        guillotine_attenuation_linear=0.25,
        apply_narrator_baritone_dsp=False,
        enable_808_drops=False,
        enable_guillotine=False,
        narrator_delay_sec=0.0,
        description="Naturalistic on-camera dialogue and foley mix with subtle underscore bed.",
    ),
}


def resolve_sonic_mix_preset_defaults(preset: SonicMixPreset | str) -> SonicMixPresetConfig:
    """Resolves a SonicMixPreset enum or string name to its canonical SonicMixPresetConfig."""
    if isinstance(preset, SonicMixPreset):
        return _SONIC_MIX_PRESET_TABLE[preset].model_copy()

    normalized = (preset or "").strip().lower()
    try:
        enum_val = SonicMixPreset(normalized)
    except ValueError as exc:
        valid = ", ".join(p.value for p in SonicMixPreset)
        raise ValueError(f"Unknown sonic mix preset '{preset}'. Expected one of: {valid}") from exc
    return _SONIC_MIX_PRESET_TABLE[enum_val].model_copy()


class AudioGuillotineWindow(BaseModel):
    """Time window [start_sec, end_sec] where music and ambient beds drop for a dry punchline."""

    start_sec: float = Field(..., ge=0.0)
    end_sec: float = Field(..., gt=0.0)
    attenuation_linear: float = Field(default=0.10, description="0.10 = -20 dB attenuation")


class LoudnessReport(BaseModel):
    """Measured EBU R128 / ITU-R BS.1770-4 loudness metrics."""

    integrated_lufs: float
    true_peak_dbtp: float
    lra_lu: float
    threshold_lufs: float
    target_offset_lu: float
    passed_spec: bool


def _safe_finite_float(
    raw_value: Any,
    *,
    default: float,
    min_val: float,
    max_val: float,
) -> tuple[float, bool]:
    """Parses raw float, guarding -inf/+inf/nan (e.g. digital silence) to finite loudnorm bounds."""
    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        return default, False

    if not math.isfinite(parsed):
        return default, False

    clamped = max(min_val, min(max_val, parsed))
    return clamped, True


class ThreeStemMasteringEngine:
    """Mixes Omni video audio, Gemini TTS VO, Lyria underscore, and 808 drops to -14.0 LUFS @ 48kHz."""

    def __init__(self, mock_mode: bool | None = None) -> None:
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self.timeout_sec = float(getattr(settings, "ffmpeg_timeout_seconds", 120.0))

    @staticmethod
    def has_audio_stream(media_path: str) -> bool:
        """Returns True if media_path contains at least one audio stream via ffprobe."""
        try:
            out = subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a",
                    "-show_entries",
                    "stream=index",
                    "-of",
                    "csv=p=0",
                    media_path,
                ],
                text=True,
                timeout=15.0,
            ).strip()
            return bool(out)
        except Exception as exc:
            logger.warning("ffprobe audio-stream check failed for %s: %s", media_path, exc)
            return False

    @staticmethod
    def probe_duration_seconds(media_path: str) -> float:
        """Measures container duration in seconds via ffprobe."""
        try:
            out = subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "csv=p=0",
                    media_path,
                ],
                text=True,
                timeout=15.0,
            ).strip()
            dur = float(out)
            return dur if math.isfinite(dur) and dur > 0.0 else 0.0
        except Exception as exc:
            logger.warning("ffprobe duration check failed for %s: %s", media_path, exc)
            return 0.0

    def measure_loudnorm_stats(
        self,
        audio_or_video_path: str,
        target_i: float = -14.0,
        target_tp: float = -1.0,
        target_lra: float = 7.0,
    ) -> LoudnessReport:
        """Runs Pass 1 of FFmpeg loudnorm filter and parses the JSON measurement block."""
        if self.mock_mode:
            return LoudnessReport(
                integrated_lufs=-14.05,
                true_peak_dbtp=-1.00,
                lra_lu=6.2,
                threshold_lufs=-24.5,
                target_offset_lu=0.05,
                passed_spec=True,
            )

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-i",
            audio_or_video_path,
            "-af",
            f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json",
            "-f",
            "null",
            "-",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout_sec)
        matches = list(re.finditer(r"\{\s*\"input_i\"\s*:.*?\}", res.stderr, flags=re.DOTALL))
        if not matches:
            raise RuntimeError(
                f"FFmpeg loudnorm Pass 1 did not emit JSON stats for {audio_or_video_path}"
            )

        stats: dict[str, Any] = json.loads(matches[-1].group(0))
        i_val, i_finite = _safe_finite_float(
            stats.get("input_i"), default=-99.0, min_val=-99.0, max_val=0.0
        )
        tp_val, tp_finite = _safe_finite_float(
            stats.get("input_tp"), default=-99.0, min_val=-99.0, max_val=99.0
        )
        lra_val, _ = _safe_finite_float(
            stats.get("input_lra"), default=0.0, min_val=0.0, max_val=99.0
        )
        thresh_val, _ = _safe_finite_float(
            stats.get("input_thresh"), default=-70.0, min_val=-99.0, max_val=0.0
        )
        offset_val, _ = _safe_finite_float(
            stats.get("target_offset"), default=0.0, min_val=-99.0, max_val=99.0
        )
        passed = i_finite and tp_finite and (-14.6 <= i_val <= -13.4) and (tp_val <= -0.85)
        return LoudnessReport(
            integrated_lufs=i_val,
            true_peak_dbtp=tp_val,
            lra_lu=lra_val,
            threshold_lufs=thresh_val,
            target_offset_lu=offset_val,
            passed_spec=passed,
        )

    def mix_and_master_scene(
        self,
        *,
        video_path: str,
        output_video_path: str,
        narrator_wav_path: str | None = None,
        narrator_delay_sec: float = 0.30,
        lyria_score_path: str | None = None,
        score_offset_sec: float = 0.0,
        sub_bass_808_path: str | None = None,
        sub_bass_808_delay_sec: float | None = None,
        guillotine: AudioGuillotineWindow | None = None,
        target_lufs: float | None = None,
        target_tp: float | None = None,
        preset: SonicMixPreset | str | None = None,
    ) -> LoudnessReport:
        """Executes the 3-stem + 808 + Audio Guillotine mix and 2-pass -14.0 LUFS master."""
        preset_cfg = (
            resolve_sonic_mix_preset_defaults(preset)
            if preset is not None
            else resolve_sonic_mix_preset_defaults(SonicMixPreset.TRAILER)
        )
        eff_lufs = (
            target_lufs
            if target_lufs is not None
            else (
                preset_cfg.target_lufs
                if preset is not None
                else float(getattr(settings, "target_lufs", -14.0))
            )
        )
        eff_tp = (
            target_tp
            if target_tp is not None
            else (
                preset_cfg.target_true_peak_dbtp
                if preset is not None
                else float(getattr(settings, "target_true_peak_dbtp", -1.0))
            )
        )
        eff_lra = preset_cfg.target_lra

        os.makedirs(os.path.dirname(os.path.abspath(output_video_path)), exist_ok=True)
        if self.mock_mode:
            with open(output_video_path, "wb") as f:
                f.write(b"mock_mastered_1080p_mp4")
            return self.measure_loudnorm_stats(
                output_video_path, target_i=eff_lufs, target_tp=eff_tp, target_lra=eff_lra
            )

        premix_wav = f"{output_video_path}.premix.wav"
        norm_wav = f"{output_video_path}.norm.wav"

        inputs: list[str] = ["-i", video_path]
        filter_parts: list[str] = []
        mix_labels: list[str] = ["[vid_a]"]

        # Stem 0: Omni Video Audio (on-camera dialogue + foley) or finite anullsrc fallback if video is silent
        if self.has_audio_stream(video_path):
            filter_parts.append(
                "[0:a]aformat=sample_rates=48000:channel_layouts=stereo,highpass=f=70[vid_a]"
            )
            input_idx = 1
        else:
            vid_dur = self.probe_duration_seconds(video_path) or 1.5
            inputs.extend(
                ["-f", "lavfi", "-t", f"{vid_dur:.4f}", "-i", "anullsrc=r=48000:cl=stereo"]
            )
            filter_parts.append("[1:a]aformat=sample_rates=48000:channel_layouts=stereo[vid_a]")
            input_idx = 2

        # Stem 1: Optional Gemini 3.8 TTS Narrator VO
        if narrator_wav_path and os.path.exists(narrator_wav_path):
            inputs.extend(["-i", narrator_wav_path])
            delay_ms = max(0, int(round(narrator_delay_sec * 1000.0)))
            filter_parts.append(
                f"[{input_idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                f"adelay={delay_ms}:all=1,apad[vo_a]"
            )
            mix_labels.append("[vo_a]")
            input_idx += 1

        # Stem 2: Optional Lyria 3 Pro Underscore with 2450 Hz EQ Carve & Audio Guillotine
        if lyria_score_path and os.path.exists(lyria_score_path):
            inputs.extend(["-ss", str(score_offset_sec), "-i", lyria_score_path])
            guillotine_filter = ""
            if guillotine is not None:
                guillotine_filter = (
                    f",volume=enable='between(t,{guillotine.start_sec:.2f},{guillotine.end_sec:.2f})'"
                    f":volume={guillotine.attenuation_linear:.3f}"
                )
            filter_parts.append(
                f"[{input_idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                f"highpass=f=35,equalizer=f={preset_cfg.consonant_carve_freq_hz}:t=q:w=1.2:"
                f"g={preset_cfg.consonant_carve_gain_db},"
                f"volume={preset_cfg.music_gain}{guillotine_filter},apad[mus_a]"
            )
            mix_labels.append("[mus_a]")
            input_idx += 1

        # Stem 3: Optional Key-Locked D1/D2 808 Sub-Bass Drop
        if (
            sub_bass_808_path
            and os.path.exists(sub_bass_808_path)
            and sub_bass_808_delay_sec is not None
        ):
            inputs.extend(["-i", sub_bass_808_path])
            drop_ms = max(0, int(round(sub_bass_808_delay_sec * 1000.0)))
            filter_parts.append(
                f"[{input_idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                f"adelay={drop_ms}:all=1,apad[sub808_a]"
            )
            mix_labels.append("[sub808_a]")
            input_idx += 1

        filter_parts.append(
            f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=0:normalize=0[premix]"
        )
        filter_complex = ";".join(filter_parts)

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    *inputs,
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[premix]",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    premix_wav,
                ],
                check=True,
                capture_output=True,
                timeout=self.timeout_sec,
            )

            # Pass 1: Measure EBU R128 stats on premix
            pass1 = self.measure_loudnorm_stats(
                premix_wav,
                target_i=eff_lufs,
                target_tp=eff_tp,
                target_lra=eff_lra,
            )

            # Pass 2: Apply linear loudnorm with finite clamped values
            loudnorm_pass2 = (
                f"loudnorm=I={eff_lufs}:TP={eff_tp}:LRA={eff_lra}:"
                f"measured_I={pass1.integrated_lufs:.2f}:"
                f"measured_TP={pass1.true_peak_dbtp:.2f}:"
                f"measured_LRA={pass1.lra_lu:.2f}:"
                f"measured_thresh={pass1.threshold_lufs:.2f}:"
                f"offset={pass1.target_offset_lu:.2f}:linear=true,"
                "aformat=sample_rates=48000:channel_layouts=stereo"
            )
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    premix_wav,
                    "-af",
                    loudnorm_pass2,
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    norm_wav,
                ],
                check=True,
                capture_output=True,
                timeout=self.timeout_sec,
            )

            # Mux normalized 48kHz stereo AAC (320k) onto video stream without re-encoding video (-c:v copy)
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    video_path,
                    "-i",
                    norm_wav,
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "320k",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "-shortest",
                    output_video_path,
                ],
                check=True,
                capture_output=True,
                timeout=self.timeout_sec,
            )
        finally:
            for tmp in (premix_wav, norm_wav):
                if os.path.exists(tmp):
                    os.remove(tmp)

        return self.measure_loudnorm_stats(
            output_video_path,
            target_i=eff_lufs,
            target_tp=eff_tp,
            target_lra=eff_lra,
        )
