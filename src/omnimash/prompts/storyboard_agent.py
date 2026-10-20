from __future__ import annotations

import concurrent.futures
import json
import logging
import math
import re
from dataclasses import asdict, dataclass
from typing import Any

from pydantic import BaseModel, Field, TypeAdapter

from omnimash.config import settings
from omnimash.prompts.character_roles import CharacterRole
from omnimash.prompts.genai_client import get_genai_client
from omnimash.prompts.parody import sanitize_real_names
from omnimash.prompts.screenplay import (
    parse_directors_notes,
    parse_timecoded_script,
    validate_prompt_input_lengths,
)

logger = logging.getLogger(__name__)

__all__ = [
    "StoryboardAgent",
    "StoryboardShot",
    "StoryboardShotSchema",
    "parse_directors_notes",
    "parse_timecoded_script",
]


def _format_character_references(text: str, characters: list[CharacterRole] | None) -> str:
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


def _ensure_continuous_shot(framing_motion: str) -> str:
    """Ensures framing and camera motion directives include continuous shot camera directives."""
    if not framing_motion or not framing_motion.strip():
        return "In a single continuous shot. No scene cuts. Medium cinematic tracking shot"
    if "in a single continuous shot. no scene cuts." in framing_motion.lower():
        return framing_motion
    if "in a single continuous shot" in framing_motion.lower():
        return framing_motion.replace(
            "In a single continuous shot", "In a single continuous shot. No scene cuts"
        ).replace("in a single continuous shot", "in a single continuous shot. No scene cuts")
    return f"In a single continuous shot. No scene cuts. {framing_motion}"


# Pydantic v2 schema for StoryboardShot validation and google-genai Structured Outputs
# Source: https://ai.google.dev/gemini-api/docs/structured-output?lang=python
# Source: https://docs.pydantic.dev/latest/concepts/type_adapter/
class StoryboardShotSchema(BaseModel):
    shot_index: int = Field(default=1)
    duration_seconds: float = Field(default=10.0)
    action: str = Field(default="")
    location: str = Field(default="")
    style_lighting: str = Field(default="")
    framing_motion: str = Field(default="")
    audio: str = Field(default="")
    summary: str = Field(default="")
    dialogue: str = Field(default="")
    start_seconds: float = Field(default=0.0)
    end_seconds: float | None = Field(default=None)
    narrative_stage: str = Field(default="Rising Action")
    preceding_context: str = Field(default="")
    camera_transition: str = Field(default="Continuous match cut")
    character_continuity: str = Field(
        default="Maintain subject outfit, posture, and facial expression from preceding shot"
    )
    audio_mode: str = Field(default="global")
    soundscape: str | None = Field(default=None)


_STORYBOARD_SHOT_LIST_ADAPTER: TypeAdapter[list[StoryboardShotSchema]] = TypeAdapter(
    list[StoryboardShotSchema]
)


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
    dialogue: str = ""
    start_seconds: float = 0.0
    end_seconds: float | None = None
    narrative_stage: str = "Rising Action"
    preceding_context: str = ""
    camera_transition: str = "Continuous match cut"
    character_continuity: str = (
        "Maintain subject outfit, posture, and facial expression from preceding shot"
    )
    audio_mode: str = "global"
    soundscape: str | None = None

    def to_dict(self) -> dict[str, Any]:
        # Python 3.12 dataclasses.asdict converts dataclass fields cleanly
        # Source: https://docs.python.org/3.12/library/dataclasses.html#dataclasses.asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoryboardShot:
        validated = StoryboardShotSchema.model_validate(data)
        return cls(**validated.model_dump())

    def to_omni_flash_prompt(self, role_mappings: str = "") -> str:
        prompt_parts: list[str] = []
        if role_mappings and role_mappings.strip():
            prompt_parts.append(role_mappings.strip())

        start_t = int(self.start_seconds)
        end_t = (
            int(round(self.end_seconds))
            if self.end_seconds is not None
            else int(round(self.duration_seconds))
        )
        parts = [
            f"[SHOT DIRECTIVE: Shot {self.shot_index} ({start_t}-{end_t}s)]",
            f"- Action / Subject: {self.action}",
            f"- Location: {self.location}",
            f"- Style & Lighting: {self.style_lighting}",
            f"- Shot Framing & Motion: {self.framing_motion}",
            f"- Audio Soundscape: {self.audio}",
        ]
        if self.dialogue and self.dialogue.strip():
            parts.append(f'- Dialogue / Text Overlay: "{self.dialogue.strip()}"')

        if self.shot_index > 1 or (self.preceding_context and self.preceding_context.strip()):
            parts.append(
                f"\n[SCENE CONTINUATION & VISUAL FLOW]\n"
                f"- Story Arc Phase: {self.narrative_stage}\n"
                f"- Preceding Shot Context: {self.preceding_context or 'Direct narrative continuation from previous scene'}\n"
                f"- Camera & Scene Transition: {self.camera_transition}\n"
                f"- Character Continuity: {self.character_continuity}"
            )

        directive = "\n".join(parts)
        prompt_parts.append(directive)
        return "\n\n".join(prompt_parts)


class StoryboardAgent:
    """Expands a 30-60s vision into 3-6 distinct <=10s shot cards adhering to DeepMind prompt guidelines."""

    def __init__(self, mock_mode: bool | None = None) -> None:
        from omnimash.config import settings

        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self._genai_client: Any = None
        if not self.mock_mode:
            self._init_genai_client()

    def _init_genai_client(self) -> None:
        self._genai_client = get_genai_client(
            location=getattr(settings, "gemini_location", "global")
        )

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
        cum_time = 0.0
        for i in range(num_shots):
            tmpl = mock_templates[i % len(mock_templates)]
            action = _format_character_references(tmpl[1], characters)
            summary = _format_character_references(tmpl[0], characters)
            location = _format_character_references(tmpl[2], characters)
            framing = _ensure_continuous_shot(tmpl[4])
            start_t = round(cum_time, 1)
            end_t = round(cum_time + per_shot_dur, 1)
            cum_time = end_t
            shots.append(
                StoryboardShot(
                    shot_index=i + 1,
                    duration_seconds=per_shot_dur,
                    start_seconds=start_t,
                    end_seconds=end_t,
                    summary=sanitize_real_names(summary),
                    action=sanitize_real_names(action),
                    location=sanitize_real_names(location),
                    style_lighting=sanitize_real_names(tmpl[3]),
                    framing_motion=sanitize_real_names(framing),
                    audio=sanitize_real_names(tmpl[5]),
                )
            )
        return shots

    def optimize_shot_prompt(
        self, raw_directive: str, style_tone: str = "Cinematic Trap Parody"
    ) -> str:
        """Optimizes a brief shot directive into a single concise, vivid cinematic visual prompt (max 40 words).

        In mock mode: returns an enriched prompt string combining style tone and directive with anamorphic lens flare
        and cinematic lighting signifiers.
        In live mode: calls Gemini SDK to expand the directive into a visual scene prompt.
        """
        if not raw_directive or not raw_directive.strip():
            return raw_directive

        if self.mock_mode or not self._genai_client:
            enriched = (
                f"{style_tone}: {raw_directive.strip()}. "
                "Cinematic high-contrast lighting with volumetric atmosphere and anamorphic lens flares."
            )
            return sanitize_real_names(enriched)

        try:
            system_instruction = (
                "You are an expert Hollywood cinematographer. "
                "Include explicit camera angles, cinematic lighting, and visual atmosphere "
                "(such as anamorphic lens flares and volumetric light). "
                "Output ONLY the final concise prompt (max 40 words) without commentary or quotes."
            )
            prompt = (
                "You are an expert Hollywood cinematographer. Expand the following brief shot directive into a single concise, vivid cinematic prompt (maximum 40 words) for AI video generation.\n"
                f'Style & Tone: "{style_tone}"\n'
                f'Shot Directive: "{raw_directive.strip()}"\n'
                "Include explicit camera angles, cinematic lighting, and visual atmosphere (such as anamorphic lens flares and volumetric light). Output ONLY the final concise prompt (max 40 words) without commentary or quotes."
            )
            from google.genai import types
            from omnimash.engine.omni_client import get_relaxed_safety_settings

            # Pass system_instruction and safety_settings via types.GenerateContentConfig
            # Source: https://googleapis.github.io/python-genai/genai.html#google.genai.types.GenerateContentConfig
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                safety_settings=get_relaxed_safety_settings(),
            )
            response = self._genai_client.models.generate_content(
                model=getattr(settings, "flash_model_id", "gemini-3.8-flash"),
                contents=prompt,
                config=config,
            )
            text = (getattr(response, "text", "") or "").strip()
            if (text.startswith('"') and text.endswith('"')) or (
                text.startswith("'") and text.endswith("'")
            ):
                text = text[1:-1].strip()
            if text:
                return sanitize_real_names(text)
        except Exception as exc:
            logger.warning("optimize_shot_prompt live call failed: %s", exc)

        enriched = (
            f"{style_tone}: {raw_directive.strip()}. "
            "Cinematic high-contrast lighting with volumetric atmosphere and anamorphic lens flares."
        )
        return sanitize_real_names(enriched)

    def _optimize_shots(self, shots: list[StoryboardShot], style_tone: str) -> None:
        """Optimizes action directives across storyboard shots, running concurrently when live."""

        def _optimize(s: StoryboardShot) -> None:
            s.action = self.optimize_shot_prompt(s.action, style_tone=style_tone)

        if len(shots) > 1 and not self.mock_mode and self._genai_client:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(shots))) as executor:
                list(executor.map(_optimize, shots))
        else:
            for s in shots:
                _optimize(s)

    def expand_vision(
        self,
        concept: str,
        style_tone: str = "Cinematic Trap Parody",
        target_duration: float = 30.0,
        characters: list[CharacterRole] | None = None,
        screenplay_script: str = "",
    ) -> list[StoryboardShot]:
        """Expands a vision concept into 3-6 distinct <=10s shot directives formatted in Gemini Omni Flash timing blocks."""
        validate_prompt_input_lengths(concept=concept, screenplay_script=screenplay_script)
        shots: list[StoryboardShot] = []
        from omnimash.prompts.compiler import PromptCompiler

        if screenplay_script and screenplay_script.strip():
            derived = (
                PromptCompiler(mock_mode=True).deconstruct_concept(concept) if concept else None
            )
            env_default = (
                derived.environment_tag
                if derived and getattr(derived, "environment_tag", None)
                else None
            ) or f"{concept} setting"
            lighting_default = (
                derived.camera_lighting_tag
                if derived and getattr(derived, "camera_lighting_tag", None)
                else None
            ) or f"{style_tone}, cinematic high-contrast lighting"
            framing_default = "Static medium shot with subtle handheld drift"
            audio_default = (
                derived.audio_beat if derived and getattr(derived, "audio_beat", None) else None
            ) or "Slow heavy 808 trap beat with sub-bass"
            parsed_timecodes = parse_timecoded_script(
                screenplay_script, default_duration=target_duration
            )
            if parsed_timecodes:
                mock_templates = [
                    (
                        "Entrance & Setup",
                        env_default,
                        lighting_default,
                        framing_default,
                        audio_default,
                    ),
                    (
                        "Dramatic Action",
                        env_default,
                        f"{lighting_default}, vibrant dramatic rim lights",
                        "Dynamic dolly zoom in on character face",
                        f"{audio_default} with crisp snare trills",
                    ),
                    (
                        "Transformation Reveal",
                        env_default,
                        f"{lighting_default}, polished anamorphic lens flares",
                        "Low angle pedestal shot moving upward slowly",
                        f"Aggressive beat: {audio_default}",
                    ),
                ]
                for i, item in enumerate(parsed_timecodes):
                    tmpl = mock_templates[i % len(mock_templates)]
                    duration = float(item.get("duration_seconds", 5.0))
                    start_sec = float(item.get("start_seconds", 0.0))
                    end_sec = float(item.get("end_seconds", start_sec + duration))
                    action_text = str(item.get("action", ""))
                    dialogue_text = str(item.get("dialogue", ""))
                    audio_text = str(item.get("audio", "")) or tmpl[4]
                    summary_text = str(item.get("summary", f"Shot {i + 1}"))

                    formatted_action = _format_character_references(action_text, characters)
                    formatted_dialogue = _format_character_references(dialogue_text, characters)
                    formatted_summary = _format_character_references(summary_text, characters)
                    formatted_location = _format_character_references(tmpl[1], characters)
                    formatted_audio = _format_character_references(audio_text, characters)

                    framing = _ensure_continuous_shot(tmpl[3])
                    preceding_ctx = shots[i - 1].summary or shots[i - 1].action if i > 0 else ""

                    shots.append(
                        StoryboardShot(
                            shot_index=i + 1,
                            duration_seconds=duration,
                            start_seconds=start_sec,
                            end_seconds=end_sec,
                            summary=sanitize_real_names(formatted_summary),
                            action=sanitize_real_names(formatted_action),
                            dialogue=sanitize_real_names(formatted_dialogue),
                            location=sanitize_real_names(formatted_location),
                            style_lighting=sanitize_real_names(tmpl[2]),
                            framing_motion=sanitize_real_names(framing),
                            audio=sanitize_real_names(formatted_audio),
                            preceding_context=sanitize_real_names(preceding_ctx),
                            camera_transition="Continuous match cut",
                            character_continuity="Maintain subject outfit, posture, and facial expression from preceding shot",
                        )
                    )
                self._optimize_shots(shots, style_tone=style_tone)
                return shots

        if self.mock_mode or not self._genai_client:
            shots = self._generate_mock_shots(
                concept, style_tone, target_duration, characters=characters
            )
            self._optimize_shots(shots, style_tone=style_tone)
            return shots

        try:
            num_shots = max(3, min(6, int(math.ceil(target_duration / 10.0))))
            char_info = ""
            if characters:
                char_lines = [f"- {c.role_id} ({c.name}): {c.description}" for c in characters]
                char_info = (
                    "\nCharacters:\n"
                    + "\n".join(char_lines)
                    + "\nIncorporate these character role references (e.g. 'Role A (Name)') into the action directives.\n"
                )

            system_instruction = (
                "You are an expert storyboard director for Gemini Omni Flash. "
                "CRITICAL SAFETY RULE: Do NOT use real celebrity or public figure full names in the output JSON. "
                "Replace any real celebrity names with descriptive fictional parody visual roles. "
                "Each shot MUST be <= 10.0 seconds in duration and structure framing with "
                "'In a single continuous shot. No scene cuts.'."
            )
            prompt = (
                f"Expand the following video concept into exactly {num_shots} storyboard shots for a {target_duration}s video formatted into Gemini Omni Flash timing blocks [X-Ys].\n"
                f'Concept: "{concept}"\n'
                f'Style & Tone: "{style_tone}"\n'
                f"{char_info}\n"
                f"CRITICAL SAFETY RULE: Do NOT use real celebrity or public figure full names in the output JSON. Replace any real celebrity names with descriptive fictional parody visual roles (e.g., use 'Fiery Master Chef' instead of 'Gordon Ramsay', 'Atlanta Rap Legend' instead of 'Jeezy', 'Melodic Rap Star' instead of 'Drake').\n\n"
                f"Each shot MUST be <= 10.0 seconds in duration.\n"
                f"Structure framing and camera movement directives with continuous shot camera instructions ('In a single continuous shot. No scene cuts.')."
            )
            from google.genai import types
            from omnimash.engine.omni_client import get_relaxed_safety_settings

            # Enforce Structured Outputs via response_schema=list[StoryboardShotSchema]
            # Source: https://ai.google.dev/gemini-api/docs/structured-output?lang=python
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=list[StoryboardShotSchema],
                safety_settings=get_relaxed_safety_settings(),
            )
            response = self._genai_client.models.generate_content(
                model=getattr(settings, "flash_model_id", "gemini-3.8-flash"),
                contents=prompt,
                config=config,
            )

            parsed_shots = getattr(response, "parsed", None)
            if isinstance(parsed_shots, list) and len(parsed_shots) > 0:
                validated_items = [
                    s
                    if isinstance(s, StoryboardShotSchema)
                    else StoryboardShotSchema.model_validate(s)
                    for s in parsed_shots
                ]
            else:
                raw_text = (getattr(response, "text", "") or "").strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()
                validated_items = _STORYBOARD_SHOT_LIST_ADAPTER.validate_python(
                    json.loads(raw_text)
                )

            if validated_items:
                shots = []
                for item_model in validated_items:
                    item = item_model.model_dump()
                    raw_summary = str(item.get("summary", ""))
                    raw_action = str(item.get("action", ""))
                    raw_location = str(item.get("location", ""))
                    raw_framing = _ensure_continuous_shot(str(item.get("framing_motion", "")))
                    formatted_summary = _format_character_references(raw_summary, characters)
                    formatted_action = _format_character_references(raw_action, characters)
                    formatted_location = _format_character_references(raw_location, characters)
                    dur = min(10.0, float(item.get("duration_seconds", 10.0)))
                    st_sec = float(item.get("start_seconds", 0.0))
                    end_sec = float(item.get("end_seconds", st_sec + dur))
                    shots.append(
                        StoryboardShot(
                            shot_index=int(item.get("shot_index", len(shots) + 1)),
                            duration_seconds=dur,
                            start_seconds=st_sec,
                            end_seconds=end_sec,
                            summary=sanitize_real_names(formatted_summary),
                            action=sanitize_real_names(formatted_action),
                            location=sanitize_real_names(formatted_location),
                            style_lighting=sanitize_real_names(
                                str(item.get("style_lighting", style_tone))
                            ),
                            framing_motion=sanitize_real_names(raw_framing),
                            audio=sanitize_real_names(str(item.get("audio", ""))),
                            narrative_stage=sanitize_real_names(
                                str(item.get("narrative_stage", "Rising Action"))
                            ),
                            preceding_context=sanitize_real_names(
                                str(item.get("preceding_context", ""))
                            ),
                            camera_transition=sanitize_real_names(
                                str(item.get("camera_transition", "Continuous match cut"))
                            ),
                            character_continuity=sanitize_real_names(
                                str(
                                    item.get(
                                        "character_continuity",
                                        "Maintain subject outfit, posture, and facial expression from preceding shot",
                                    )
                                )
                            ),
                            audio_mode=str(item.get("audio_mode", "global")),
                            soundscape=str(item.get("soundscape"))
                            if item.get("soundscape")
                            else None,
                        )
                    )
                self._optimize_shots(shots, style_tone=style_tone)
                return shots
        except Exception as exc:
            logger.warning("Live expand_vision failed, falling back to mock: %s", exc)

        shots = self._generate_mock_shots(
            concept, style_tone, target_duration, characters=characters
        )
        self._optimize_shots(shots, style_tone=style_tone)
        return shots
