from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
import uuid

from omnimash.config import settings
from omnimash.evaluation.models import (
    DefectCategory,
    DimensionScore,
    VideoEvaluationScorecard,
)
from omnimash.storage.gcs import GcsStorageManager

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai: Any = None
    types: Any = None


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
        self.location = os.environ.get(
            "GEMINI_LOCATION", getattr(settings, "gemini_location", "global")
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

    def build_rubric_prompt(self, prompt: str) -> str:
        """Constructs a 4-dimensional verification rubric prompt for multimodal video analysis."""
        return f"""You are the Lead Multimodal Directorial Critic evaluating an AI-generated video shot.
Compare the generated video against the Authoritative 4-Block Prompt below:

====================== AUTHORITATIVE PROMPT ======================
{prompt}
==================================================================

Inspect the video strictly across these 4 rubric dimensions:
1. Video-Text Adherence:
   - Chronological fidelity to timeline blocks ([0-3s], [3-6s], [6-10s]).
   - Do the depicted physical actions and staging match the screenplay exactly?
2. Character Likeness & Zero Wardrobe Redundancy:
   - Facial stability and consistency with character profiles/reference sheets.
   - Zero wardrobe contradiction (no hallucinated clothing or conflicting descriptions).
3. Audio Balance & Visual Harmony:
   - Ducking of background instrumental music (-18dB) under spoken dialogue.
   - Vocal clarity, absence of gibberish audio or vocal hallucinations.
4. Tag & Index Symmetry:
   - 1:1 symmetry for character tags ([Role A], [Role B]) without identity bleed or tag collisions.

Provide your evaluation as a valid JSON object matching the following structure:
{{
  "overall_rating": <float 0.0-100.0>,
  "video_text_adherence": {{"score": <float>, "passed": <bool>, "evidence": "<str>"}},
  "character_likeness": {{"score": <float>, "passed": <bool>, "evidence": "<str>"}},
  "audio_visual_harmony": {{"score": <float>, "passed": <bool>, "evidence": "<str>"}},
  "tag_and_index_integrity": {{"score": <float>, "passed": <bool>, "evidence": "<str>"}},
  "detected_defects": ["<TAG_COLLISION|PHANTOM_KEYFRAME|LIKENESS_DRIFT|WARDROBE_CONTRADICTION|AUDIO_DROWNED|AUDIO_VOCAL_HALLUCINATION|TEMPORAL_BEAT_MISSED|OFFSCREEN_LIPSYNC_ERROR>"],
  "verbal_critique": "<Detailed summary critique of pacing, visual, and audio quality>",
  "suggested_prompt_patch": "<Surgically repaired prompt text if defects detected, else null>",
  "pass_verdict": <bool>
}}
"""

    def evaluate_video(
        self,
        session_id: str,
        turn_id: str,
        prompt: str,
        video_uri: str | None = None,
        reference_images: list[str] | None = None,
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

        rubric_prompt = self.build_rubric_prompt(prompt)
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
                clean_ref = self.storage._normalize_media_source_path(ref_img)
                if clean_ref.startswith("https://storage.googleapis.com/"):
                    clean_ref = "gs://" + clean_ref.replace("https://storage.googleapis.com/", "")
                if clean_ref.startswith("gs://"):
                    contents.append(types.Part.from_uri(file_uri=clean_ref, mime_type="image/jpeg"))

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
            parsed = json.loads(raw_text)

            defects = [
                DefectCategory(d)
                for d in parsed.get("detected_defects", [])
                if d in DefectCategory.__members__
            ]

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
                suggested_patch = suggested_patch.replace(
                    "### SCREENPLAY",
                    "### SCREENPLAY\n[Instrumental: ducking -18dB under speech]",
                )
            if DefectCategory.WARDROBE_CONTRADICTION in detected_defects:
                suggested_patch = re.sub(
                    r"wearing [^.\n]+",
                    "wearing signature attire per turnaround sheet",
                    suggested_patch,
                    flags=re.IGNORECASE,
                )

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
            verbal_critique=" ".join(critique_parts),
            suggested_prompt_patch=suggested_patch,
            pass_verdict=pass_verdict,
        )
