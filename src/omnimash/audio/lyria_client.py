"""Lyria 3 instrumental score client via Gemini Interactions API (clip <=30s, pro >30s)."""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

from pydantic import BaseModel

from omnimash.audio.sub_bass_808 import write_mock_tone_wav
from omnimash.audio.tts_client import (
    build_audio_genai_clients,
    create_interaction_with_client_fallback,
    extract_interaction_audio_bytes,
)
from omnimash.config import settings

logger = logging.getLogger(__name__)


class LyriaScoreResult(BaseModel):
    """Structured result from LyriaClient instrumental score generation."""

    audio_path: str
    model_id: str
    duration_seconds: float
    prompt_used: str
    interaction_id: str | None = None
    mime_type: str = "audio/wav"


class LyriaClient:
    """Client for Lyria 3 music score generation with <=30s clip / >30s pro model routing."""

    def __init__(
        self,
        project_id: str | None = None,
        location: str | None = None,
        api_key: str | None = None,
        mock_mode: bool | None = None,
        genai_client: Any | None = None,
    ) -> None:
        self.project_id = project_id or getattr(settings, "google_cloud_project", "hybrid-vertex")
        self.location = (
            location
            or os.environ.get("GEMINI_LOCATION")
            or getattr(settings, "gemini_location", "global")
        )
        self.clip_model_id = getattr(settings, "lyria_clip_model_id", "lyria-3-clip-preview")
        self.pro_model_id = getattr(settings, "lyria_pro_model_id", "lyria-3-pro-preview")
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self._genai_client, self._dev_client, self._vertex_client = build_audio_genai_clients(
            project_id=self.project_id,
            location=self.location,
            api_key=api_key,
            genai_client=genai_client,
            mock_mode=self.mock_mode,
        )

    def select_model_id(self, duration_sec: float) -> str:
        """Selects lyria-3-clip-preview for <=30s cues and lyria-3-pro-preview for >30s scores."""
        if duration_sec <= 30.0:
            return self.clip_model_id
        return self.pro_model_id

    def generate_score(
        self,
        prompt: str,
        output_path: str,
        duration_sec: float = 30.0,
        model_id: str | None = None,
    ) -> LyriaScoreResult:
        """Generates a 48kHz stereo WAV underscore stem using Lyria 3 via Interactions API."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        selected_model = model_id or self.select_model_id(duration_sec)
        cleaned_prompt = (prompt or "").strip()

        if self.mock_mode:
            write_mock_tone_wav(
                output_path,
                duration_sec=duration_sec,
                freq_hz=73.42,
                amplitude=0.05,
            )
            return LyriaScoreResult(
                audio_path=output_path,
                model_id=selected_model,
                duration_seconds=duration_sec,
                prompt_used=cleaned_prompt,
                interaction_id="mock_lyria_interaction",
            )

        if self._genai_client is None or not hasattr(self._genai_client, "interactions"):
            raise RuntimeError("GenAI client with interactions API is not initialized for Lyria")

        kwargs: dict[str, Any] = {
            "model": selected_model,
            "input": cleaned_prompt,
            "response_format": {
                "type": "audio",
                "mime_type": "audio/wav",
            },
        }

        interaction, self._genai_client = create_interaction_with_client_fallback(
            active_client=self._genai_client,
            dev_client=self._dev_client,
            vertex_client=self._vertex_client,
            kwargs=kwargs,
        )

        raw_bytes = extract_interaction_audio_bytes(interaction, client=self._genai_client)
        raw_path = f"{output_path}.raw.audio"
        try:
            with open(raw_path, "wb") as f:
                f.write(raw_bytes)
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    raw_path,
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    output_path,
                ],
                check=True,
                capture_output=True,
                timeout=float(getattr(settings, "ffmpeg_timeout_seconds", 120.0)),
            )
        finally:
            if os.path.exists(raw_path):
                os.remove(raw_path)

        inter_id = getattr(interaction, "id", None) or getattr(interaction, "interaction_id", None)
        return LyriaScoreResult(
            audio_path=output_path,
            model_id=selected_model,
            duration_seconds=duration_sec,
            prompt_used=cleaned_prompt,
            interaction_id=inter_id,
        )
