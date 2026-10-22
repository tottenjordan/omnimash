import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from omnimash.api.deps import AgentDep
from omnimash.evaluation.models import (
    DefectCategory,
    UserFeedbackRecord,
    VideoEvaluationScorecard,
)
from omnimash.evaluation.prompt_refiner import PromptRefiner
from omnimash.evaluation.video_critic import VideoCriticAgent

logger = logging.getLogger(__name__)

router = APIRouter()

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _validate_safe_id(value: str, field_name: str = "identifier") -> str:
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


class FeedbackSubmitResponse(BaseModel):
    success: bool
    feedback_id: str
    url: str
    message: str = "Feedback submitted successfully."


class DiagnoseRequest(BaseModel):
    session_id: str
    turn_id: str
    prompt: str | None = None
    video_uri: str | None = None
    critique: str | None = None
    defects: list[DefectCategory] = Field(default_factory=list)
    project_id: str | None = None


@router.post("/api/feedback", response_model=FeedbackSubmitResponse)
def submit_feedback(record: UserFeedbackRecord, agent: AgentDep) -> FeedbackSubmitResponse:
    """Submits directorial feedback for a rendered turn and persists it to GCS."""
    session_id = _validate_safe_id(record.session_id, "session_id")
    turn_id = _validate_safe_id(record.turn_id, "turn_id")
    project_id = _validate_safe_id(record.project_id, "project_id") if record.project_id else None
    try:
        url = agent.storage.save_feedback(session_id, turn_id, record, project_id=project_id)
        return FeedbackSubmitResponse(
            success=True,
            feedback_id=record.feedback_id,
            url=url,
            message="Feedback saved to GCS storage.",
        )
    except Exception as exc:
        logger.error("Failed to save feedback for session %s turn %s: %s", session_id, turn_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to persist feedback: {exc}")


@router.get("/api/feedback/{session_id}/{turn_id}")
def get_feedback(
    session_id: str,
    turn_id: str,
    agent: AgentDep,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Retrieves directorial feedback for a session and turn."""
    sid = _validate_safe_id(session_id, "session_id")
    tid = _validate_safe_id(turn_id, "turn_id")
    pid = _validate_safe_id(project_id, "project_id") if project_id else None
    data = agent.storage.get_feedback(sid, tid, project_id=pid)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Feedback not found for session {sid} turn {tid}",
        )
    return data


@router.get("/api/eval/scorecard/{session_id}/{turn_id}")
def get_scorecard(
    session_id: str,
    turn_id: str,
    agent: AgentDep,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Retrieves the latest evaluation scorecard for a session and turn."""
    sid = _validate_safe_id(session_id, "session_id")
    tid = _validate_safe_id(turn_id, "turn_id")
    pid = _validate_safe_id(project_id, "project_id") if project_id else None
    data = agent.storage.get_scorecard(sid, tid, project_id=pid)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Scorecard not found for session {sid} turn {tid}",
        )
    return data


@router.post("/api/eval/diagnose", response_model=VideoEvaluationScorecard)
def diagnose_shot(req: DiagnoseRequest, agent: AgentDep) -> VideoEvaluationScorecard:
    """Performs multimodal directorial diagnosis and generates a repaired prompt patch."""
    session_id = _validate_safe_id(req.session_id, "session_id")
    turn_id = _validate_safe_id(req.turn_id, "turn_id")
    project_id = _validate_safe_id(req.project_id, "project_id") if req.project_id else None

    prompt = req.prompt or ""
    if not prompt:
        manifest = agent.storage.get_session_manifest(session_id, project_id=project_id)
        if manifest and "compiled_prompt" in manifest:
            prompt = str(manifest["compiled_prompt"])

    critic = VideoCriticAgent(
        storage=agent.storage,
        mock_mode=agent.storage.mock_mode,
    )
    scorecard = critic.evaluate_video(
        session_id=session_id,
        turn_id=turn_id,
        prompt=prompt,
        video_uri=req.video_uri,
        user_critique=req.critique,
        reported_defects=req.defects,
    )
    scorecard.project_id = project_id

    refiner = PromptRefiner(mock_mode=agent.storage.mock_mode)
    refinement = refiner.refine_prompt(
        original_prompt=prompt,
        scorecard=scorecard,
        user_feedback={"critique_text": req.critique or "", "defects": req.defects},
    )
    if refinement.repaired_prompt and refinement.repaired_prompt != prompt:
        scorecard.suggested_prompt_patch = refinement.repaired_prompt

    # Automatically save scorecard to GCS storage
    agent.storage.save_scorecard(session_id, turn_id, scorecard, project_id=project_id)

    return scorecard
