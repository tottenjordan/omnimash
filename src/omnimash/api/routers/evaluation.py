from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from omnimash.api.deps import AgentDep
from omnimash.evaluation.exemplar_bank import ExemplarBankManager
from omnimash.evaluation.rule_inducer import DirectorialRuleInducer
from omnimash.evaluation.strategy_bank import StrategyBankManager

logger = logging.getLogger(__name__)

router = APIRouter()
evaluation_router = router

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _validate_safe_id(value: str, field_name: str = "identifier") -> str:
    """Validates that identifier is safe from path traversal and invalid characters."""
    cleaned = (value or "").strip()
    if (
        not cleaned
        or ".." in cleaned
        or "/" in cleaned
        or "\\" in cleaned
        or "\x00" in cleaned
        or not _SAFE_ID_RE.match(cleaned)
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} '{value}': must match alphanumeric, underscore, or hyphen characters.",
        )
    return cleaned


class InduceRulesRequest(BaseModel):
    project_id: str | None = None
    min_defect_count: int = Field(default=2, ge=1)


class PruneRulesRequest(BaseModel):
    project_id: str | None = None
    max_rules: int = Field(default=20, ge=1)


class IngestExemplarRequest(BaseModel):
    session_id: str
    concept: str
    compiled_prompt: str
    user_rating: int = Field(default=5, ge=1, le=5)
    style_preset: str = "cinematic"
    project_id: str | None = None


@router.post("/api/eval/induce-rules")
def induce_rules(req: InduceRulesRequest, agent: AgentDep) -> dict[str, Any]:
    """Induces directorial invariant rules from defect patterns across review history."""
    project_id = _validate_safe_id(req.project_id, "project_id") if req.project_id else None
    inducer = DirectorialRuleInducer(
        storage=agent.storage,
        strategy_bank=getattr(agent, "strategy_bank", None),
        mock_mode=agent.storage.mock_mode,
    )
    rules = inducer.induce_rules_from_history(
        project_id=project_id, min_defect_count=req.min_defect_count
    )
    return {
        "status": "success",
        "rules_induced": [r.model_dump() for r in rules],
        "count": len(rules),
    }


@router.get("/api/eval/rules")
def get_rules(
    agent: AgentDep,
    project_id: str | None = Query(default=None),
) -> dict[str, Any]:
    """Retrieves active StrategyBank invariant rules with telemetry attributes."""
    pid = _validate_safe_id(project_id, "project_id") if project_id else None
    strategy_mgr = getattr(agent, "strategy_bank", None) or StrategyBankManager(
        storage=agent.storage,
        mock_mode=agent.storage.mock_mode,
    )
    bank = strategy_mgr.get_strategy_bank(project_id=pid)
    rules_dump = [r.model_dump() for r in bank.rules]
    return {
        "status": "success",
        "rules": rules_dump,
        "total": len(rules_dump),
        "strategy_bank": bank.model_dump(),
    }


@router.post("/api/eval/rules/prune")
def prune_rules(req: PruneRulesRequest, agent: AgentDep) -> dict[str, Any]:
    """Applies Pareto-optimal pruning to deduplicate rules and drop underperforming invariants."""
    project_id = _validate_safe_id(req.project_id, "project_id") if req.project_id else None
    inducer = DirectorialRuleInducer(
        storage=agent.storage,
        strategy_bank=getattr(agent, "strategy_bank", None),
        mock_mode=agent.storage.mock_mode,
    )
    pruned_bank = inducer.pareto_prune_rules(
        project_id=project_id,
        max_rules=req.max_rules,
    )
    return {
        "status": "success",
        "strategy_bank": pruned_bank.model_dump(),
    }


@router.get("/api/eval/exemplars")
def get_exemplars(
    agent: AgentDep,
    project_id: str | None = Query(default=None),
    style_preset: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1),
) -> list[dict[str, Any]]:
    """Retrieves 5-star reference exemplars filtered by project and style preset."""
    pid = _validate_safe_id(project_id, "project_id") if project_id else None
    style = _validate_safe_id(style_preset, "style_preset") if style_preset else None
    exemplars = agent.storage.list_exemplars(
        project_id=pid,
        style_preset=style,
    )
    return exemplars[:limit]


@router.post("/api/eval/exemplars")
def ingest_exemplar(req: IngestExemplarRequest, agent: AgentDep) -> dict[str, Any]:
    """Ingests a verified 5-star directorial prompt into the Exemplar Bank."""
    session_id = _validate_safe_id(req.session_id, "session_id")
    project_id = _validate_safe_id(req.project_id, "project_id") if req.project_id else None
    style = _validate_safe_id(req.style_preset, "style_preset") if req.style_preset else "cinematic"

    exemplar_mgr = ExemplarBankManager(
        storage=agent.storage,
        mock_mode=agent.storage.mock_mode,
    )
    try:
        record = exemplar_mgr.ingest_5star_prompt(
            session_id=session_id,
            concept=req.concept,
            compiled_prompt=req.compiled_prompt,
            user_rating=req.user_rating,
            style_preset=style,
            project_id=project_id,
        )
        return record.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = [
    "InduceRulesRequest",
    "IngestExemplarRequest",
    "PruneRulesRequest",
    "evaluation_router",
    "router",
]
