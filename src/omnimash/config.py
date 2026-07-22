from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OmniMashSettings(BaseSettings):
    """Centralized, type-safe application settings loaded automatically from environment and .env."""

    google_cloud_project: str = "hybrid-vertex"
    gcp_region: str = "us-central1"
    google_cloud_region: str = "us-central1"
    google_cloud_location: str = "global"
    gemini_location: str = "global"
    omnimash_gcs_bucket: str | None = None
    google_api_key: str | None = None
    gemini_api_key: str | None = None
    model_armor_template_id: str = "omnimash-safety-filter"
    # Read-only reference buckets the media proxy may serve in addition to the
    # app's own bucket. Keeps the default character references loadable while
    # blocking arbitrary cross-bucket reads (see download_blob_bytes).
    allowed_read_buckets: list[str] = ["reference-images-jt-trend-trawler"]
    # Real generation is the default; opt into offline fakes with MOCK_MODE=true.
    mock_mode: bool = False
    port: int = 8080
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _require_real_credentials(self) -> "OmniMashSettings":
        """In real mode, fail fast on a broken config instead of serving fakes.

        Requires either an explicit API key or a GCP project (for Application
        Default Credentials + bucket derivation). Mock mode is unconstrained so
        offline dev/tests keep working. This does not touch guardrail behavior.
        """
        if self.mock_mode:
            return self
        has_api_key = bool(self.google_api_key or self.gemini_api_key)
        has_adc = bool(self.google_cloud_project)
        if not (has_api_key or has_adc):
            raise ValueError(
                "Real mode requires credentials: set GOOGLE_API_KEY / GEMINI_API_KEY, "
                "or GOOGLE_CLOUD_PROJECT for Application Default Credentials. "
                "Set MOCK_MODE=true for offline development."
            )
        return self

    @property
    def gcs_bucket_name(self) -> str:
        """Derives the GCS bucket name, defaulting dynamically to omnimash-media-{project_id}."""
        if self.omnimash_gcs_bucket:
            return self.omnimash_gcs_bucket
        return f"omnimash-media-{self.google_cloud_project}"


# Global settings singleton instance
settings = OmniMashSettings()
