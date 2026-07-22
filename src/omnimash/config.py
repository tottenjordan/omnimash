from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OmniMashSettings(BaseSettings):
    """Centralized, type-safe application settings loaded automatically from environment and .env."""

    google_cloud_project: str = "hybrid-vertex"
    gcp_region: str = "us-central1"
    google_cloud_region: str = "us-central1"
    google_cloud_location: str = "global"
    gemini_location: str = "global"
    omnimash_gcs_bucket: str | None = None
    google_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    model_armor_template_id: str = "omnimash-safety-filter"
    # Read-only reference buckets the media proxy may serve in addition to the
    # app's own bucket. Keeps the default character references loadable while
    # blocking arbitrary cross-bucket reads (see download_blob_bytes).
    allowed_read_buckets: list[str] = ["reference-images-jt-trend-trawler"]
    # Real generation is the default; opt into offline fakes with MOCK_MODE=true.
    mock_mode: bool = False
    # Upper bound on in-memory sessions before LRU eviction kicks in. Bounds
    # memory for long-running processes; 0 disables eviction.
    max_sessions: int = 512
    port: int = 8080
    log_level: str = "INFO"

    # --- Video engine (Gemini Omni Flash) tuning -------------------------------
    # Sole video+audio model per CLAUDE.md; Veo is never permitted. Centralized
    # here so deployment/cost-sensitive values are tuned via env, not code edits.
    omni_model_id: str = "gemini-omni-flash-preview"
    omni_http_timeout_ms: int = 300000
    omni_max_retries: int = 3
    omni_retry_base_delay: float = 0.5
    # Upper bound on concurrent workers when generating independent clips in a
    # batch. Chained diff/commit edits stay strictly sequential regardless.
    clip_batch_max_workers: int = 4

    # Text-only LLMs used to deconstruct/optimize prompts (NOT video generation).
    # Two-tier fallback: a stronger Pro model first, then a faster Flash model.
    deconstruct_pro_model: str = "gemini-3.1-pro-preview"
    deconstruct_flash_model: str = "gemini-2.5-flash"

    # Wall-clock budget (seconds) for individual GCS upload/download/list calls,
    # so a stalled network op fails fast instead of hanging a worker.
    gcs_timeout: int = 60
    # Lifetime of V4 signed browser URLs for private-bucket objects (seconds).
    signed_url_ttl_seconds: int = 3600

    # --- ffmpeg render/stitch presets ------------------------------------------
    ffmpeg_timeout: int = 120
    ffmpeg_preset: str = "fast"
    ffmpeg_crf: int = 18
    ffmpeg_fps: int = 24
    ffmpeg_audio_bitrate: str = "192k"

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
        has_api_key = bool(self.effective_api_key)
        has_adc = bool(self.google_cloud_project)
        if not (has_api_key or has_adc):
            raise ValueError(
                "Real mode requires credentials: set GOOGLE_API_KEY / GEMINI_API_KEY, "
                "or GOOGLE_CLOUD_PROJECT for Application Default Credentials. "
                "Set MOCK_MODE=true for offline development."
            )
        return self

    @property
    def effective_api_key(self) -> str | None:
        """Return the first configured API key as a plain string, or ``None``.

        Prefers ``GEMINI_API_KEY`` over ``GOOGLE_API_KEY`` and unwraps the
        :class:`~pydantic.SecretStr` only at the point of use, so the raw value
        never lands in ``repr``/logs/tracebacks.
        """
        for key in (self.gemini_api_key, self.google_api_key):
            if key is not None:
                value = key.get_secret_value()
                if value:
                    return value
        return None

    @property
    def gcs_bucket_name(self) -> str:
        """Derives the GCS bucket name, defaulting dynamically to omnimash-media-{project_id}."""
        if self.omnimash_gcs_bucket:
            return self.omnimash_gcs_bucket
        return f"omnimash-media-{self.google_cloud_project}"


# Global settings singleton instance
settings = OmniMashSettings()
