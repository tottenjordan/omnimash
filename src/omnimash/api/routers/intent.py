"""Mode 4: Director's Co-Pilot (Intent Clarification & Auto-Orchestration) Router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from omnimash.api.deps import AgentDep
from omnimash.api.models import (
    AnalyzeIntentGapsRequest,
    AnalyzeIntentGapsResponse,
    AutoFillIntentPlanRequest,
    AutoFillIntentPlanResponse,
    GenerateResponse,
)
from omnimash.prompts.intent_agent import IntentAutoFiller, IntentGapAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["intent"])


@router.post("/api/intent/analyze-gaps", response_model=AnalyzeIntentGapsResponse)
def analyze_intent_gaps(
    req: AnalyzeIntentGapsRequest, agent: AgentDep
) -> AnalyzeIntentGapsResponse:
    """Analyzes user premise/intent across 7 production slots and generates targeted clarification questions."""
    raw_intent = (req.intent or "").strip()
    if not raw_intent:
        raise HTTPException(status_code=400, detail="Missing intent")

    analyzer = IntentGapAnalyzer(mock_mode=agent.storage.mock_mode)
    return analyzer.analyze(
        intent=req.intent,
        inputs=req.optional_inputs,
        session_name=req.session_name,
    )


@router.post("/api/intent/auto-fill", response_model=AutoFillIntentPlanResponse)
def auto_fill_intent_plan(
    req: AutoFillIntentPlanRequest, agent: AgentDep
) -> AutoFillIntentPlanResponse:
    """Auto-fills missing slots into a cohesive production plan and canonical 4-block Gemini Omni Flash prompt."""
    raw_intent = (req.intent or "").strip()
    if not raw_intent:
        raise HTTPException(status_code=400, detail="Missing intent")

    autofiller = IntentAutoFiller(mock_mode=agent.storage.mock_mode)
    return autofiller.generate_plan(
        intent=req.intent,
        inputs=req.optional_inputs,
        answers=req.question_answers,
        resolution=req.resolution,
        aspect_ratio=req.aspect_ratio,
        session_name=req.session_name,
        enable_safety_sanitization=req.enable_safety_sanitization,
    )


@router.post("/api/intent/render-direct", response_model=GenerateResponse)
def render_intent_direct(req: AutoFillIntentPlanRequest, agent: AgentDep) -> GenerateResponse:
    """Auto-fills a production plan from intent and directly dispatches video generation."""
    raw_intent = (req.intent or "").strip()
    if not raw_intent:
        raise HTTPException(status_code=400, detail="Missing intent")

    autofiller = IntentAutoFiller(mock_mode=agent.storage.mock_mode)
    fill_response = autofiller.generate_plan(
        intent=req.intent,
        inputs=req.optional_inputs,
        answers=req.question_answers,
        resolution=req.resolution,
        aspect_ratio=req.aspect_ratio,
        session_name=req.session_name,
        enable_safety_sanitization=req.enable_safety_sanitization,
    )
    plan = fill_response.plan

    agent_turn = agent.process_user_turn(
        prompt=plan.raw_compiled_prompt,
        session_name=req.session_name,
        resolution=req.resolution,
        aspect_ratio=req.aspect_ratio,
        enable_sanitization=req.enable_safety_sanitization,
    )

    return GenerateResponse(
        success=agent_turn.success,
        status=agent_turn.status_event,
        video_url=agent_turn.video_url,
        turn_id=agent_turn.turn_id,
        depth=agent_turn.depth,
        error=agent_turn.error_message,
        generation_mode=agent_turn.generation_mode,
        raw_compiled_prompt=agent_turn.raw_compiled_prompt or plan.raw_compiled_prompt,
        reference_analysis=agent_turn.reference_analysis,
    )
