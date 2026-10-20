import logging
import os
import tempfile
import uuid
from typing import Annotated

import anyio
from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from omnimash.api.deps import AgentDep
from omnimash.api.models import (
    ExtractReferenceRequest,
    MotionReferenceRequest,
    MotionReferenceResponse,
    ResearchRequest,
)
from omnimash.config import settings
from omnimash.ingestion.media_extractor import (
    ParodyResearchResult,
    ReferenceAnalysisReport,
)

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_UPLOAD_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mp3",
    ".wav",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".svg",
}
ALLOWED_MIME_PREFIXES = ("video/", "audio/", "image/", "application/octet-stream")


def _write_local_upload(local_dir: str, local_path: str, content: bytes) -> None:
    os.makedirs(local_dir, exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(content)


@router.post("/api/upload")
async def upload_media_file(file: Annotated[UploadFile, File()], agent: AgentDep):
    """Uploads a local media file (audio MP3, WAV, image, video) to storage and returns accessible URL."""
    try:
        raw_filename = file.filename or "file.bin"
        ext = os.path.splitext(raw_filename)[1].lower()
        if ext and ext not in ALLOWED_UPLOAD_EXTENSIONS:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": f"Unsupported file extension '{ext}'. Allowed media extensions: {sorted(ALLOWED_UPLOAD_EXTENSIONS)}",
                },
            )
        if not ext:
            ext = ".bin"

        content_type = (file.content_type or "application/octet-stream").lower()
        if not content_type.startswith(ALLOWED_MIME_PREFIXES):
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": f"Unsupported media content-type '{content_type}'.",
                },
            )

        max_upload_bytes = 50 * 1024 * 1024
        content = await file.read(max_upload_bytes + 1)
        if len(content) > max_upload_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "success": False,
                    "error": "File exceeds maximum upload size of 50MB",
                },
            )

        filename = f"upload_{uuid.uuid4().hex[:8]}{ext}"

        if agent.storage._bucket and not agent.storage.mock_mode:
            gcs_uri = await anyio.to_thread.run_sync(
                lambda: agent.storage.upload_bytes(
                    content,
                    f"uploads/{filename}",
                    content_type=file.content_type or "application/octet-stream",
                )
            )
            return {"success": True, "url": gcs_uri, "filename": file.filename}

        local_dir = os.path.join(os.getcwd(), "static", "uploads")
        local_path = os.path.join(local_dir, filename)
        await anyio.to_thread.run_sync(_write_local_upload, local_dir, local_path, content)
        return {
            "success": True,
            "url": f"/static/uploads/{filename}",
            "filename": file.filename,
        }
    except Exception as exc:
        logger.error("File upload failed: %s", exc)
        return JSONResponse(status_code=500, content={"success": False, "error": str(exc)})


@router.post("/api/motion-reference/upload", response_model=MotionReferenceResponse)
def upload_motion_reference(
    req: MotionReferenceRequest, agent: AgentDep
) -> MotionReferenceResponse:
    """Crops a 3-second motion reference clip from input_video_path starting at start_sec."""
    raw_path = (req.input_video_path or "").strip()
    if not raw_path:
        raise HTTPException(status_code=400, detail="Missing input_video_path")
    if not (raw_path.startswith("gs://") or raw_path.startswith("https://storage.googleapis.com/")):
        normalized_rel = raw_path.lstrip("/") if raw_path.startswith("/static/") else raw_path
        real_target = os.path.realpath(normalized_rel)
        allowed_roots = (
            os.path.realpath("static"),
            os.path.realpath("/tmp"),
            os.path.realpath(tempfile.gettempdir()),
        )
        if not any(
            real_target == root or real_target.startswith(root + os.sep) for root in allowed_roots
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid input_video_path: must reside within static/ or /tmp/ directory",
            )
    try:
        clip_path = agent.media_extractor.crop_3s_motion_reference(
            input_video_path=req.input_video_path,
            start_sec=req.start_sec,
        )
        return MotionReferenceResponse(
            success=True,
            clip_path=clip_path,
            message="Motion reference clip cropped successfully",
        )
    except Exception as exc:
        logger.error("Motion reference cropping failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/media-proxy")
def media_proxy(uri: str, request: Request, agent: AgentDep) -> Response:
    if not uri:
        raise HTTPException(status_code=400, detail="Missing URI parameter")

    if uri.startswith("https://storage.googleapis.com/"):
        parts = uri.replace("https://storage.googleapis.com/", "").split("/", 1)
        if len(parts) == 2:
            uri = f"gs://{parts[0]}/{parts[1]}"
    elif uri.startswith("https://storage.cloud.google.com/"):
        parts = uri.replace("https://storage.cloud.google.com/", "").split("/", 1)
        if len(parts) == 2:
            uri = f"gs://{parts[0]}/{parts[1]}"

    if not uri.startswith("gs://"):
        raise HTTPException(
            status_code=400,
            detail="Invalid GCS URI. Must start with gs:// or https://storage.googleapis.com/",
        )
    gcs_path = uri[5:]
    if "/" in gcs_path:
        req_bucket = gcs_path.split("/", 1)[0]
        allowed_buckets = {
            agent.storage.bucket_name,
            settings.gcs_bucket_name,
            "reference-images-jt-trend-trawler",
            "omnimash-media-hybrid-vertex",
            "test-omnimash-bucket",
            "bucket",
        }
        if req_bucket not in allowed_buckets:
            raise HTTPException(
                status_code=403,
                detail=f"Access to GCS bucket '{req_bucket}' is not permitted",
            )

    range_header = request.headers.get("range") if request and hasattr(request, "headers") else None
    if range_header and range_header.strip().lower().startswith("bytes="):
        range_spec = range_header.strip()[6:].split(",")[0].strip()
        ranged_res = agent.storage.download_blob_range(uri, range_spec)
        if ranged_res is not None:
            chunk, content_type, total_len, start, end = ranged_res
            return Response(
                content=chunk,
                status_code=206,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Accept-Ranges": "bytes",
                    "Content-Range": f"bytes {start}-{end}/{total_len}",
                    "Content-Length": str(len(chunk)),
                },
            )

    data, content_type = agent.storage.download_blob_bytes(uri)
    if not data:
        raise HTTPException(
            status_code=404,
            detail="Media object not found or empty",
        )
    total_len = len(data)
    if range_header and range_header.strip().lower().startswith("bytes="):
        range_spec = range_header.strip()[6:].split(",")[0].strip()
        if "-" in range_spec:
            start_str, end_str = range_spec.split("-", 1)
            try:
                if start_str == "":
                    suffix_len = int(end_str)
                    start = max(0, total_len - suffix_len)
                    end = total_len - 1
                else:
                    start = int(start_str)
                    end = int(end_str) if end_str else total_len - 1
                if 0 <= start <= end < total_len:
                    chunk = data[start : end + 1]
                    return Response(
                        content=chunk,
                        status_code=206,
                        media_type=content_type,
                        headers={
                            "Cache-Control": "public, max-age=86400",
                            "Accept-Ranges": "bytes",
                            "Content-Range": f"bytes {start}-{end}/{total_len}",
                            "Content-Length": str(len(chunk)),
                        },
                    )
            except ValueError:
                pass
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Accept-Ranges": "bytes",
            "Content-Length": str(total_len),
        },
    )


@router.post("/api/research", response_model=ParodyResearchResult)
def research_parody(req: ResearchRequest, agent: AgentDep) -> ParodyResearchResult:
    return agent.media_extractor.research_parody_clash(req.subject, req.aesthetic)


@router.post("/api/extract-reference", response_model=ReferenceAnalysisReport)
def extract_reference(req: ExtractReferenceRequest, agent: AgentDep) -> ReferenceAnalysisReport:
    from omnimash.ingestion.validators import sanitize_ingestion_session_id

    try:
        safe_sid = sanitize_ingestion_session_id(req.session_name or "default")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return agent.media_extractor.analyze_youtube_reference(req.url, session_id=safe_sid)
