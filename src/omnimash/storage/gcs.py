import os
from typing import Any
from omnimash.config import settings

try:
    from google.cloud import storage
except ImportError:
    storage: Any = None


class GcsStorageManager:
    """Manages persistent cloud storage for final and intermediate video, audio, and image artifacts."""

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

    def upload_file(
        self,
        local_path: str,
        destination_blob_name: str | None = None,
        content_type: str | None = None,
    ) -> str:
        """Uploads a local media artifact to GCS and returns the persistent HTTPS storage URL."""
        if not destination_blob_name:
            basename = os.path.basename(local_path)
            destination_blob_name = f"rendered/{basename}"

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
