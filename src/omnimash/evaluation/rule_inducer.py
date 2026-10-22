from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import logging
import re
from typing import Any
import uuid

from omnimash.config import settings
from omnimash.evaluation.models import (
    DefectCategory,
    DirectorialInvariantRule,
    StrategyBank,
    UserFeedbackRecord,
    VideoEvaluationScorecard,
)
from omnimash.evaluation.strategy_bank import StrategyBankManager
from omnimash.storage.gcs import GcsStorageManager

logger = logging.getLogger(__name__)

INDUCED_RULE_TEMPLATES: dict[DefectCategory, dict[str, Any]] = {
    DefectCategory.AUDIO_DROWNED: {
        "trigger_pattern": "spoken dialogue with background music",
        "invariant_directive": "[Instrumental: ducking -18dB under speech]",
        "rationale": "Prevents synthesized background score from masking vocal tracks in Gemini Omni Flash.",
        "confidence_score": 0.96,
    },
    DefectCategory.WARDROBE_CONTRADICTION: {
        "trigger_pattern": "character reference sheet with detailed text wardrobe",
        "invariant_directive": "Zero Wardrobe Redundancy: Rely on visual reference turnaround sheet without descriptive clothing clauses.",
        "rationale": "Textual wardrobe descriptions clash with image reference latents in Gemini Omni Flash.",
        "confidence_score": 0.95,
    },
    DefectCategory.LIKENESS_DRIFT: {
        "trigger_pattern": "multi-character interaction scene",
        "invariant_directive": "Establish Left / Right screen-staging in [0-3s] and lock facial turnaround features.",
        "rationale": "Maintains character identity separation and prevents micro-drift across 8-10s Omni generation.",
        "confidence_score": 0.93,
    },
    DefectCategory.TAG_COLLISION: {
        "trigger_pattern": "multi-character interaction scene",
        "invariant_directive": "Establish Left / Right screen-staging in [0-3s] to anchor multi-character physical identities.",
        "rationale": "Maintains identity separation in multi-character dialogue scenes in Gemini Omni Flash.",
        "confidence_score": 0.92,
    },
    DefectCategory.PHANTOM_KEYFRAME: {
        "trigger_pattern": "keyframe transition with character reference tags",
        "invariant_directive": "Keyframe tag offset: Character tags start at index 1 + len(keyframes).",
        "rationale": "Prevents index collision between transition keyframes and character visual anchors.",
        "confidence_score": 0.94,
    },
    DefectCategory.AUDIO_VOCAL_HALLUCINATION: {
        "trigger_pattern": "spoken character dialogue",
        "invariant_directive": 'Wrap all vocal lines in [Dialogue: speaker: "quote"] to eliminate unscripted vocal gibberish.',
        "rationale": "Guides the Omni audio synthesizer to produce only scripted dialogue phonemes.",
        "confidence_score": 0.97,
    },
    DefectCategory.TEMPORAL_BEAT_MISSED: {
        "trigger_pattern": "standard 8-10 second Omni clip",
        "invariant_directive": "Decompose screenplay into exact [0-3s], [3-6s], and [6-10s] chronological beats.",
        "rationale": "Aligns narrative pacing with Gemini Omni Flash temporal attention windows.",
        "confidence_score": 0.95,
    },
    DefectCategory.OFFSCREEN_LIPSYNC_ERROR: {
        "trigger_pattern": "narrator voiceover without on-camera speaker",
        "invariant_directive": "Explicitly annotate offscreen narrators with [Voiceover/Offscreen] to prevent camera-facing lip movement.",
        "rationale": "Stops on-screen characters from lip-syncing narrator voiceover in Gemini Omni Flash.",
        "confidence_score": 0.93,
    },
}

_EXPLICIT_CONTRADICTION_PAIRS = [
    (
        re.compile(r"\b(?:no|without|disable)\s+ducking\b", re.IGNORECASE),
        re.compile(r"\bducking\s*-\d+db\b|\bducking\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\brely\s+on\s+text\b|\btextual\s+wardrobe\b", re.IGNORECASE),
        re.compile(r"\bzero\s+wardrobe\s+redundancy\b|\brely\s+on\s+visual\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(?:permit|allow|enable)\s+(?:cuts|cut|jump\s+cuts?)\b", re.IGNORECASE),
        re.compile(
            r"\b(?:no\s+abrupt\s+cuts|never\s+cut|single\s+continuous\s+camera)\b", re.IGNORECASE
        ),
    ),
]

_NEGATION_VERBS = re.compile(
    r"\b(?:prohibit|disable|never|no|without)\s+([a-z]{3,})", re.IGNORECASE
)
_ASSERTION_VERBS = re.compile(
    r"\b(?:require|mandatory|always|allow|enable)\s+([a-z]{3,})", re.IGNORECASE
)


def _normalize_category_str(cat: DefectCategory | str) -> str:
    """Normalizes DefectCategory or category string to canonical uppercase string."""
    if isinstance(cat, DefectCategory):
        return str(cat.value)
    return str(cat).strip().upper()


def _are_directives_contradictory(d1: str, d2: str) -> bool:
    """Checks whether two invariant directives present semantic contradiction."""
    # 1. Check explicit domain contradiction pairs
    for pat_a, pat_b in _EXPLICIT_CONTRADICTION_PAIRS:
        if (pat_a.search(d1) and pat_b.search(d2)) or (pat_a.search(d2) and pat_b.search(d1)):
            return True

    # 2. Check opposing polarity on the same subject
    neg_matches_1 = {m.group(1).lower() for m in _NEGATION_VERBS.finditer(d1)}
    pos_matches_2 = {m.group(1).lower() for m in _ASSERTION_VERBS.finditer(d2)}
    if neg_matches_1 & pos_matches_2:
        return True

    neg_matches_2 = {m.group(1).lower() for m in _NEGATION_VERBS.finditer(d2)}
    pos_matches_1 = {m.group(1).lower() for m in _ASSERTION_VERBS.finditer(d1)}
    if neg_matches_2 & pos_matches_1:
        return True

    return False


class DirectorialRuleInducer:
    """Induces directorial invariant rules from historical review signals,
    performs counterfactual validation, and Pareto-prunes the Strategy Bank.
    """

    def __init__(
        self,
        storage: GcsStorageManager | None = None,
        strategy_bank: StrategyBankManager | None = None,
        mock_mode: bool | None = None,
    ):
        if mock_mode is not None:
            self.mock_mode = mock_mode
        elif storage is not None:
            self.mock_mode = storage.mock_mode
        elif strategy_bank is not None:
            self.mock_mode = strategy_bank.mock_mode
        else:
            self.mock_mode = getattr(settings, "mock_mode", False)

        self.storage = (
            storage
            or (strategy_bank.storage if strategy_bank else None)
            or GcsStorageManager(mock_mode=self.mock_mode)
        )
        self.strategy_bank = strategy_bank or StrategyBankManager(
            storage=self.storage, mock_mode=self.mock_mode
        )

    def cluster_defects(self, project_id: str | None = None) -> dict[DefectCategory, int]:
        """Analyzes historical feedback and scorecards to compute defect frequencies."""
        defect_counter: Counter[DefectCategory] = Counter()

        # 1. Historical user feedback records
        feedback_records = self.storage.list_feedback_records(project_id=project_id)
        for fb in feedback_records:
            defects: list[Any] = []
            if isinstance(fb, dict):
                defects = fb.get("defects") or []
            elif isinstance(fb, UserFeedbackRecord):
                defects = fb.defects or []
            elif hasattr(fb, "defects"):
                defects = getattr(fb, "defects") or []

            for d in defects:
                if isinstance(d, DefectCategory):
                    defect_counter[d] += 1
                else:
                    raw_val = str(getattr(d, "value", d)).strip().upper()
                    try:
                        cat = DefectCategory(raw_val)
                        defect_counter[cat] += 1
                    except ValueError:
                        pass

        # 2. Historical video evaluation scorecards
        scorecards = self.storage.list_scorecards(project_id=project_id)
        for sc in scorecards:
            detected: list[Any] = []
            if isinstance(sc, dict):
                detected = sc.get("detected_defects") or []
            elif isinstance(sc, VideoEvaluationScorecard):
                detected = sc.detected_defects or []
            elif hasattr(sc, "detected_defects"):
                detected = getattr(sc, "detected_defects") or []

            for d in detected:
                if isinstance(d, DefectCategory):
                    defect_counter[d] += 1
                else:
                    raw_val = str(getattr(d, "value", d)).strip().upper()
                    try:
                        cat = DefectCategory(raw_val)
                        defect_counter[cat] += 1
                    except ValueError:
                        pass

        return dict(defect_counter)

    def validate_counterfactual(
        self, candidate: DirectorialInvariantRule, bank: StrategyBank
    ) -> bool:
        """Validates that candidate rule has acceptable confidence and does not conflict
        or duplicate existing rules in StrategyBank.
        """
        if candidate.confidence_score < 0.70:
            return False

        cand_directive = candidate.invariant_directive.strip().lower()
        if (
            not cand_directive
            or not candidate.trigger_pattern.strip()
            or not candidate.rationale.strip()
        ):
            return False

        cand_cat = _normalize_category_str(candidate.category)

        for rule in bank.rules:
            # Reject exact rule ID collision
            if candidate.rule_id == rule.rule_id:
                return False

            exist_directive = rule.invariant_directive.strip().lower()
            exist_cat = _normalize_category_str(rule.category)

            # Contradiction check for matching category
            if (
                cand_cat == exist_cat
                or cand_cat in ("ALL", "GENERAL")
                or exist_cat in ("ALL", "GENERAL")
            ):
                if _are_directives_contradictory(cand_directive, exist_directive):
                    return False

        return True

    def induce_rules_from_history(
        self, project_id: str | None = None, min_defect_count: int = 2
    ) -> list[DirectorialInvariantRule]:
        """Clusters historical defects, generates candidate invariant rules, validates
        compatibility, and registers passing rules with StrategyBank.
        """
        defect_counts = self.cluster_defects(project_id=project_id)
        if not defect_counts:
            return []

        # Find qualifying defect categories meeting min_defect_count
        qualifying = [cat for cat, cnt in defect_counts.items() if cnt >= min_defect_count]
        # Fallback in mock/test mode when count is below threshold but defects exist
        if not qualifying and self.mock_mode:
            qualifying = [cat for cat, cnt in defect_counts.items() if cnt >= 1]

        if not qualifying:
            return []

        current_bank = self.strategy_bank.get_strategy_bank(project_id=project_id)
        existing_rule_ids = {r.rule_id for r in current_bank.rules}
        induced_rules: list[DirectorialInvariantRule] = []

        for category in qualifying:
            template = INDUCED_RULE_TEMPLATES.get(category)
            if not template:
                cat_label = (
                    str(category.value if hasattr(category, "value") else category)
                    .replace("_", " ")
                    .title()
                )
                template = {
                    "trigger_pattern": f"scenes susceptible to {cat_label.lower()}",
                    "invariant_directive": f"Enforce directorial constraints to prevent {cat_label.lower()}.",
                    "rationale": f"Prevents recurrent {cat_label.lower()} defects observed in historical review telemetry.",
                    "confidence_score": 0.90,
                }

            rule_id = f"RULE-INDUCED-{uuid.uuid4().hex[:6].upper()}"
            while rule_id in existing_rule_ids:
                rule_id = f"RULE-INDUCED-{uuid.uuid4().hex[:6].upper()}"

            candidate = DirectorialInvariantRule(
                rule_id=rule_id,
                category=category,
                trigger_pattern=str(template["trigger_pattern"]),
                invariant_directive=str(template["invariant_directive"]),
                rationale=str(template["rationale"]),
                confidence_score=float(template["confidence_score"]),
                times_applied=0,
                defect_reduction_rate=0.0,
            )

            if self.validate_counterfactual(candidate, current_bank):
                self.strategy_bank.add_rule(candidate, project_id=project_id)
                induced_rules.append(candidate)
                # Update current bank in-memory representation for subsequent candidates
                current_bank.rules.append(candidate)
                existing_rule_ids.add(candidate.rule_id)

        return induced_rules

    def pareto_prune_rules(
        self, project_id: str | None = None, max_rules: int = 20
    ) -> StrategyBank:
        """Prunes low-confidence or negative-yield rules, deduplicates near-identical
        trigger patterns, and caps bank size according to Pareto sorting.
        """
        current_bank = self.strategy_bank.get_strategy_bank(project_id=project_id)
        raw_rules = current_bank.rules

        # 1. Deduplicate rules with identical or near-identical trigger patterns and categories
        deduped_map: dict[tuple[str, str], DirectorialInvariantRule] = {}
        for r in raw_rules:
            cat_key = _normalize_category_str(r.category)
            trigger_clean = re.sub(r"[^\w\s]", "", r.trigger_pattern.lower()).strip()
            trigger_norm = re.sub(r"\s+", " ", trigger_clean)
            key = (cat_key, trigger_norm)

            if key not in deduped_map:
                deduped_map[key] = r
            else:
                existing = deduped_map[key]
                exist_score = (
                    existing.confidence_score,
                    existing.defect_reduction_rate,
                    existing.times_applied,
                )
                new_score = (
                    r.confidence_score,
                    r.defect_reduction_rate,
                    r.times_applied,
                )
                if new_score > exist_score:
                    deduped_map[key] = r

        # 2. Prune rules with confidence_score < 0.70 or defect_reduction_rate < 0.0
        quality_rules = [
            r
            for r in deduped_map.values()
            if r.confidence_score >= 0.70 and r.defect_reduction_rate >= 0.0
        ]

        # 3. If rule count > max_rules, keep top max_rules sorted by confidence_score and times_applied
        quality_rules.sort(
            key=lambda r: (r.confidence_score, r.times_applied),
            reverse=True,
        )
        final_rules = quality_rules[: max(0, max_rules)]

        pruned_bank = StrategyBank(
            version=current_bank.version,
            updated_at=datetime.now(timezone.utc).isoformat(),
            rules=final_rules,
        )

        self.strategy_bank.save_strategy_bank(pruned_bank, project_id=project_id)
        return pruned_bank
