"""Router for adk_pipe-aligned frozen-snapshot shareable links (/s/<token>) and GCS share management."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import html
import json
import logging
import os
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from omnimash.api.deps import AgentDep
from omnimash.api.models import CreateShareLinkRequest, CreateShareLinkResponse
from omnimash.storage.share_snapshot import (
    build_share_snapshot,
    is_valid_share_token,
    new_share_token,
)
from omnimash.storage.shares_store import ShareRecord, get_shares_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["share"])


async def share_mode_lockdown_middleware(request: Request, call_next: Any) -> Any:
    """Locks down the server to public /s/<token> routes when SHARE_MODE=1."""
    path = request.url.path or ""
    share_mode = os.environ.get("SHARE_MODE", "0").strip() in ("1", "true", "TRUE")
    if share_mode:
        allowed = (
            path == "/s"
            or path.startswith("/s/")
            or path in ("/robots.txt", "/favicon.ico", "/api/health")
        )
        if not allowed:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
    response = await call_next(request)
    if path == "/s" or path.startswith("/s/"):
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


class CreateFrozenShareRequest(BaseModel):
    session_id: str = "default_session"
    session_name: str | None = None
    project_id: str = "prj_default"
    video_url: str = ""
    title: str = "Shared OmniMash Video"
    master_title: str | None = None
    scope: str = "video"
    aspect_ratio: str = "16:9"
    duration_seconds: float = 10.0
    clips: list[dict[str, Any]] | None = None
    expiration_days: int = Field(default=7, ge=1, le=7)


def _resolve_share_base_url(request: Request) -> str:
    env_base = (os.environ.get("SHARE_BASE_URL") or "").strip().rstrip("/")
    if env_base:
        return env_base
    if request and request.base_url:
        return str(request.base_url).rstrip("/")
    return "http://localhost:8080"


def _create_frozen_share_bundle(
    *,
    video_url: str,
    title: str,
    scope: str,
    aspect_ratio: str,
    duration_seconds: float,
    clips: list[dict[str, Any]] | None,
    session_id: str,
    project_id: str,
    request: Request,
    agent: Any,
) -> tuple[ShareRecord, dict[str, Any]]:
    token = new_share_token()
    created_at = datetime.now(UTC).isoformat()
    snapshot = build_share_snapshot(
        token=token,
        scope="slate" if scope == "slate" else "video",
        title=title,
        aspect_ratio=aspect_ratio,
        duration_seconds=duration_seconds,
        clips=clips,
        created_at=created_at,
    )
    bundle_info = agent.storage.freeze_share_bundle(
        token=token,
        source_blob_or_uri=video_url,
        snapshot=snapshot,
    )
    base_url = _resolve_share_base_url(request)
    public_url = f"{base_url}/s/{token}"
    rec = ShareRecord(
        token=token,
        url=public_url,
        scope=snapshot["scope"],
        title=snapshot["title"],
        aspect_ratio=snapshot["aspect_ratio"],
        session_id=session_id,
        project_id=project_id,
        gcs_prefix=bundle_info["gcs_prefix"],
        created_at=created_at,
    )
    get_shares_store().put(rec)
    return rec, snapshot


@router.post("/api/shares", status_code=201)
def create_share_snapshot_endpoint(
    req: CreateFrozenShareRequest,
    request: Request,
    agent: AgentDep,
) -> dict[str, Any]:
    """Creates an adk_pipe-aligned frozen share bundle at shares/<token>/ and returns /s/<token>."""
    raw_url = (req.video_url or "").strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="Missing video_url")

    eff_title = (req.title or req.master_title or "Shared OmniMash Video").strip()
    eff_session = (req.session_name or req.session_id or "default_session").strip()
    rec, snapshot = _create_frozen_share_bundle(
        video_url=raw_url,
        title=eff_title,
        scope=req.scope,
        aspect_ratio=req.aspect_ratio,
        duration_seconds=req.duration_seconds,
        clips=req.clips,
        session_id=eff_session,
        project_id=req.project_id,
        request=request,
        agent=agent,
    )
    base_url = _resolve_share_base_url(request)
    download_url = f"{base_url}/s/{rec.token}/video?download=1"
    expires_at = (datetime.now(UTC) + timedelta(days=req.expiration_days)).isoformat()
    filename = f"{eff_title.replace(' ', '_')}.mp4" if not eff_title.endswith(".mp4") else eff_title
    embed_snippet = (
        f'<video controls preload="metadata" src="{rec.url}/video" width="100%">'
        f'<source src="{rec.url}/video" type="video/mp4">'
        f"</video>"
    )
    return {
        "success": True,
        "token": rec.token,
        "url": rec.url,
        "share_url": rec.url,
        "download_url": download_url,
        "embed_snippet": embed_snippet,
        "created_at": rec.created_at,
        "expires_at": expires_at,
        "lifespan_days": req.expiration_days,
        "scope": rec.scope,
        "title": rec.title,
        "aspect_ratio": rec.aspect_ratio,
        "gcs_uri": rec.gcs_prefix,
        "filename": filename,
        "snapshot": snapshot,
        "message": f"Public share snapshot created at {rec.url}",
    }


def _hydrate_shares_from_gcs(agent: Any, request: Request | None = None) -> None:
    """Hydrates SharesStore from shares/*/snapshot.json in GCS when running across Cloud Run instances."""
    if getattr(agent.storage, "mock_mode", True) or not getattr(agent.storage, "bucket", None):
        return
    try:
        bucket = agent.storage.bucket
        store = get_shares_store()
        base_url = _resolve_share_base_url(request) if request else "http://localhost:8080"
        blobs = list(bucket.list_blobs(prefix="shares/"))
        for blob in blobs:
            name = getattr(blob, "name", "") or ""
            if not name.endswith("/snapshot.json"):
                continue
            parts = name.split("/")
            if len(parts) != 3 or parts[0] != "shares":
                continue
            token = parts[1]
            if not is_valid_share_token(token) or store.get(token) is not None:
                continue
            raw = (
                blob.download_as_text()
                if hasattr(blob, "download_as_text")
                else blob.download_as_bytes().decode("utf-8")
            )
            snap = json.loads(raw)
            if not isinstance(snap, dict):
                continue
            rec = ShareRecord(
                token=token,
                url=f"{base_url}/s/{token}",
                scope=str(snap.get("scope") or "video"),
                title=str(snap.get("title") or "Shared OmniMash Video"),
                aspect_ratio=str(snap.get("aspect_ratio") or "16:9"),
                session_id="",
                gcs_prefix=f"gs://{agent.storage.bucket_name}/shares/{token}/",
                created_at=str(snap.get("created_at") or datetime.now(UTC).isoformat()),
            )
            store.put(rec)
    except Exception as exc:
        logger.debug("Hydrating shares from GCS skipped/failed: %s", exc)


@router.get("/api/shares")
def list_active_shares(
    request: Request,
    agent: AgentDep,
    session_id: str | None = None,
    owner_user: str | None = None,
) -> dict[str, Any]:
    """Lists active (non-revoked) share links, hydrating from GCS shares/*/snapshot.json if needed."""
    _hydrate_shares_from_gcs(agent=agent, request=request)
    items = get_shares_store().list_for(session_id=session_id, owner_user=owner_user)
    return {
        "success": True,
        "shares": items,
    }


@router.delete("/api/shares/{token}")
def revoke_share_link(token: str, agent: AgentDep) -> dict[str, Any]:
    """Revokes a share token and deletes all objects under shares/<token>/."""
    if not is_valid_share_token(token):
        raise HTTPException(status_code=404, detail="Share link not found")
    rec = get_shares_store().revoke(token)
    deleted_blobs = agent.storage.delete_share_prefix(token)
    return {
        "success": True,
        "token": token,
        "revoked_at": rec.revoked_at if rec else datetime.now(UTC).isoformat(),
        "deleted_blobs": deleted_blobs,
    }


@router.post("/api/share/create", response_model=CreateShareLinkResponse)
def create_share_link(
    req: CreateShareLinkRequest,
    request: Request,
    agent: AgentDep,
) -> CreateShareLinkResponse:
    """Generates both a frozen /s/<token> share bundle and a GCS link payload."""
    raw_url = (req.video_url or "").strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="Missing video_url")

    try:
        result = agent.storage.create_shareable_link(
            blob_path_or_uri=req.video_url,
            expiration_days=req.expiration_days,
            master_title=req.master_title,
        )
        eff_title = (
            req.title or req.master_title or result.get("filename") or "Shared OmniMash Video"
        ).strip()
        rec, _ = _create_frozen_share_bundle(
            video_url=raw_url,
            title=eff_title,
            scope=req.scope,
            aspect_ratio=req.aspect_ratio,
            duration_seconds=req.duration_seconds,
            clips=req.clips,
            session_id=req.session_name or "default_session",
            project_id="prj_default",
            request=request,
            agent=agent,
        )
        raw_share_url = result.get("share_url") or ""
        raw_download_url = result.get("download_url") or ""
        is_live_mode = not getattr(agent.storage, "mock_mode", False)
        has_real_signed_url = bool(result.get("signed_v4")) or (
            ("X-Goog-Signature=" in raw_share_url or "signed_" in raw_share_url)
            and "mockv4signature" not in raw_share_url
        )
        if is_live_mode and not has_real_signed_url:
            base_url = _resolve_share_base_url(request)
            share_url = rec.url
            download_url = f"{base_url}/s/{rec.token}/video?download=1"
            embed_src = f"{rec.url}/video"
        else:
            share_url = raw_share_url
            download_url = raw_download_url
            embed_src = share_url
        embed_snippet = (
            f'<video controls src="{embed_src}" width="100%">'
            f'<source src="{embed_src}" type="video/mp4">'
            f"</video>"
        )
        return CreateShareLinkResponse(
            success=True,
            token=rec.token,
            url=rec.url,
            created_at=rec.created_at,
            scope=rec.scope,
            title=rec.title,
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
        raise HTTPException(status_code=500, detail=f"Failed to generate share link: {exc}")


def _render_share_viewer_html(snapshot: dict[str, Any], token: str, base_url: str) -> str:
    title = html.escape(str(snapshot.get("title") or "Shared OmniMash Video"))
    aspect = html.escape(str(snapshot.get("aspect_ratio") or "16:9"))
    scope = html.escape(str(snapshot.get("scope") or "video"))
    duration = snapshot.get("duration_seconds") or 10
    video_src = f"/s/{token}/video"
    download_src = f"/s/{token}/video?download=1"
    share_link = f"{base_url}/s/{token}"

    return f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="robots" content="noindex, nofollow" />
  <meta name="referrer" content="no-referrer" />
  <title>{title} — OmniMash Share</title>
  <style>
    :root {{
      color-scheme: dark;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: radial-gradient(circle at top, #1e1b4b 0%, #09090b 65%);
      color: #f4f4f5;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2rem 1rem;
    }}
    .viewer-shell {{
      width: 100%;
      max-width: 960px;
      background: rgba(24, 24, 27, 0.88);
      border: 1px solid rgba(99, 102, 241, 0.28);
      border-radius: 16px;
      padding: 1.5rem;
      box-shadow: 0 24px 48px rgba(0, 0, 0, 0.6);
    }}
    .header-row {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      margin-bottom: 1rem;
    }}
    .badge {{
      display: inline-block;
      font-size: 0.75rem;
      padding: 0.25rem 0.65rem;
      border-radius: 9999px;
      background: rgba(99, 102, 241, 0.2);
      border: 1px solid rgba(129, 140, 248, 0.4);
      color: #c7d2fe;
      margin-right: 0.5rem;
    }}
    .tabs {{
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1rem;
    }}
    .tab-btn {{
      background: #27272a;
      color: #d4d4d8;
      border: 1px solid #3f3f46;
      padding: 0.45rem 0.9rem;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 600;
    }}
    .tab-btn.active {{
      background: #4f46e5;
      color: #ffffff;
      border-color: #6366f1;
    }}
    .stage-container {{
      display: flex;
      justify-content: center;
      align-items: center;
      background: #000;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid #27272a;
      margin-bottom: 1.25rem;
    }}
    .stage-container.mode-story video {{
      max-width: 380px;
      aspect-ratio: 9 / 16;
    }}
    video {{
      width: 100%;
      max-height: 72vh;
      display: block;
      background: #000;
    }}
    .actions-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      justify-content: space-between;
      align-items: center;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.55rem 1.1rem;
      border-radius: 8px;
      font-size: 0.875rem;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      border: 1px solid transparent;
    }}
    .btn-primary {{
      background: #4f46e5;
      color: #fff;
    }}
    .btn-secondary {{
      background: #27272a;
      color: #e4e4e7;
      border-color: #3f3f46;
    }}
  </style>
</head>
<body>
  <div class="viewer-shell">
    <div class="header-row">
      <div>
        <h1 style="margin: 0 0 0.35rem 0; font-size: 1.35rem;">{title}</h1>
        <div>
          <span class="badge">Scope: {scope}</span>
          <span class="badge">Aspect: {aspect}</span>
          <span class="badge">{duration}s</span>
        </div>
      </div>
      <div class="tabs" role="tablist">
        <button type="button" class="tab-btn active" onclick="setViewMode('card', this)">Card View</button>
        <button type="button" class="tab-btn" onclick="setViewMode('feed', this)">Social Feed View</button>
        <button type="button" class="tab-btn" onclick="setViewMode('story', this)">9:16 Story Frame</button>
      </div>
    </div>

    <div id="videoStage" class="stage-container mode-card">
      <video controls preload="metadata" playsinline src="{video_src}">
        <source src="{video_src}" type="video/mp4" />
      </video>
    </div>

    <div class="actions-bar">
      <div style="font-size: 0.8rem; color: #a1a1aa;">
        Frozen Snapshot Share • Privacy Protected
      </div>
      <div style="display: flex; gap: 0.6rem;">
        <button type="button" class="btn btn-secondary" onclick="copyShareUrl('{share_link}', this)">
          Copy Link
        </button>
        <a class="btn btn-primary" href="{download_src}" download>
          Download MP4
        </a>
      </div>
    </div>
  </div>

  <script>
    function setViewMode(mode, btn) {{
      var stage = document.getElementById('videoStage');
      stage.className = 'stage-container mode-' + mode;
      var buttons = document.querySelectorAll('.tab-btn');
      buttons.forEach(function(b) {{ b.classList.remove('active'); }});
      if (btn) btn.classList.add('active');
    }}
    function copyShareUrl(url, btn) {{
      if (navigator.clipboard) {{
        navigator.clipboard.writeText(url);
      }}
      if (btn) {{
        var prev = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(function() {{ btn.textContent = prev; }}, 1800);
      }}
    }}
  </script>
</body>
</html>"""


@router.get("/s/{token}", response_model=None)
def get_public_share_viewer(
    token: str,
    request: Request,
    agent: AgentDep,
) -> Response:
    """Serves the self-contained public HTML viewer for a frozen share snapshot."""
    headers = {
        "X-Robots-Tag": "noindex, nofollow",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
    }
    if not is_valid_share_token(token):
        return JSONResponse(
            status_code=404,
            content={"detail": "Invalid or expired share link"},
            headers=headers,
        )
    if get_shares_store().is_revoked(token):
        return JSONResponse(
            status_code=410,
            content={"detail": "This shared link has been revoked"},
            headers=headers,
        )

    snapshot = agent.storage.read_share_snapshot(token)
    if not snapshot:
        return JSONResponse(
            status_code=404,
            content={"detail": "Share snapshot not found"},
            headers=headers,
        )

    base_url = _resolve_share_base_url(request)
    html_content = _render_share_viewer_html(snapshot, token=token, base_url=base_url)
    return HTMLResponse(content=html_content, status_code=200, headers=headers)


@router.get("/s/{token}/video", response_model=None)
def stream_public_share_video(
    token: str,
    request: Request,
    agent: AgentDep,
    download: int | None = None,
) -> Response:
    """Streams shares/{token}/video.mp4 with HTTP Range (206 Partial Content) support."""
    base_headers = {
        "X-Robots-Tag": "noindex, nofollow",
        "Referrer-Policy": "no-referrer",
        "Accept-Ranges": "bytes",
    }
    if not is_valid_share_token(token):
        return JSONResponse(
            status_code=404,
            content={"detail": "Invalid share token"},
            headers=base_headers,
        )
    if get_shares_store().is_revoked(token):
        return JSONResponse(
            status_code=410,
            content={"detail": "This shared link has been revoked"},
            headers=base_headers,
        )

    video_bytes = agent.storage.stream_share_video(token)
    if not video_bytes:
        return JSONResponse(
            status_code=404,
            content={"detail": "Shared video not found"},
            headers=base_headers,
        )

    total_len = len(video_bytes)
    disposition = (
        f'attachment; filename="omnimash_{token[:8]}.mp4"'
        if download
        else f'inline; filename="omnimash_{token[:8]}.mp4"'
    )
    range_header = request.headers.get("range") or request.headers.get("Range")
    if range_header and range_header.strip().lower().startswith("bytes="):
        m = re.match(r"bytes=(\d*)-(\d*)", range_header.strip(), flags=re.IGNORECASE)
        if m:
            start_str, end_str = m.group(1), m.group(2)
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else (total_len - 1)
            start = max(0, min(start, total_len - 1))
            end = max(start, min(end, total_len - 1))
            chunk = video_bytes[start : end + 1]
            headers = {
                **base_headers,
                "Content-Range": f"bytes {start}-{end}/{total_len}",
                "Content-Length": str(len(chunk)),
                "Content-Disposition": disposition,
            }
            return Response(
                content=chunk,
                status_code=206,
                media_type="video/mp4",
                headers=headers,
            )

    headers = {
        **base_headers,
        "Content-Length": str(total_len),
        "Content-Disposition": disposition,
    }
    return Response(
        content=video_bytes,
        status_code=200,
        media_type="video/mp4",
        headers=headers,
    )
