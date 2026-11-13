from __future__ import annotations

import json
import math
from pathlib import Path
import struct
from types import SimpleNamespace
import wave

from omnimash.evaluation.models import (
    DEFECT_TO_REMEDIATION_TIER,
    DefectCategory,
    RemediationActionTier,
    VideoEvaluationScorecard,
    resolve_highest_cost_remediation_tier,
)
from omnimash.evaluation.strategy_bank import FOUNDATIONAL_INVARIANTS, StrategyBankManager
from omnimash.evaluation.video_critic import VideoCriticAgent
from omnimash.storage.gcs import GcsStorageManager


def _write_16khz_mono_wav(
    path: Path,
    duration_sec: float = 3.0,
    silence_ranges_sec: list[tuple[float, float]] | None = None,
    freq_hz: float = 440.0,
    amplitude: float = 0.5,
) -> Path:
    """Writes a 16 kHz mono 16-bit PCM WAV file with optional zeroed silence spans."""
    sample_rate = 16000
    total_samples = int(round(duration_sec * sample_rate))
    silence_ranges = silence_ranges_sec or []
    frames = bytearray()

    for idx in range(total_samples):
        t = idx / sample_rate
        in_silence = any(start <= t < end for start, end in silence_ranges)
        if in_silence:
            sample_val = 0
        else:
            sample_val = int(round(amplitude * 32767.0 * math.sin(2.0 * math.pi * freq_hz * t)))
        frames.extend(struct.pack("<h", sample_val))

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))

    return path


def test_defect_to_remediation_tier_routes_audio_to_tier1_tts_to_tier2_motion_to_tier3_and_framing_to_tier4():
    assert len(DefectCategory) == 16
    assert set(DefectCategory) == set(DEFECT_TO_REMEDIATION_TIER.keys())

    # Tier 1: Audio / remux-only fixes
    assert (
        DEFECT_TO_REMEDIATION_TIER[DefectCategory.TECHNICAL_SPEC_NONCOMPLIANT]
        == RemediationActionTier.TIER_1_REMUX_AUDIO_ONLY
    )
    assert (
        DEFECT_TO_REMEDIATION_TIER[DefectCategory.GUILLOTINE_OR_808_MISALIGNED]
        == RemediationActionTier.TIER_1_REMUX_AUDIO_ONLY
    )
    assert (
        DEFECT_TO_REMEDIATION_TIER[DefectCategory.AUDIO_DROWNED]
        == RemediationActionTier.TIER_1_REMUX_AUDIO_ONLY
    )

    # Tier 2: Offscreen TTS regeneration
    assert (
        DEFECT_TO_REMEDIATION_TIER[DefectCategory.OFFSCREEN_LIPSYNC_ERROR]
        == RemediationActionTier.TIER_2_REGENERATE_TTS_ONLY
    )

    # Tier 3: Video clip recreation (motion, syllable, prop glitch, tags)
    for defect in (
        DefectCategory.SYLLABLE_SKIP_OR_DIALECT_DRIFT,
        DefectCategory.AUDIO_VOCAL_HALLUCINATION,
        DefectCategory.BILATERAL_PROP_GLITCH,
        DefectCategory.TEMPORAL_BEAT_MISSED,
        DefectCategory.TAG_COLLISION,
        DefectCategory.PHANTOM_KEYFRAME,
    ):
        assert (
            DEFECT_TO_REMEDIATION_TIER[defect] == RemediationActionTier.TIER_3_RECREATE_VIDEO_CLIP
        )

    # Tier 4: Keyframe + clip recreation (framing, trope, parallax, likeness, wardrobe)
    for defect in (
        DefectCategory.FLAT_MATTE_NO_PARALLAX,
        DefectCategory.REF_PANEL_OR_LANDMARK_BLEED,
        DefectCategory.SCALE_OR_AXIS_FRAMING_MISS,
        DefectCategory.ARCHITECTURAL_TROPE_DRIFT,
        DefectCategory.LIKENESS_DRIFT,
        DefectCategory.WARDROBE_CONTRADICTION,
    ):
        assert (
            DEFECT_TO_REMEDIATION_TIER[defect]
            == RemediationActionTier.TIER_4_RECREATE_KEYFRAME_AND_CLIP
        )

    # Cost-ordered precedence: TIER_4 > TIER_3 > TIER_2 > TIER_1 > NONE
    assert resolve_highest_cost_remediation_tier([]) == RemediationActionTier.NONE
    assert (
        resolve_highest_cost_remediation_tier([DefectCategory.AUDIO_DROWNED])
        == RemediationActionTier.TIER_1_REMUX_AUDIO_ONLY
    )
    assert (
        resolve_highest_cost_remediation_tier(
            [DefectCategory.AUDIO_DROWNED, DefectCategory.OFFSCREEN_LIPSYNC_ERROR]
        )
        == RemediationActionTier.TIER_2_REGENERATE_TTS_ONLY
    )
    assert (
        resolve_highest_cost_remediation_tier(
            [
                DefectCategory.GUILLOTINE_OR_808_MISALIGNED,
                DefectCategory.OFFSCREEN_LIPSYNC_ERROR,
                DefectCategory.BILATERAL_PROP_GLITCH,
            ]
        )
        == RemediationActionTier.TIER_3_RECREATE_VIDEO_CLIP
    )
    assert (
        resolve_highest_cost_remediation_tier(
            [
                DefectCategory.AUDIO_DROWNED,
                DefectCategory.OFFSCREEN_LIPSYNC_ERROR,
                DefectCategory.SYLLABLE_SKIP_OR_DIALECT_DRIFT,
                DefectCategory.SCALE_OR_AXIS_FRAMING_MISS,
            ]
        )
        == RemediationActionTier.TIER_4_RECREATE_KEYFRAME_AND_CLIP
    )


def test_detect_rms_syllable_dropouts_flags_unscripted_350ms_mid_line_gap_and_passes_continuous_speech(
    tmp_path: Path,
):
    continuous_wav = _write_16khz_mono_wav(tmp_path / "continuous.wav", duration_sec=3.0)
    has_dropout_clean, gaps_clean = VideoCriticAgent.detect_rms_syllable_dropouts(
        str(continuous_wav),
        speech_start_sec=0.5,
        speech_end_sec=2.5,
    )
    assert has_dropout_clean is False
    assert gaps_clean == []

    short_pause_wav = _write_16khz_mono_wav(
        tmp_path / "short_pause_180ms.wav",
        duration_sec=3.0,
        silence_ranges_sec=[(1.20, 1.38)],
    )
    has_dropout_short, gaps_short = VideoCriticAgent.detect_rms_syllable_dropouts(
        str(short_pause_wav),
        speech_start_sec=0.5,
        speech_end_sec=2.5,
    )
    assert has_dropout_short is False
    assert gaps_short == []

    dropout_wav = _write_16khz_mono_wav(
        tmp_path / "dropout_350ms.wav",
        duration_sec=3.0,
        silence_ranges_sec=[(1.20, 1.55)],
    )
    has_dropout_bad, gaps_bad = VideoCriticAgent.detect_rms_syllable_dropouts(
        str(dropout_wav),
        speech_start_sec=0.5,
        speech_end_sec=2.5,
    )
    assert has_dropout_bad is True
    assert len(gaps_bad) == 1
    gap_start, gap_end = gaps_bad[0]
    assert 1.15 <= gap_start <= 1.25
    assert 1.45 <= gap_end <= 1.60
    assert (gap_end - gap_start) > 0.25


def test_strategy_bank_includes_foundational_invariants_inv06_through_inv10():
    foundational_ids = {r.rule_id for r in FOUNDATIONAL_INVARIANTS}
    for inv_id in ("INV-06", "INV-07", "INV-08", "INV-09", "INV-10"):
        assert inv_id in foundational_ids

    storage = GcsStorageManager(mock_mode=True)
    manager = StrategyBankManager(storage=storage, mock_mode=True)
    bank = manager.get_strategy_bank()
    rules_by_id = {r.rule_id: r for r in bank.rules}

    assert "clean_single_ref.png" in rules_by_id["INV-06"].invariant_directive
    assert "MatchedLocationBlock" in rules_by_id["INV-06"].invariant_directive
    assert "quotation marks" in rules_by_id["INV-07"].invariant_directive.lower()
    assert "positive" in rules_by_id["INV-08"].invariant_directive.lower()
    assert "left" in rules_by_id["INV-09"].invariant_directive.lower()
    assert "right" in rules_by_id["INV-09"].invariant_directive.lower()
    assert "guillotine" in rules_by_id["INV-10"].invariant_directive.lower()
    assert "-14.0 lufs" in rules_by_id["INV-10"].invariant_directive.lower()


def test_video_critic_scorecard_populates_recommended_remediation_tier_and_builds_8gate_rubric():
    critic = VideoCriticAgent(mock_mode=True)
    prompt = (
        "### DIRECTORIAL INTENT\nScottish courtyard confrontation.\n"
        "### CHARACTER PROFILES\n[Role A] Headmaster.\n"
        "### SCREENPLAY\n[Role A] speaks calmly without timecode slicing.\n"
    )
    rubric = critic.build_8gate_rubric_prompt(prompt)

    # Preserves 4 core dimension names and adds all 8 gates + all 16 defect categories
    for expected_term in (
        "Video-Text Adherence",
        "Character Likeness",
        "Audio Balance",
        "Tag & Index Symmetry",
        "Gate 1",
        "Gate 2",
        "Gate 3",
        "Gate 4",
        "Gate 5",
        "Gate 6",
        "Gate 7",
        "Gate 8",
    ):
        assert expected_term in rubric

    for defect in DefectCategory:
        assert defect.value in rubric

    # Clean mock evaluation -> NONE
    clean_scorecard = critic.evaluate_video(
        session_id="sess_clean",
        turn_id="turn_0",
        prompt=prompt,
    )
    assert isinstance(clean_scorecard, VideoEvaluationScorecard)
    assert clean_scorecard.recommended_remediation_tier == RemediationActionTier.NONE

    # Tier 1 mock evaluation
    tier1_scorecard = critic.evaluate_video(
        session_id="sess_t1",
        turn_id="turn_1",
        prompt=prompt,
        reported_defects=[DefectCategory.GUILLOTINE_OR_808_MISALIGNED],
    )
    assert (
        tier1_scorecard.recommended_remediation_tier
        == RemediationActionTier.TIER_1_REMUX_AUDIO_ONLY
    )

    # Multi-defect mock evaluation resolves highest-cost tier (Tier 4 > Tier 1)
    tier4_scorecard = critic.evaluate_video(
        session_id="sess_t4",
        turn_id="turn_2",
        prompt=prompt,
        reported_defects=[
            DefectCategory.AUDIO_DROWNED,
            DefectCategory.SCALE_OR_AXIS_FRAMING_MISS,
        ],
    )
    assert (
        tier4_scorecard.recommended_remediation_tier
        == RemediationActionTier.TIER_4_RECREATE_KEYFRAME_AND_CLIP
    )

    # Live-parsed response path also populates recommended_remediation_tier
    live_payload = {
        "overall_rating": 68.0,
        "video_text_adherence": {"score": 85.0, "passed": True, "evidence": "ok"},
        "character_likeness": {"score": 88.0, "passed": True, "evidence": "ok"},
        "audio_visual_harmony": {"score": 60.0, "passed": False, "evidence": "syllable skip"},
        "tag_and_index_integrity": {"score": 90.0, "passed": True, "evidence": "ok"},
        "detected_defects": [
            DefectCategory.AUDIO_DROWNED.value,
            DefectCategory.SYLLABLE_SKIP_OR_DIALECT_DRIFT.value,
        ],
        "verbal_critique": "Detected mid-line syllable dropout.",
        "suggested_prompt_patch": None,
        "pass_verdict": False,
    }
    live_critic = VideoCriticAgent(mock_mode=False)
    live_critic._genai_client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **_kwargs: SimpleNamespace(text=json.dumps(live_payload))
        )
    )
    live_scorecard = live_critic.evaluate_video(
        session_id="sess_live",
        turn_id="turn_3",
        prompt=prompt,
    )
    assert (
        live_scorecard.recommended_remediation_tier
        == RemediationActionTier.TIER_3_RECREATE_VIDEO_CLIP
    )
