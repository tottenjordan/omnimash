"""GCS V4 signed URL generation helpers for shareable and downloadable media links."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import os
from typing import Any
from urllib.parse import quote_plus, unquote
import uuid

logger = logging.getLogger(__name__)


def _extract_blob_name(storage: Any, blob_path_or_uri: str) -> str:
    """Normalizes a proxy URL, gs:// URI, HTTPS storage URL, or path into a bucket-relative blob name."""
    clean_path = unquote(storage._normalize_media_source_path(blob_path_or_uri).strip())
    bucket_gs_prefix = f"gs://{storage.bucket_name}/"
    bucket_https_prefix = f"https://storage.googleapis.com/{storage.bucket_name}/"
    gcs_https_prefix = "https://storage.googleapis.com/"

    if clean_path.startswith(bucket_gs_prefix):
        blob_name = clean_path[len(bucket_gs_prefix) :].lstrip("/")
    elif clean_path.startswith("gs://"):
        parts = clean_path[5:].split("/", 1)
        blob_name = parts[1] if len(parts) > 1 else parts[0]
    elif clean_path.startswith(bucket_https_prefix):
        blob_name = clean_path[len(bucket_https_prefix) :].lstrip("/")
    elif clean_path.startswith(gcs_https_prefix):
        parts = clean_path[len(gcs_https_prefix) :].split("/", 1)
        blob_name = parts[1] if len(parts) > 1 else parts[0]
    else:
        blob_name = clean_path.lstrip("/")

    if "?" in blob_name:
        blob_name = blob_name.split("?", 1)[0]
    return blob_name


def _resolve_download_filename(blob_name: str, master_title: str | None) -> str:
    """Resolves the `.mp4` attachment filename from master_title or the blob basename."""
    if master_title and master_title.strip():
        clean_title = master_title.strip()
        return clean_title if clean_title.endswith(".mp4") else f"{clean_title}.mp4"
    raw_base = os.path.basename(blob_name)
    if raw_base:
        return raw_base if raw_base.endswith(".mp4") else f"{raw_base}.mp4"
    return "final_master.mp4"


def _build_mock_v4_urls(
    bucket_name: str,
    blob_name: str,
    filename: str,
    content_type: str,
    mock_sa: str,
    now_dt: datetime,
    expiration_seconds: int,
) -> tuple[str, str]:
    """Builds deterministic mock V4-formatted share and download URLs for mock mode."""
    date_stamp = now_dt.strftime("%Y%m%d")
    time_stamp = now_dt.strftime("%Y%m%dT%H%M%SZ")
    cred_scope = f"{quote_plus(mock_sa)}%2F{date_stamp}%2Fauto%2Fstorage%2Fgoog4_request"
    query_base = (
        f"X-Goog-Algorithm=GOOG4-RSA-SHA256"
        f"&X-Goog-Credential={cred_scope}"
        f"&X-Goog-Date={time_stamp}"
        f"&X-Goog-Expires={expiration_seconds}"
        f"&X-Goog-SignedHeaders=host"
        f"&X-Goog-Signature=mockv4signature{uuid.uuid4().hex}"
    )
    base_url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}?"
    share_url = (
        f"{base_url}{query_base}"
        f"&response-content-disposition=inline&response-content-type={quote_plus(content_type)}"
    )
    download_url = (
        f"{base_url}{query_base}"
        f"&response-content-disposition={quote_plus(f'attachment; filename="{filename}"')}"
    )
    return share_url, download_url


def _sign_with_iam_credentials(
    storage: Any,
    blob: Any,
    expires_delta: timedelta,
    content_type: str,
    filename: str,
    mock_sa: str,
    primary_exc: Exception,
) -> tuple[str | None, str | None]:
    """Attempts IAM token-based V4 signing when local credentials lack a private key."""
    try:
        import google.auth
        from google.auth.transport import requests as google_auth_requests

        creds = getattr(storage._client_instance, "_credentials", None)
        if creds is None:
            creds, _ = google.auth.default()
        if creds is None:
            return None, None

        needs_refresh = (
            not getattr(creds, "token", None)
            or getattr(creds, "valid", True) is False
            or getattr(creds, "service_account_email", None) in (None, "default")
        )
        if needs_refresh:
            creds.refresh(google_auth_requests.Request())

        sa_email = (
            getattr(creds, "service_account_email", None)
            or getattr(creds, "signer_email", None)
            or mock_sa
        )
        if sa_email == "default":
            sa_email = mock_sa
        access_token = getattr(creds, "token", None)
        if not (sa_email and access_token):
            return None, None

        share_url = blob.generate_signed_url(
            version="v4",
            expiration=expires_delta,
            method="GET",
            response_type=content_type,
            response_disposition="inline",
            service_account_email=sa_email,
            access_token=access_token,
        )
        download_url = blob.generate_signed_url(
            version="v4",
            expiration=expires_delta,
            method="GET",
            response_disposition=f'attachment; filename="{filename}"',
            service_account_email=sa_email,
            access_token=access_token,
        )
        return share_url, download_url
    except Exception as iam_exc:
        logger.warning(
            "Cryptographic V4 signing via credentials/IAM failed (%s / %s); omitting fake V4 signature in live mode.",
            primary_exc,
            iam_exc,
        )
        return None, None


def create_v4_shareable_link(
    storage: Any,
    blob_path_or_uri: str,
    expiration_days: int = 7,
    master_title: str | None = None,
    content_type: str = "video/mp4",
) -> dict[str, Any]:
    """Generates a secure GCS V4 Signed URL (up to 7-day lifespan) allowing external
    users to stream or download finalized videos without exposing the main application.
    """
    if not (1 <= expiration_days <= 7):
        raise ValueError("Expiration days must be between 1 and 7")

    blob_name = _extract_blob_name(storage, blob_path_or_uri)
    filename = _resolve_download_filename(blob_name, master_title)
    if not os.path.basename(blob_name):
        blob_name = f"{blob_name.rstrip('/')}/{filename}"

    expires_delta = timedelta(days=expiration_days)
    expiration_seconds = int(expires_delta.total_seconds())
    now_dt = datetime.now(timezone.utc)
    expires_at_iso = (now_dt + expires_delta).isoformat()

    project_id = storage.project_id or "hybrid-vertex"
    mock_sa = f"omnimash-sa@{project_id}.iam.gserviceaccount.com"

    if storage.mock_mode:
        share_url, download_url = _build_mock_v4_urls(
            bucket_name=storage.bucket_name,
            blob_name=blob_name,
            filename=filename,
            content_type=content_type,
            mock_sa=mock_sa,
            now_dt=now_dt,
            expiration_seconds=expiration_seconds,
        )
        return {
            "success": True,
            "signed_v4": False,
            "blob_name": blob_name,
            "gcs_uri": f"gs://{storage.bucket_name}/{blob_name}",
            "share_url": share_url,
            "download_url": download_url,
            "expires_at": expires_at_iso,
            "lifespan_days": expiration_days,
            "filename": filename,
            "message": f"Shareable link generated. Valid for {expiration_days} days until {expires_at_iso}.",
        }

    signed_v4 = False
    share_url = f"https://storage.googleapis.com/{storage.bucket_name}/{blob_name}"
    download_url = share_url

    if storage.bucket:
        blob = storage.bucket.blob(blob_name)
        try:
            share_url = blob.generate_signed_url(
                version="v4",
                expiration=expires_delta,
                method="GET",
                response_type=content_type,
                response_disposition="inline",
            )
            download_url = blob.generate_signed_url(
                version="v4",
                expiration=expires_delta,
                method="GET",
                response_disposition=f'attachment; filename="{filename}"',
            )
            signed_v4 = True
        except Exception as primary_exc:
            iam_share, iam_download = _sign_with_iam_credentials(
                storage=storage,
                blob=blob,
                expires_delta=expires_delta,
                content_type=content_type,
                filename=filename,
                mock_sa=mock_sa,
                primary_exc=primary_exc,
            )
            if iam_share and iam_download:
                share_url = iam_share
                download_url = iam_download
                signed_v4 = True

    return {
        "success": True,
        "signed_v4": signed_v4,
        "blob_name": blob_name,
        "gcs_uri": f"gs://{storage.bucket_name}/{blob_name}",
        "share_url": share_url,
        "download_url": download_url,
        "expires_at": expires_at_iso,
        "lifespan_days": expiration_days,
        "filename": filename,
        "message": f"Shareable link generated. Valid for {expiration_days} days until {expires_at_iso}.",
    }
