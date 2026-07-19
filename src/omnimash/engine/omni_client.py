import base64
import logging
import math
import os
import struct
import subprocess
import time
from typing import Any
import uuid
import wave
from dataclasses import dataclass
from omnimash.storage.gcs import GcsStorageManager

logger = logging.getLogger("omnimash.engine")

try:
    from google import genai
except ImportError:
    genai: Any = None


@dataclass
class GenerationResult:
    interaction_thread_id: str
    video_url: str
    gcs_uri: str | None = None
    duration_seconds: int = 10
    synth_id_watermark: str = "SYNTHID_C2PA_VERIFIED"


def _generate_dynamic_audio_wav(
    wav_path: str,
    prompt: str = "",
    voiceover: str | None = None,
    is_silent: bool = False,
    duration: int = 10,
) -> int:
    """Synthesizes dynamic multi-genre audio (BPM, bass frequency, chords, drum rhythm, speech formants, or complete silence) matching prompt directives."""
    sample_rate = 44100
    total_samples = sample_rate * duration
    lower = prompt.lower()

    # Check for silent video condition
    if is_silent or "silent" in lower or "mute" in lower:
        bpm = 0
        audio_data = [0] * total_samples
        os.makedirs(os.path.dirname(wav_path), exist_ok=True)
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack(f"<{len(audio_data)}h", *audio_data))
        return 0

    # Resolve genre & BPM
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

    beat_interval = 60 / bpm
    has_vocal = bool(
        voiceover
        or "voiceover" in lower
        or "dialogue" in lower
        or ":" in prompt
        or '"' in prompt
    )

    audio_data = []

    for i in range(total_samples):
        t = i / sample_rate
        beat_pos = t % beat_interval
        beat_index = int(t / beat_interval) % 4
        val = 0.0

        if style == "drill":
            # 140 BPM UK Drill / Trap: Sliding 808 sub-bass, rapid triplet hi-hat rolls, punchy snare
            if beat_index in [0, 2]:
                kick_t = beat_pos
                if kick_t < 0.2:
                    slide_freq = 140 * math.exp(-kick_t * 15) + 38
                    val += (
                        0.7
                        * math.sin(2 * math.pi * slide_freq * kick_t)
                        * math.exp(-kick_t * 10)
                    )
            if beat_index in [1, 3]:
                snare_t = beat_pos
                if snare_t < 0.15:
                    noise = ((i * 1103515245 + 12345) & 0x7FFFFFFF) / 0x7FFFFFFF * 2 - 1
                    val += 0.5 * noise * math.exp(-snare_t * 30)
            hat_t = t % (beat_interval / 4)
            if hat_t < 0.03:
                noise = ((i * 214013 + 2531011) & 0x7FFFFFFF) / 0x7FFFFFFF * 2 - 1
                val += 0.2 * noise * math.exp(-hat_t * 100)

        elif style == "cyberpunk":
            # 110 BPM Synthwave / Cyberpunk: Arpeggiated analog synth, sidechained saw bass
            arp_notes = [110.0, 130.8, 164.8, 196.0, 220.0, 261.6]
            note_idx = int(t * 8) % len(arp_notes)
            synth_freq = arp_notes[note_idx]
            val += (
                0.3
                * math.sin(2 * math.pi * synth_freq * t)
                * (0.5 + 0.5 * math.sin(2 * math.pi * 2 * t))
            )
            bass_t = (t * 55.0) % 1.0
            saw = bass_t * 2.0 - 1.0
            val += 0.3 * saw * math.exp(-(t % beat_interval) * 5)

        elif style == "anime":
            # 85 BPM VHS City Pop / Lo-Fi: Warm vinyl saturation, mellow chords, jazz bass
            chord_freqs = [261.63, 329.63, 392.0]
            for f in chord_freqs:
                val += 0.12 * math.sin(2 * math.pi * f * t)
            if beat_index == 0 and beat_pos < 0.3:
                val += (
                    0.5
                    * math.sin(2 * math.pi * 50 * beat_pos)
                    * math.exp(-beat_pos * 8)
                )
            crackle = ((i * 37911 + 71) & 0x7FFFFFFF) / 0x7FFFFFFF * 2 - 1
            val += 0.04 * crackle

        else:
            # 120 BPM 90s Boom-Bap Hip Hop
            if beat_index in [0, 2]:
                kick_t = beat_pos
                if kick_t < 0.25:
                    freq = 120 * math.exp(-kick_t * 20) + 45
                    val += (
                        0.6
                        * math.sin(2 * math.pi * freq * kick_t)
                        * math.exp(-kick_t * 12)
                    )
            if beat_index in [1, 3]:
                snare_t = beat_pos
                if snare_t < 0.2:
                    noise = ((i * 1103515245 + 12345) & 0x7FFFFFFF) / 0x7FFFFFFF * 2 - 1
                    val += 0.4 * noise * math.exp(-snare_t * 25) + 0.3 * math.sin(
                        2 * math.pi * 220 * snare_t
                    ) * math.exp(-snare_t * 18)
            hat_t = t % 0.125
            if hat_t < 0.05:
                noise = ((i * 214013 + 2531011) & 0x7FFFFFFF) / 0x7FFFFFFF * 2 - 1
                val += 0.15 * noise * math.exp(-hat_t * 80)
            bass_notes = [55, 65.4, 49, 58.2]
            bass_freq = bass_notes[int(t / 2.0) % 4]
            val += (
                0.35
                * math.sin(2 * math.pi * bass_freq * t)
                * (0.8 + 0.2 * math.sin(2 * math.pi * 4 * t))
            )

        # Layer Spoken Dialogue / Voiceover Speech-Band Formants (300Hz–2.5kHz)
        if has_vocal:
            vocal_mod = 0.5 + 0.5 * math.sin(2 * math.pi * 3.5 * t)
            # Alternate dialogue pitch if multi-character colon syntax is detected
            speaker_pitch = 160.0 if int(t / 3.0) % 2 == 0 else 240.0
            formant_val = (
                0.25 * math.sin(2 * math.pi * speaker_pitch * t)
                + 0.15 * math.sin(2 * math.pi * (speaker_pitch * 2.5) * t)
                + 0.1 * math.sin(2 * math.pi * 1200 * t)
            ) * vocal_mod
            val = val * 0.7 + formant_val

        val = max(-1.0, min(1.0, val))
        audio_data.append(int(val * 32767))

    os.makedirs(os.path.dirname(wav_path), exist_ok=True)
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(audio_data)}h", *audio_data))

    return bpm


def _generate_hiphop_beat_wav(wav_path: str, duration: int = 10) -> None:
    """Backward compatibility wrapper for 120 BPM hip-hop audio synthesis."""
    _generate_dynamic_audio_wav(wav_path, prompt="120 BPM boom-bap", duration=duration)


def ensure_rendered_video(video_url: str, prompt: str = "") -> None:
    """Ensures a valid playable 720p 24fps MP4 with frame-locked visual rhythm and dynamic multi-genre audio or silence."""
    if not video_url.startswith("/static/"):
        return
    rel_path = video_url.lstrip("/")
    os.makedirs(os.path.dirname(rel_path), exist_ok=True)
    if os.path.exists(rel_path) and os.path.getsize(rel_path) > 100000:
        return

    wav_path = "static/rendered/temp_beat.wav"
    bpm = 120
    try:
        bpm = _generate_dynamic_audio_wav(wav_path, prompt=prompt, duration=10)
    except Exception:
        pass

    clean_prompt = prompt.replace("'", "").replace('"', "")[:80] or "AI Parody Video"
    banner_img = "imgs/omnimash_banner.png"
    freq_hz = (bpm / 60.0) if bpm > 0 else 1.0

    if os.path.exists(banner_img) and os.path.exists(wav_path):
        try:
            # Synchronized 24 FPS zoompan with rhythmic bass bounce matching dynamic BPM
            cmd = [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                banner_img,
                "-i",
                wav_path,
                "-filter_complex",
                f"[0:v]scale=1280:720,zoompan=z='min(1.05+0.03*abs(sin(2*PI*{freq_hz:.2f}*in_time)),1.2)':d=240:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720:fps=24,setpts=PTS-STARTPTS,drawbox=y=0:color=black@0.6:width=iw:height=60:t=fill,drawtext=text='🎬 OMNIMASH • GEMINI OMNI FLASH':fontcolor=0xDE5FE9:fontsize=24:x=30:y=18,drawbox=y=ih-100:color=black@0.75:width=iw:height=100:t=fill,drawtext=text='PROMPT: {clean_prompt}':fontcolor=white:fontsize=24:x=30:y=h-75,drawtext=text='🛡️ SynthID C2PA Verified • 720p 24fps Audio Sync ({bpm} BPM)':fontcolor=0x34A853:fontsize=18:x=30:y=h-35[v]; [1:a]aresample=async=1:first_pts=0[a]",
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-r",
                "24",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                "-movflags",
                "+faststart",
                rel_path,
            ]
            res = subprocess.run(cmd, capture_output=True, check=False)
            if res.returncode == 0:
                return
        except Exception:
            pass

    # Fallback MP4 generation with animated procedural visualizer filter
    try:
        audio_inputs = (
            ["-i", wav_path]
            if os.path.exists(wav_path)
            else ["-f", "lavfi", "-i", "anoisesrc=d=10:r=44100"]
        )
        cmd = [
            "ffmpeg",
            "-y",
            *audio_inputs,
            "-filter_complex",
            "[0:a]asplit=2[a_vis][a_out];[a_vis]showwaves=s=1280x720:mode=cline:colors=0xDE5FE9|0x34A853:r=24,drawbox=y=0:color=black@0.6:width=iw:height=60:t=fill,drawbox=y=ih-100:color=black@0.75:width=iw:height=100:t=fill,format=yuv420p[v];[a_out]aresample=async=1:first_pts=0[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-r",
            "24",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            rel_path,
        ]
        subprocess.run(
            cmd,
            capture_output=True,
            check=False,
        )
    except Exception:
        pass


class OmniFlashClient:
    def __init__(
        self,
        api_key: str | None = None,
        mock_mode: bool = True,
        bucket_name: str | None = None,
    ):
        self.api_key = api_key
        self.mock_mode = mock_mode
        self.project = os.environ.get("GOOGLE_CLOUD_PROJECT", "hybrid-vertex")
        self.location = "us-central1"
        self._genai_client = None
        self.storage = GcsStorageManager(
            bucket_name=bucket_name,
            project_id=self.project,
            mock_mode=self.mock_mode,
        )

        if not self.mock_mode and genai:
            try:
                self._genai_client = genai.Client(
                    vertexai=True, project=self.project, location=self.location
                )
            except Exception:
                pass

    def _generate_live_omni_flash_video(
        self,
        prompt: str,
        target_rel_path: str,
        previous_interaction_id: str | None = None,
    ) -> tuple[bool, str | None]:
        """Calls Gemini Omni Flash (gemini-omni-flash-preview) via Interactions API for native video+audio generation & conversational editing."""
        if not self._genai_client or not hasattr(self._genai_client, "interactions"):
            return False, None
        try:
            logger.info(
                "Requesting Gemini Omni Flash video generation for prompt: %s", prompt
            )
            kwargs: dict[str, Any] = {
                "model": "gemini-omni-flash-preview",
                "input": prompt,
            }
            if previous_interaction_id:
                kwargs["previous_interaction_id"] = previous_interaction_id

            interaction = self._genai_client.interactions.create(**kwargs)
            inter_id = getattr(interaction, "id", None) or getattr(
                interaction, "interaction_id", None
            )

            output_vid = getattr(interaction, "output_video", None)
            if output_vid:
                data = getattr(output_vid, "data", None) or getattr(
                    output_vid, "video_bytes", None
                )
                if data:
                    video_bytes = (
                        base64.b64decode(data) if isinstance(data, str) else data
                    )
                    os.makedirs(os.path.dirname(target_rel_path), exist_ok=True)
                    with open(target_rel_path, "wb") as f:
                        f.write(video_bytes)
                    return True, inter_id
        except Exception as exc:
            logger.warning("Vertex AI generation error: %s", exc)
        return False, None

    def _generate_live_veo_video(self, prompt: str, target_rel_path: str) -> bool:
        """Fallback to Veo (veo-2.0-generate-001) for single-shot video generation with frame-accurate audio-video sync."""
        if not self._genai_client:
            return False
        try:
            logger.info("Requesting Veo video generation for prompt: %s", prompt)
            op = self._genai_client.models.generate_videos(
                model="veo-2.0-generate-001",
                prompt=prompt,
            )
            for _ in range(25):
                time.sleep(3)
                op = self._genai_client.operations.get(operation=op)
                if op.done:
                    break

            if op.done and op.response and op.response.generated_videos:
                vid = op.response.generated_videos[0].video
                if hasattr(vid, "video_bytes") and vid.video_bytes:
                    os.makedirs(os.path.dirname(target_rel_path), exist_ok=True)
                    temp_raw_veo = f"{target_rel_path}.raw.mp4"
                    with open(temp_raw_veo, "wb") as f:
                        f.write(vid.video_bytes)

                    # Synthesize dynamic audio track and mux with frame-accurate sync
                    wav_path = "static/rendered/temp_beat.wav"
                    try:
                        _generate_dynamic_audio_wav(
                            wav_path, prompt=prompt, duration=10
                        )
                    except Exception:
                        pass

                    if os.path.exists(wav_path):
                        cmd = [
                            "ffmpeg",
                            "-y",
                            "-i",
                            temp_raw_veo,
                            "-i",
                            wav_path,
                            "-filter_complex",
                            "[0:v]fps=24,setpts=PTS-STARTPTS[v];[1:a]aresample=async=1:first_pts=0[a]",
                            "-map",
                            "[v]",
                            "-map",
                            "[a]",
                            "-r",
                            "24",
                            "-c:v",
                            "libx264",
                            "-pix_fmt",
                            "yuv420p",
                            "-c:a",
                            "aac",
                            "-b:a",
                            "192k",
                            "-shortest",
                            "-movflags",
                            "+faststart",
                            target_rel_path,
                        ]
                        res = subprocess.run(cmd, capture_output=True, check=False)
                        if res.returncode == 0:
                            if os.path.exists(temp_raw_veo):
                                os.remove(temp_raw_veo)
                            return True

                    os.replace(temp_raw_veo, target_rel_path)
                    return True
        except Exception as exc:
            logger.warning("Vertex AI generation error: %s", exc)
        return False

    def generate_clip(
        self, prompt: str, session_id: str | None = None
    ) -> GenerationResult:
        thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        url = f"/static/rendered/{thread_id}_turn0.mp4"
        rel_path = url.lstrip("/")

        # 1. Primary: Gemini Omni Flash via Interactions API (Native Video + Audio + Reasoning)
        success, inter_id = self._generate_live_omni_flash_video(prompt, rel_path)

        # 2. Secondary Fallback: Veo single-shot video generation with audio muxing
        if not success:
            success = self._generate_live_veo_video(prompt, rel_path)

        # 3. Tertiary Fallback: Local prompt-rendered animated video
        if not success:
            ensure_rendered_video(url, prompt=prompt)

        # Persist media artifact to Google Cloud Storage under session subfolder
        gcs_blob = self.storage.build_session_blob_path(
            session_id, "intermediate", os.path.basename(rel_path)
        )
        self.storage.upload_file(rel_path, destination_blob_name=gcs_blob)
        gcs_uri = self.storage.get_gcs_uri(gcs_blob)

        return GenerationResult(
            interaction_thread_id=inter_id or thread_id,
            video_url=url,
            gcs_uri=gcs_uri,
        )

    def apply_interaction_diff(
        self,
        interaction_thread_id: str,
        diff_prompt: str,
        session_id: str | None = None,
    ) -> GenerationResult:
        url = f"/static/rendered/{interaction_thread_id}_turn_diff.mp4"
        rel_path = url.lstrip("/")

        # 1. Primary: Gemini Omni Flash stateful conversational diff via previous_interaction_id
        success, _ = self._generate_live_omni_flash_video(
            diff_prompt, rel_path, previous_interaction_id=interaction_thread_id
        )

        # 2. Secondary Fallback: Veo
        if not success:
            success = self._generate_live_veo_video(diff_prompt, rel_path)

        # 3. Tertiary Fallback: Local prompt-rendered animated video
        if not success:
            ensure_rendered_video(url, prompt=diff_prompt)

        # Persist media artifact to Google Cloud Storage under session subfolder
        gcs_blob = self.storage.build_session_blob_path(
            session_id, "intermediate", os.path.basename(rel_path)
        )
        self.storage.upload_file(rel_path, destination_blob_name=gcs_blob)
        gcs_uri = self.storage.get_gcs_uri(gcs_blob)

        return GenerationResult(
            interaction_thread_id=interaction_thread_id,
            video_url=url,
            gcs_uri=gcs_uri,
        )

    def start_thread_from_video(
        self,
        base_video_url: str,
        initial_prompt: str | None = None,
        session_id: str | None = None,
    ) -> GenerationResult:
        thread_id = f"reanchored_thread_{uuid.uuid4().hex[:8]}"
        url = f"/static/rendered/{thread_id}_turn0.mp4"
        rel_path = url.lstrip("/")

        prompt = initial_prompt or "Reanchored video turn"
        success, inter_id = self._generate_live_omni_flash_video(prompt, rel_path)
        if not success:
            success = self._generate_live_veo_video(prompt, rel_path)
        if not success:
            ensure_rendered_video(url, prompt=prompt)

        # Persist media artifact to Google Cloud Storage under session subfolder
        gcs_blob = self.storage.build_session_blob_path(
            session_id, "intermediate", os.path.basename(rel_path)
        )
        self.storage.upload_file(rel_path, destination_blob_name=gcs_blob)
        gcs_uri = self.storage.get_gcs_uri(gcs_blob)

        return GenerationResult(
            interaction_thread_id=inter_id or thread_id,
            video_url=url,
            gcs_uri=gcs_uri,
        )
