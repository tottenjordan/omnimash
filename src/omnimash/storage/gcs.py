from __future__ import annotations

import dataclasses
import json
import os
from typing import TYPE_CHECKING, Any

from omnimash.config import settings

if TYPE_CHECKING:
    from omnimash.ingestion.media_extractor import ReferenceAnalysisReport

try:
    from google.cloud import storage
except ImportError:
    storage: Any = None


class GcsStorageManager:
    """Manages persistent cloud storage for session-scoped video, audio, prompt, and reference artifacts."""

    def __init__(
        self,
        bucket_name: str | None = None,
        project_id: str | None = None,
        mock_mode: bool | None = None,
    ):
        self.mock_mode = settings.mock_mode if mock_mode is None else mock_mode
        self.project_id = project_id or settings.google_cloud_project
        self.bucket_name = bucket_name or settings.gcs_bucket_name
        self._client: Any = None
        self._bucket: Any = None
        self._mock_analyses: dict[str, dict[str, Any]] = {}

        if not self.mock_mode and storage:
            try:
                self._client = storage.Client(project=self.project_id)
                self.ensure_bucket_exists()
            except Exception:
                pass

    def ensure_bucket_exists(self, location: str | None = None) -> bool:
        """Verifies or programmatically creates the GCS bucket in the configured GCP project."""
        if self.mock_mode or not self._client:
            return True
        try:
            loc = location or settings.google_cloud_region or "us-central1"
            bucket = self._client.lookup_bucket(self.bucket_name)
            if not bucket:
                self._bucket = self._client.create_bucket(
                    self.bucket_name, location=loc
                )
            else:
                self._bucket = bucket
            return True
        except Exception:
            return False

    def get_public_url(self, blob_name: str) -> str:
        """Returns the public HTTPS URL for a given GCS blob name."""
        clean_blob = blob_name.lstrip("/")
        return f"https://storage.googleapis.com/{self.bucket_name}/{clean_blob}"

    def get_gcs_uri(self, blob_name: str) -> str:
        """Returns the gs:// URI for a given GCS blob name."""
        clean_blob = blob_name.lstrip("/")
        return f"gs://{self.bucket_name}/{clean_blob}"

    def build_session_blob_path(
        self,
        session_id: str | None,
        category: str,
        filename: str,
    ) -> str:
        """Constructs a hierarchical session-scoped blob path: sessions/{session_id}/{category}/{filename}."""
        sid = session_id or "global"
        clean_cat = category.strip("/")
        clean_file = os.path.basename(filename)
        return f"sessions/{sid}/{clean_cat}/{clean_file}"

    def upload_file(
        self,
        local_path: str,
        destination_blob_name: str | None = None,
        session_id: str | None = None,
        category: str = "intermediate",
        content_type: str | None = None,
    ) -> str:
        """Uploads a local media artifact to GCS under its session subfolder."""
        if not destination_blob_name:
            basename = os.path.basename(local_path)
            destination_blob_name = self.build_session_blob_path(
                session_id=session_id,
                category=category,
                filename=basename,
            )

        destination_blob_name = destination_blob_name.lstrip("/")

        if self.mock_mode or not self._bucket:
            return self.get_public_url(destination_blob_name)

        try:
            if not content_type:
                if local_path.endswith(".mp4"):
                    content_type = "video/mp4"
                elif local_path.endswith(".wav"):
                    content_type = "audio/wav"
                elif local_path.endswith(".jpg") or local_path.endswith(".jpeg"):
                    content_type = "image/jpeg"
                elif local_path.endswith(".png"):
                    content_type = "image/png"
                elif local_path.endswith(".json"):
                    content_type = "application/json"

            blob = self._bucket.blob(destination_blob_name)
            blob.upload_from_filename(local_path, content_type=content_type)
            return self.get_public_url(destination_blob_name)
        except Exception:
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
            blob.upload_from_string(data, content_type=content_type)
            return self.get_public_url(destination_blob_name)
        except Exception:
            return self.get_public_url(destination_blob_name)

    def save_session_prompt(
        self,
        session_id: str,
        turn_index: int,
        prompt_data: dict[str, Any] | str,
    ) -> str:
        """Persists compiled prompts (5-part Anchor/Inject or 2-part Lock/Isolate) to sessions/{session_id}/prompts/."""
        filename = f"turn_{turn_index}_prompt.json"
        blob_path = self.build_session_blob_path(session_id, "prompts", filename)
        content = (
            json.dumps(prompt_data, indent=2)
            if isinstance(prompt_data, dict)
            else json.dumps({"prompt": prompt_data}, indent=2)
        )
        return self.upload_bytes(
            content.encode("utf-8"), blob_path, content_type="application/json"
        )

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

        self._mock_analyses[session_id] = report_dict

        filename = "reference_analysis.json"
        blob_path = self.build_session_blob_path(session_id, "references", filename)
        content = json.dumps(report_dict, indent=2)
        return self.upload_bytes(
            content.encode("utf-8"), blob_path, content_type="application/json"
        )

    def get_reference_analysis(self, session_id: str) -> dict[str, Any] | None:
        """Retrieves reference video acoustic and visual analysis metadata for a session."""
        if session_id in self._mock_analyses:
            return self._mock_analyses[session_id]

        if not self.mock_mode and self._bucket:
            try:
                blob_path = self.build_session_blob_path(
                    session_id, "references", "reference_analysis.json"
                ).lstrip("/")
                blob = self._bucket.blob(blob_path)
                if blob.exists():
                    data = blob.download_as_text()
                    res: dict[str, Any] = json.loads(data)
                    self._mock_analyses[session_id] = res
                    return res
            except Exception:
                pass

        return None
