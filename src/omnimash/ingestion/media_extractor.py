from dataclasses import dataclass, field
from omnimash.storage.gcs import GcsStorageManager


@dataclass
class ExtractedReference:
    is_valid: bool
    source_url: str | None = None
    keyframes: list[str] = field(default_factory=list)
    audio_track_path: str | None = None
    description: str | None = None
    gcs_uri: str | None = None


class MediaExtractor:
    def __init__(self, mock_mode: bool = True, bucket_name: str | None = None):
        self.mock_mode = mock_mode
        self.storage = GcsStorageManager(
            bucket_name=bucket_name, mock_mode=self.mock_mode
        )

    def process_youtube_url(self, url: str) -> ExtractedReference:
        if self.mock_mode:
            ref = ExtractedReference(
                is_valid=True,
                source_url=url,
                keyframes=["/tmp/mock_frame_1.jpg", "/tmp/mock_frame_2.jpg"],
                audio_track_path="/tmp/mock_audio_stem.mp3",
                description="Extracted 90s hip-hop beat and character portrait keyframes.",
                gcs_uri=self.storage.get_gcs_uri(
                    "references/mock_reference_bundle.tar"
                ),
            )
            return ref

        return ExtractedReference(
            is_valid=True,
            source_url=url,
            gcs_uri=self.storage.get_gcs_uri("references/live_reference.tar"),
        )
