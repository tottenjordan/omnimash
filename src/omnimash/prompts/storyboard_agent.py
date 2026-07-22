from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from typing import Any

from omnimash.config import settings

logger = logging.getLogger(__name__)


@dataclass
class StoryboardShot:
    shot_index: int
    duration_seconds: float
    action: str
    location: str
    style_lighting: str
    framing_motion: str
    audio: str

    def to_omni_flash_prompt(self, role_mappings: str = "") -> str:
        prompt_parts: list[str] = []
        if role_mappings and role_mappings.strip():
            prompt_parts.append(role_mappings.strip())

        shot_end = int(round(self.duration_seconds))
        directive = (
            f"[SHOT DIRECTIVE: Shot {self.shot_index} (0-{shot_end}s)]\n"
            f"- Action / Subject: {self.action}\n"
            f"- Location: {self.location}\n"
            f"- Style & Lighting: {self.style_lighting}\n"
            f"- Shot Framing & Motion: {self.framing_motion}\n"
            f"- Audio Soundscape: {self.audio}"
        )
        prompt_parts.append(directive)
        return "\n\n".join(prompt_parts)


class StoryboardAgent:
    """Expands a 30-60s vision into 3-6 distinct <=10s shot cards adhering to DeepMind prompt guidelines."""

    def __init__(self, mock_mode: bool = False) -> None:
        self.mock_mode = mock_mode
        self._genai_client: Any = None
        if not self.mock_mode:
            self._init_genai_client()

    def _init_genai_client(self) -> None:
        try:
            from google import genai

            api_key = (
                os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or getattr(settings, "gemini_api_key", None)
                or getattr(settings, "google_api_key", None)
            )
            project = os.environ.get(
                "GOOGLE_CLOUD_PROJECT",
                getattr(settings, "google_cloud_project", "hybrid-vertex"),
            )
            if api_key:
                self._genai_client = genai.Client(api_key=api_key)
            else:
                self._genai_client = genai.Client(
                    vertexai=True,
                    project=project,
                    location="us-central1",
                )
        except Exception as exc:
            logger.warning(
                "StoryboardAgent failed to initialize GenAI client: %s", exc
            )
            self._genai_client = None

    def _generate_mock_shots(
        self, concept: str, style_tone: str, target_duration: float
    ) -> list[StoryboardShot]:
        num_shots = max(3, min(6, int(math.ceil(target_duration / 10.0))))
        per_shot_dur = min(10.0, round(target_duration / num_shots, 1))

        mock_templates = [
            (
                f"Establishing shot for concept: '{concept}'. Key characters enter the scene.",
                "A dimly lit stone dungeon classroom with bubbling cauldrons and soft ambient smoke",
                f"{style_tone}, cinematic high-contrast lighting with warm shadows",
                "Static medium shot with subtle handheld drift",
                "Slow heavy 808 trap beat with bubbling liquid sound and quiet vinyl crackle",
            ),
            (
                "Key character performs the central dramatic action or consumes a potion, reacting in surprise.",
                "Gothic potion classroom with floating candles and glowing mystical symbols",
                f"{style_tone}, vibrant dramatic color grading and neon rim lights",
                "Dynamic dolly zoom in on character face",
                "Trap beat drop with sub-bass and crisp snare trills",
            ),
            (
                "Subject is transformed, stepping forward in upgraded aesthetic wardrobe with high confidence.",
                "High contrast Hogwarts courtyard with dramatic stage smoke and ambient flares",
                f"{style_tone}, polished commercial lighting and anamorphic lens flares",
                "Low angle pedestal shot moving upward slowly",
                "Aggressive 90s hip hop beat with heavy kick drum and vocal sample",
            ),
            (
                "Secondary characters react in awe as the scene reaches high energy performance.",
                "Grand hall entrance with towering archways and laser fog reflections",
                f"{style_tone}, pulse-synced strobing spotlights and atmospheric beam flares",
                "Fast whip pan between subjects",
                "Blown-out 808 bass slides with rapid 16th-note trap hi-hats",
            ),
            (
                "Group dynamic shot with synchronized gestures and striking visual poses.",
                "Rain-slicked cobblestone alleyway lit by atmospheric green and purple lights",
                f"{style_tone}, wet asphalt reflections and sharp rim highlights",
                "Widescreen tracking shot following group motion",
                "Synthesizer arpeggios layering over heavy boom-bap rhythm",
            ),
            (
                "Climactic resolution pose facing the camera directly as scene fades out.",
                "Spotlit center stage with receding back-lighting and lingering smoke effect",
                f"{style_tone}, golden hour backlight with volumetric rim light",
                "Slow push-in zoom settling into final freeze-frame pose",
                "Final booming kick drum hit with long reverb tail",
            ),
        ]

        shots: list[StoryboardShot] = []
        for i in range(num_shots):
            tmpl = mock_templates[i % len(mock_templates)]
            shots.append(
                StoryboardShot(
                    shot_index=i + 1,
                    duration_seconds=per_shot_dur,
                    action=tmpl[0],
                    location=tmpl[1],
                    style_lighting=tmpl[2],
                    framing_motion=tmpl[3],
                    audio=tmpl[4],
                )
            )
        return shots

    def expand_vision(
        self,
        concept: str,
        style_tone: str = "Cinematic Trap Parody",
        target_duration: float = 30.0,
    ) -> list[StoryboardShot]:
        """Expands a vision concept into 3-6 distinct <=10s shot directives."""
        if self.mock_mode or not self._genai_client:
            return self._generate_mock_shots(concept, style_tone, target_duration)

        try:
            num_shots = max(3, min(6, int(math.ceil(target_duration / 10.0))))
            prompt = (
                f"Expand the following video concept into exactly {num_shots} storyboard shots for a {target_duration}s video.\n"
                f'Concept: "{concept}"\n'
                f'Style & Tone: "{style_tone}"\n\n'
                f"Each shot MUST be <= 10.0 seconds in duration.\n"
                f"Return ONLY a JSON array of shot objects with schema:\n"
                f"[\n"
                f"  {{\n"
                f'    "shot_index": 1,\n'
                f'    "duration_seconds": 10.0,\n'
                f'    "action": "Visual description of action/subject",\n'
                f'    "location": "Environment and location details",\n'
                f'    "style_lighting": "Aesthetic, color grading, and lighting",\n'
                f'    "framing_motion": "Camera angle, framing, and movement",\n'
                f'    "audio": "Sound design, music beat, and vocal cues"\n'
                f"  }}\n"
                f"]"
            )
            try:
                from google.genai import types

                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                )
                response = self._genai_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=config,
                )
            except Exception:
                response = self._genai_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )

            raw_text = (getattr(response, "text", "") or "").strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            data = json.loads(raw_text)
            if isinstance(data, list) and len(data) > 0:
                shots: list[StoryboardShot] = []
                for item in data:
                    shots.append(
                        StoryboardShot(
                            shot_index=int(item.get("shot_index", len(shots) + 1)),
                            duration_seconds=min(
                                10.0, float(item.get("duration_seconds", 10.0))
                            ),
                            action=str(item.get("action", "")),
                            location=str(item.get("location", "")),
                            style_lighting=str(item.get("style_lighting", style_tone)),
                            framing_motion=str(item.get("framing_motion", "")),
                            audio=str(item.get("audio", "")),
                        )
                    )
                return shots
        except Exception as exc:
            logger.warning("Live expand_vision failed, falling back to mock: %s", exc)

        return self._generate_mock_shots(concept, style_tone, target_duration)
