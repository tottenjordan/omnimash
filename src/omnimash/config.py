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
    mock_mode: bool = True
    port: int = 8080
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def gcs_bucket_name(self) -> str:
        """Derives the GCS bucket name, defaulting dynamically to omnimash-media-{project_id}."""
        if self.omnimash_gcs_bucket:
            return self.omnimash_gcs_bucket
        return f"omnimash-media-{self.google_cloud_project}"


# Global settings singleton instance
settings = OmniMashSettings()
