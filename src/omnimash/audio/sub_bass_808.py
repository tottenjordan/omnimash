"""Key-locked 808 sub-bass synthesizer with pitch-envelope punch and BPM beat-grid snapping."""

from __future__ import annotations

import math
import os
import struct
import wave

NOTE_FREQUENCIES_HZ: dict[str, float] = {
    "C1": 32.703,
    "C#1": 34.648,
    "D1": 36.708,
    "D#1": 38.891,
    "E1": 41.203,
    "F1": 43.654,
    "F#1": 46.249,
    "G1": 48.999,
    "G#1": 51.913,
    "A1": 55.000,
    "A#1": 58.270,
    "B1": 61.735,
}


def write_mock_tone_wav(
    output_path: str,
    duration_sec: float = 1.5,
    freq_hz: float = 110.0,
    amplitude: float = 0.08,
    sample_rate: int = 48000,
) -> str:
    """Writes a playable 48kHz stereo PCM16 RIFF WAV for mock mode and hermetic tests."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    total_frames = max(1, int(round(max(0.05, duration_sec) * sample_rate)))

    # Precompute one integer cycle of the tone and tile it to avoid per-sample Python loops on long durations.
    period_samples = max(1, int(round(sample_rate / max(20.0, freq_hz))))
    cycle_buf = bytearray()
    for i in range(period_samples):
        val = int(
            max(-1.0, min(1.0, amplitude * math.sin(2.0 * math.pi * i / period_samples))) * 32767.0
        )
        cycle_buf.extend(struct.pack("<hh", val, val))

    frame_size = 4  # 2 channels * 2 bytes (16-bit PCM)
    target_bytes = total_frames * frame_size
    repeats = (target_bytes // len(cycle_buf)) + 1
    pcm_bytes = (bytes(cycle_buf) * repeats)[:target_bytes]

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)

    return output_path


def snap_timestamp_to_bpm_grid(
    raw_timestamp_sec: float,
    bpm: float = 142.0,
    beat_offset: float = 0.0,
) -> float:
    """Snaps an 808 trigger timestamp to the nearest beat (plus optional beat_offset) at the given BPM."""
    if bpm <= 0:
        return max(0.0, raw_timestamp_sec)
    beat_dur = 60.0 / float(bpm)
    nearest_beat_idx = round(raw_timestamp_sec / beat_dur)
    snapped = (nearest_beat_idx + beat_offset) * beat_dur
    return round(max(0.0, snapped), 4)


def synthesize_tuned_808_wav(
    output_path: str,
    root_note: str = "D1",
    duration_sec: float = 2.2,
    sample_rate: int = 48000,
    second_harmonic_ratio: float = 0.38,
    drive: float = 1.65,
) -> str:
    """Synthesizes a 48kHz stereo WAV 808 sub-bass drop with fundamental + 2nd harmonic saturation."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    f0 = NOTE_FREQUENCIES_HZ.get(root_note.upper().strip(), 36.708)
    f_harm2 = f0 * 2.0  # e.g. D1 (36.71 Hz) + D2 (73.42 Hz)
    num_samples = max(1, int(duration_sec * sample_rate))

    phase1 = 0.0
    phase2 = 0.0
    frames = bytearray()
    tanh_drive = math.tanh(drive) if drive != 0.0 else 1.0

    for i in range(num_samples):
        t = i / float(sample_rate)
        # 18ms punchy pitch envelope dropping from 3.0 * f0 -> f0
        pitch_mult = 1.0 + 2.0 * math.exp(-t / 0.018)
        inst_f1 = f0 * pitch_mult
        inst_f2 = f_harm2 * pitch_mult

        phase1 += (2.0 * math.pi * inst_f1) / sample_rate
        phase2 += (2.0 * math.pi * inst_f2) / sample_rate

        # Fast 6ms attack + smooth exponential sub decay
        attack_env = 1.0 - math.exp(-t / 0.006)
        decay_env = math.exp(-t / 0.85)
        amp_env = attack_env * decay_env

        raw_sig = math.sin(phase1) + second_harmonic_ratio * math.sin(phase2)
        saturated = math.tanh(drive * raw_sig) / tanh_drive
        sample_val = int(max(-1.0, min(1.0, saturated * amp_env * 0.92)) * 32767.0)
        frames.extend(struct.pack("<hh", sample_val, sample_val))

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))

    return output_path
