from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import dataclasses
from datetime import datetime, timezone
import json
import logging
import mimetypes
import os
import re
import threading
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, unquote, urlparse

from omnimash.config import settings
from omnimash.storage.defaults import DEFAULT_CHARACTERS

logger = logging.getLogger(__name__)
_CLIENTS_LOCK = threading.Lock()

_EXTRA_MIME_TYPES: dict[str, str] = {
    ".mp4": "video/mp4",
    ".wav": "audio/wav",
    ".aac": "audio/aac",
    ".mp3": "audio/mpeg",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _guess_content_type(path_or_filename: str, default: str = "application/octet-stream") -> str:
    """Accurately detects MIME type using standard mimetypes with video/audio overrides."""
    if not path_or_filename or not isinstance(path_or_filename, str):
        return default
    ext = os.path.splitext(path_or_filename.lower())[1]
    if ext in _EXTRA_MIME_TYPES:
        return _EXTRA_MIME_TYPES[ext]
    guessed, _ = mimetypes.guess_type(path_or_filename)
    return guessed or default


if TYPE_CHECKING:
    from omnimash.ingestion.media_extractor import ReferenceAnalysisReport

try:
    from google.cloud import storage
except ImportError:
    storage: Any = None


class GcsStorageManager:
    """Manages persistent cloud storage for session-scoped video, audio, prompt, and reference artifacts."""

    _SHARED_CLIENTS: dict[str, Any] = {}

    def __init__(
        self,
        bucket_name: str | None = None,
        project_id: str | None = None,
        mock_mode: bool | None = None,
    ):
        self.mock_mode = settings.mock_mode if mock_mode is None else mock_mode
        self.project_id = project_id or settings.google_cloud_project
        self.bucket_name = bucket_name or settings.gcs_bucket_name
        self._client_instance: Any = None
        self._bucket_instance: Any = None
        self._mock_analyses: dict[str, dict[str, Any]] = {}
        self._mock_session_manifests: dict[str, dict[str, Any]] = {}
        self._mock_characters: dict[str, dict[str, Any]] = {
            self._slugify(c["name"]): dict(c) for c in DEFAULT_CHARACTERS
        }
        self._mock_rosters: dict[str, list[dict[str, Any]]] = {}
        self._mock_storyboards: dict[str, dict[str, Any]] = {}
        self._mock_projects: list[str] = ["default_project"]
        self._mock_project_sessions: dict[str, list[str]] = {
            "default_project": ["parody_session_1", "session_8492", "dripwarts_battle"]
        }
        self._mock_project_characters: dict[str, list[dict[str, Any]]] = {}
        self._mock_project_products: dict[str, list[dict[str, Any]]] = {}
        self._mock_project_reference_sheets: dict[str, list[dict[str, Any]]] = {}

    @property
    def timeout(self) -> float:
        """Configured GCS SDK network timeout in seconds."""
        return float(getattr(settings, "gcs_timeout_seconds", 30.0))

    def _get_client(self) -> Any:
        if self._client_instance is not None:
            return self._client_instance
        if self.mock_mode or storage is None:
            return None
        with _CLIENTS_LOCK:
            if self._client_instance is not None:
                return self._client_instance
            client_key = self.project_id or "default"
            if client_key not in self._SHARED_CLIENTS:
                try:
                    self._SHARED_CLIENTS[client_key] = storage.Client(project=self.project_id)
                except Exception as exc:
                    logger.warning(
                        "Failed to initialize GCS client for project %s: %s",
                        self.project_id,
                        exc,
                    )
                    return None
            self._client_instance = self._SHARED_CLIENTS[client_key]
            return self._client_instance

    @property
    def client(self) -> Any:
        """Lazily retrieves or initializes the thread-safe GCS client singleton."""
        return self._get_client()

    @property
    def _client(self) -> Any:
        return self._get_client()

    @_client.setter
    def _client(self, val: Any) -> None:
        self._client_instance = val

    def _get_bucket(self) -> Any:
        if self._bucket_instance is not None:
            return self._bucket_instance
        if self.mock_mode or storage is None:
            return None
        c = self.client
        if c is not None:
            try:
                self._bucket_instance = c.bucket(self.bucket_name)
            except Exception as exc:
                logger.warning("Failed to get bucket %s: %s", self.bucket_name, exc)
                return None
        return self._bucket_instance

    @property
    def bucket(self) -> Any:
        """Lazily retrieves or initializes the GCS bucket reference."""
        return self._get_bucket()

    @property
    def _bucket(self) -> Any:
        return self._get_bucket()

    @_bucket.setter
    def _bucket(self, val: Any) -> None:
        self._bucket_instance = val

    def ensure_bucket_exists(self, location: str | None = None) -> bool:
        """Verifies or programmatically creates the GCS bucket in the configured GCP project."""
        if self.mock_mode or not self.client:
            return True
        try:
            loc = location or settings.google_cloud_region or "us-central1"
            bucket = self.client.lookup_bucket(self.bucket_name, timeout=self.timeout)
            if not bucket:
                self._bucket = self.client.create_bucket(
                    self.bucket_name, location=loc, timeout=self.timeout
                )
            else:
                self._bucket = bucket
            return True
        except Exception as exc:
            logger.warning("Failed to ensure bucket %s exists: %s", self.bucket_name, exc)
            return False

    def get_public_url(self, blob_name: str) -> str:
        """Returns the public HTTPS URL for a given GCS blob name."""
        clean_blob = blob_name.lstrip("/")
        return f"https://storage.googleapis.com/{self.bucket_name}/{clean_blob}"

    def get_gcs_uri(self, blob_name: str) -> str:
        """Returns the gs:// URI for a given GCS blob name."""
        clean_blob = blob_name.lstrip("/")
        return f"gs://{self.bucket_name}/{clean_blob}"

    def blob_exists(self, blob_path: str) -> bool:
        """Returns True if the specified blob path exists in GCS."""
        if self.mock_mode or not self._bucket:
            return False
        clean_path = (
            self._normalize_media_source_path(blob_path)
            .replace(f"gs://{self.bucket_name}/", "")
            .lstrip("/")
        )
        try:
            blob = self._bucket.blob(clean_path)
            return bool(blob.exists(timeout=self.timeout))
        except Exception as exc:
            logger.warning("Failed to check existence for %s: %s", clean_path, exc)
            return False

    def get_blob_metadata(self, blob_path: str) -> dict[str, Any] | None:
        """Retrieves blob metadata (size, content_type, updated) without downloading content."""
        if self.mock_mode or not self._bucket:
            return None
        clean_path = (
            self._normalize_media_source_path(blob_path)
            .replace(f"gs://{self.bucket_name}/", "")
            .lstrip("/")
        )
        try:
            blob = self._bucket.get_blob(clean_path, timeout=self.timeout)
            if not blob:
                return None
            return {
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_type,
                "updated": blob.updated,
                "metadata": blob.metadata or {},
            }
        except Exception as exc:
            logger.warning("Failed to get blob metadata for %s: %s", clean_path, exc)
            return None

    def delete_blob(self, blob_path: str) -> bool:
        """Deletes a blob from GCS if it exists."""
        if self.mock_mode or not self._bucket:
            return True
        clean_path = (
            self._normalize_media_source_path(blob_path)
            .replace(f"gs://{self.bucket_name}/", "")
            .lstrip("/")
        )
        try:
            blob = self._bucket.blob(clean_path)
            if blob.exists(timeout=self.timeout):
                blob.delete(timeout=self.timeout)
            return True
        except Exception as exc:
            logger.warning("Failed to delete blob %s: %s", clean_path, exc)
            return False

    def build_session_blob_path(
        self,
        session_id: str | None,
        category: str,
        filename: str,
        project_id: str | None = None,
    ) -> str:
        """Constructs a hierarchical session-scoped or project/session-scoped blob path."""
        sid = session_id or "global"
        clean_cat = category.strip("/")
        clean_file = os.path.basename(filename)
        if project_id:
            return f"projects/{project_id}/sessions/{sid}/{clean_cat}/{clean_file}"
        return f"sessions/{sid}/{clean_cat}/{clean_file}"

    def upload_file(
        self,
        local_path: str,
        destination_blob_name: str | None = None,
        session_id: str | None = None,
        category: str = "intermediate",
        content_type: str | None = None,
        project_id: str | None = None,
    ) -> str:
        """Uploads a local media artifact to GCS under its session/project subfolder."""
        if not destination_blob_name:
            basename = os.path.basename(local_path)
            destination_blob_name = self.build_session_blob_path(
                session_id=session_id,
                category=category,
                filename=basename,
                project_id=project_id,
            )

        destination_blob_name = destination_blob_name.lstrip("/")

        if self.mock_mode or not self._bucket:
            return self.get_public_url(destination_blob_name)

        try:
            if not content_type:
                content_type = _guess_content_type(local_path, default="application/octet-stream")

            blob = self._bucket.blob(destination_blob_name)
            blob.upload_from_filename(local_path, content_type=content_type, timeout=self.timeout)
            return self.get_public_url(destination_blob_name)
        except Exception as exc:
            logger.warning("upload_file failed on %s: %s", destination_blob_name, exc)
            return self.get_public_url(destination_blob_name)

    def upload_bytes(
        self,
        data: bytes,
        destination_blob_name: str,
        content_type: str = "video/mp4",
    ) -> str:
        """Uploads binary data directly to GCS."""
        destination_blob_name = destination_blob_name.lstrip("/")
        if self.mock_mode or not self._bucket:
            return self.get_public_url(destination_blob_name)

        try:
            blob = self._bucket.blob(destination_blob_name)
            blob.upload_from_string(data, content_type=content_type, timeout=self.timeout)
            return self.get_public_url(destination_blob_name)
        except Exception as exc:
            logger.warning("upload_bytes failed on %s: %s", destination_blob_name, exc)
            return self.get_public_url(destination_blob_name)

    def download_blob_bytes(self, gs_uri: str) -> tuple[bytes, str]:
        """Downloads binary bytes and infers content_type from a GCS URI (gs://bucket/blob_path) or HTTPS storage URL."""
        if not isinstance(gs_uri, str) or not gs_uri.strip():
            return (b"", "image/jpeg")

        raw_uri = self._normalize_media_source_path(gs_uri.strip())

        if raw_uri.startswith("https://storage.googleapis.com/"):
            raw_uri = "gs://" + raw_uri.replace("https://storage.googleapis.com/", "")

        if not raw_uri.startswith("gs://"):
            return (b"", "image/jpeg")

        path = raw_uri[5:]
        parts = path.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return (b"", "image/jpeg")

        bucket_name, blob_path = parts[0], parts[1]

        if self.mock_mode:
            return (b"mock_image_bytes", "image/jpeg")

        try:
            if self._bucket_instance is not None and getattr(
                self._bucket_instance, "name", None
            ) in (bucket_name, None, ""):
                bucket = self._bucket_instance
            elif self.client:
                bucket = self.client.bucket(bucket_name)
            else:
                return (b"", "image/jpeg")

            blob = bucket.blob(blob_path)
            raw_data = blob.download_as_bytes(timeout=self.timeout)
            data = raw_data if isinstance(raw_data, (bytes, bytearray)) else b""
            content_type = getattr(blob, "content_type", None) or _guess_content_type(
                blob_path, default="image/jpeg"
            )
            return (data, content_type)
        except Exception as exc:
            logger.warning("download_blob_bytes failed on %s/%s: %s", bucket_name, blob_path, exc)
            return (b"", "image/jpeg")

    def download_blob_range(
        self, gs_uri: str, range_spec: str
    ) -> tuple[bytes, str, int, int, int] | None:
        """Downloads only the requested byte range [start, end] from GCS without buffering the full blob."""
        if self.mock_mode or not self._client or not isinstance(gs_uri, str) or not gs_uri.strip():
            return None

        raw_uri = gs_uri.strip()
        if raw_uri.startswith("https://storage.googleapis.com/"):
            raw_uri = "gs://" + raw_uri.replace("https://storage.googleapis.com/", "")
        if not raw_uri.startswith("gs://"):
            return None

        parts = raw_uri[5:].split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return None

        bucket_name, blob_path = parts[0], parts[1]
        if "-" not in range_spec:
            return None

        try:
            if self._bucket_instance is not None and getattr(
                self._bucket_instance, "name", None
            ) in (bucket_name, None, ""):
                bucket = self._bucket_instance
            elif self.client:
                bucket = self.client.bucket(bucket_name)
            else:
                return None

            blob = bucket.blob(blob_path)
            blob.reload(timeout=self.timeout)
            total_len = int(blob.size or 0)
            if total_len <= 0:
                return None

            start_str, end_str = range_spec.split("-", 1)
            if start_str == "":
                suffix_len = int(end_str)
                start = max(0, total_len - suffix_len)
                end = total_len - 1
            else:
                start = int(start_str)
                end = min(int(end_str), total_len - 1) if end_str else total_len - 1

            if not (0 <= start <= end < total_len):
                return None

            chunk = blob.download_as_bytes(start=start, end=end, timeout=self.timeout)
            content_type = getattr(blob, "content_type", None) or _guess_content_type(
                blob_path, default="application/octet-stream"
            )
            return (chunk, content_type, total_len, start, end)
        except Exception as exc:
            logger.warning("download_blob_range failed on %s: %s", raw_uri, exc)
            return None

    def load_bytes(self, gs_uri_or_path: str) -> tuple[bytes, str]:
        """Loads binary bytes and content_type from a GCS URI or local filesystem path."""
        if isinstance(gs_uri_or_path, str) and gs_uri_or_path.startswith("gs://"):
            return self.download_blob_bytes(gs_uri_or_path)

        if isinstance(gs_uri_or_path, str):
            path = gs_uri_or_path if os.path.exists(gs_uri_or_path) else gs_uri_or_path.lstrip("/")
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    mime = _guess_content_type(path, default="image/jpeg")
                    return (data, mime)
                except Exception as exc:
                    logger.warning("load_bytes failed on local file %s: %s", path, exc)

        if self.mock_mode:
            mime = _guess_content_type(str(gs_uri_or_path), default="image/jpeg")
            return (b"mock_image_bytes", mime)

        return (b"", "image/jpeg")

    def _upload_json_payload(
        self,
        blob_path: str,
        payload: Any,
        mock_cache_dict: dict[str, Any] | None = None,
        mock_cache_key: str | None = None,
    ) -> tuple[str, str]:
        """Encapsulates JSON serialization, GCS upload, and synchronized in-memory caching."""
        clean_path = blob_path.lstrip("/")
        if mock_cache_dict is not None and mock_cache_key is not None:
            mock_cache_dict[mock_cache_key] = payload

        content = json.dumps(payload, indent=2)
        self.upload_bytes(
            content.encode("utf-8"),
            clean_path,
            content_type="application/json",
        )
        return self.get_public_url(clean_path), self.get_gcs_uri(clean_path)

    def _download_json_payload(
        self,
        blob_path: str,
        mock_cache_dict: dict[str, Any] | None = None,
        mock_cache_key: str | None = None,
    ) -> Any | None:
        """Encapsulates JSON download, decoding, and fallback to synchronized cache."""
        clean_path = blob_path.lstrip("/")
        if not self.mock_mode and self._bucket:
            try:
                blob = self._bucket.blob(clean_path)
                if blob.exists(timeout=self.timeout):
                    content = blob.download_as_text(timeout=self.timeout)
                    parsed = json.loads(content)
                    if mock_cache_dict is not None and mock_cache_key is not None:
                        mock_cache_dict[mock_cache_key] = parsed
                    return parsed
            except Exception as exc:
                logger.warning("Failed to download JSON from %s: %s", clean_path, exc)

        if self.mock_mode and mock_cache_dict is not None and mock_cache_key is not None:
            return mock_cache_dict.get(mock_cache_key)
        return None

    def _download_blobs_concurrently(self, blobs: list[Any]) -> list[dict[str, Any]]:
        """Downloads multiple JSON blobs concurrently using ThreadPoolExecutor."""
        results: list[dict[str, Any]] = []
        if not blobs:
            return results
        json_blobs = [b for b in blobs if getattr(b, "name", "").endswith(".json")]
        if not json_blobs:
            return results
        workers = min(len(json_blobs), 8)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_blob = {
                executor.submit(
                    lambda b: json.loads(b.download_as_text(timeout=self.timeout)), blob
                ): blob
                for blob in json_blobs
            }
            for future in as_completed(future_to_blob):
                blob = future_to_blob[future]
                try:
                    data = future.result()
                    if isinstance(data, dict):
                        results.append(data)
                except Exception as exc:
                    logger.warning("Failed to download/parse blob %s: %s", blob.name, exc)
        return results

    def save_session_prompt(
        self,
        session_id: str,
        turn_index: int,
        prompt_data: dict[str, Any] | str,
    ) -> str:
        """Persists compiled prompts (5-part Anchor/Inject or 2-part Lock/Isolate) to sessions/{session_id}/prompts/."""
        filename = f"turn_{turn_index}_prompt.json"
        blob_path = self.build_session_blob_path(session_id, "prompts", filename)
        payload = prompt_data if isinstance(prompt_data, dict) else {"prompt": prompt_data}
        pub_url, _ = self._upload_json_payload(blob_path, payload)
        return pub_url

    def save_session_manifest(
        self,
        session_id: str,
        manifest_data: dict[str, Any],
        project_id: str | None = None,
    ) -> str:
        """Persists session manifest to projects/{project_id}/sessions/{session_id}/prompts/session_manifest.json in GCS."""
        pid = project_id or "default_project"
        key = f"{pid}/{session_id}"
        blob_path = self.build_session_blob_path(
            session_id, "prompts", "session_manifest.json", project_id=project_id
        )
        pub_url, _ = self._upload_json_payload(
            blob_path,
            manifest_data,
            mock_cache_dict=self._mock_session_manifests,
            mock_cache_key=key,
        )
        self._mock_session_manifests[session_id] = manifest_data
        return pub_url

    def get_session_manifest(
        self,
        session_id: str,
        project_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Retrieves session manifest metadata for a session."""
        key = f"{project_id}/{session_id}" if project_id else session_id
        if key in self._mock_session_manifests:
            return self._mock_session_manifests[key]
        if session_id in self._mock_session_manifests:
            return self._mock_session_manifests[session_id]

        candidate_paths = []
        if project_id:
            candidate_paths.append(
                self.build_session_blob_path(
                    session_id,
                    "prompts",
                    "session_manifest.json",
                    project_id=project_id,
                )
            )
        candidate_paths.append(
            self.build_session_blob_path(session_id, "prompts", "session_manifest.json")
        )
        for blob_path in candidate_paths:
            res = self._download_json_payload(
                blob_path,
                mock_cache_dict=self._mock_session_manifests,
                mock_cache_key=key,
            )
            if res is not None:
                self._mock_session_manifests[session_id] = res
                return res

        return None

    def save_reference_analysis(
        self,
        session_id: str,
        report: ReferenceAnalysisReport | dict[str, Any],
    ) -> str:
        """Persists reference video acoustic and visual analysis metadata to sessions/{session_id}/references/reference_analysis.json."""
        report_dict: dict[str, Any]
        if dataclasses.is_dataclass(report) and not isinstance(report, type):
            report_dict = dataclasses.asdict(report)
        elif isinstance(report, dict):
            report_dict = {str(k): v for k, v in report.items()}
        else:
            report_dict = {}

        filename = "reference_analysis.json"
        blob_path = self.build_session_blob_path(session_id, "references", filename)
        pub_url, _ = self._upload_json_payload(
            blob_path,
            report_dict,
            mock_cache_dict=self._mock_analyses,
            mock_cache_key=session_id,
        )
        return pub_url

    def get_reference_analysis(self, session_id: str) -> dict[str, Any] | None:
        """Retrieves reference video acoustic and visual analysis metadata for a session."""
        if session_id in self._mock_analyses:
            return self._mock_analyses[session_id]

        blob_path = self.build_session_blob_path(
            session_id, "references", "reference_analysis.json"
        )
        return self._download_json_payload(
            blob_path,
            mock_cache_dict=self._mock_analyses,
            mock_cache_key=session_id,
        )

    def _normalize_media_source_path(self, src: str) -> str:
        """Normalizes proxy URLs, GCS URIs, or relative paths to a raw GCS URI or local path."""
        if not src or not isinstance(src, str):
            return ""
        src = src.strip()
        if "/api/media-proxy" in src and "uri=" in src:
            try:
                parsed = urlparse(src)
                qs = parse_qs(parsed.query)
                if "uri" in qs and qs["uri"]:
                    return unquote(qs["uri"][0]).strip()
            except Exception as exc:
                logger.warning("Failed to parse media-proxy URL %s: %s", src, exc)
        return src

    def save_final_master(
        self,
        session_id: str | None,
        source_rel_path: str,
        master_title: str,
        prompt_data: dict[str, Any] | str | None = None,
    ) -> tuple[str, str]:
        """Copies or uploads video files to sessions/{session_id}/final_masters/{master_title}.mp4 in GCS."""
        title_base = master_title[:-4] if master_title.endswith(".mp4") else master_title
        clean_title = f"{title_base}.mp4"
        dest_blob_path = self.build_session_blob_path(
            session_id, "final_masters", clean_title
        ).lstrip("/")
        public_url = self.get_public_url(dest_blob_path)
        gcs_uri = self.get_gcs_uri(dest_blob_path)

        if not self.mock_mode and self.bucket:
            try:
                from omnimash.engine.media_loader import validate_local_media_path

                norm_source = self._normalize_media_source_path(source_rel_path)
                safe_local = validate_local_media_path(norm_source)
                if safe_local and os.path.isfile(safe_local):
                    blob = self.bucket.blob(dest_blob_path)
                    blob.upload_from_filename(
                        safe_local, content_type="video/mp4", timeout=self.timeout
                    )
                elif (
                    not norm_source.startswith("/")
                    and not os.path.isabs(norm_source)
                    and not norm_source.startswith("gs://")
                ):
                    candidate = os.path.join(os.getcwd(), norm_source)
                    safe_local = validate_local_media_path(candidate)
                    if safe_local and os.path.isfile(safe_local):
                        blob = self.bucket.blob(dest_blob_path)
                        blob.upload_from_filename(
                            safe_local, content_type="video/mp4", timeout=self.timeout
                        )
                    else:
                        src_blob_name = norm_source.replace(f"gs://{self.bucket_name}/", "").lstrip(
                            "/"
                        )
                        src_blob = self.bucket.blob(src_blob_name)
                        if src_blob.exists(timeout=self.timeout):
                            self.bucket.copy_blob(
                                src_blob, self.bucket, dest_blob_path, timeout=self.timeout
                            )
                else:
                    src_blob_name = norm_source.replace(f"gs://{self.bucket_name}/", "").lstrip("/")
                    src_blob = self.bucket.blob(src_blob_name)
                    if src_blob.exists(timeout=self.timeout):
                        self.bucket.copy_blob(
                            src_blob, self.bucket, dest_blob_path, timeout=self.timeout
                        )
            except Exception as exc:
                logger.warning(
                    "save_final_master failed to upload/copy source %s: %s", source_rel_path, exc
                )

        if prompt_data is not None:
            prompt_filename = f"{title_base}_prompt.json"
            prompt_blob_path = self.build_session_blob_path(
                session_id, "final_masters", prompt_filename
            )
            content = (
                json.dumps(prompt_data, indent=2)
                if isinstance(prompt_data, dict)
                else json.dumps({"prompt": prompt_data}, indent=2)
            )
            self.upload_bytes(
                content.encode("utf-8"),
                prompt_blob_path,
                content_type="application/json",
            )

        return public_url, gcs_uri

    @staticmethod
    def _slugify(name: str) -> str:
        """Converts a character or entity name into a normalized lowercase slug."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
        return slug or "character"

    def save_character(
        self,
        character: dict[str, Any],
        session_id: str | None = None,
        is_library: bool = True,
        project_id: str | None = None,
    ) -> tuple[str, str]:
        """Persists character definitions as JSON in GCS under project, library, or session scope."""
        name = str(character.get("name", "character"))
        slug = self._slugify(name)
        if project_id:
            blob_path = f"projects/{project_id}/saved_characters/{slug}.json"
        elif is_library or session_id is None:
            blob_path = f"library/characters/{slug}.json"
        else:
            blob_path = f"sessions/{session_id}/characters/{slug}.json"

        pub_url, gcs_uri = self._upload_json_payload(
            blob_path,
            character,
            mock_cache_dict=self._mock_characters,
            mock_cache_key=slug,
        )

        if project_id:
            if project_id not in self._mock_projects:
                self._mock_projects.append(project_id)
            if project_id not in self._mock_project_characters:
                self._mock_project_characters[project_id] = []
            existing = [
                c
                for c in self._mock_project_characters[project_id]
                if self._slugify(str(c.get("name", ""))) != slug
            ]
            existing.append(character)
            self._mock_project_characters[project_id] = existing

        return pub_url, gcs_uri

    def save_character_sheet(
        self,
        image_data: str | bytes,
        custom_name: str,
        session_id: str | None = None,
        project_id: str | None = None,
    ) -> tuple[str, str]:
        """Saves a character reference sheet image to GCS under project or session scope."""
        name_base = (
            custom_name.removesuffix(".png")
            if isinstance(custom_name, str)
            else "character_sheet_v1"
        )
        clean_name = self._slugify(name_base)
        if not clean_name:
            clean_name = "character_sheet_v1"

        filename = f"{clean_name}.png"
        if project_id:
            if session_id:
                blob_path = (
                    f"projects/{project_id}/sessions/{session_id}/character_sheets/{filename}"
                )
            else:
                blob_path = f"projects/{project_id}/saved_reference_sheets/{filename}"
        elif session_id:
            blob_path = f"sessions/{session_id}/character_sheets/{filename}"
        else:
            blob_path = f"character_sheets/{filename}"

        raw_bytes = b""
        if isinstance(image_data, bytes):
            raw_bytes = image_data
        elif isinstance(image_data, str):
            from omnimash.engine.media_loader import fetch_media_bytes

            raw_bytes, _ = fetch_media_bytes(image_data, storage=self)
            if not raw_bytes:
                # Fallback: try decoding as raw base64 string
                try:
                    raw_bytes = base64.b64decode(image_data)
                except Exception:
                    pass

        if not raw_bytes and self.mock_mode:
            raw_bytes = b"mock_character_sheet_bytes"

        self.upload_bytes(raw_bytes, blob_path, content_type="image/png")
        pub_url = self.get_public_url(blob_path)
        gcs_uri = self.get_gcs_uri(blob_path)

        if project_id:
            if project_id not in self._mock_projects:
                self._mock_projects.append(project_id)
            if project_id not in self._mock_project_reference_sheets:
                self._mock_project_reference_sheets[project_id] = []
            sheet_meta = {
                "name": clean_name,
                "filename": filename,
                "url": pub_url,
                "gcs_uri": gcs_uri,
            }
            existing = [
                s
                for s in self._mock_project_reference_sheets[project_id]
                if s.get("name") != clean_name
            ]
            existing.append(sheet_meta)
            self._mock_project_reference_sheets[project_id] = existing

        return pub_url, gcs_uri

    def save_product(
        self,
        product: dict[str, Any],
        project_id: str | None = None,
        session_id: str | None = None,
    ) -> tuple[str, str]:
        """Persists product definition JSON in GCS under project, session, or library scope."""
        name = str(product.get("name", "product"))
        slug = self._slugify(name)
        if project_id:
            if session_id:
                blob_path = f"projects/{project_id}/sessions/{session_id}/products/{slug}.json"
            else:
                blob_path = f"projects/{project_id}/saved_products/{slug}.json"
        elif session_id:
            blob_path = f"sessions/{session_id}/products/{slug}.json"
        else:
            blob_path = f"library/products/{slug}.json"

        content = json.dumps(product, indent=2)
        self.upload_bytes(
            content.encode("utf-8"),
            blob_path,
            content_type="application/json",
        )
        if project_id:
            if project_id not in self._mock_projects:
                self._mock_projects.append(project_id)
            if project_id not in self._mock_project_products:
                self._mock_project_products[project_id] = []
            existing = [
                p
                for p in self._mock_project_products[project_id]
                if self._slugify(str(p.get("name", ""))) != slug
            ]
            existing.append(product)
            self._mock_project_products[project_id] = existing

        return self.get_public_url(blob_path), self.get_gcs_uri(blob_path)

    def save_video_clip(
        self,
        video_data_or_path: str | bytes,
        filename: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        category: str = "clips",
    ) -> tuple[str, str]:
        """Saves a video clip artifact to GCS under project and/or session path."""
        fname = filename or f"clip_{int(datetime.now(timezone.utc).timestamp())}.mp4"
        if not fname.endswith(".mp4"):
            fname = f"{fname}.mp4"

        blob_path = self.build_session_blob_path(
            session_id=session_id,
            category=category,
            filename=fname,
            project_id=project_id,
        )

        if isinstance(video_data_or_path, str) and os.path.exists(video_data_or_path):
            self.upload_file(
                local_path=video_data_or_path,
                destination_blob_name=blob_path,
                content_type="video/mp4",
            )
        elif isinstance(video_data_or_path, bytes):
            self.upload_bytes(
                data=video_data_or_path,
                destination_blob_name=blob_path,
                content_type="video/mp4",
            )
        elif isinstance(video_data_or_path, str):
            raw_bytes, _ = self.load_bytes(video_data_or_path)
            if not raw_bytes and self.mock_mode:
                raw_bytes = b"mock_video_bytes"
            self.upload_bytes(
                data=raw_bytes,
                destination_blob_name=blob_path,
                content_type="video/mp4",
            )
        else:
            if self.mock_mode:
                self.upload_bytes(
                    data=b"mock_video_bytes",
                    destination_blob_name=blob_path,
                    content_type="video/mp4",
                )

        if project_id:
            if project_id not in self._mock_projects:
                self._mock_projects.append(project_id)
            if session_id:
                if project_id not in self._mock_project_sessions:
                    self._mock_project_sessions[project_id] = []
                if session_id not in self._mock_project_sessions[project_id]:
                    self._mock_project_sessions[project_id].append(session_id)

        return self.get_public_url(blob_path), self.get_gcs_uri(blob_path)

    def save_keyframe_image(
        self,
        image_data: str | bytes,
        filename: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
    ) -> tuple[str, str]:
        """Saves a keyframe image artifact to GCS under project and/or session path."""
        fname = filename or f"keyframe_{int(datetime.now(timezone.utc).timestamp())}.png"
        if not (fname.endswith(".png") or fname.endswith(".jpg") or fname.endswith(".jpeg")):
            fname = f"{fname}.png"

        blob_path = self.build_session_blob_path(
            session_id=session_id,
            category="keyframes",
            filename=fname,
            project_id=project_id,
        )

        raw_bytes = b""
        if isinstance(image_data, bytes):
            raw_bytes = image_data
        elif isinstance(image_data, str):
            from omnimash.engine.media_loader import fetch_media_bytes

            raw_bytes, _ = fetch_media_bytes(image_data, storage=self)
            if not raw_bytes:
                try:
                    raw_bytes = base64.b64decode(image_data)
                except Exception as exc:
                    logger.debug("Base64 decode fallback failed for keyframe: %s", exc)

        if not raw_bytes and self.mock_mode:
            raw_bytes = b"mock_keyframe_bytes"

        content_type = _guess_content_type(fname, default="image/png")
        self.upload_bytes(raw_bytes, blob_path, content_type=content_type)

        if project_id:
            if project_id not in self._mock_projects:
                self._mock_projects.append(project_id)
            if session_id:
                if project_id not in self._mock_project_sessions:
                    self._mock_project_sessions[project_id] = []
                if session_id not in self._mock_project_sessions[project_id]:
                    self._mock_project_sessions[project_id].append(session_id)

        return self.get_public_url(blob_path), self.get_gcs_uri(blob_path)

    def list_projects(self) -> list[str]:
        """Lists subfolders under projects/ in GCS."""
        projects: set[str] = set(self._mock_projects)
        if "default_project" not in projects:
            projects.add("default_project")

        if not self.mock_mode and self._client and self.bucket_name:
            try:
                blobs = self._client.list_blobs(
                    self.bucket_name, prefix="projects/", delimiter="/", timeout=self.timeout
                )
                for page in blobs.pages:
                    for prefix in page.prefixes:
                        parts = prefix.rstrip("/").split("/")
                        if len(parts) >= 2 and parts[-1]:
                            projects.add(parts[-1])
            except Exception as exc:
                logger.warning("list_projects failed: %s", exc)

        return sorted(list(projects))

    def create_project(self, project_id: str) -> str:
        """Creates a new project directory structure in GCS."""
        if project_id and project_id not in self._mock_projects:
            self._mock_projects.append(project_id)
        if project_id and project_id not in self._mock_project_sessions:
            self._mock_project_sessions[project_id] = []
        blob_path = f"projects/{project_id}/.keep"
        self.upload_bytes(b"", blob_path, content_type="text/plain")
        return self.get_gcs_uri(blob_path)

    def list_sessions(self, project_id: str = "default_project") -> list[str]:
        """Lists subfolders under projects/{project_id}/sessions/ in GCS."""
        sessions: set[str] = set(self._mock_project_sessions.get(project_id, []))
        if project_id == "default_project" and not sessions:
            sessions.update(["parody_session_1", "session_8492", "dripwarts_battle"])

        if not self.mock_mode and self._client and self.bucket_name:
            try:
                prefix = f"projects/{project_id}/sessions/"
                blobs = self._client.list_blobs(
                    self.bucket_name, prefix=prefix, delimiter="/", timeout=self.timeout
                )
                for page in blobs.pages:
                    for pfix in page.prefixes:
                        parts = pfix.rstrip("/").split("/")
                        if parts and parts[-1]:
                            sessions.add(parts[-1])
            except Exception as exc:
                logger.warning("list_sessions failed for project %s: %s", project_id, exc)

        return sorted(list(sessions))

    def create_session(self, session_id: str, project_id: str = "default_project") -> str:
        """Creates a new session directory under a project in GCS."""
        if project_id not in self._mock_projects:
            self._mock_projects.append(project_id)
        if project_id not in self._mock_project_sessions:
            self._mock_project_sessions[project_id] = []
        if session_id not in self._mock_project_sessions[project_id]:
            self._mock_project_sessions[project_id].append(session_id)
        blob_path = f"projects/{project_id}/sessions/{session_id}/.keep"
        self.upload_bytes(b"", blob_path, content_type="text/plain")
        return self.get_gcs_uri(blob_path)

    def list_project_characters(self, project_id: str = "default_project") -> list[dict[str, Any]]:
        """Lists character dicts from projects/{project_id}/saved_characters/ and legacy session subfolders."""
        characters: list[dict[str, Any]] = []
        seen_slugs: set[str] = set()

        if not self.mock_mode and self._bucket:
            try:
                prefix = f"projects/{project_id}/saved_characters/"
                blobs = self._bucket.list_blobs(prefix=prefix, timeout=self.timeout)
                json_blobs = [b for b in blobs if getattr(b, "name", "").endswith(".json")]
                for data in self._download_blobs_concurrently(json_blobs):
                    slug = self._slugify(str(data.get("name", "")))
                    if slug not in seen_slugs:
                        seen_slugs.add(slug)
                        characters.append(data)
            except Exception as exc:
                logger.warning("list_project_characters failed on prefix %s: %s", prefix, exc)

            try:
                prefix_sessions = f"projects/{project_id}/sessions/"
                blobs = self._bucket.list_blobs(prefix=prefix_sessions, timeout=self.timeout)
                json_blobs = [
                    b
                    for b in blobs
                    if "/characters/" in getattr(b, "name", "")
                    and getattr(b, "name", "").endswith(".json")
                ]
                for data in self._download_blobs_concurrently(json_blobs):
                    slug = self._slugify(str(data.get("name", "")))
                    if slug not in seen_slugs:
                        seen_slugs.add(slug)
                        characters.append(data)
            except Exception as exc:
                logger.warning(
                    "list_project_characters failed on session prefix %s: %s", prefix_sessions, exc
                )

        if characters:
            return characters

        if project_id in self._mock_project_characters:
            return self._mock_project_characters[project_id]

        if project_id == "default_project":
            return list(self._mock_characters.values())

        return []

    def list_project_products(self, project_id: str = "default_project") -> list[dict[str, Any]]:
        """Lists product dicts from projects/{project_id}/saved_products/."""
        products: list[dict[str, Any]] = []
        seen_slugs: set[str] = set()

        if not self.mock_mode and self._bucket:
            try:
                prefix = f"projects/{project_id}/saved_products/"
                blobs = self._bucket.list_blobs(prefix=prefix, timeout=self.timeout)
                for blob in blobs:
                    if blob.name.endswith(".json"):
                        try:
                            data = json.loads(blob.download_as_text(timeout=self.timeout))
                            if isinstance(data, dict):
                                slug = self._slugify(str(data.get("name", "")))
                                if slug not in seen_slugs:
                                    seen_slugs.add(slug)
                                    products.append(data)
                        except Exception as exc:
                            logger.warning("Failed to load product blob %s: %s", blob.name, exc)
            except Exception as exc:
                logger.warning("list_project_products failed on prefix %s: %s", prefix, exc)

        if products:
            return products

        return self._mock_project_products.get(project_id, [])

    def list_project_reference_sheets(
        self, project_id: str = "default_project"
    ) -> list[dict[str, Any]]:
        """Lists turnaround/reference sheet dicts from projects/{project_id}/saved_reference_sheets/."""
        sheets: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        if not self.mock_mode and self._bucket:
            try:
                prefix = f"projects/{project_id}/saved_reference_sheets/"
                blobs = self._bucket.list_blobs(prefix=prefix, timeout=self.timeout)
                for blob in blobs:
                    name = os.path.basename(blob.name)
                    if name and name not in seen_names:
                        seen_names.add(name)
                        sheets.append(
                            {
                                "name": name.removesuffix(".png").removesuffix(".jpg"),
                                "filename": name,
                                "url": self.get_public_url(blob.name),
                                "gcs_uri": self.get_gcs_uri(blob.name),
                            }
                        )
            except Exception as exc:
                logger.warning("list_project_reference_sheets failed on prefix %s: %s", prefix, exc)

        if sheets:
            return sheets

        return self._mock_project_reference_sheets.get(project_id, [])

    def list_characters(
        self,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Returns list of character dicts from library and session scope."""
        if not self.mock_mode and self._bucket:
            try:
                characters: list[dict[str, Any]] = []
                seen_slugs: set[str] = set()

                prefixes = ["library/characters/"]
                if session_id:
                    prefixes.append(f"sessions/{session_id}/characters/")

                for prefix in prefixes:
                    blobs = self._bucket.list_blobs(prefix=prefix, timeout=self.timeout)
                    json_blobs = [
                        b
                        for b in blobs
                        if getattr(b, "name", "").endswith(".json")
                        and not getattr(b, "name", "").endswith("roster.json")
                    ]
                    for data in self._download_blobs_concurrently(json_blobs):
                        slug = self._slugify(str(data.get("name", "")))
                        if slug not in seen_slugs:
                            seen_slugs.add(slug)
                            characters.append(data)
                            self._mock_characters[slug] = data
                if characters:
                    return characters
            except Exception as exc:
                logger.warning("list_characters failed: %s", exc)

        return list(self._mock_characters.values())

    def load_character(
        self,
        slug: str,
        session_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Fetches character dict for a given slug from session scope, library scope, or mock cache."""
        clean_slug = self._slugify(slug)

        paths_to_try: list[str] = []
        if session_id:
            paths_to_try.append(f"sessions/{session_id}/characters/{clean_slug}.json")
        paths_to_try.append(f"library/characters/{clean_slug}.json")

        for blob_path in paths_to_try:
            data = self._download_json_payload(
                blob_path,
                mock_cache_dict=self._mock_characters,
                mock_cache_key=clean_slug,
            )
            if isinstance(data, dict):
                return data

        if slug in self._mock_characters:
            return self._mock_characters[slug]
        if clean_slug in self._mock_characters:
            return self._mock_characters[clean_slug]

        for key, char in self._mock_characters.items():
            if (
                key == clean_slug
                or key.startswith(f"{clean_slug}_")
                or self._slugify(str(char.get("name", ""))) == clean_slug
            ):
                return char

        return None

    def save_session_roster(
        self,
        session_id: str,
        characters: list[dict[str, Any]],
    ) -> tuple[str, str]:
        """Saves session cast roster to sessions/{session_id}/characters/roster.json."""
        blob_path = f"sessions/{session_id}/characters/roster.json"
        return self._upload_json_payload(
            blob_path,
            characters,
            mock_cache_dict=self._mock_rosters,
            mock_cache_key=session_id,
        )

    def load_session_roster(
        self,
        session_id: str,
    ) -> list[dict[str, Any]] | None:
        """Loads session cast roster JSON for a given session ID."""
        blob_path = f"sessions/{session_id}/characters/roster.json"
        data = self._download_json_payload(
            blob_path,
            mock_cache_dict=self._mock_rosters,
            mock_cache_key=session_id,
        )
        if isinstance(data, list):
            return data

        return self._mock_rosters.get(session_id)

    def list_session_ids(self) -> list[str]:
        """Returns list of session IDs found in storage, sorted with the most recently created/updated sessions first."""
        default_sessions = ["parody_session_1", "session_8492", "dripwarts_battle"]
        if self.mock_mode or not self._bucket or not self._client:
            return default_sessions

        try:
            blobs_iter = self._client.list_blobs(
                self.bucket_name, prefix="sessions/", page_size=100, timeout=self.timeout
            )
            session_latest: dict[str, Any] = {}
            for b in blobs_iter:
                parts = b.name.removeprefix("sessions/").split("/")
                if parts and parts[0]:
                    sid = parts[0]
                    updated = getattr(b, "updated", None)
                    if sid not in session_latest or (
                        updated and session_latest[sid] and updated > session_latest[sid]
                    ):
                        session_latest[sid] = updated
                    elif sid not in session_latest:
                        session_latest[sid] = updated

            if session_latest:
                sorted_sessions = sorted(
                    session_latest.keys(),
                    key=lambda k: session_latest[k] if session_latest[k] is not None else "",
                    reverse=True,
                )
                return sorted_sessions
            return default_sessions
        except Exception as exc:
            logger.warning("list_session_ids failed: %s", exc)
            return default_sessions

    def _extract_storyboard_metadata(
        self, data: dict[str, Any], fallback_slug: str = ""
    ) -> dict[str, Any]:
        """Extracts standard storyboard metadata dictionary from a storyboard payload."""
        scenes = data.get("scenes", [])
        shot_count = len(scenes) if isinstance(scenes, list) else 0
        name = str(data.get("name") or "")
        slug = str(data.get("slug") or fallback_slug or self._slugify(name))
        concept = str(data.get("concept") or "")
        updated_at = str(data.get("updated_at") or "")
        return {
            "name": name,
            "slug": slug,
            "concept": concept,
            "shot_count": shot_count,
            "updated_at": updated_at,
        }

    def save_storyboard(
        self,
        name: str,
        storyboard_data: dict[str, Any],
        session_id: str | None = None,
    ) -> tuple[str, str]:
        """Persists a storyboard grid payload as JSON in GCS under library or session scope."""
        slug = self._slugify(name)
        if session_id is None:
            blob_path = f"library/storyboards/{slug}.json"
        else:
            blob_path = f"sessions/{session_id}/storyboards/{slug}.json"

        payload = dict(storyboard_data)
        payload["name"] = name
        payload["slug"] = slug
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()

        return self._upload_json_payload(
            blob_path,
            payload,
            mock_cache_dict=self._mock_storyboards,
            mock_cache_key=slug,
        )

    def list_storyboards(
        self,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Returns a list of storyboard metadata dicts from library and session scope."""
        if not self.mock_mode and self._bucket:
            try:
                storyboards: list[dict[str, Any]] = []
                seen_slugs: set[str] = set()

                prefixes: list[str] = []
                if session_id:
                    prefixes.append(f"sessions/{session_id}/storyboards/")
                prefixes.append("library/storyboards/")

                for prefix in prefixes:
                    blobs = self._bucket.list_blobs(prefix=prefix, timeout=self.timeout)
                    json_blobs = [b for b in blobs if getattr(b, "name", "").endswith(".json")]
                    for data in self._download_blobs_concurrently(json_blobs):
                        slug = str(data.get("slug", "") or self._slugify(str(data.get("name", ""))))
                        if slug and slug not in seen_slugs:
                            seen_slugs.add(slug)
                            meta = self._extract_storyboard_metadata(data, fallback_slug=slug)
                            storyboards.append(meta)
                            self._mock_storyboards[slug] = data
                if storyboards:
                    return storyboards
            except Exception as exc:
                logger.warning("list_storyboards failed: %s", exc)

        return [
            self._extract_storyboard_metadata(data, fallback_slug=slug)
            for slug, data in self._mock_storyboards.items()
        ]

    def load_storyboard(
        self,
        slug: str,
        session_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Loads a storyboard payload by slug from session scope, library scope, or mock cache."""
        clean_slug = self._slugify(slug)

        paths_to_try: list[str] = []
        if session_id:
            paths_to_try.append(f"sessions/{session_id}/storyboards/{clean_slug}.json")
        paths_to_try.append(f"library/storyboards/{clean_slug}.json")

        for blob_path in paths_to_try:
            data = self._download_json_payload(
                blob_path,
                mock_cache_dict=self._mock_storyboards,
                mock_cache_key=clean_slug,
            )
            if isinstance(data, dict):
                return data

        if slug in self._mock_storyboards:
            return self._mock_storyboards[slug]
        if clean_slug in self._mock_storyboards:
            return self._mock_storyboards[clean_slug]

        for key, sb in self._mock_storyboards.items():
            if key == clean_slug or self._slugify(str(sb.get("name", ""))) == clean_slug:
                return sb

        return None

    def delete_storyboard(
        self,
        slug: str,
        session_id: str | None = None,
    ) -> bool:
        """Deletes a storyboard payload from GCS and removes it from mock cache."""
        clean_slug = self._slugify(slug)
        deleted = False

        if not self.mock_mode and self._bucket:
            try:
                paths_to_try: list[str] = []
                if session_id:
                    paths_to_try.append(f"sessions/{session_id}/storyboards/{clean_slug}.json")
                paths_to_try.append(f"library/storyboards/{clean_slug}.json")

                for blob_path in paths_to_try:
                    blob = self._bucket.blob(blob_path)
                    if blob.exists(timeout=self.timeout):
                        blob.delete(timeout=self.timeout)
                        deleted = True
                        break
            except Exception as exc:
                logger.warning("delete_storyboard failed for %s: %s", clean_slug, exc)

        deleted_from_mock = False
        if slug in self._mock_storyboards:
            del self._mock_storyboards[slug]
            deleted_from_mock = True
        elif clean_slug in self._mock_storyboards:
            del self._mock_storyboards[clean_slug]
            deleted_from_mock = True
        else:
            for key in list(self._mock_storyboards.keys()):
                sb = self._mock_storyboards[key]
                if key == clean_slug or self._slugify(str(sb.get("name", ""))) == clean_slug:
                    del self._mock_storyboards[key]
                    deleted_from_mock = True
                    break

        return deleted or deleted_from_mock


# Alias for backward compatibility and convenience
GCSStorage = GcsStorageManager
