"""Media proxy endpoint with HTTP Range streaming support."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from omnimash.agent.orchestrator import OmniMashAgent
from omnimash.api.deps import get_agent

router = APIRouter()

AgentDep = Annotated[OmniMashAgent, Depends(get_agent)]


def _parse_range_header(range_header: str | None, size: int) -> tuple[int, int] | None | str:
    """Parse a single-range HTTP ``Range`` header against a known object size.

    Returns ``None`` when there is no (or an unparseable, hence ignorable)
    Range header — the caller then serves the full body with 200. Returns an
    inclusive ``(start, end)`` for a satisfiable range. Returns the sentinel
    ``"invalid"`` for a syntactically-valid but unsatisfiable range so the
    caller can answer 416. Only ``bytes=`` single ranges are supported; anything
    else falls back to a full 200 response.
    """
    if not range_header:
        return None
    range_header = range_header.strip()
    if not range_header.startswith("bytes=") or "," in range_header:
        return None
    spec = range_header[len("bytes=") :].strip()
    start_s, sep, end_s = spec.partition("-")
    if not sep:
        return None

    if not start_s:
        # Suffix range: last N bytes (bytes=-500).
        if not end_s.isdigit():
            return None
        suffix = int(end_s)
        if suffix == 0 or size == 0:
            return "invalid"
        start = max(0, size - suffix)
        return (start, size - 1)

    if not start_s.isdigit():
        return None
    start = int(start_s)
    if start >= size:
        return "invalid"
    if end_s:
        if not end_s.isdigit():
            return None
        end = int(end_s)
    else:
        end = size - 1
    end = min(end, size - 1)
    if end < start:
        return "invalid"
    return (start, end)


@router.get("/api/media-proxy")
def media_proxy(uri: str, request: Request, agent: AgentDep) -> Response:
    if not uri or not uri.startswith("gs://"):
        raise HTTPException(
            status_code=400,
            detail="Invalid GCS URI. Must start with gs://",
        )

    # Metadata first: size drives Range math and lets us stream the body
    # instead of buffering the whole object in memory. A None result covers
    # both "not found" and "cross-bucket read blocked" (Task 1.2).
    meta = agent.storage.get_media_metadata(uri)
    if meta is None:
        raise HTTPException(status_code=404, detail="Media object not found or empty")
    size, content_type = meta

    base_headers = {
        "Cache-Control": "public, max-age=86400",
        "Accept-Ranges": "bytes",
    }

    range_spec = _parse_range_header(request.headers.get("range"), size)
    if range_spec == "invalid":
        # Unsatisfiable range -> 416 with the full size so clients can retry.
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{size}"},
        )

    if range_spec is None:
        body = agent.storage.iter_blob_range(uri, start=0, end=size - 1 if size else None)
        headers = {**base_headers, "Content-Length": str(size)}
        return StreamingResponse(body, media_type=content_type, headers=headers)

    start, end = range_spec
    body = agent.storage.iter_blob_range(uri, start=start, end=end)
    headers = {
        **base_headers,
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Content-Length": str(end - start + 1),
    }
    return StreamingResponse(
        body,
        status_code=206,
        media_type=content_type,
        headers=headers,
    )
