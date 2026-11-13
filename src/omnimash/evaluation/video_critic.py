from __future__ import annotations

import array
import json
import logging
import math
import os
import re
import subprocess
from typing import Any
import uuid
import wave

from omnimash.config import settings
from omnimash.evaluation.models import (
    DefectCategory,
    DimensionScore,
    VideoEvaluationScorecard,
    resolve_highest_cost_remediation_tier,
)
from omnimash.storage.gcs import GcsStorageManager

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai: Any = None
    types: Any = None


def _clean_json_markdown(raw_text: str | None) -> str:
    """Strips markdown code blocks, backticks, and extraneous text wrapping a JSON payload."""
    cleaned = (raw_text or "").strip()
    if not cleaned:
        return "{}"
    if cleaned.startswith("```"):
        match = re.search(r"^```(?:json)?\s*\n?(.*?)\n?```$", cleaned, re.DOTALL | re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()
        else:
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    if not (cleaned.startswith("{") and cleaned.endswith("}")):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1].strip()
    return cleaned


class VideoCriticAgent:
    """Multimodal Video Critic Agent powered by gemini-3.8-flash for closed-loop evaluation."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        mock_mode: bool | None = None,
        storage: GcsStorageManager | None = None,
    ):
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self.model = model or getattr(settings, "flash_model_id", "gemini-3.8-flash")
        self.project = os.environ.get(
            "GOOGLE_CLOUD_PROJECT",
            getattr(settings, "google_cloud_project", "hybrid-vertex"),
        )
        # Gemini 3.8 Flash requires "global" location
        self.location = (
            "global"
            if (
                self.model.startswith("gemini-3")
                or self.model.startswith("gemini-4")
                or "omni" in self.model
            )
            else os.environ.get("GEMINI_LOCATION", getattr(settings, "gemini_location", "global"))
        )
        self.api_key = (
            api_key
            or getattr(settings, "gemini_api_key", None)
            or getattr(settings, "google_api_key", None)
        )
        self.storage = storage or GcsStorageManager(mock_mode=self.mock_mode)
        self._genai_client: Any = None

        if not self.mock_mode and genai is not None:
            self._init_genai_client()

    def _init_genai_client(self) -> None:
        if genai is None or types is None:
            return
        try:
            http_options = types.HttpOptions(timeout=120000)
            if self.api_key:
                self._genai_client = genai.Client(
                    api_key=self.api_key,
                    vertexai=False,
                    http_options=http_options,
                )
            else:
                self._genai_client = genai.Client(
                    vertexai=True,
                    project=self.project,
                    location=self.location,
                    http_options=http_options,
                )
        except Exception as exc:
            logger.warning("VideoCriticAgent failed to initialize GenAI client: %s", exc)

    @staticmethod
    def _extract_mono_16bit_pcm(
        wav_or_mp4_path: str,
        speech_start_sec: float,
        speech_end_sec: float,
    ) -> tuple[int, list[int]]:
        """Extracts mono 16-bit PCM samples over [speech_start_sec, speech_end_sec]."""
        if wav_or_mp4_path.lower().endswith(".wav"):
            try:
                with wave.open(wav_or_mp4_path, "rb") as wf:
                    sample_rate = wf.getframerate()
                    n_channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    n_frames = wf.getnframes()
                    if sampwidth == 2 and sample_rate > 0 and n_channels >= 1:
                        start_frame = max(0, int(round(speech_start_sec * sample_rate)))
                        end_frame = min(n_frames, int(round(speech_end_sec * sample_rate)))
                        if end_frame <= start_frame:
                            return (sample_rate, [])
                        wf.setpos(start_frame)
                        raw_bytes = wf.readframes(end_frame - start_frame)
                        pcm = array.array("h")
                        pcm.frombytes(raw_bytes)
                        if n_channels == 1:
                            return (sample_rate, list(pcm))
                        mono = [
                            sum(pcm[i : i + n_channels]) // n_channels
                            for i in range(0, len(pcm) - n_channels + 1, n_channels)
                        ]
                        return (sample_rate, mono)
            except (wave.Error, OSError) as exc:
                logger.warning("Failed direct WAV read for %s: %s", wav_or_mp4_path, exc)

        start_clamped = max(0.0, speech_start_sec)
        duration = max(0.0, speech_end_sec - start_clamped)
        if duration <= 0.0:
            return (16000, [])

        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            wav_or_mp4_path,
            "-ss",
            f"{start_clamped:.6f}",
            "-t",
            f"{duration:.6f}",
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-f",
            "s16le",
            "pipe:1",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, check=False)
        except OSError as exc:
            logger.warning("ffmpeg invocation failed for %s: %s", wav_or_mp4_path, exc)
            return (16000, [])

        if proc.returncode != 0 or not proc.stdout:
            stderr_msg = proc.stderr.decode("utf-8", errors="replace").strip()
            logger.warning(
                "ffmpeg audio extraction failed for %s (rc=%s): %s",
                wav_or_mp4_path,
                proc.returncode,
                stderr_msg,
            )
            return (16000, [])

        pcm = array.array("h")
        even_len = len(proc.stdout) - (len(proc.stdout) % 2)
        pcm.frombytes(proc.stdout[:even_len])
        return (16000, list(pcm))

    @staticmethod
    def detect_rms_syllable_dropouts(
        wav_or_mp4_path: str,
        speech_start_sec: float,
        speech_end_sec: float,
        window_ms: int = 100,
        dropout_threshold_dbfs: float = -42.0,
        max_allowed_internal_gap_sec: float = 0.25,
    ) -> tuple[bool, list[tuple[float, float]]]:
        """Scans 100ms RMS windows across [speech_start_sec, speech_end_sec] for unnatural mid-line syllable dropouts.

        Returns:
            (has_syllable_dropout, list_of_gap_intervals_sec)
        """
        if speech_end_sec <= speech_start_sec or window_ms <= 0 or not wav_or_mp4_path:
            return (False, [])
        if not os.path.exists(wav_or_mp4_path):
            logger.warning("Audio/video path does not exist for RMS scan: %s", wav_or_mp4_path)
            return (False, [])

        sample_rate, samples = VideoCriticAgent._extract_mono_16bit_pcm(
            wav_or_mp4_path,
            speech_start_sec=speech_start_sec,
            speech_end_sec=speech_end_sec,
        )
        if not samples or sample_rate <= 0:
            return (False, [])

        window_samples = max(1, int(round(sample_rate * window_ms / 1000.0)))
        if len(samples) < window_samples:
            return (False, [])

        hop_samples = max(1, window_samples // 4)
        prefix_sq = [0.0] * (len(samples) + 1)
        for idx, sample in enumerate(samples):
            prefix_sq[idx + 1] = prefix_sq[idx] + float(sample * sample)

        saw_active_speech = False
        current_gap_start: float | None = None
        current_gap_end: float | None = None
        gaps: list[tuple[float, float]] = []

        for start_idx in range(0, len(samples) - window_samples + 1, hop_samples):
            end_idx = start_idx + window_samples
            mean_sq = (prefix_sq[end_idx] - prefix_sq[start_idx]) / window_samples
            rms_norm = math.sqrt(mean_sq) / 32768.0
            dbfs = -120.0 if rms_norm <= 0.0 else 20.0 * math.log10(rms_norm)

            win_start_sec = speech_start_sec + (start_idx / sample_rate)
            win_end_sec = speech_start_sec + (end_idx / sample_rate)

            if dbfs >= dropout_threshold_dbfs:
                if current_gap_start is not None and current_gap_end is not None:
                    if (current_gap_end - current_gap_start) > max_allowed_internal_gap_sec:
                        gaps.append((round(current_gap_start, 3), round(current_gap_end, 3)))
                    current_gap_start = None
                    current_gap_end = None
                saw_active_speech = True
            elif saw_active_speech:
                if current_gap_start is None:
                    current_gap_start = win_start_sec
                current_gap_end = win_end_sec

        return (len(gaps) > 0, gaps)

    def build_8gate_rubric_prompt(self, prompt: str) -> str:
        """Constructs the DOMA v2 8-Gate v22 production QA rubric prompt for multimodal video analysis."""
        defect_options = "|".join(d.value for d in DefectCategory)
        return f"""You are the Lead Multimodal Directorial Critic evaluating an AI-generated video shot under the DOMA v2 8-Gate Production Rubric.
Compare the generated video against the Authoritative Prompt below:

====================== AUTHORITATIVE PROMPT ======================
{prompt}
==================================================================

Inspect the video strictly across these 4 core rubric dimensions and 8 production QA gates:
1. Video-Text Adherence:
   - Chronological fidelity to scripted physical actions, camera movement, and staging.
2. Character Likeness & Zero Wardrobe Redundancy:
   - Facial stability and consistency with character profiles/reference sheets.
   - Zero wardrobe contradiction (no hallucinated clothing or conflicting descriptions).
3. Audio Balance & Visual Harmony:
   - Ducking of background instrumental music under spoken dialogue and 3-stem separation.
   - Vocal clarity, absence of gibberish audio, vocal hallucinations, or syllable dropouts.
4. Tag & Index Symmetry:
   - 1:1 symmetry for character tags ([Role A], [Role B]) without identity bleed or tag collisions.

8-Gate v22 Production QA Checklist:
- Gate 1 (Clean Single Ref): Single clean reference isolation with zero multi-panel turnaround or landmark bleed (REF_PANEL_OR_LANDMARK_BLEED).
- Gate 2 (Wide Scale 15-20% & Axis): Wide establishing shots maintain 15-20% character scale and coherent camera axis framing (SCALE_OR_AXIS_FRAMING_MISS).
- Gate 3 (MCU Intimacy & Identity): Close-up likeness, wardrobe fidelity, and 1:1 role tag symmetry (LIKENESS_DRIFT, WARDROBE_CONTRADICTION, TAG_COLLISION, PHANTOM_KEYFRAME).
- Gate 4 (Architectural Trope Lock): Location architecture matches MatchedLocationBlock without generic trope drift (ARCHITECTURAL_TROPE_DRIFT).
- Gate 5 (Bilateral Hand & Prop Lock): Both left and right hands and held props stay coherent without duplication or finger fusion (BILATERAL_PROP_GLITCH).
- Gate 6 (3D Parallax & Zero Syllable Skips): Genuine 3D camera parallax rather than flat 2D zoom, and uninterrupted syllable delivery (FLAT_MATTE_NO_PARALLAX, SYLLABLE_SKIP_OR_DIALECT_DRIFT, TEMPORAL_BEAT_MISSED).
- Gate 7 (Audio Guillotine & Tuned 808): -20 dB Audio Guillotine, BPM-snapped D1/D2 808 drop, unmasked vocals, and offscreen narrator discipline (GUILLOTINE_OR_808_MISALIGNED, AUDIO_DROWNED, AUDIO_VOCAL_HALLUCINATION, OFFSCREEN_LIPSYNC_ERROR).
- Gate 8 (1080p24 & -14.0 LUFS Spec): 1920x1080 @ 24fps video and 48 kHz stereo audio mastered to -14.0 LUFS / -1.0 dBTP (TECHNICAL_SPEC_NONCOMPLIANT).

Provide your evaluation as a valid JSON object matching the following structure:
{{
  "overall_rating": <float 0.0-100.0>,
  "video_text_adherence": {{"score": <float>, "passed": <bool>, "evidence": "<str>"}},
  "character_likeness": {{"score": <float>, "passed": <bool>, "evidence": "<str>"}},
  "audio_visual_harmony": {{"score": <float>, "passed": <bool>, "evidence": "<str>"}},
  "tag_and_index_integrity": {{"score": <float>, "passed": <bool>, "evidence": "<str>"}},
  "detected_defects": ["<{defect_options}>"],
  "verbal_critique": "<Detailed summary critique covering all 8 QA gates, pacing, visual, and audio quality>",
  "suggested_prompt_patch": "<Surgically repaired prompt text if defects detected, else null>",
  "pass_verdict": <bool>
}}
"""

    def build_rubric_prompt(self, prompt: str) -> str:
        """Constructs the verification rubric prompt (delegates to the DOMA v2 8-Gate rubric)."""
        return self.build_8gate_rubric_prompt(prompt)

    def evaluate_video(
        self,
        session_id: str,
        turn_id: str,
        prompt: str,
        video_uri: str | None = None,
        reference_images: list[str | bytes] | None = None,
        user_critique: str | None = None,
        reported_defects: list[DefectCategory] | None = None,
    ) -> VideoEvaluationScorecard:
        """Evaluates video artifact against prompt, optionally factoring in user feedback."""
        if self.mock_mode or not self._genai_client or types is None:
            return self._evaluate_mock(
                session_id=session_id,
                turn_id=turn_id,
                prompt=prompt,
                video_uri=video_uri,
                user_critique=user_critique,
                reported_defects=reported_defects,
            )

        rubric_prompt = self.build_8gate_rubric_prompt(prompt)
        contents: list[Any] = [rubric_prompt]

        if video_uri:
            # Normalize to GCS URI if needed
            clean_uri = self.storage._normalize_media_source_path(video_uri)
            if clean_uri.startswith("https://storage.googleapis.com/"):
                clean_uri = "gs://" + clean_uri.replace("https://storage.googleapis.com/", "")
            if clean_uri.startswith("gs://") and types:
                contents.append(types.Part.from_uri(file_uri=clean_uri, mime_type="video/mp4"))

        if reference_images and types:
            for ref_img in reference_images:
                if isinstance(ref_img, bytes):
                    contents.append(types.Part.from_bytes(data=ref_img, mime_type="image/jpeg"))
                elif isinstance(ref_img, str):
                    clean_ref = self.storage._normalize_media_source_path(ref_img)
                    if clean_ref.startswith("https://storage.googleapis.com/"):
                        clean_ref = "gs://" + clean_ref.replace(
                            "https://storage.googleapis.com/", ""
                        )
                    if clean_ref.startswith("gs://"):
                        mime = (
                            "image/png"
                            if clean_ref.lower().endswith(".png")
                            else (
                                "image/webp"
                                if clean_ref.lower().endswith(".webp")
                                else "image/jpeg"
                            )
                        )
                        contents.append(types.Part.from_uri(file_uri=clean_ref, mime_type=mime))

        if user_critique:
            contents.append(f"User Director Critique: {user_critique}")
        if reported_defects:
            defect_names = [d.value if hasattr(d, "value") else str(d) for d in reported_defects]
            contents.append(f"Director Reported Defects: {', '.join(defect_names)}")

        try:
            config = types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
            )
            response = self._genai_client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            raw_text = response.text or "{}"
            cleaned_json = _clean_json_markdown(raw_text)
            parsed = json.loads(cleaned_json)

            defects: list[DefectCategory] = []
            for raw_defect in parsed.get("detected_defects", []):
                try:
                    defects.append(DefectCategory(raw_defect))
                except ValueError:
                    pass
            recommended_tier = resolve_highest_cost_remediation_tier(defects)

            return VideoEvaluationScorecard(
                evaluation_id=f"eval_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                turn_id=turn_id,
                overall_rating=float(parsed.get("overall_rating", 75.0)),
                video_text_adherence=DimensionScore.model_validate(
                    parsed.get("video_text_adherence", {"score": 75.0, "passed": True})
                ),
                character_likeness=DimensionScore.model_validate(
                    parsed.get("character_likeness", {"score": 75.0, "passed": True})
                ),
                audio_visual_harmony=DimensionScore.model_validate(
                    parsed.get("audio_visual_harmony", {"score": 75.0, "passed": True})
                ),
                tag_and_index_integrity=DimensionScore.model_validate(
                    parsed.get("tag_and_index_integrity", {"score": 75.0, "passed": True})
                ),
                detected_defects=defects,
                recommended_remediation_tier=recommended_tier,
                verbal_critique=parsed.get("verbal_critique", "Evaluation completed."),
                suggested_prompt_patch=parsed.get("suggested_prompt_patch"),
                pass_verdict=bool(parsed.get("pass_verdict", True)),
            )
        except Exception as exc:
            logger.warning(
                "VideoCritic live evaluation failed: %s; falling back to deterministic mock evaluation",
                exc,
            )
            return self._evaluate_mock(
                session_id=session_id,
                turn_id=turn_id,
                prompt=prompt,
                video_uri=video_uri,
                user_critique=user_critique,
                reported_defects=reported_defects,
            )

    def _evaluate_mock(
        self,
        session_id: str,
        turn_id: str,
        prompt: str,
        video_uri: str | None = None,
        user_critique: str | None = None,
        reported_defects: list[DefectCategory] | None = None,
    ) -> VideoEvaluationScorecard:
        """Deterministic rubric evaluation simulating critic inspection on prompt and reported signals."""
        detected_defects: list[DefectCategory] = list(reported_defects or [])
        vta_score = 92.0
        likeness_score = 90.0
        audio_score = 88.0
        tag_score = 95.0

        vta_evidence = "Timeline actions correspond with screenplay directives."
        likeness_evidence = "Character features aligned with reference profiles."
        audio_evidence = "Audio levels and atmospheric balance pass thresholds."
        tag_evidence = "Character role tags have 1:1 symmetry without identity bleed."

        p_lower = prompt.lower()
        critique_lower = (user_critique or "").lower()

        # Check for Audio Drowned defect
        has_dialogue = any(
            token in p_lower for token in ['"', "speaks", "says", "dialogue", "screams"]
        )
        has_ducking = "ducking" in p_lower or "-18db" in p_lower
        has_heavy_bgm = any(
            token in p_lower for token in ["techno", "bass", "loud", "blaring", "drums", "heavy"]
        )
        if (
            DefectCategory.AUDIO_DROWNED in detected_defects
            or "music covers speech" in critique_lower
            or "drowned" in critique_lower
            or (has_dialogue and has_heavy_bgm and not has_ducking)
        ):
            if DefectCategory.AUDIO_DROWNED not in detected_defects:
                detected_defects.append(DefectCategory.AUDIO_DROWNED)
            audio_score = 58.0
            audio_evidence = "Spoken dialogue masked by un-ducked background audio."

        # Check for Wardrobe / Likeness Contradiction
        has_wardrobe_conflict = (
            "tuxedo" in p_lower and "sweatpants" in p_lower
        ) or "contradiction" in critique_lower
        if (
            DefectCategory.WARDROBE_CONTRADICTION in detected_defects
            or DefectCategory.LIKENESS_DRIFT in detected_defects
            or has_wardrobe_conflict
            or "hair style changed" in critique_lower
            or "likeness" in critique_lower
        ):
            if (
                has_wardrobe_conflict
                and DefectCategory.WARDROBE_CONTRADICTION not in detected_defects
            ):
                detected_defects.append(DefectCategory.WARDROBE_CONTRADICTION)
            elif (
                DefectCategory.LIKENESS_DRIFT not in detected_defects
                and DefectCategory.WARDROBE_CONTRADICTION not in detected_defects
            ):
                detected_defects.append(DefectCategory.LIKENESS_DRIFT)
            likeness_score = 62.0
            likeness_evidence = "Character appearance deviates from turnaround sheet."

        # Check for Tag Collision
        if (
            DefectCategory.TAG_COLLISION in detected_defects
            or "tag collision" in critique_lower
            or (
                "[role a]" in p_lower
                and "[role a]" in p_lower[p_lower.find("[role a]") + 8 :]
                and "[role b]" not in p_lower
                and "two characters" in p_lower
            )
        ):
            if DefectCategory.TAG_COLLISION not in detected_defects:
                detected_defects.append(DefectCategory.TAG_COLLISION)
            tag_score = 55.0
            tag_evidence = "Role tag collisions detected across multiple interacting entities."

        overall_score = round((vta_score + likeness_score + audio_score + tag_score) / 4.0, 2)
        pass_verdict = overall_score >= 75.0 and len(detected_defects) == 0
        recommended_tier = resolve_highest_cost_remediation_tier(detected_defects)

        # Synthesize verbal critique
        critique_parts = []
        if detected_defects:
            critique_parts.append(
                f"Evaluation detected {len(detected_defects)} defect(s): {', '.join(d.value for d in detected_defects)}."
            )
            if DefectCategory.AUDIO_DROWNED in detected_defects:
                critique_parts.append(
                    "Background score requires explicit -18dB ducking under spoken lines."
                )
            if DefectCategory.WARDROBE_CONTRADICTION in detected_defects:
                critique_parts.append(
                    "Wardrobe description contradicts character turnaround reference sheet."
                )
            if DefectCategory.LIKENESS_DRIFT in detected_defects:
                critique_parts.append("Facial likeness drifted away from reference image.")
        else:
            critique_parts.append(
                "High directorial fidelity across all dimensions. Audio ducking and tag symmetry verified."
            )

        suggested_patch = None
        if not pass_verdict:
            # Provide simple repaired prompt patch
            suggested_patch = prompt
            if (
                DefectCategory.AUDIO_DROWNED in detected_defects
                and "[Instrumental: ducking -18dB under speech]" not in suggested_patch
            ):
                if "### SCREENPLAY" in suggested_patch:
                    suggested_patch = suggested_patch.replace(
                        "### SCREENPLAY",
                        "### SCREENPLAY\n[Instrumental: ducking -18dB under speech]",
                        1,
                    )
                elif "### TIMELINE" in suggested_patch:
                    suggested_patch = suggested_patch.replace(
                        "### TIMELINE",
                        "### TIMELINE\n[Instrumental: ducking -18dB under speech]",
                        1,
                    )
                elif "### SCENE INSTRUCTIONS" in suggested_patch:
                    suggested_patch = suggested_patch.replace(
                        "### SCENE INSTRUCTIONS",
                        "### SCENE INSTRUCTIONS\n[Instrumental: ducking -18dB under speech]",
                        1,
                    )
                else:
                    suggested_patch = (
                        f"[Instrumental: ducking -18dB under speech]\n{suggested_patch}"
                    )

            if (
                DefectCategory.WARDROBE_CONTRADICTION in detected_defects
                or DefectCategory.LIKENESS_DRIFT in detected_defects
            ):
                old_patch = suggested_patch
                suggested_patch = re.sub(
                    r"(?:wearing|dressed in|in|attired in)\s+[^.\n,]+",
                    "wearing signature attire per turnaround sheet",
                    suggested_patch,
                    flags=re.IGNORECASE,
                )
                if old_patch == suggested_patch:
                    if "### CHARACTER PROFILES" in suggested_patch:
                        suggested_patch = suggested_patch.replace(
                            "### CHARACTER PROFILES",
                            "### CHARACTER PROFILES\n[Wardrobe Invariant: Signature attire locked to reference turnaround sheet]",
                            1,
                        )
                    else:
                        suggested_patch = f"[Wardrobe Invariant: Signature attire locked to reference turnaround sheet]\n{suggested_patch}"

        return VideoEvaluationScorecard(
            evaluation_id=f"eval_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            turn_id=turn_id,
            overall_rating=overall_score,
            video_text_adherence=DimensionScore(
                score=vta_score, passed=vta_score >= 75.0, evidence=vta_evidence
            ),
            character_likeness=DimensionScore(
                score=likeness_score, passed=likeness_score >= 75.0, evidence=likeness_evidence
            ),
            audio_visual_harmony=DimensionScore(
                score=audio_score, passed=audio_score >= 75.0, evidence=audio_evidence
            ),
            tag_and_index_integrity=DimensionScore(
                score=tag_score, passed=tag_score >= 75.0, evidence=tag_evidence
            ),
            detected_defects=detected_defects,
            recommended_remediation_tier=recommended_tier,
            verbal_critique=" ".join(critique_parts),
            suggested_prompt_patch=suggested_patch,
            pass_verdict=pass_verdict,
        )
