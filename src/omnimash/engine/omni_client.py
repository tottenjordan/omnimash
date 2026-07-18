import uuid
from dataclasses import dataclass


@dataclass
class GenerationResult:
    interaction_thread_id: str
    video_url: str
    duration_seconds: int = 10
    synth_id_watermark: str = "SYNTHID_C2PA_VERIFIED"


class OmniFlashClient:
    def __init__(self, api_key: str | None = None, mock_mode: bool = True):
        self.api_key = api_key
        self.mock_mode = mock_mode

    def generate_clip(self, prompt: str) -> GenerationResult:
        if self.mock_mode:
            thread_id = f"thread_{uuid.uuid4().hex[:8]}"
            return GenerationResult(
                interaction_thread_id=thread_id,
                video_url=f"/static/rendered/{thread_id}_turn0.mp4",
            )
        raise NotImplementedError("Live API calls require active GCP credentials.")

    def apply_interaction_diff(
        self, interaction_thread_id: str, diff_prompt: str
    ) -> GenerationResult:
        if self.mock_mode:
            return GenerationResult(
                interaction_thread_id=interaction_thread_id,
                video_url=f"/static/rendered/{interaction_thread_id}_turn_diff.mp4",
            )
        raise NotImplementedError("Live API calls require active GCP credentials.")
