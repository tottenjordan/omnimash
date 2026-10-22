"""Router for time-limited shareable video link generation."""

import logging
from fastapi import APIRouter, HTTPException
from omnimash.api.deps import AgentDep
from omnimash.api.models import CreateShareLinkRequest, CreateShareLinkResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["share"])


@router.post("/api/share/create", response_model=CreateShareLinkResponse)
def create_share_link(
    req: CreateShareLinkRequest, agent: AgentDep
) -> CreateShareLinkResponse:
    """Generates a 7-day GCS V4 signed URL for streaming or downloading finalized videos.

    Recipients connect directly to Google Cloud Storage CDN without hitting the OmniMash app.
    """
    raw_url = (req.video_url or "").strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="Missing video_url")

    try:
        result = agent.storage.create_shareable_link(
            blob_path_or_uri=req.video_url,
            expiration_days=req.expiration_days,
            master_title=req.master_title,
        )
        share_url = result["share_url"]
        download_url = result["download_url"]
        embed_snippet = (
            f'<video controls src="{share_url}" width="100%">'
            f'<source src="{share_url}" type="video/mp4">'
            f"</video>"
        )
        return CreateShareLinkResponse(
            success=True,
            share_url=share_url,
            download_url=download_url,
            embed_snippet=embed_snippet,
            expires_at=result["expires_at"],
            lifespan_days=result["lifespan_days"],
            gcs_uri=result["gcs_uri"],
            filename=result["filename"],
            message=result["message"],
        )
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        logger.error("Failed to generate share link: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate share link: {exc}"
        )
