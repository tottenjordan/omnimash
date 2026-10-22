from __future__ import annotations

import logging
import os
import re
import warnings
from typing import Any

from omnimash.config import settings
from omnimash.evaluation.models import (
    ExemplarPromptRecord,
    VideoEvaluationScorecard,
)
from omnimash.storage.gcs import GcsStorageManager

logger = logging.getLogger(__name__)

try:
    import vertexai
except ImportError:
    vertexai: Any = None

_STOPWORDS = {
    "the",
    "and",
    "with",
    "for",
    "from",
    "that",
    "this",
    "into",
    "onto",
    "scene",
    "shot",
    "video",
    "prompt",
    "clip",
    "about",
    "after",
}


def _extract_character_count(compiled_prompt: str | None, concept: str | None) -> int:
    """Estimates character count from prompt character blocks, tags, and concept text."""
    prompt_str = compiled_prompt or ""
    concept_str = concept or ""

    # Pattern for explicit role or character lines in ### CHARACTER PROFILES
    role_matches = re.findall(
        r"(?i)(?:^|\n)\s*[-*]?\s*(?:Role|Character|\[Role)\b(?:\s*[:\sA-Za-z0-9_]|\s*\(|\])",
        prompt_str,
    )
    if role_matches:
        return len(role_matches)

    image_ref_matches = re.findall(r"<IMAGE_REF_\d+>", prompt_str)
    if image_ref_matches:
        unique_refs = set(image_ref_matches)
        return len(unique_refs)

    # Check for text hints in concept like "solo", "lone", "2 characters", "3 people"
    concept_lower = concept_str.lower()
    if any(w in concept_lower for w in ["lone", "solo", "alone", "monologue"]):
        return 1

    digit_match = re.search(
        r"(\d+)\s*(?:character|actor|person|people|duel|trio|duo)", concept_lower
    )
    if digit_match:
        return max(1, int(digit_match.group(1)))

    if "duo" in concept_lower or "duel" in concept_lower:
        return 2
    if "trio" in concept_lower:
        return 3

    return 1


class ExemplarBankManager:
    """Manages few-shot directorial exemplar prompts with GCS storage mirroring
    and Vertex AI Agent Platform Memory Bank registration.
    """

    def __init__(
        self,
        storage: GcsStorageManager | None = None,
        agent_engine_id: str | None = None,
        mock_mode: bool | None = None,
    ):
        if mock_mode is not None:
            self.mock_mode = mock_mode
        elif storage is not None:
            self.mock_mode = storage.mock_mode
        else:
            self.mock_mode = getattr(settings, "mock_mode", False)

        self.storage = storage or GcsStorageManager(mock_mode=self.mock_mode)
        self.agent_engine_id = (
            agent_engine_id
            or os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID")
            or getattr(settings, "agent_engine_id", None)
        )
        self._memory_client: Any = None
        if not self.mock_mode and self.agent_engine_id and vertexai is not None:
            self._init_memory_client()

    def _init_memory_client(self) -> None:
        """Initializes Vertex AI Client for Agent Platform Memory Bank operations."""
        if vertexai is None:
            return
        try:
            project = self.storage.project_id or getattr(
                settings, "google_cloud_project", "hybrid-vertex"
            )
            location = getattr(settings, "gcp_region", "us-central1")
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=FutureWarning, message=r".*vertexai\.Client.*"
                )
                self._memory_client = vertexai.Client(project=project, location=location)
        except Exception as exc:
            logger.warning("Failed to initialize Vertex AI memory client: %s", exc)
            self._memory_client = None

    def save_exemplar(
        self,
        exemplar: ExemplarPromptRecord | dict[str, Any],
        project_id: str | None = None,
    ) -> str:
        """Saves to storage mirror and attempts to register memory in Vertex AI Agent
        Platform Memory Bank if available.
        """
        if isinstance(exemplar, dict):
            ex_record = ExemplarPromptRecord.model_validate(exemplar)
        else:
            ex_record = exemplar

        effective_project = project_id or ex_record.project_id
        gcs_uri = self.storage.save_exemplar(ex_record, project_id=effective_project)

        if not self.mock_mode and self._memory_client and self.agent_engine_id:
            try:
                if hasattr(self._memory_client, "create_memory"):
                    self._memory_client.create_memory(
                        agent_id=self.agent_engine_id,
                        content=(
                            f"Exemplar ({ex_record.style_preset}): {ex_record.concept}\n"
                            f"{ex_record.compiled_4block_prompt}"
                        ),
                        metadata={
                            "exemplar_id": ex_record.exemplar_id,
                            "style_preset": ex_record.style_preset,
                            "rating": ex_record.user_rating,
                            "project_id": effective_project or "global",
                        },
                    )
            except Exception as exc:
                logger.warning("Failed to register exemplar in Vertex AI Memory Bank: %s", exc)

        return gcs_uri

    def ingest_5star_prompt(
        self,
        session_id: str,
        concept: str,
        compiled_prompt: str,
        scorecard: VideoEvaluationScorecard | dict[str, Any] | None = None,
        user_rating: int = 5,
        style_preset: str = "cinematic",
        project_id: str | None = None,
    ) -> ExemplarPromptRecord:
        """Validates rating >= 4 (defaults 5) and passed scorecard if present,
        creates ExemplarPromptRecord, persists and returns it.
        """
        if not session_id or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        if not concept or not concept.strip():
            raise ValueError("concept must be a non-empty string")
        if not compiled_prompt or not compiled_prompt.strip():
            raise ValueError(
                "compiled_prompt must be a non-empty string to be ingested as an exemplar"
            )

        if user_rating < 4:
            raise ValueError(
                f"Rating {user_rating} is below 4-star minimum threshold for exemplar bank ingestion"
            )
        if user_rating > 5:
            raise ValueError(f"Rating {user_rating} exceeds maximum 5-star rating scale")

        validated_scorecard: VideoEvaluationScorecard | None = None
        if scorecard is not None:
            if isinstance(scorecard, dict):
                validated_scorecard = VideoEvaluationScorecard.model_validate(scorecard)
            elif isinstance(scorecard, VideoEvaluationScorecard):
                validated_scorecard = scorecard
            else:
                validated_scorecard = VideoEvaluationScorecard.model_validate(scorecard)

            if not validated_scorecard.pass_verdict:
                raise ValueError(
                    "Scorecard must have pass_verdict=True to be ingested as an exemplar"
                )

        record = ExemplarPromptRecord(
            session_id=session_id.strip(),
            concept=concept.strip(),
            style_preset=style_preset.strip() if style_preset else "cinematic",
            compiled_4block_prompt=compiled_prompt,
            scorecard=validated_scorecard,
            user_rating=int(user_rating),
            project_id=project_id.strip() if project_id else None,
        )

        self.save_exemplar(record, project_id=record.project_id)
        return record

    def query_relevant_exemplars(
        self,
        concept: str | None = "",
        style_preset: str | None = None,
        character_count: int | None = None,
        project_id: str | None = None,
        limit: int = 2,
    ) -> list[ExemplarPromptRecord]:
        """Queries saved exemplars (layering project-level over global), scores relevance
        based on preset matching, character count similarity, and concept keyword overlap,
        and returns top-k exemplars.
        """
        raw_exemplars: dict[str, dict[str, Any]] = {}

        # 1. Fetch global exemplars
        global_records = self.storage.list_exemplars(project_id=None)
        for r in global_records:
            eid = r.get("exemplar_id")
            if eid:
                raw_exemplars[eid] = r

        # 2. Layer project-level exemplars if project_id is provided
        if project_id:
            project_records = self.storage.list_exemplars(project_id=project_id)
            for r in project_records:
                eid = r.get("exemplar_id")
                if eid:
                    raw_exemplars[eid] = r

        if not raw_exemplars:
            return []

        # Convert to ExemplarPromptRecord objects
        records: list[ExemplarPromptRecord] = []
        for r in raw_exemplars.values():
            try:
                records.append(ExemplarPromptRecord.model_validate(r) if isinstance(r, dict) else r)
            except Exception as exc:
                logger.warning("Failed to validate exemplar record: %s", exc)

        clean_concept = concept or ""
        q_tokens = {
            w.lower()
            for w in re.split(r"\W+", clean_concept)
            if len(w) >= 3 and w.lower() not in _STOPWORDS
        }

        target_style = (
            style_preset.strip().lower() if style_preset and style_preset.strip() else None
        )

        scored: list[tuple[float, ExemplarPromptRecord]] = []
        for ex in records:
            score = 0.0

            # 1. Preset matching
            if target_style:
                ex_style = str(ex.style_preset or "").strip().lower()
                if ex_style == target_style:
                    score += 25.0

            # 2. Concept & prompt keyword overlap
            c_text = ex.concept or ""
            p_text = ex.compiled_4block_prompt or ""
            c_tokens = {
                w.lower()
                for w in re.split(r"\W+", c_text)
                if len(w) >= 3 and w.lower() not in _STOPWORDS
            }
            p_tokens = {
                w.lower()
                for w in re.split(r"\W+", p_text)
                if len(w) >= 3 and w.lower() not in _STOPWORDS
            }

            concept_overlap = len(q_tokens & c_tokens)
            prompt_overlap = len(q_tokens & p_tokens)
            score += concept_overlap * 6.0 + prompt_overlap * 1.5

            # 3. Character count similarity
            if character_count is not None and character_count > 0:
                ex_chars = _extract_character_count(ex.compiled_4block_prompt, ex.concept)
                diff = abs(ex_chars - character_count)
                score += max(0.0, 10.0 - diff * 3.0)

            # 4. Project-level layering priority boost (tenant affinity)
            if project_id and ex.project_id == project_id:
                score += 15.0

            # 5. Quality rating contribution
            score += (ex.user_rating - 4) * 1.5
            rating_val = None
            if ex.scorecard is not None:
                if hasattr(ex.scorecard, "overall_rating"):
                    rating_val = ex.scorecard.overall_rating
                elif isinstance(ex.scorecard, dict):
                    rating_val = ex.scorecard.get("overall_rating")
            if rating_val is not None:
                try:
                    score += (float(rating_val) / 100.0) * 2.0
                except (ValueError, TypeError):
                    pass

            scored.append((score, ex))

        scored.sort(key=lambda item: item[0], reverse=True)
        max_items = max(0, limit)
        return [ex for _, ex in scored[:max_items]]

    def format_exemplars_as_few_shot_block(
        self,
        exemplars: list[ExemplarPromptRecord | dict[str, Any]],
    ) -> str:
        """Formats the exemplars into a clean, few-shot markdown string suitable
        for injection into StoryboardCompilerAgent or PromptCompiler system instructions.
        """
        if not exemplars:
            return ""

        lines = [
            "### DIRECTORIAL FEW-SHOT EXEMPLARS (5-STAR MASTER REFERENCE PROMPTS)",
            "The following verified master reference prompts illustrate target directorial decomposition, staging, and syntax:\n",
        ]

        for idx, item in enumerate(exemplars, start=1):
            if isinstance(item, dict):
                ex = ExemplarPromptRecord.model_validate(item)
            else:
                ex = item

            raw_style = getattr(ex, "style_preset", "") or "cinematic"
            style_name = str(raw_style).replace("_", " ").title()
            lines.append(f"Example {idx} (Style: {style_name}):")
            lines.append(f"**Concept:** {ex.concept}")
            lines.append(f"**User Rating:** {ex.user_rating} Stars")

            critique = None
            if ex.scorecard is not None:
                if hasattr(ex.scorecard, "verbal_critique"):
                    critique = ex.scorecard.verbal_critique
                elif isinstance(ex.scorecard, dict):
                    critique = ex.scorecard.get("verbal_critique")
            if critique:
                lines.append(f"**Screening Room Verdict:** {critique}")

            lines.append("**Directorial Master Prompt:**")
            prompt_content = ex.compiled_4block_prompt.strip()
            backtick_runs = re.findall(r"`+", prompt_content)
            max_backticks = max([len(r) for r in backtick_runs], default=0)
            fence = "`" * max(3, max_backticks + 1)
            lines.append(fence)
            lines.append(prompt_content)
            lines.append(f"{fence}\n")

        return "\n".join(lines).strip()
