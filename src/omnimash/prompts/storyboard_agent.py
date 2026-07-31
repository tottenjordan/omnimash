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


def parse_directors_notes(script_text: str) -> dict[str, str]:
    """Parses [DIRECTOR'S NOTES] block from screenplay text.

    Extracts keys like 'tone', 'relational_dynamic', and character profiles into a dictionary.
    """
    if not script_text or "[DIRECTOR'S NOTES]" not in script_text.upper():
        return {}

    notes: dict[str, str] = {}
    notes_match = re.search(
        r"\[\s*DIRECTOR['’]?S\s+NOTES\s*\]([\s\S]*?)(?=\[\s*\d|\Z)",
        script_text,
        re.IGNORECASE,
    )
    if not notes_match:
        return notes

    block = notes_match.group(1).strip()
    for line in block.splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if not line:
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key_clean = key.strip().lower().replace(" ", "_")
            notes[key_clean] = val.strip()

    notes["raw_notes"] = block
    return notes


def _slice_lines(lines: list[str], chunk_idx: int, num_chunks: int) -> list[str]:
    """Helper to slice or distribute lines across sequential shot chunks."""
    if not lines:
        return []
    if len(lines) <= num_chunks:
        if chunk_idx < len(lines):
            return [lines[chunk_idx]]
        return [lines[-1]]
    chunk_size = math.ceil(len(lines) / num_chunks)
    start = chunk_idx * chunk_size
    if start >= len(lines):
        return [lines[-1]]
    end = min(len(lines), start + chunk_size)
    return lines[start:end]


_RESERVED_KEYWORD_SET = {
    "ACTION",
    "DIALOGUE",
    "AUDIO",
    "SOUND",
    "MUSIC",
    "SOUND DESIGN",
    "BACKGROUND AUDIO",
    "AUDIO CUES",
    "CAMERA",
    "LOCATION",
    "LIGHTING",
    "STYLE",
    "NOTE",
    "NOTES",
    "DIRECTOR'S NOTES",
    "DIRECTORS NOTES",
    "VISUAL",
    "SHOT",
}


def _extract_character_dialogue(text: str) -> tuple[str, str | None]:
    """Extracts character dialogue from a line or action text if present.

    Returns (action_text, dialogue_text).
    If dialogue is found, action_text is the remaining action text before dialogue (or empty),
    and dialogue_text is 'Character Name: Dialogue...'.
    """
    if not text or not text.strip():
        return text.strip(), None

    stripped = text.strip()

    patterns = [
        re.compile(
            r"(?:^|(?<=[\.\?\!,;–—\-\:])\s+|\b(?i:DIALOGUE|ACTION):\s*|\s+)"
            r"([A-Z0-9][A-Za-z0-9_\-\']*(?:\s+[A-Z0-9\(][A-Za-z0-9_\-\)\']*){0,4})"
            r"(?:\s+says:?|:)\s*"
            r"([\"'].*[\"']|[^\n]+)$"
        ),
        re.compile(
            r"(?:^|(?<=[\.\?\!,;–—\-\:])\s+|\b(?i:DIALOGUE|ACTION):\s*)"
            r"([A-Za-z0-9_\s\-\(\)\']+?)"
            r"(?:\s+says:?|:)\s*"
            r"([\"'].*[\"']|[^\n]+)$"
        ),
    ]

    for pattern in patterns:
        for match in pattern.finditer(stripped):
            char_name = match.group(1).strip()
            if char_name.upper() not in _RESERVED_KEYWORD_SET and len(char_name) <= 60:
                start_pos = match.start(1)
                action_part = stripped[:start_pos].strip()
                action_part = re.sub(
                    r"^(?:ACTION|DIALOGUE):\s*", "", action_part, flags=re.IGNORECASE
                ).strip()
                action_part = re.sub(
                    r"\s*(?:ACTION|DIALOGUE):\s*$", "", action_part, flags=re.IGNORECASE
                ).strip()
                dialogue_part = f"{char_name}: {match.group(2).strip()}"
                return action_part, dialogue_part

    return stripped, None


def parse_timecoded_script(
    script_text: str, default_duration: float = 30.0
) -> list[dict[str, Any]]:
    """Parses timecode intervals like [0-3s], [3-6s] with optional ACTION:, DIALOGUE:, and AUDIO: blocks.

    If any script block duration exceeds 10.0s, or if no explicit timecodes exist in screenplay_script,
    automatically splits the screenplay into sequential <=10s shot directives ([0-10s], [10-20s], etc.).
    """
    if not script_text or not script_text.strip():
        return []

    pattern = r"\[\s*(\d+(?:\.\d+)?)\s*s?\s*-\s*(\d+(?:\.\d+)?)\s*s?\s*\]"
    matches = list(re.finditer(pattern, script_text))

    raw_blocks: list[dict[str, Any]] = []

    if matches:
        for i, m in enumerate(matches):
            start_t = float(m.group(1))
            end_t = float(m.group(2))
            text_start = m.end()
            text_end = matches[i + 1].start() if i + 1 < len(matches) else len(script_text)
            block = script_text[text_start:text_end].strip()
            raw_blocks.append({
                "start_t": start_t,
                "end_t": end_t,
                "block": block,
            })
    else:
        clean_text = re.sub(
            r"\[\s*DIRECTOR['’]?S\s+NOTES\s*\][\s\S]*?(?=\[\s*\d|\Z)",
            "",
            script_text,
            flags=re.IGNORECASE,
        ).strip()
        if clean_text:
            raw_blocks.append({
                "start_t": 0.0,
                "end_t": float(default_duration),
                "block": clean_text,
            })

    if not raw_blocks:
        return []

    results: list[dict[str, Any]] = []

    for raw in raw_blocks:
        start_t = raw["start_t"]
        end_t = raw["end_t"]
        block = raw["block"]
        total_duration = max(0.0, round(end_t - start_t, 2))

        action_lines: list[str] = []
        dialogue_lines: list[str] = []
        audio_lines: list[str] = []

        lines = block.splitlines()
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            line_upper = line_str.upper()
            if line_upper.startswith("ACTION:"):
                raw_act = line_str[7:].strip()
                act_part, diag_part = _extract_character_dialogue(raw_act)
                if act_part:
                    action_lines.append(act_part)
                if diag_part:
                    dialogue_lines.append(diag_part)
            elif line_upper.startswith("DIALOGUE:"):
                raw_diag = line_str[9:].strip()
                act_part, diag_part = _extract_character_dialogue(raw_diag)
                if diag_part:
                    if act_part:
                        action_lines.append(act_part)
                    dialogue_lines.append(diag_part)
                else:
                    dialogue_lines.append(raw_diag)
            elif line_upper.startswith(
                ("AUDIO:", "SOUND:", "SOUND DESIGN:", "BACKGROUND AUDIO:", "AUDIO CUES:", "MUSIC:")
            ):
                _, val = line_str.split(":", 1)
                audio_lines.append(val.strip())
            elif line_str.startswith('"') and line_str.endswith('"'):
                dialogue_lines.append(line_str.strip('"'))
            else:
                act_part, diag_part = _extract_character_dialogue(line_str)
                if diag_part:
                    if act_part:
                        action_lines.append(act_part)
                    dialogue_lines.append(diag_part)
                else:
                    inline_match = re.search(
                        r"(ACTION|DIALOGUE|AUDIO|SOUND|MUSIC):\s*", line_str, re.IGNORECASE
                    )
                    if inline_match:
                        sections = re.split(
                            r"(ACTION|DIALOGUE|AUDIO|SOUND|MUSIC):\s*",
                            line_str,
                            flags=re.IGNORECASE,
                        )
                        j = 1
                        while j < len(sections) - 1:
                            key = sections[j].upper()
                            val = sections[j + 1].strip()
                            if key == "ACTION":
                                val_act, val_diag = _extract_character_dialogue(val)
                                if val_act:
                                    action_lines.append(val_act)
                                if val_diag:
                                    dialogue_lines.append(val_diag)
                            elif key == "DIALOGUE":
                                dialogue_lines.append(val)
                            elif key in ("AUDIO", "SOUND", "MUSIC"):
                                audio_lines.append(val)
                            j += 2
                    else:
                        action_lines.append(line_str)

        if total_duration > 10.0:
            num_chunks = int(math.ceil(total_duration / 10.0))
            for k in range(num_chunks):
                chunk_start = round(start_t + k * 10.0, 2)
                chunk_end = round(min(end_t, chunk_start + 10.0), 2)
                chunk_dur = max(0.0, round(chunk_end - chunk_start, 2))
                start_str = f"{int(chunk_start) if chunk_start.is_integer() else chunk_start}"
                end_str = f"{int(chunk_end) if chunk_end.is_integer() else chunk_end}"
                tc_label = f"[{start_str}-{end_str}s]"

                chunk_action_lines = _slice_lines(action_lines, k, num_chunks)
                chunk_dialogue_lines = _slice_lines(dialogue_lines, k, num_chunks)
                chunk_audio_lines = _slice_lines(audio_lines, k, num_chunks)

                action_text = (
                    "\n".join(chunk_action_lines).strip()
                    if chunk_action_lines
                    else (block if not dialogue_lines and not audio_lines else "")
                )
                dialogue_text = "\n".join(chunk_dialogue_lines).strip()
                audio_text = "\n".join(chunk_audio_lines).strip()
                summary_text = (
                    chunk_action_lines[0]
                    if chunk_action_lines
                    else (
                        chunk_dialogue_lines[0]
                        if chunk_dialogue_lines
                        else (action_lines[0] if action_lines else f"Shot {len(results) + 1}")
                    )
                )

                results.append(
                    {
                        "timecode": tc_label,
                        "start_seconds": chunk_start,
                        "end_seconds": chunk_end,
                        "duration_seconds": chunk_dur,
                        "action": action_text,
                        "dialogue": dialogue_text,
                        "audio": audio_text,
                        "summary": summary_text,
                        "raw_text": block,
                    }
                )
        else:
            start_str = f"{int(start_t) if start_t.is_integer() else start_t}"
            end_str = f"{int(end_t) if end_t.is_integer() else end_t}"
            tc_label = f"[{start_str}-{end_str}s]"

            action_text = (
                "\n".join(action_lines).strip()
                if action_lines
                else (block if not dialogue_lines and not audio_lines else "")
            )
            dialogue_text = "\n".join(dialogue_lines).strip()
            audio_text = "\n".join(audio_lines).strip()
            summary_text = (
                action_lines[0]
                if action_lines
                else (
                    dialogue_lines[0]
                    if dialogue_lines
                    else (block.splitlines()[0] if block else f"Shot {len(results) + 1}")
                )
            )

            results.append(
                {
                    "timecode": tc_label,
                    "start_seconds": start_t,
                    "end_seconds": end_t,
                    "duration_seconds": total_duration,
                    "action": action_text,
                    "dialogue": dialogue_text,
                    "audio": audio_text,
                    "summary": summary_text,
                    "raw_text": block,
                }
            )

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


def _ensure_continuous_shot(framing_motion: str) -> str:
    """Ensures framing and camera motion directives include continuous shot camera directives."""
    if not framing_motion or not framing_motion.strip():
        return "In a single continuous shot. No scene cuts. Medium cinematic tracking shot"
    if "in a single continuous shot. no scene cuts." in framing_motion.lower():
        return framing_motion
    if "in a single continuous shot" in framing_motion.lower():
        return framing_motion.replace(
            "In a single continuous shot", "In a single continuous shot. No scene cuts"
        ).replace(
            "in a single continuous shot", "in a single continuous shot. No scene cuts"
        )
    return f"In a single continuous shot. No scene cuts. {framing_motion}"


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
    character_continuity: str = "Maintain subject outfit, posture, and facial expression from preceding shot"

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

        self.mock_mode = mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
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
            prompt = (
                "You are an expert Hollywood cinematographer. Expand the following brief shot directive into a single concise, vivid cinematic prompt (maximum 40 words) for AI video generation.\n"
                f'Style & Tone: "{style_tone}"\n'
                f'Shot Directive: "{raw_directive.strip()}"\n'
                "Include explicit camera angles, cinematic lighting, and visual atmosphere (such as anamorphic lens flares and volumetric light). Output ONLY the final concise prompt (max 40 words) without commentary or quotes."
            )
            from google.genai import types
            from omnimash.engine.omni_client import get_relaxed_safety_settings

            config = types.GenerateContentConfig(
                temperature=0.7,
                safety_settings=get_relaxed_safety_settings(),
            )
            response = self._genai_client.models.generate_content(
                model="gemini-2.5-flash",
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

    def expand_vision(
        self,
        concept: str,
        style_tone: str = "Cinematic Trap Parody",
        target_duration: float = 30.0,
        characters: list[CharacterRole] | None = None,
        screenplay_script: str = "",
    ) -> list[StoryboardShot]:
        """Expands a vision concept into 3-6 distinct <=10s shot directives formatted in Gemini Omni Flash timing blocks."""
        shots: list[StoryboardShot] = []
        if screenplay_script and screenplay_script.strip():
            parsed_timecodes = parse_timecoded_script(
                screenplay_script, default_duration=target_duration
            )
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
                    preceding_ctx = (
                        shots[i - 1].summary or shots[i - 1].action
                        if i > 0
                        else ""
                    )

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
                for shot in shots:
                    shot.action = self.optimize_shot_prompt(shot.action, style_tone=style_tone)
                return shots

        if self.mock_mode or not self._genai_client:
            shots = self._generate_mock_shots(
                concept, style_tone, target_duration, characters=characters
            )
            for shot in shots:
                shot.action = self.optimize_shot_prompt(shot.action, style_tone=style_tone)
            return shots

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
                f"Expand the following video concept into exactly {num_shots} storyboard shots for a {target_duration}s video formatted into Gemini Omni Flash timing blocks [X-Ys].\n"
                f'Concept: "{concept}"\n'
                f'Style & Tone: "{style_tone}"\n'
                f"{char_info}\n"
                f"CRITICAL SAFETY RULE: Do NOT use real celebrity or public figure full names in the output JSON. Replace any real celebrity names with descriptive fictional parody visual roles (e.g., use 'Fiery Master Chef' instead of 'Gordon Ramsay', 'Atlanta Rap Legend' instead of 'Jeezy', 'Melodic Rap Star' instead of 'Drake').\n\n"
                f"Each shot MUST be <= 10.0 seconds in duration.\n"
                f"Structure framing and camera movement directives with continuous shot camera instructions ('In a single continuous shot. No scene cuts.').\n"
                f"Return ONLY a JSON array of shot objects with schema:\n"
                f"[\n"
                f"  {{\n"
                f'    "shot_index": 1,\n'
                f'    "start_seconds": 0.0,\n'
                f'    "end_seconds": 10.0,\n'
                f'    "duration_seconds": 10.0,\n'
                f'    "summary": "One-line shot summary",\n'
                f'    "action": "Visual description of action/subject",\n'
                f'    "location": "Environment and location details",\n'
                f'    "style_lighting": "Aesthetic, color grading, and lighting",\n'
                f'    "framing_motion": "In a single continuous shot. No scene cuts. Camera angle, framing, and movement",\n'
                f'    "audio": "Sound design, music beat, and vocal cues",\n'
                f'    "narrative_stage": "Setup | Inciting Incident | Rising Action | Climax | Resolution",\n'
                f'    "preceding_context": "Recap of preceding shot action or setup",\n'
                f'    "camera_transition": "Transition instruction e.g. Match cut from previous shot",\n'
                f'    "character_continuity": "Costume/prop retention directive"\n'
                f"  }}\n"
                f"]"
            )
            try:
                from google.genai import types
                from omnimash.engine.omni_client import get_relaxed_safety_settings

                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                    safety_settings=get_relaxed_safety_settings(),
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
                shots = []
                for item in data:
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
                            style_lighting=sanitize_real_names(str(item.get("style_lighting", style_tone))),
                            framing_motion=sanitize_real_names(raw_framing),
                            audio=sanitize_real_names(str(item.get("audio", ""))),
                            narrative_stage=sanitize_real_names(str(item.get("narrative_stage", "Rising Action"))),
                            preceding_context=sanitize_real_names(str(item.get("preceding_context", ""))),
                            camera_transition=sanitize_real_names(str(item.get("camera_transition", "Continuous match cut"))),
                            character_continuity=sanitize_real_names(str(item.get("character_continuity", "Maintain subject outfit, posture, and facial expression from preceding shot"))),
                        )
                    )
                for shot in shots:
                    shot.action = self.optimize_shot_prompt(shot.action, style_tone=style_tone)
                return shots
        except Exception as exc:
            logger.warning("Live expand_vision failed, falling back to mock: %s", exc)

        shots = self._generate_mock_shots(
            concept, style_tone, target_duration, characters=characters
        )
        for shot in shots:
            shot.action = self.optimize_shot_prompt(shot.action, style_tone=style_tone)
        return shots


