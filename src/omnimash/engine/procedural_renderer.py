"""Procedural audio and FFmpeg visualizer fallback renderer for offline/mock simulation."""

from array import array
import math
import os
import re
import subprocess
from typing import Any
import uuid
import wave

_DIALOGUE_REGEX = re.compile(r'Dialogue:\s*"([^"]+)"', re.IGNORECASE)
_QUOTE_REGEX = re.compile(r'"([^"]{4,})"')
_ACTION_REGEX = re.compile(r"Action:\s*([^\n]+)", re.IGNORECASE)
_BRACKET_TAG_REGEX = re.compile(r"\[[A-Z\s_]+\]")


def _generate_dynamic_audio_wav(
    wav_path: str,
    prompt: str = "",
    voiceover: str | None = None,
    is_silent: bool = False,
    duration: int = 10,
) -> int:
    """Synthesizes dynamic multi-genre audio (BPM, bass frequency, chords, drum rhythm, speech formants, or complete silence) matching prompt directives.

    Uses a 2-second tiled array.array('h') buffer to avoid per-sample Python loop overhead across 10s+ clips.
    """
    sample_rate = 44100
    total_samples = sample_rate * max(1, duration)
    lower = prompt.lower()

    if is_silent or "silent" in lower or "mute" in lower:
        if dirname := os.path.dirname(wav_path):
            os.makedirs(dirname, exist_ok=True)
        temp_wav = f"{wav_path}.tmp.{uuid.uuid4().hex[:8]}"
        with wave.open(temp_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b"\x00\x00" * total_samples)
        os.replace(temp_wav, wav_path)
        return 0

    if "140" in lower or "drill" in lower or "trap" in lower:
        bpm = 140
        style = "drill"
    elif "anime" in lower or "vhs" in lower or "city pop" in lower or "lo-fi" in lower:
        bpm = 85
        style = "anime"
    elif "cyberpunk" in lower or "synth" in lower:
        bpm = 110
        style = "cyberpunk"
    else:
        bpm = 120
        style = "boombap"

    beat_interval = 60.0 / bpm
    has_vocal = bool(
        voiceover or "voiceover" in lower or "dialogue" in lower or ":" in prompt or '"' in prompt
    )

    cycle_seconds = min(max(1, duration), 2)
    cycle_samples = sample_rate * cycle_seconds
    cycle_buf = array("h", [0] * cycle_samples)
    two_pi = 2.0 * math.pi

    for i in range(cycle_samples):
        t = i / sample_rate
        beat_pos = t % beat_interval
        beat_index = int(t / beat_interval) % 4
        val = 0.0

        if style == "drill":
            if beat_index in (0, 2) and beat_pos < 0.2:
                slide_freq = 140.0 * math.exp(-beat_pos * 15.0) + 38.0
                val += 0.7 * math.sin(two_pi * slide_freq * beat_pos) * math.exp(-beat_pos * 10.0)
            if beat_index in (1, 3) and beat_pos < 0.15:
                noise = ((i * 1103515245 + 12345) & 0x7FFFFFFF) / 0x7FFFFFFF * 2.0 - 1.0
                val += 0.5 * noise * math.exp(-beat_pos * 30.0)
            hat_t = t % (beat_interval / 4.0)
            if hat_t < 0.03:
                noise = ((i * 214013 + 2531011) & 0x7FFFFFFF) / 0x7FFFFFFF * 2.0 - 1.0
                val += 0.2 * noise * math.exp(-hat_t * 100.0)

        elif style == "cyberpunk":
            arp_notes = (110.0, 130.8, 164.8, 196.0, 220.0, 261.6)
            synth_freq = arp_notes[int(t * 8.0) % 6]
            val += (
                0.3 * math.sin(two_pi * synth_freq * t) * (0.5 + 0.5 * math.sin(two_pi * 2.0 * t))
            )
            bass_t = (t * 55.0) % 1.0
            saw = bass_t * 2.0 - 1.0
            val += 0.3 * saw * math.exp(-(t % beat_interval) * 5.0)

        elif style == "anime":
            for f in (261.63, 329.63, 392.0):
                val += 0.12 * math.sin(two_pi * f * t)
            if beat_index == 0 and beat_pos < 0.3:
                val += 0.5 * math.sin(two_pi * 50.0 * beat_pos) * math.exp(-beat_pos * 8.0)
            crackle = ((i * 37911 + 71) & 0x7FFFFFFF) / 0x7FFFFFFF * 2.0 - 1.0
            val += 0.04 * crackle

        else:
            if beat_index in (0, 2) and beat_pos < 0.25:
                freq = 120.0 * math.exp(-beat_pos * 20.0) + 45.0
                val += 0.6 * math.sin(two_pi * freq * beat_pos) * math.exp(-beat_pos * 12.0)
            if beat_index in (1, 3) and beat_pos < 0.2:
                noise = ((i * 1103515245 + 12345) & 0x7FFFFFFF) / 0x7FFFFFFF * 2.0 - 1.0
                val += 0.4 * noise * math.exp(-beat_pos * 25.0) + 0.3 * math.sin(
                    two_pi * 220.0 * beat_pos
                ) * math.exp(-beat_pos * 18.0)
            hat_t = t % 0.125
            if hat_t < 0.05:
                noise = ((i * 214013 + 2531011) & 0x7FFFFFFF) / 0x7FFFFFFF * 2.0 - 1.0
                val += 0.15 * noise * math.exp(-hat_t * 80.0)
            bass_notes = (55.0, 65.4, 49.0, 58.2)
            bass_freq = bass_notes[int(t / 2.0) % 4]
            val += (
                0.35 * math.sin(two_pi * bass_freq * t) * (0.8 + 0.2 * math.sin(two_pi * 4.0 * t))
            )

        if has_vocal:
            vocal_mod = 0.5 + 0.5 * math.sin(two_pi * 3.5 * t)
            speaker_pitch = 160.0 if int(t / 3.0) % 2 == 0 else 240.0
            formant_val = (
                0.25 * math.sin(two_pi * speaker_pitch * t)
                + 0.15 * math.sin(two_pi * (speaker_pitch * 2.5) * t)
                + 0.1 * math.sin(two_pi * 1200.0 * t)
            ) * vocal_mod
            val = val * 0.18 + formant_val

        val = max(-1.0, min(1.0, val))
        cycle_buf[i] = int(val * 32767)

    repeats = (total_samples + cycle_samples - 1) // cycle_samples
    pcm_bytes = (cycle_buf.tobytes() * repeats)[: total_samples * 2]

    if dirname := os.path.dirname(wav_path):
        os.makedirs(dirname, exist_ok=True)
    temp_wav = f"{wav_path}.tmp.{uuid.uuid4().hex[:8]}"
    with wave.open(temp_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    os.replace(temp_wav, wav_path)

    return bpm


def extract_clean_dialogue_summary(prompt: str) -> str:
    """Extracts clean character dialogue quotes or short scene summaries from structured prompts for offline simulation subtitles."""
    if not prompt:
        return "AI Parody Storyboard Preview"

    dialogues = _DIALOGUE_REGEX.findall(prompt)
    if dialogues:
        return " ".join(dialogues)

    quotes = _QUOTE_REGEX.findall(prompt)
    if quotes:
        return " ".join(quotes)

    actions = _ACTION_REGEX.findall(prompt)
    if actions:
        return actions[0][:100]

    cleaned = _BRACKET_TAG_REGEX.sub("", prompt)
    lines = [
        line.strip()
        for line in cleaned.splitlines()
        if line.strip()
        and not line.strip().startswith(("Role ", "Active Roles:", "Environment:", "Aesthetic:"))
    ]
    return " ".join(lines)[:100] or "AI Parody Storyboard Preview"


def ensure_rendered_video(
    video_url: str,
    prompt: str = "",
    voiceover: str | None = None,
    is_silent: bool = False,
    audio_stem: str | None = None,
    duration: int = 1,
    subprocess_runner: Any = None,
) -> None:
    """Ensures a valid playable 720p 24fps MP4 with synthesized audio and crisp vector TrueType subtitles."""
    if not video_url.startswith("/static/"):
        return
    rel_path = video_url.lstrip("/")
    if os.path.exists(rel_path) and os.path.getsize(rel_path) > 1000:
        return
    os.makedirs(os.path.dirname(rel_path), exist_ok=True)

    run_cmd = subprocess_runner or subprocess.run
    effective_silent = is_silent or "silent" in prompt.lower() or "mute" in prompt.lower()

    unique_id = uuid.uuid4().hex[:8]
    wav_silent_path = f"static/rendered/temp_silent_{unique_id}.wav"
    txt_prompt_path = f"static/rendered/temp_prompt_{unique_id}.txt"
    txt_sub_path = f"static/rendered/temp_subtitles_{unique_id}.txt"
    temp_mp4_path = f"{rel_path}.tmp.{unique_id}.mp4"

    try:
        _generate_dynamic_audio_wav(
            wav_silent_path,
            prompt=prompt,
            voiceover=voiceover,
            is_silent=effective_silent,
            duration=duration,
        )
        target_audio_wav = wav_silent_path

        effective_voiceover = voiceover or extract_clean_dialogue_summary(prompt) or ""
        clean_prompt = prompt.replace("'", "").replace('"', "")[:80] or "AI Parody Video"
        clean_subtitles = effective_voiceover.replace("'", "").replace('"', "")[:100]

        with open(txt_prompt_path, "w", encoding="utf-8") as f:
            f.write(f"PROMPT: {clean_prompt}")
        with open(txt_sub_path, "w", encoding="utf-8") as f:
            f.write(f"🗣️ {clean_subtitles}")

        font_arg = ""
        font_candidates = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        )
        for fc in font_candidates:
            if os.path.exists(fc):
                font_arg = f":fontfile={fc}"
                break

        banner_img = "imgs/omnimash_banner.png"

        if os.path.exists(banner_img) and os.path.exists(target_audio_wav):
            try:
                filter_str = (
                    f"[0:v]scale=1280:720,fps=24,setpts=PTS-STARTPTS,"
                    f"drawbox=x=0:y=0:w=iw:h=60:color=black@0.75:t=fill,"
                    f"drawtext=text='🎬 OMNIMASH • DIGITAL DIRECTORS STUDIO'{font_arg}:fontcolor=0xDE5FE9:fontsize=24:x=30:y=18,"
                    f"drawbox=x=60:y=ih-150:w=iw-120:h=110:color=black@0.88:t=fill,"
                    f"drawbox=x=60:y=ih-150:w=iw-120:h=110:color=0x38BDF8:t=3,"
                    f"drawtext=textfile={txt_prompt_path}{font_arg}:fontcolor=0x94A3B8:fontsize=18:x=90:y=h-135,"
                    f"drawtext=textfile={txt_sub_path}{font_arg}:fontcolor=0xFACC15:fontsize=24:x=90:y=h-95[v]; [1:a]aresample=async=1:first_pts=0[a]"
                )
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    banner_img,
                    "-i",
                    target_audio_wav,
                    "-filter_complex",
                    filter_str,
                    "-map",
                    "[v]",
                    "-map",
                    "[a]",
                    "-r",
                    "24",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-shortest",
                    "-movflags",
                    "+faststart",
                    temp_mp4_path,
                ]
                res = run_cmd(cmd, capture_output=True, check=False)
                if res.returncode == 0 and os.path.exists(temp_mp4_path):
                    os.replace(temp_mp4_path, rel_path)
                    return
            except Exception:
                pass

        try:
            audio_inputs = (
                ["-i", target_audio_wav]
                if os.path.exists(target_audio_wav)
                else ["-f", "lavfi", "-i", f"anoisesrc=d={duration}:r=44100"]
            )
            filter_str = (
                f"[0:a]asplit=2[a_vis][a_out];[a_vis]showwaves=s=1280x720:mode=cline:colors=0xDE5FE9|0x34A853:r=24,"
                f"drawbox=x=0:y=0:w=iw:h=60:color=black@0.75:t=fill,"
                f"drawbox=x=60:y=ih-150:w=iw-120:h=110:color=black@0.88:t=fill,"
                f"drawbox=x=60:y=ih-150:w=iw-120:h=110:color=0x38BDF8:t=3,"
                f"drawtext=textfile={txt_sub_path}{font_arg}:fontcolor=0xFACC15:fontsize=24:x=90:y=h-95,format=yuv420p[v];[a_out]aresample=async=1:first_pts=0[a]"
            )
            cmd = [
                "ffmpeg",
                "-y",
                *audio_inputs,
                "-filter_complex",
                filter_str,
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-r",
                "24",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                "-movflags",
                "+faststart",
                temp_mp4_path,
            ]
            res = run_cmd(cmd, capture_output=True, check=False)
            if res.returncode == 0 and os.path.exists(temp_mp4_path):
                os.replace(temp_mp4_path, rel_path)
        except Exception:
            pass
    finally:
        for tmp_file in (wav_silent_path, txt_prompt_path, txt_sub_path, temp_mp4_path):
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
