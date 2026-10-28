"""FastAPI + Server-Sent Events (SSE) router for Mode 5: Commercial Soundstage (`/api/soundstage/*`)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
import os
import time
from typing import NoReturn

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask

from omnimash.agent.soundstage_runner import (
    SoundstageConflictError,
    SoundstageGuardrailBlockedError,
    SoundstageNotFoundError,
    get_soundstage_service,
)
from omnimash.api.deps import AgentDep
from omnimash.api.soundstage_models import (
    SoundstageBoardsRequest,
    SoundstageCastRequest,
    SoundstageDiscoverRequest,
    SoundstageDiscoverResponse,
    SoundstagePlanRequest,
    SoundstageReconformRequest,
    SoundstageReviseRequest,
    SoundstageRunRequest,
    SoundstageStatusResponse,
    SoundstageVariationRequest,
)

router = APIRouter(prefix="/api/soundstage", tags=["soundstage"])

_ACTIVE_STREAM_STAGES = frozenset({"filming_acts", "conforming", "critic_evaluated"})
_SSE_STREAM_TIMEOUT_SEC = 180.0


def _raise_http_for_soundstage_error(exc: Exception) -> NoReturn:
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, SoundstageNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, SoundstageGuardrailBlockedError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, SoundstageConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc


def _format_sse_frame(event_name: str, payload: dict[str, object]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"


def _cleanup_temp_zip(path: str) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


@router.post("/discover", response_model=SoundstageDiscoverResponse)
def discover_soundstage(
    req: SoundstageDiscoverRequest,
    agent: AgentDep,
) -> SoundstageDiscoverResponse:
    """Runs 10-step intake discovery, 60/30/10 palette lock, and first-principles offering physics."""
    try:
        return get_soundstage_service(agent).discover(req)
    except Exception as exc:
        _raise_http_for_soundstage_error(exc)


@router.post("/plan", response_model=SoundstageStatusResponse)
def plan_soundstage(
    req: SoundstagePlanRequest,
    agent: AgentDep,
) -> SoundstageStatusResponse:
    """Compiles a 3-Act x 3-Beat (9-Shot) commercial plan and initializes a persistent Soundstage run."""
    try:
        return get_soundstage_service(agent).create_plan(req)
    except Exception as exc:
        _raise_http_for_soundstage_error(exc)


@router.post("/cast", response_model=SoundstageStatusResponse)
def cast_soundstage(
    req: SoundstageCastRequest,
    agent: AgentDep,
) -> SoundstageStatusResponse:
    """Generates or hydrates lead cast reference sheets, studio emblems, and hero packshot anchors."""
    try:
        return get_soundstage_service(agent).manage_cast_and_kit(req)
    except Exception as exc:
        _raise_http_for_soundstage_error(exc)


@router.post("/boards", response_model=SoundstageStatusResponse)
def boards_soundstage(
    req: SoundstageBoardsRequest,
    agent: AgentDep,
) -> SoundstageStatusResponse:
    """Synthesizes 9 storyboard plates (or regenerates 1 tile) with person-free reference isolation."""
    try:
        return get_soundstage_service(agent).generate_boards(req)
    except Exception as exc:
        _raise_http_for_soundstage_error(exc)


@router.post("/run", response_model=SoundstageStatusResponse)
def run_soundstage(
    req: SoundstageRunRequest,
    agent: AgentDep,
) -> SoundstageStatusResponse:
    """Executes parallel 3-act Omni Flash filming, multi-format conform, and DOMA critic evaluation."""
    try:
        return get_soundstage_service(agent).execute_filming_and_conform(req)
    except Exception as exc:
        _raise_http_for_soundstage_error(exc)


@router.get("/{run_id}/events")
async def stream_soundstage_events(
    run_id: str,
    agent: AgentDep,
    once: bool = Query(default=False),
) -> StreamingResponse:
    """Streams calibrated Mode 5 Soundstage progress events as `text/event-stream` SSE frames."""
    service = get_soundstage_service(agent)
    try:
        initial_status = service.get_status(run_id)
    except Exception as exc:
        _raise_http_for_soundstage_error(exc)

    async def _event_generator() -> AsyncIterator[str]:
        seen_count = 0
        deadline = time.monotonic() + _SSE_STREAM_TIMEOUT_SEC
        current = initial_status

        while True:
            for ev in current.events[seen_count:]:
                yield _format_sse_frame("progress", ev.model_dump(mode="json"))
            seen_count = len(current.events)

            if current.stage == "completed":
                yield _format_sse_frame(
                    "complete",
                    {
                        "run_id": current.run_id,
                        "stage": current.stage,
                        "progress_pct": current.progress_pct,
                        "deliverables": (
                            current.deliverables.model_dump(mode="json")
                            if current.deliverables is not None
                            else None
                        ),
                    },
                )
                return

            if current.stage == "failed":
                yield _format_sse_frame(
                    "error",
                    {
                        "run_id": current.run_id,
                        "stage": "failed",
                        "progress_pct": current.progress_pct,
                        "error": current.error or "Soundstage run failed.",
                    },
                )
                return

            is_active = (current.stage in _ACTIVE_STREAM_STAGES) or service.is_actively_running(
                run_id
            )
            if not is_active and not once:
                latest = service.get_status(run_id)
                if len(latest.events) > seen_count or latest.stage != current.stage:
                    current = latest
                    continue
            if once or not is_active:
                yield _format_sse_frame(
                    "idle",
                    {
                        "run_id": current.run_id,
                        "stage": current.stage,
                        "progress_pct": current.progress_pct,
                    },
                )
                return

            if time.monotonic() >= deadline:
                yield _format_sse_frame(
                    "timeout",
                    {
                        "run_id": current.run_id,
                        "stage": current.stage,
                        "progress_pct": current.progress_pct,
                    },
                )
                return

            await asyncio.sleep(0.04)
            current = service.get_status(run_id)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{run_id}/status", response_model=SoundstageStatusResponse)
def get_soundstage_status(
    run_id: str,
    agent: AgentDep,
) -> SoundstageStatusResponse:
    """Returns the authoritative persistent status snapshot for a Mode 5 Soundstage run."""
    try:
        return get_soundstage_service(agent).get_status(run_id)
    except Exception as exc:
        _raise_http_for_soundstage_error(exc)


@router.post("/{run_id}/revise", response_model=SoundstageStatusResponse)
def revise_soundstage_act(
    run_id: str,
    req: SoundstageReviseRequest,
    agent: AgentDep,
) -> SoundstageStatusResponse:
    """Surgically re-films a single target act from a trademark-scrubbed Director Note (Lock & Isolate)."""
    try:
        return get_soundstage_service(agent).revise_act(run_id, req)
    except Exception as exc:
        _raise_http_for_soundstage_error(exc)


@router.post("/{run_id}/reconform", response_model=SoundstageStatusResponse)
def reconform_soundstage_timeline(
    run_id: str,
    req: SoundstageReconformRequest,
    agent: AgentDep,
) -> SoundstageStatusResponse:
    """Re-conforms 30s/15s/6s deliverables from NLE sub-shot trim/bypass adjustments (0 re-filming)."""
    try:
        return get_soundstage_service(agent).reconform(run_id, req)
    except Exception as exc:
        _raise_http_for_soundstage_error(exc)


@router.post("/{run_id}/variations", response_model=SoundstageStatusResponse)
def fork_soundstage_variation(
    run_id: str,
    req: SoundstageVariationRequest,
    agent: AgentDep,
) -> SoundstageStatusResponse:
    """Forks a session-isolated commercial variation across `place`, `cast`, or `offering`."""
    try:
        return get_soundstage_service(agent).fork_variation(run_id, req)
    except Exception as exc:
        _raise_http_for_soundstage_error(exc)


@router.get("/{run_id}/package.zip")
def download_soundstage_package_zip(
    run_id: str,
    agent: AgentDep,
) -> FileResponse:
    """Exports and streams a campaign `.zip` archive containing deliverables, storyboards, kit, and manifest."""
    try:
        local_zip_path, _ = get_soundstage_service(agent).export_package_zip(run_id)
    except Exception as exc:
        _raise_http_for_soundstage_error(exc)

    return FileResponse(
        path=local_zip_path,
        media_type="application/zip",
        filename=os.path.basename(local_zip_path),
        background=BackgroundTask(_cleanup_temp_zip, local_zip_path),
    )


__all__ = ["router"]
