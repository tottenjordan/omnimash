"""Data models and Pydantic schemas for prompt compilation and structured deconstruction."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from pydantic import BaseModel, Field

from omnimash.prompts.character_roles import CharacterRole


@dataclass
class CompiledPromptParts:
    subject_anchor: str
    aesthetic_injection: str
    environment: str
    camera_lighting: str
    motion: str
    audio_track: str
    voiceover: str = ""
    is_silent: bool = False
    on_screen_text: str = ""
    drip_props: list[str] = field(default_factory=list)
    vibe_intensity: int = 50
    character_references: list[str] = field(default_factory=list)
    timecode_blocks: list[str] = field(default_factory=list)
    input_roles: list[str] = field(default_factory=list)
    character_profiles: list[str] = field(default_factory=list)
    scene_instructions: list[str] = field(default_factory=list)

    def to_full_prompt(self) -> str:
        cam = self.camera_lighting.strip()
        cam_clean = re.sub(
            r"in a single continuous shot,\s*no scene cuts\.?",
            "In a single continuous shot. No scene cuts.",
            cam,
            flags=re.IGNORECASE,
        )
        if "in a single continuous shot. no scene cuts." not in cam_clean.lower():
            camera_header = f"In a single continuous shot. No scene cuts. {cam_clean}"
        else:
            camera_header = cam_clean

        # 1. ### INPUT ROLES
        input_roles_str = "\n".join(self.input_roles).strip() if self.input_roles else ""
        if not input_roles_str and self.character_references:
            input_roles_str = "\n".join(self.character_references).strip()
        if not input_roles_str:
            input_roles_str = "None."
        block_input = f"### INPUT ROLES\n{input_roles_str}"

        # 2. ### CHARACTER PROFILES
        char_profiles_str = (
            "\n".join(self.character_profiles).strip() if self.character_profiles else ""
        )
        if not char_profiles_str:
            char_profiles_str = "None."
        block_profiles = f"### CHARACTER PROFILES\n{char_profiles_str}"

        # 3. ### SCENE INSTRUCTIONS
        lower_audio = self.audio_track.lower().strip()
        if self.is_silent or lower_audio in ("none", "mute", "silent"):
            sound_desc = "Sound design: Silent video. No background music, no audio."
        else:
            audio_track_clean = self.audio_track.strip()
            if not audio_track_clean.lower().startswith("instrumental"):
                instr_audio = f"instrumental {audio_track_clean}"
            else:
                instr_audio = audio_track_clean

            if self.voiceover and self.voiceover.strip():
                sound_desc = (
                    f"Sound design: Foreground spoken voiceover/dialogue is dominant, crystal-clear, and front-of-mix. "
                    f"Background beat ({instr_audio}) is subtly ducked in the background beneath dialogue."
                )
            else:
                sound_desc = f"Sound design: {instr_audio}."

        scene_inst_parts = [
            f"Camera & Lighting: {camera_header}",
            f"Environment: {self.environment}",
            f"Audio: {sound_desc}",
        ]

        if self.voiceover and self.voiceover.strip():
            vo = self.voiceover.strip()
            if ":" in vo or "\n" in vo:
                scene_inst_parts.append(f"Dialogue between subjects: {vo}.")
            else:
                vo_clean = vo.rstrip(".")
                scene_inst_parts.append(f"Voiceover: {vo_clean}.")

        if self.on_screen_text and self.on_screen_text.strip():
            txt = self.on_screen_text.strip()
            scene_inst_parts.append(f"On-screen text: '{txt}' reading \"{txt}\"")

        if self.scene_instructions:
            scene_inst_parts.extend(self.scene_instructions)

        block_scene = "### SCENE INSTRUCTIONS\n" + "\n".join(scene_inst_parts)

        # 4. ### TIMELINE
        if self.timecode_blocks:
            blocks_str = "\n".join(self.timecode_blocks).strip()
        else:
            action_main = f"{self.subject_anchor}. {self.aesthetic_injection}. {self.environment}. {self.motion}."

            vocal_directive = ""
            if self.voiceover and self.voiceover.strip():
                vo = self.voiceover.strip()
                if "narrator" in vo.lower():
                    clean_vo = re.sub(
                        r"^(?:Narrator\s*(?:\(VO\))?:?\s*)[\"']?|[\"']?$",
                        "",
                        vo,
                        flags=re.IGNORECASE,
                    ).strip()
                    vocal_directive = f' Dialogue: Narrator (VO) says: "{clean_vo}".'
                elif ":" in vo or "\n" in vo:
                    vocal_directive = f" Dialogue between subjects: {vo}."
                else:
                    vo_clean = vo.rstrip(".")
                    vocal_directive = f" Voiceover: {vo_clean}."

            b1 = f"[0-3s] Action: {action_main} Audio: {sound_desc}.{vocal_directive}"
            b2 = f"[3-6s] Action: Continuation of {self.motion}. Audio: {sound_desc}."
            b3 = f"[6-10s] Action: Final dynamic resolution. Audio: {sound_desc}."
            blocks_str = f"{b1}\n{b2}\n{b3}"

        block_timeline = f"### TIMELINE\n{blocks_str}"

        return f"{block_input}\n\n{block_profiles}\n\n{block_scene}\n\n{block_timeline}"


@dataclass
class CompiledDeltaPrompt:
    preservation_lock: str
    isolated_diff: str

    def to_delta_prompt(self) -> str:
        return (
            f"[PRESERVATION LOCK]: {self.preservation_lock} | [ISOLATED DIFF]: {self.isolated_diff}"
        )


@dataclass
class SceneDirective:
    scene_number: int
    active_roles: list[str]
    action: str
    dialogue: str = ""
    screenplay_text: str | None = None
    audio_cues: str = ""
    timecode: str = ""
    duration_seconds: float = 10.0
    title_card_text: str | None = None
    title_card_subtitle: str | None = None
    narrator_text: str | None = None


@dataclass
class MetaPromptTags:
    characters: list[CharacterRole] = field(default_factory=list)
    aesthetic_tags: list[str] = field(default_factory=list)
    environment_tag: str = ""
    camera_lighting_tag: str = ""
    audio_beat: str = ""
    vocal_delivery: str = ""


# Pydantic v2 schemas for google-genai Structured Outputs (response_schema)
# Source: https://ai.google.dev/gemini-api/docs/structured-output?lang=python
# Source: https://docs.pydantic.dev/latest/concepts/models/
class DeconstructedCharacterSchema(BaseModel):
    role_id: str = Field(default="Role A", description="Positional role ID e.g. Role A, Role B")
    name: str = Field(default="Lead Subject", description="Character name or parody role title")
    description: str = Field(
        default="A distinct cinematic character",
        description="Visual description of character including wardrobe and aesthetic tags",
    )
    reference_url: str | None = Field(default=None, description="Optional reference image URL")
    aesthetic_tags: list[str] = Field(
        default_factory=list, description="Character wardrobe and aesthetic tags"
    )
    voice_style: str = Field(default="", description="Character voice style and delivery")


class DeconstructedConceptSchema(BaseModel):
    characters: list[DeconstructedCharacterSchema] = Field(default_factory=list)
    aesthetic_tags: list[str] = Field(default_factory=list)
    environment_tag: str = Field(default="")
    camera_lighting_tag: str = Field(default="")
    audio_beat: str = Field(default="")
    vocal_delivery: str = Field(default="")


__all__ = [
    "CompiledDeltaPrompt",
    "CompiledPromptParts",
    "DeconstructedCharacterSchema",
    "DeconstructedConceptSchema",
    "MetaPromptTags",
    "SceneDirective",
]
