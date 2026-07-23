from __future__ import annotations

import json
import logging
import math
import os
import re
from dataclasses import dataclass
from typing import Any

from omnimash.config import settings
from omnimash.prompts.compiler import CharacterRole, sanitize_real_names

logger = logging.getLogger(__name__)


def parse_timecoded_script(script_text: str) -> list[tuple[float, str]]:
    """Parses timecode intervals like [0-3s], [3-6s], [6-10s], [0-5.5s] or [0-3] from screenplay text.

    Returns a list of tuples containing (duration_in_seconds, action_text).
    """
    if not script_text or not script_text.strip():
        return []

    pattern = r"\[\s*(\d+(?:\.\d+)?)\s*s?\s*-\s*(\d+(?:\.\d+)?)\s*s?\s*\]"
    matches = list(re.finditer(pattern, script_text))
    if not matches:
        return []

    results: list[tuple[float, str]] = []
    for i, m in enumerate(matches):
        start_t = float(m.group(1))
        end_t = float(m.group(2))
        duration = max(0.0, round(end_t - start_t, 2))
        text_start = m.end()
        text_end = matches[i + 1].start() if i + 1 < len(matches) else len(script_text)
        action_text = script_text[text_start:text_end].strip()
        results.append((duration, action_text))

    return results


def _format_character_references(
    text: str, characters: list[CharacterRole] | None
) -> str:
    """Ensures character roles are referenced as Role A (Name) in directives."""
    if not text or not characters:
        return text

    res = text
    for char in characters:
        role_ref = f"{char.role_id} ({char.name})" if char.name else char.role_id
        if role_ref in res:
            continue
        if char.name and char.name in res:
            res = re.sub(rf"\b{re.escape(char.name)}\b", role_ref, res)
        elif char.role_id in res and role_ref not in res:
            res = re.sub(rf"\b{re.escape(char.role_id)}\b(?! \()", role_ref, res)

    return res


@dataclass
class StoryboardShot:
    shot_index: int
    duration_seconds: float
    action: str
    location: str
    style_lighting: str
    framing_motion: str
    audio: str
    summary: str = ""

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
        self,
        concept: str,
        style_tone: str,
        target_duration: float,
        characters: list[CharacterRole] | None = None,
    ) -> list[StoryboardShot]:
        num_shots = max(3, min(6, int(math.ceil(target_duration / 10.0))))
        per_shot_dur = min(10.0, round(target_duration / num_shots, 1))

        char_refs = (
            [f"{c.role_id} ({c.name})" if c.name else c.role_id for c in characters]
            if characters
            else []
        )

        mock_templates = [
            (
                "Entrance & Setup",
                f"Establishing shot for concept: '{concept}'. {char_refs[0] if char_refs else 'Key characters'} enter the scene.",
                "A dimly lit stone dungeon classroom with bubbling cauldrons and soft ambient smoke",
                f"{style_tone}, cinematic high-contrast lighting with warm shadows",
                "Static medium shot with subtle handheld drift",
                "Slow heavy 808 trap beat with bubbling liquid sound and quiet vinyl crackle",
            ),
            (
                "Dramatic Action & Potion Consumption",
                f"{char_refs[0] if char_refs else 'Key character'} performs the central dramatic action or consumes a potion, reacting in surprise.",
                "Gothic potion classroom with floating candles and glowing mystical symbols",
                f"{style_tone}, vibrant dramatic color grading and neon rim lights",
                "Dynamic dolly zoom in on character face",
                "Trap beat drop with sub-bass and crisp snare trills",
            ),
            (
                "Transformation Reveal & Aesthetic Drip",
                f"{char_refs[1] if len(char_refs) > 1 else (char_refs[0] if char_refs else 'Subject')} is transformed, stepping forward in upgraded aesthetic wardrobe with high confidence.",
                "High contrast Hogwarts courtyard with dramatic stage smoke and ambient flares",
                f"{style_tone}, polished commercial lighting and anamorphic lens flares",
                "Low angle pedestal shot moving upward slowly",
                "Aggressive 90s hip hop beat with heavy kick drum and vocal sample",
            ),
            (
                "Secondary Reaction & High-Energy Clash",
                f"{', '.join(char_refs) if char_refs else 'Secondary characters'} react in awe as the scene reaches high energy performance.",
                "Grand hall entrance with towering archways and laser fog reflections",
                f"{style_tone}, pulse-synced strobing spotlights and atmospheric beam flares",
                "Fast whip pan between subjects",
                "Blown-out 808 bass slides with rapid 16th-note trap hi-hats",
            ),
            (
                "Group Synchronized Pose & Motion",
                f"{', '.join(char_refs) if char_refs else 'Group'} dynamic shot with synchronized gestures and striking visual poses.",
                "Rain-slicked cobblestone alleyway lit by atmospheric green and purple lights",
                f"{style_tone}, wet asphalt reflections and sharp rim highlights",
                "Widescreen tracking shot following group motion",
                "Synthesizer arpeggios layering over heavy boom-bap rhythm",
            ),
            (
                "Climactic Freeze-Frame & Outro",
                f"{char_refs[0] if char_refs else 'Climactic'} resolution pose facing the camera directly as scene fades out.",
                "Spotlit center stage with receding back-lighting and lingering smoke effect",
                f"{style_tone}, golden hour backlight with volumetric rim light",
                "Slow push-in zoom settling into final freeze-frame pose",
                "Final booming kick drum hit with long reverb tail",
            ),
        ]

        shots: list[StoryboardShot] = []
        for i in range(num_shots):
            tmpl = mock_templates[i % len(mock_templates)]
            action = _format_character_references(tmpl[1], characters)
            summary = _format_character_references(tmpl[0], characters)
            shots.append(
                StoryboardShot(
                    shot_index=i + 1,
                    duration_seconds=per_shot_dur,
                    summary=sanitize_real_names(summary),
                    action=sanitize_real_names(action),
                    location=sanitize_real_names(tmpl[2]),
                    style_lighting=sanitize_real_names(tmpl[3]),
                    framing_motion=sanitize_real_names(tmpl[4]),
                    audio=sanitize_real_names(tmpl[5]),
                )
            )
        return shots

    def expand_vision(
        self,
        concept: str,
        style_tone: str = "Cinematic Trap Parody",
        target_duration: float = 30.0,
        characters: list[CharacterRole] | None = None,
        screenplay_script: str = "",
    ) -> list[StoryboardShot]:
        """Expands a vision concept into 3-6 distinct <=10s shot directives."""
        if screenplay_script and screenplay_script.strip():
            parsed_timecodes = parse_timecoded_script(screenplay_script)
            if parsed_timecodes:
                mock_templates = [
                    (
                        "Entrance & Setup",
                        "A dimly lit stone dungeon classroom with bubbling cauldrons and soft ambient smoke",
                        f"{style_tone}, cinematic high-contrast lighting with warm shadows",
                        "Static medium shot with subtle handheld drift",
                        "Slow heavy 808 trap beat with bubbling liquid sound and quiet vinyl crackle",
                    ),
                    (
                        "Dramatic Action",
                        "Gothic potion classroom with floating candles and glowing mystical symbols",
                        f"{style_tone}, vibrant dramatic color grading and neon rim lights",
                        "Dynamic dolly zoom in on character face",
                        "Trap beat drop with sub-bass and crisp snare trills",
                    ),
                    (
                        "Transformation Reveal",
                        "High contrast Hogwarts courtyard with dramatic stage smoke and ambient flares",
                        f"{style_tone}, polished commercial lighting and anamorphic lens flares",
                        "Low angle pedestal shot moving upward slowly",
                        "Aggressive 90s hip hop beat with heavy kick drum and vocal sample",
                    ),
                ]
                shots: list[StoryboardShot] = []
                for i, (duration, action_text) in enumerate(parsed_timecodes):
                    tmpl = mock_templates[i % len(mock_templates)]
                    formatted_action = _format_character_references(action_text, characters)
                    summary_text = action_text.splitlines()[0] if action_text else f"Shot {i + 1}"
                    formatted_summary = _format_character_references(summary_text, characters)

                    shots.append(
                        StoryboardShot(
                            shot_index=i + 1,
                            duration_seconds=duration,
                            summary=sanitize_real_names(formatted_summary),
                            action=sanitize_real_names(formatted_action),
                            location=sanitize_real_names(tmpl[1]),
                            style_lighting=sanitize_real_names(tmpl[2]),
                            framing_motion=sanitize_real_names(tmpl[3]),
                            audio=sanitize_real_names(tmpl[4]),
                        )
                    )
                return shots

        if self.mock_mode or not self._genai_client:
            return self._generate_mock_shots(
                concept, style_tone, target_duration, characters=characters
            )

        try:
            num_shots = max(3, min(6, int(math.ceil(target_duration / 10.0))))
            char_info = ""
            if characters:
                char_lines = [
                    f"- {c.role_id} ({c.name}): {c.description}" for c in characters
                ]
                char_info = (
                    "\nCharacters:\n"
                    + "\n".join(char_lines)
                    + "\nIncorporate these character role references (e.g. 'Role A (Name)') into the action directives.\n"
                )

            prompt = (
                f"Expand the following video concept into exactly {num_shots} storyboard shots for a {target_duration}s video.\n"
                f'Concept: "{concept}"\n'
                f'Style & Tone: "{style_tone}"\n'
                f"{char_info}\n"
                f"CRITICAL SAFETY RULE: Do NOT use real celebrity or public figure full names in the output JSON. Replace any real celebrity names with descriptive fictional parody visual roles (e.g., use 'Fiery Master Chef' instead of 'Gordon Ramsay', 'Atlanta Rap Legend' instead of 'Jeezy', 'Melodic Rap Star' instead of 'Drake').\n\n"
                f"Each shot MUST be <= 10.0 seconds in duration.\n"
                f"Return ONLY a JSON array of shot objects with schema:\n"
                f"[\n"
                f"  {{\n"
                f'    "shot_index": 1,\n'
                f'    "duration_seconds": 10.0,\n'
                f'    "summary": "One-line shot summary",\n'
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
                    raw_summary = str(item.get("summary", ""))
                    raw_action = str(item.get("action", ""))
                    formatted_summary = _format_character_references(raw_summary, characters)
                    formatted_action = _format_character_references(raw_action, characters)
                    shots.append(
                        StoryboardShot(
                            shot_index=int(item.get("shot_index", len(shots) + 1)),
                            duration_seconds=min(
                                10.0, float(item.get("duration_seconds", 10.0))
                            ),
                            summary=sanitize_real_names(formatted_summary),
                            action=sanitize_real_names(formatted_action),
                            location=sanitize_real_names(str(item.get("location", ""))),
                            style_lighting=sanitize_real_names(str(item.get("style_lighting", style_tone))),
                            framing_motion=sanitize_real_names(str(item.get("framing_motion", ""))),
                            audio=sanitize_real_names(str(item.get("audio", ""))),
                        )
                    )
                return shots
        except Exception as exc:
            logger.warning("Live expand_vision failed, falling back to mock: %s", exc)

        return self._generate_mock_shots(
            concept, style_tone, target_duration, characters=characters
        )

