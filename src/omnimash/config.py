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
    omni_model_id: str = "gemini-omni-1.1-flash-preview"
    pro_model_id: str = "gemini-4-argon"
    flash_model_id: str = "gemini-3.8-flash"
    image_model_id: str = "gemini-nano-banana-2.1"
    default_resolution: str = "720p"
    draft_resolution: str = "360p"
    studio_resolution: str = "1080p"
    master_resolution: str = "4k"
    model_armor_template_id: str = "omnimash-safety-filter"
    model_armor_fail_closed: bool = False
    model_armor_timeout: float = 5.0
    ffmpeg_timeout_seconds: float = 120.0
    mock_mode: bool = False
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

    @property
    def model_armor_location(self) -> str:
        """Model Armor is a regional service, defaulting to gcp_region (e.g. us-central1)."""
        return self.gcp_region

    @property
    def model_armor_template_name(self) -> str:
        """Returns the fully-qualified Model Armor template resource name:
        projects/{project}/locations/{location}/templates/{template}
        """
        if self.model_armor_template_id.startswith("projects/"):
            return self.model_armor_template_id
        return (
            f"projects/{self.google_cloud_project}/locations/{self.model_armor_location}/"
            f"templates/{self.model_armor_template_id}"
        )

    @property
    def model_armor_endpoint(self) -> str:
        """Returns the regional Model Armor API endpoint."""
        return f"modelarmor.{self.model_armor_location}.rep.googleapis.com"


# Global settings singleton instance
settings = OmniMashSettings()
