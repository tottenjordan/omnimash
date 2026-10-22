from __future__ import annotations

from datetime import datetime, timezone
import logging
import os
import re
from typing import Any

from omnimash.config import settings
from omnimash.evaluation.models import (
    DefectCategory,
    DirectorialInvariantRule,
    StrategyBank,
)
from omnimash.storage.gcs import GcsStorageManager

logger = logging.getLogger(__name__)

FOUNDATIONAL_INVARIANTS: list[DirectorialInvariantRule] = [
    DirectorialInvariantRule(
        rule_id="RULE-AUDIO-001",
        category=DefectCategory.AUDIO_DROWNED,
        trigger_pattern="spoken dialogue with background music",
        invariant_directive="[Instrumental: ducking -18dB under speech]",
        rationale="Prevents synthesized background score from masking vocal tracks.",
        confidence_score=0.98,
    ),
    DirectorialInvariantRule(
        rule_id="RULE-WARDROBE-001",
        category=DefectCategory.WARDROBE_CONTRADICTION,
        trigger_pattern="character reference image with detailed text wardrobe",
        invariant_directive="Zero Wardrobe Redundancy: Rely on visual reference turnaround sheet without descriptive clothing clauses.",
        rationale="Textual wardrobe descriptions clash with image reference latents.",
        confidence_score=0.95,
    ),
    DirectorialInvariantRule(
        rule_id="RULE-KEYFRAME-001",
        category=DefectCategory.PHANTOM_KEYFRAME,
        trigger_pattern="keyframe transition with character reference tags",
        invariant_directive="Keyframe tag offset: Character tags start at index 1 + len(keyframes).",
        rationale="Prevents index collision between transition keyframes and character visual anchors.",
        confidence_score=0.96,
    ),
    DirectorialInvariantRule(
        rule_id="RULE-SPATIAL-001",
        category=DefectCategory.TAG_COLLISION,
        trigger_pattern="multi-character interaction scene",
        invariant_directive="Establish Left / Right screen-staging in [0-3s] to anchor multi-character physical identities.",
        rationale="Maintains identity separation in multi-character dialogue scenes.",
        confidence_score=0.92,
    ),
    DirectorialInvariantRule(
        rule_id="RULE-LIKENESS-001",
        category=DefectCategory.LIKENESS_DRIFT,
        trigger_pattern="close-up or medium dialogue shot",
        invariant_directive="Explicitly anchor primary facial structure to the reference turnaround sheet.",
        rationale="Prevents micro-drift across 8-10 second video generation.",
        confidence_score=0.94,
    ),
    DirectorialInvariantRule(
        rule_id="RULE-AUDIO-002",
        category=DefectCategory.AUDIO_VOCAL_HALLUCINATION,
        trigger_pattern="spoken character dialogue",
        invariant_directive='Wrap all vocal lines in [Dialogue: speaker: "quote"] to eliminate unscripted vocal gibberish.',
        rationale="Instructs audio synthesizer to generate only scripted phonemes.",
        confidence_score=0.97,
    ),
    DirectorialInvariantRule(
        rule_id="RULE-TEMPORAL-001",
        category=DefectCategory.TEMPORAL_BEAT_MISSED,
        trigger_pattern="standard 8-10 second Omni clip",
        invariant_directive="Decompose screenplay into exact [0-3s], [3-6s], and [6-10s] chronological beats.",
        rationale="Matches Omni temporal attention window for pacing fidelity.",
        confidence_score=0.95,
    ),
    DirectorialInvariantRule(
        rule_id="RULE-LIPSYNC-001",
        category=DefectCategory.OFFSCREEN_LIPSYNC_ERROR,
        trigger_pattern="narrator voiceover without on-camera speaker",
        invariant_directive="Explicitly annotate offscreen narrators with [Voiceover/Offscreen] to prevent camera-facing lip movement.",
        rationale="Stops on-screen characters from lip-syncing narrator voiceover.",
        confidence_score=0.93,
    ),
    DirectorialInvariantRule(
        rule_id="RULE-CAMERA-001",
        category=DefectCategory.TAG_COLLISION,
        trigger_pattern="action or dynamic camera prompt",
        invariant_directive="Maintain a single continuous camera move per clip without abrupt cuts.",
        rationale="Prevents sudden cut artifacts inside a single generated shot.",
        confidence_score=0.90,
    ),
    DirectorialInvariantRule(
        rule_id="RULE-LIGHTING-001",
        category=DefectCategory.LIKENESS_DRIFT,
        trigger_pattern="scene transition across turns",
        invariant_directive="Lock volumetric lighting and color temperature to the keyframe palette.",
        rationale="Prevents jarring lighting jumps between consecutive scenes.",
        confidence_score=0.91,
    ),
    DirectorialInvariantRule(
        rule_id="RULE-WARDROBE-002",
        category=DefectCategory.WARDROBE_CONTRADICTION,
        trigger_pattern="conversational video diffs",
        invariant_directive="Lock materials and accessories across multi-turn conversational diffs.",
        rationale="Eliminates accessory popping during turn-by-turn modifications.",
        confidence_score=0.92,
    ),
    DirectorialInvariantRule(
        rule_id="RULE-PACING-001",
        category=DefectCategory.TEMPORAL_BEAT_MISSED,
        trigger_pattern="high action or chaotic screenplay",
        invariant_directive="Limit physical movements to a maximum of 2 distinct key actions per 3-second window.",
        rationale="Avoids visual smearing caused by rapid multi-action overloading.",
        confidence_score=0.89,
    ),
]


class StrategyBankManager:
    """Manages the hybrid Directorial Strategy Bank combining Vertex AI Agent Platform
    Memory Bank with persistent Google Cloud Storage mirroring.
    """

    def __init__(
        self,
        storage: GcsStorageManager | None = None,
        agent_engine_id: str | None = None,
        mock_mode: bool | None = None,
    ):
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self.storage = storage or GcsStorageManager(mock_mode=self.mock_mode)
        self.agent_engine_id = (
            agent_engine_id
            or os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID")
            or getattr(settings, "agent_engine_id", None)
        )
        self._memory_client: Any = None
        self._seed_foundational_invariants()

    def _seed_foundational_invariants(self) -> None:
        """Seeds the 12 foundational rules into global GCS mirror if not already initialized."""
        existing = self.storage.get_strategy_bank()
        if not existing:
            bank = StrategyBank(
                version="1.0.0",
                rules=FOUNDATIONAL_INVARIANTS,
            )
            self.storage.save_strategy_bank(bank)

    def get_strategy_bank(self, project_id: str | None = None) -> StrategyBank:
        """Retrieves active strategy bank, layering project-specific invariants over global foundational rules."""
        raw_global = self.storage.get_strategy_bank()
        rules_dict: dict[str, DirectorialInvariantRule] = {
            r.rule_id: r for r in FOUNDATIONAL_INVARIANTS
        }

        if raw_global and "rules" in raw_global:
            for r in raw_global["rules"]:
                rule_obj = DirectorialInvariantRule.model_validate(r)
                rules_dict[rule_obj.rule_id] = rule_obj

        if project_id:
            raw_proj = self.storage.get_strategy_bank(project_id=project_id)
            if raw_proj and "rules" in raw_proj:
                for r in raw_proj["rules"]:
                    rule_obj = DirectorialInvariantRule.model_validate(r)
                    rules_dict[rule_obj.rule_id] = rule_obj

        return StrategyBank(
            version="1.0.0",
            updated_at=datetime.now(timezone.utc).isoformat(),
            rules=list(rules_dict.values()),
        )

    def save_strategy_bank(self, bank: StrategyBank, project_id: str | None = None) -> str:
        """Persists strategy bank to storage mirror and memory bank adapter."""
        return self.storage.save_strategy_bank(bank, project_id=project_id)

    def add_rule(self, rule: DirectorialInvariantRule, project_id: str | None = None) -> None:
        """Adds or updates a rule in the strategy bank."""
        current_bank = self.get_strategy_bank(project_id=project_id)
        existing_rules = {r.rule_id: r for r in current_bank.rules}
        existing_rules[rule.rule_id] = rule
        new_bank = StrategyBank(
            version=current_bank.version,
            updated_at=datetime.now(timezone.utc).isoformat(),
            rules=list(existing_rules.values()),
        )
        self.save_strategy_bank(new_bank, project_id=project_id)

    def query_applicable_rules(
        self,
        concept: str = "",
        characters: list[str] | None = None,
        has_keyframe: bool = False,
        defect_categories: list[DefectCategory] | None = None,
        project_id: str | None = None,
    ) -> list[DirectorialInvariantRule]:
        """Queries and returns matching rules based on scenario flags, concept keywords, and defect signals."""
        bank = self.get_strategy_bank(project_id=project_id)
        matched: list[DirectorialInvariantRule] = []

        defect_set = {d.value if hasattr(d, "value") else str(d) for d in (defect_categories or [])}
        text_corpus = f"{concept} {' '.join(characters or [])}".lower()

        for rule in bank.rules:
            cat_str = rule.category.value if hasattr(rule.category, "value") else str(rule.category)
            if defect_set and cat_str in defect_set:
                matched.append(rule)
                continue

            if has_keyframe and rule.rule_id == "RULE-KEYFRAME-001":
                matched.append(rule)
                continue

            # Keyword matching on trigger pattern
            pattern_tokens = [
                w.lower() for w in re.split(r"\W+", rule.trigger_pattern) if len(w) > 3
            ]
            if pattern_tokens and any(tok in text_corpus for tok in pattern_tokens):
                matched.append(rule)

        return matched
