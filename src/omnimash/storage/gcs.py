from __future__ import annotations

import dataclasses
import json
import os
import re
from typing import TYPE_CHECKING, Any

from omnimash.config import settings

if TYPE_CHECKING:
    from omnimash.ingestion.media_extractor import ReferenceAnalysisReport

try:
    from google.cloud import storage
except ImportError:
    storage: Any = None


DEFAULT_CHARACTERS: list[dict[str, Any]] = [
    {
        "role_id": "Role A",
        "name": 'Harry "Gucci"',
        "description": "Harry Potter, a young wizard with round gold wire-rim Cartier glasses, untidy jet-black hair, and distinct lightning scar wearing a red Gucci tracksuit",
        "reference_url": "gs://reference-images-jt-trend-trawler/harry_drip.jpeg",
        "aesthetic_tags": ["Red Gucci Tracksuit", "Cartier Glasses"],
        "voice_style": "Fast-paced confident Atlanta rap flow with autotune",
    },
    {
        "role_id": "Role B",
        "name": 'Young Draco "Jeezy"',
        "description": 'Young Draco "Jeezy", pale blonde rival wizard with slicked-back platinum hair, sharp sneering facial features, and tailored green velvet blazer',
        "reference_url": "gs://reference-images-jt-trend-trawler/draco.jpeg",
        "aesthetic_tags": ["Platinum Slicked Hair", "Diamond Iced-Out Chain"],
        "voice_style": "Pompous, cynical British drawl with aggressive rap cadence",
    },
    {
        "role_id": "Role A",
        "name": "Cyborg Gordon Ramsay",
        "description": "Cyborg Gordon Ramsay, a fiery celebrity chef with sharp blond hair, intense focused gaze, robotic eye implant, and chrome chef jacket",
        "reference_url": "gs://reference-images-jt-trend-trawler/gordon_ramsay.jpeg",
        "aesthetic_tags": [
            "Chrome Chef Jacket",
            "Bionic Eye Implant",
            "Cybernetic Kitchen Knife",
        ],
        "voice_style": "Aggressive British shouting with robotic vocoder undertones",
    },
    {
        "role_id": "Role B",
        "name": "Neon Julia Child",
        "description": "Neon Julia Child, legendary TV chef with towering frame, pearl necklace, vibrant neon French apron, and whisk",
        "reference_url": "gs://reference-images-jt-trend-trawler/julia_child.jpeg",
        "aesthetic_tags": ["Neon French Apron", "Pearl Necklace", "Glowing Whisk"],
        "voice_style": "Warbling, enthusiastic high-pitched mid-Atlantic accent with electronic delay",
    },
]


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
        self._mock_characters: dict[str, dict[str, Any]] = {
            self._slugify(c["name"]): dict(c) for c in DEFAULT_CHARACTERS
        }
        self._mock_rosters: dict[str, list[dict[str, Any]]] = {}

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
                self._bucket = self._client.create_bucket(self.bucket_name, location=loc)
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
        sid = self.sanitize_path_segment(session_id)
        clean_cat = self.sanitize_path_segment(category, default="misc")
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

    def download_blob_bytes(self, gs_uri: str) -> tuple[bytes, str]:
        """Downloads binary bytes and infers content_type from a GCS URI (gs://bucket/blob_path)."""
        if not isinstance(gs_uri, str) or not gs_uri.startswith("gs://"):
            return (b"", "image/jpeg")

        path = gs_uri[5:]
        parts = path.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return (b"", "image/jpeg")

        bucket_name, blob_path = parts[0], parts[1]

        if not self._is_bucket_allowed(bucket_name):
            # Reject cross-bucket reads: only the app bucket and explicitly
            # allow-listed reference buckets may be proxied. Empty bytes make the
            # media proxy return 404 without leaking which buckets exist.
            return (b"", "")

        if self.mock_mode:
            return (b"mock_image_bytes", "image/jpeg")

        if not self._client:
            return (b"", "image/jpeg")

        try:
            bucket = self._client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            data = blob.download_as_bytes()
            content_type = getattr(blob, "content_type", None)
            if not content_type:
                if blob_path.endswith(".mp4"):
                    content_type = "video/mp4"
                elif blob_path.endswith(".wav"):
                    content_type = "audio/wav"
                elif blob_path.endswith(".jpg") or blob_path.endswith(".jpeg"):
                    content_type = "image/jpeg"
                elif blob_path.endswith(".png"):
                    content_type = "image/png"
                elif blob_path.endswith(".json"):
                    content_type = "application/json"
                else:
                    content_type = "image/jpeg"
            return (data, content_type)
        except Exception:
            return (b"", "image/jpeg")

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
                    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
                    return (data, mime)
                except Exception:
                    pass

        if self.mock_mode:
            mime = "image/png" if str(gs_uri_or_path).lower().endswith(".png") else "image/jpeg"
            return (b"mock_image_bytes", mime)

        return (b"", "image/jpeg")

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

        if not self.mock_mode and self._bucket:
            try:
                local_path = source_rel_path
                if local_path.startswith("/static/"):
                    local_path = os.path.join(os.getcwd(), local_path.lstrip("/"))
                elif not os.path.isabs(local_path) and os.path.exists(
                    os.path.join(os.getcwd(), local_path)
                ):
                    local_path = os.path.join(os.getcwd(), local_path)

                if os.path.exists(local_path):
                    blob = self._bucket.blob(dest_blob_path)
                    blob.upload_from_filename(local_path, content_type="video/mp4")
                else:
                    src_blob_name = source_rel_path.replace(f"gs://{self.bucket_name}/", "").lstrip(
                        "/"
                    )
                    src_blob = self._bucket.blob(src_blob_name)
                    if src_blob.exists():
                        self._bucket.copy_blob(src_blob, self._bucket, dest_blob_path)
            except Exception:
                pass

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

    @staticmethod
    def sanitize_path_segment(value: str | None, *, default: str = "global") -> str:
        """Sanitize a single GCS key path segment: no traversal, no separators.

        Unlike :meth:`_slugify`, this preserves case, ``-`` and ``_`` so real
        identifiers (uuids, ``user:project`` -> ``user_project``) survive intact
        while ``../`` / leading-slash payloads can never escape their prefix.
        """
        if not value or not value.strip():
            return default
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", value.strip())
        cleaned = cleaned.strip("._-")  # kill leading/trailing dots and dashes
        return cleaned or default

    def _is_bucket_allowed(self, bucket_name: str) -> bool:
        """True if a bucket may be read via the proxy (app bucket + allow-list)."""
        allowed = {self.bucket_name, *settings.allowed_read_buckets}
        return bucket_name in allowed

    def save_character(
        self,
        character: dict[str, Any],
        session_id: str | None = None,
        is_library: bool = True,
    ) -> tuple[str, str]:
        """Persists character definitions as JSON in GCS under library or session scope."""
        name = str(character.get("name", "character"))
        slug = self._slugify(name)
        if is_library or session_id is None:
            blob_path = f"library/characters/{slug}.json"
        else:
            blob_path = f"sessions/{session_id}/characters/{slug}.json"

        content = json.dumps(character, indent=2)
        self.upload_bytes(
            content.encode("utf-8"),
            blob_path,
            content_type="application/json",
        )
        self._mock_characters[slug] = character
        return self.get_public_url(blob_path), self.get_gcs_uri(blob_path)

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
                    blobs = self._bucket.list_blobs(prefix=prefix)
                    for blob in blobs:
                        if blob.name.endswith(".json") and not blob.name.endswith("roster.json"):
                            try:
                                data = json.loads(blob.download_as_text())
                                if isinstance(data, dict):
                                    slug = self._slugify(str(data.get("name", "")))
                                    if slug not in seen_slugs:
                                        seen_slugs.add(slug)
                                        characters.append(data)
                                        self._mock_characters[slug] = data
                            except Exception:
                                pass
                if characters:
                    return characters
            except Exception:
                pass

        return list(self._mock_characters.values())

    def load_character(
        self,
        slug: str,
        session_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Fetches character dict for a given slug from session scope, library scope, or mock cache."""
        clean_slug = self._slugify(slug)

        if not self.mock_mode and self._bucket:
            try:
                paths_to_try: list[str] = []
                if session_id:
                    paths_to_try.append(f"sessions/{session_id}/characters/{clean_slug}.json")
                paths_to_try.append(f"library/characters/{clean_slug}.json")

                for blob_path in paths_to_try:
                    blob = self._bucket.blob(blob_path)
                    if blob.exists():
                        data = json.loads(blob.download_as_text())
                        if isinstance(data, dict):
                            self._mock_characters[clean_slug] = data
                            return data
            except Exception:
                pass

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
        content = json.dumps(characters, indent=2)
        self.upload_bytes(
            content.encode("utf-8"),
            blob_path,
            content_type="application/json",
        )
        self._mock_rosters[session_id] = characters
        return self.get_public_url(blob_path), self.get_gcs_uri(blob_path)

    def load_session_roster(
        self,
        session_id: str,
    ) -> list[dict[str, Any]] | None:
        """Loads session cast roster JSON for a given session ID."""
        if not self.mock_mode and self._bucket:
            try:
                blob_path = f"sessions/{session_id}/characters/roster.json"
                blob = self._bucket.blob(blob_path)
                if blob.exists():
                    data = json.loads(blob.download_as_text())
                    if isinstance(data, list):
                        self._mock_rosters[session_id] = data
                        return data
            except Exception:
                pass

        return self._mock_rosters.get(session_id)

    def list_session_ids(self) -> list[str]:
        """Returns list of session IDs found in storage or default mock session IDs."""
        default_sessions = ["parody_session_1", "session_8492", "dripwarts_battle"]
        if self.mock_mode or not self._bucket or not self._client:
            return default_sessions

        try:
            blobs = self._client.list_blobs(self.bucket_name, prefix="sessions/", delimiter="/")
            for _ in blobs:
                pass
            session_ids: list[str] = []
            prefixes = getattr(blobs, "prefixes", set())
            for prefix in prefixes:
                clean = prefix.removeprefix("sessions/").strip("/")
                if clean:
                    session_ids.append(clean)
            return session_ids if session_ids else default_sessions
        except Exception:
            return default_sessions
