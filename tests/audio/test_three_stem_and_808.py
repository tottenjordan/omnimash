"""Hermetic unit and FFmpeg integration tests for OmniMash v2.0 3-stem audio engine."""

from __future__ import annotations

import base64
import io
import json
import math
import subprocess
import struct
from types import SimpleNamespace
from typing import Any
import wave

import pytest

from omnimash.audio.lyria_client import LyriaClient, LyriaScoreResult
from omnimash.audio.mastering import (
    AudioGuillotineWindow,
    LoudnessReport,
    SonicMixPreset,
    SonicMixPresetConfig,
    ThreeStemMasteringEngine,
    resolve_sonic_mix_preset_defaults,
)
from omnimash.audio.sub_bass_808 import (
    NOTE_FREQUENCIES_HZ,
    snap_timestamp_to_bpm_grid,
    synthesize_tuned_808_wav,
)
from omnimash.audio.tts_client import (
    CANONICAL_TRAILER_NARRATOR_VOICE_ID,
    DEFAULT_FALLBACK_NARRATOR_VOICE,
    TRAILER_NARRATOR_AF_CHAIN,
    GeminiTTSClient,
    TTSSynthesisResult,
    normalize_tts_transcript,
)


def _make_wav_bytes(
    duration_sec: float = 0.6,
    sample_rate: int = 24000,
    channels: int = 1,
    freq_hz: float = 220.0,
    amplitude: float = 0.25,
) -> bytes:
    """Builds valid PCM16 RIFF WAV bytes in memory without external tools."""
    num_samples = max(1, int(round(duration_sec * sample_rate)))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(num_samples):
            val = int(amplitude * math.sin(2.0 * math.pi * freq_hz * (i / sample_rate)) * 32767.0)
            for _ in range(channels):
                frames.extend(struct.pack("<h", val))
        wf.writeframes(bytes(frames))
    return buf.getvalue()


def _goertzel_power(samples: list[float], sample_rate: int, target_hz: float) -> float:
    """Computes normalized DFT bin power at target_hz using Goertzel's algorithm."""
    n = len(samples)
    omega = 2.0 * math.pi * target_hz / sample_rate
    coeff = 2.0 * math.cos(omega)
    q1 = 0.0
    q2 = 0.0
    for s in samples:
        q0 = coeff * q1 - q2 + s
        q2 = q1
        q1 = q0
    real = q1 - q2 * math.cos(omega)
    imag = q2 * math.sin(omega)
    return math.sqrt(real * real + imag * imag) / max(1, n)


def test_synthesize_tuned_808_wav_creates_48khz_stereo_pcm_with_d1_d2_harmonics(tmp_path) -> None:
    out_wav = tmp_path / "drop_d1.wav"
    result_path = synthesize_tuned_808_wav(
        output_path=str(out_wav),
        root_note="D1",
        duration_sec=1.0,
        sample_rate=48000,
    )
    assert result_path == str(out_wav)
    assert out_wav.exists()

    with wave.open(str(out_wav), "rb") as wf:
        assert wf.getnchannels() == 2
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 48000
        assert wf.getnframes() == 48000
        raw = wf.readframes(wf.getnframes())

    # Extract left channel samples after the 18ms pitch-punch settles (t >= 0.10s)
    total_samples = len(raw) // 4
    left_tail: list[float] = []
    start_idx = int(0.10 * 48000)
    for i in range(start_idx, total_samples):
        left_val, right_val = struct.unpack_from("<hh", raw, i * 4)
        assert left_val == right_val
        left_tail.append(left_val / 32767.0)

    d1_power = _goertzel_power(left_tail, 48000, NOTE_FREQUENCIES_HZ["D1"])
    d2_power = _goertzel_power(left_tail, 48000, NOTE_FREQUENCIES_HZ["D1"] * 2.0)
    off_key_power = _goertzel_power(left_tail, 48000, 55.0)

    assert d1_power > 0.08
    assert d2_power > 0.02
    assert d1_power > off_key_power * 3.0


def test_snap_timestamp_to_bpm_grid_aligns_9_78s_to_142_bpm_beat() -> None:
    snapped = snap_timestamp_to_bpm_grid(9.78, bpm=142.0)
    assert snapped == pytest.approx(9.7183, abs=1e-4)
    assert snapped == 9.7183
    assert snap_timestamp_to_bpm_grid(-1.0, bpm=142.0) == 0.0
    assert snap_timestamp_to_bpm_grid(2.5, bpm=0.0) == 2.5


def test_normalize_tts_transcript_expands_1017_and_strips_pause_tags_when_requested() -> None:
    raw = "In 1017, <short pause> a boy appeared... <long pause> right here."
    preserved = normalize_tts_transcript(raw, strip_pause_tags=False)
    assert "Ten-Seventeen" in preserved
    assert "1017" not in preserved
    assert "<short pause>" in preserved

    stripped = normalize_tts_transcript(raw, strip_pause_tags=True)
    assert "Ten-Seventeen" in stripped
    assert "<short pause>" not in stripped
    assert "<long pause>" not in stripped
    assert "..." not in stripped


def test_gemini_tts_client_falls_back_to_prebuilt_voice_when_custom_voice_fails_and_never_sends_temperature(
    tmp_path,
) -> None:
    captured_calls: list[dict[str, Any]] = []
    wav_b64 = base64.b64encode(_make_wav_bytes(duration_sec=0.8, sample_rate=24000)).decode("utf-8")

    class FakeInteractions:
        def create(self, **kwargs):
            captured_calls.append(kwargs)
            voice = kwargs["generation_config"]["speech_config"][0]["voice"]
            if voice == CANONICAL_TRAILER_NARRATOR_VOICE_ID:
                raise RuntimeError("404 custom voice_9fb52507 not found")
            return SimpleNamespace(
                id="int_tts_fallback",
                output_audio=SimpleNamespace(data=wav_b64, mime_type="audio/wav"),
            )

    fake_client = SimpleNamespace(interactions=FakeInteractions())
    client = GeminiTTSClient(genai_client=fake_client, mock_mode=False)
    out_wav = tmp_path / "narrator.wav"
    verbose_style = (
        "Deep gravelly cinematic movie trailer baritone with deadpan ominous gravitas "
        "and dramatic tension across every syllable"
    )

    res = client.synthesize_narrator_stem(
        text="In 1017, the gates opened.",
        output_path=str(out_wav),
        voice_name=CANONICAL_TRAILER_NARRATOR_VOICE_ID,
        style=verbose_style,
        target_window_sec=None,
        apply_baritone_dsp=True,
    )

    assert isinstance(res, TTSSynthesisResult)
    assert len(captured_calls) == 2
    assert captured_calls[0]["generation_config"]["speech_config"][0]["voice"] == (
        CANONICAL_TRAILER_NARRATOR_VOICE_ID
    )
    assert (
        captured_calls[1]["generation_config"]["speech_config"][0]["voice"]
        == DEFAULT_FALLBACK_NARRATOR_VOICE
    )
    assert DEFAULT_FALLBACK_NARRATOR_VOICE == "Orus"
    assert res.voice_name == "Orus"
    assert "Ten-Seventeen" in res.transcript_used

    for call in captured_calls:
        for forbidden in (
            "temperature",
            "systemInstruction",
            "system_instruction",
            "topP",
            "top_p",
            "topK",
            "top_k",
            "candidateCount",
            "candidate_count",
        ):
            assert forbidden not in call
            assert forbidden not in call.get("generation_config", {})
        assert "audioConfig" not in call.get("generation_config", {})
        annotations = call["input"][0]["annotations"]
        assert annotations[0]["type"] == "speech_metadata"
        assert len(annotations[0]["style"].split()) <= 12

    with wave.open(str(out_wav), "rb") as wf:
        assert wf.getnchannels() == 2
        assert wf.getframerate() == 48000
        assert wf.getnframes() > 0

    # Verify mock_mode=True writes a real playable 48kHz stereo RIFF WAV
    mock_wav = tmp_path / "mock_narrator.wav"
    mock_client = GeminiTTSClient(mock_mode=True)
    mock_res = mock_client.synthesize_narrator_stem(
        text="In 1017, test.",
        output_path=str(mock_wav),
        target_window_sec=2.0,
    )
    assert mock_res.duration_seconds > 0.0
    with wave.open(str(mock_wav), "rb") as wf:
        assert wf.getnchannels() == 2
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 48000
        assert wf.getnframes() > 0


def test_trailer_narrator_af_chain_normalizes_to_24khz_before_asetrate_pitch_shift() -> None:
    assert "aresample=24000,asetrate=24000*0.91,aresample=48000" in TRAILER_NARRATOR_AF_CHAIN


def test_lyria_client_selects_clip_model_under_30s_and_pro_model_above_30s(tmp_path) -> None:
    recorded_models: list[str] = []
    wav_b64 = base64.b64encode(
        _make_wav_bytes(duration_sec=0.5, sample_rate=48000, channels=2)
    ).decode("utf-8")

    class FakeInteractions:
        def create(self, **kwargs):
            recorded_models.append(kwargs["model"])
            return SimpleNamespace(
                id="int_lyria_1",
                output_audio=SimpleNamespace(data=wav_b64, mime_type="audio/wav"),
            )

    fake_client = SimpleNamespace(interactions=FakeInteractions())
    live_lyria = LyriaClient(genai_client=fake_client, mock_mode=False)

    res_short = live_lyria.generate_score(
        prompt="142 BPM UK Drill instrumental in D minor, no vocals.",
        output_path=str(tmp_path / "short.wav"),
        duration_sec=18.0,
    )
    res_boundary = live_lyria.generate_score(
        prompt="142 BPM UK Drill instrumental in D minor, no vocals.",
        output_path=str(tmp_path / "boundary.wav"),
        duration_sec=30.0,
    )
    res_long = live_lyria.generate_score(
        prompt="142 BPM UK Drill instrumental in D minor, no vocals.",
        output_path=str(tmp_path / "long.wav"),
        duration_sec=45.0,
    )

    assert isinstance(res_short, LyriaScoreResult)
    assert recorded_models == [
        "lyria-3-clip-preview",
        "lyria-3-clip-preview",
        "lyria-3-pro-preview",
    ]
    assert res_short.model_id == "lyria-3-clip-preview"
    assert res_boundary.model_id == "lyria-3-clip-preview"
    assert res_long.model_id == "lyria-3-pro-preview"

    # mock_mode=True writes playable 48kHz stereo WAVs and selects clip vs pro
    mock_lyria = LyriaClient(mock_mode=True)
    mock_clip_wav = tmp_path / "mock_clip.wav"
    mock_pro_wav = tmp_path / "mock_pro.wav"
    clip_res = mock_lyria.generate_score(
        prompt="Orchestral trailer underscore",
        output_path=str(mock_clip_wav),
        duration_sec=1.2,
    )
    pro_res = mock_lyria.generate_score(
        prompt="Extended orchestral trailer underscore",
        output_path=str(mock_pro_wav),
        duration_sec=35.0,
    )
    assert clip_res.model_id == "lyria-3-clip-preview"
    assert pro_res.model_id == "lyria-3-pro-preview"
    for wav_file in (mock_clip_wav, mock_pro_wav):
        with wave.open(str(wav_file), "rb") as wf:
            assert wf.getnchannels() == 2
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 48000
            assert wf.getnframes() > 0


def _create_test_mp4(path: str, duration_sec: float = 1.5, with_audio: bool = True) -> None:
    """Creates a tiny hermetic H.264 MP4 (with or without an AAC audio stream) via FFmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=160x90:r=24:d={duration_sec}",
    ]
    if with_audio:
        cmd.extend(
            [
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=180:sample_rate=48000:duration={duration_sec}",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-c:a",
                "aac",
                "-ac",
                "2",
                "-ar",
                "48000",
                path,
            ]
        )
    else:
        cmd.extend(["-an", "-c:v", "libx264", "-preset", "ultrafast", path])
    subprocess.run(cmd, check=True, capture_output=True, timeout=30.0)


def _ffprobe_audio_stream(media_path: str) -> dict[str, Any]:
    """Returns the first audio stream metadata dict via ffprobe."""
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels",
            "-of",
            "json",
            media_path,
        ],
        text=True,
        timeout=15.0,
    )
    streams = json.loads(out).get("streams", [])
    return streams[0] if streams else {}


def test_three_stem_mastering_engine_masters_real_stems_to_minus_14_lufs_and_48khz_stereo(
    tmp_path,
) -> None:
    in_mp4 = str(tmp_path / "scene_raw.mp4")
    out_mp4 = str(tmp_path / "scene_mastered.mp4")
    narrator_wav = str(tmp_path / "narrator.wav")
    score_wav = str(tmp_path / "score.wav")
    drop_wav = str(tmp_path / "drop_808.wav")

    _create_test_mp4(in_mp4, duration_sec=1.5, with_audio=True)
    with open(narrator_wav, "wb") as f:
        f.write(_make_wav_bytes(duration_sec=1.2, sample_rate=48000, channels=2, freq_hz=440.0))
    with open(score_wav, "wb") as f:
        f.write(_make_wav_bytes(duration_sec=2.0, sample_rate=48000, channels=2, freq_hz=260.0))
    synthesize_tuned_808_wav(drop_wav, root_note="D1", duration_sec=0.8, sample_rate=48000)

    engine = ThreeStemMasteringEngine(mock_mode=False)
    report = engine.mix_and_master_scene(
        video_path=in_mp4,
        output_video_path=out_mp4,
        narrator_wav_path=narrator_wav,
        narrator_delay_sec=0.1,
        lyria_score_path=score_wav,
        score_offset_sec=0.0,
        sub_bass_808_path=drop_wav,
        sub_bass_808_delay_sec=0.4,
        guillotine=AudioGuillotineWindow(start_sec=0.5, end_sec=0.9, attenuation_linear=0.10),
    )

    assert isinstance(report, LoudnessReport)
    assert math.isfinite(report.integrated_lufs)
    assert -14.6 <= report.integrated_lufs <= -13.4
    assert report.true_peak_dbtp <= -0.85
    assert report.passed_spec is True

    audio_meta = _ffprobe_audio_stream(out_mp4)
    assert audio_meta["codec_name"] == "aac"
    assert int(audio_meta["sample_rate"]) == 48000
    assert int(audio_meta["channels"]) == 2


def test_three_stem_mastering_engine_handles_silent_video_without_audio_stream_via_anullsrc(
    tmp_path,
) -> None:
    silent_mp4 = str(tmp_path / "silent_video.mp4")
    out_with_stems = str(tmp_path / "silent_with_stems.mp4")
    out_pure_silent = str(tmp_path / "pure_silent_mastered.mp4")
    narrator_wav = str(tmp_path / "narrator.wav")

    _create_test_mp4(silent_mp4, duration_sec=1.5, with_audio=False)
    with open(narrator_wav, "wb") as f:
        f.write(_make_wav_bytes(duration_sec=1.2, sample_rate=48000, channels=2, freq_hz=330.0))

    engine = ThreeStemMasteringEngine(mock_mode=False)
    assert engine.has_audio_stream(silent_mp4) is False

    report = engine.mix_and_master_scene(
        video_path=silent_mp4,
        output_video_path=out_with_stems,
        narrator_wav_path=narrator_wav,
        narrator_delay_sec=0.1,
    )
    assert engine.has_audio_stream(out_with_stems) is True
    assert -14.6 <= report.integrated_lufs <= -13.4
    assert report.passed_spec is True
    audio_meta = _ffprobe_audio_stream(out_with_stems)
    assert int(audio_meta["sample_rate"]) == 48000
    assert int(audio_meta["channels"]) == 2

    # Even with zero stems on a video-only MP4, mastering completes cleanly without crashing
    silent_report = engine.mix_and_master_scene(
        video_path=silent_mp4,
        output_video_path=out_pure_silent,
    )
    assert engine.has_audio_stream(out_pure_silent) is True
    assert math.isfinite(silent_report.integrated_lufs)
    assert silent_report.passed_spec is False


def test_measure_loudnorm_stats_guards_digital_silence_minus_inf_without_crashing(
    tmp_path,
) -> None:
    silence_wav = tmp_path / "digital_silence.wav"
    with wave.open(str(silence_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        wf.writeframes(b"\x00\x00\x00\x00" * 48000)

    engine = ThreeStemMasteringEngine(mock_mode=False)
    report = engine.measure_loudnorm_stats(str(silence_wav))

    assert math.isfinite(report.integrated_lufs)
    assert math.isfinite(report.true_peak_dbtp)
    assert math.isfinite(report.lra_lu)
    assert math.isfinite(report.threshold_lufs)
    assert math.isfinite(report.target_offset_lu)
    assert report.integrated_lufs <= -70.0
    assert report.passed_spec is False
    # Must serialize to strict JSON without NaN/Infinity errors
    assert json.loads(report.model_dump_json())["passed_spec"] is False


def test_sonic_mix_preset_populates_trailer_commercial_and_diegetic_profiles() -> None:
    trailer_cfg = resolve_sonic_mix_preset_defaults(SonicMixPreset.TRAILER)
    commercial_cfg = resolve_sonic_mix_preset_defaults("commercial")
    diegetic_cfg = resolve_sonic_mix_preset_defaults("DIEGETIC")

    for cfg in (trailer_cfg, commercial_cfg, diegetic_cfg):
        assert isinstance(cfg, SonicMixPresetConfig)
        assert cfg.target_lufs == -14.0
        assert cfg.target_true_peak_dbtp == -1.0
        assert cfg.sample_rate_hz == 48000
        assert cfg.consonant_carve_freq_hz == 2450

    assert trailer_cfg.preset == SonicMixPreset.TRAILER
    assert trailer_cfg.apply_narrator_baritone_dsp is True
    assert trailer_cfg.enable_808_drops is True
    assert trailer_cfg.enable_guillotine is True

    assert commercial_cfg.preset == SonicMixPreset.COMMERCIAL
    assert commercial_cfg.apply_narrator_baritone_dsp is False
    assert commercial_cfg.enable_guillotine is True

    assert diegetic_cfg.preset == SonicMixPreset.DIEGETIC
    assert diegetic_cfg.enable_808_drops is False
    assert diegetic_cfg.enable_guillotine is False

    with pytest.raises(ValueError):
        resolve_sonic_mix_preset_defaults("unknown_profile")
