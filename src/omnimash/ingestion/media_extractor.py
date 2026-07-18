from dataclasses import dataclass, field


@dataclass
class ExtractedReference:
    is_valid: bool
    source_url: str | None = None
    keyframes: list[str] = field(default_factory=list)
    audio_track_path: str | None = None
    description: str | None = None


class MediaExtractor:
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode

    def process_youtube_url(self, url: str) -> ExtractedReference:
        if self.mock_mode:
            return ExtractedReference(
                is_valid=True,
                source_url=url,
                keyframes=["/tmp/mock_frame_1.jpg", "/tmp/mock_frame_2.jpg"],
                audio_track_path="/tmp/mock_audio_stem.mp3",
                description="Extracted 90s hip-hop beat and character portrait keyframes.",
            )
        return ExtractedReference(is_valid=True, source_url=url)
