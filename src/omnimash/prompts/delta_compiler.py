"""Lean Delta-Only Image-to-Video (I2V) prompt compiler and 4-subblock Keyframe prompt builder."""

from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, Field

from omnimash.prompts.parody import sanitize_real_names

CompilationMode = Literal["auto", "i2v_delta_only", "t2v_4block"]

_SURROUNDING_QUOTES_RE = re.compile(r'^[\s"“”\'‘’]+|[\s"“”\'‘’]+$')
_TIMECODE_PREFIX_RE = re.compile(
    r"\[\s*\d+(?:\.\d+)?\s*s?\s*-\s*\d+(?:\.\d+)?\s*s?\s*\]\s*",
    re.IGNORECASE,
)
_BRACKET_SOURCES_RE = re.compile(r"(?m)^\s*\[#\s*(?:Sources|References)\b[^\]]*\]\s*\n?")
_INLINE_BRACKET_SOURCES_RE = re.compile(r"\[#\s*(?:Sources|References)\b[^\]]*\]\s*")


def calculate_shot_word_budget(
    shot_seconds: float,
    wpm: int = 130,
    cut_buffer_seconds: float = 0.7,
    max_wps: float = 3.5,
) -> int:
    """Calculates maximum spoken words for a shot per multimodal-media-production Stage 2 Rule 1.

    Formula: floor((shot_seconds - 0.7) * WPM / 60), capped at 3.5 words/sec.
    """
    usable_sec = max(0.0, float(shot_seconds) - cut_buffer_seconds)
    wpm_cap = math.floor(usable_sec * (float(wpm) / 60.0))
    wps_cap = math.floor(usable_sec * max_wps)
    return max(0, min(wpm_cap, wps_cap))


def format_unquoted_video_dialogue(
    speaker_descriptor: str,
    voice_style: str,
    dialogue_text: str,
    enable_sanitization: bool = True,
) -> str:
    """Formats spoken video dialogue using colon syntax WITHOUT quotation marks.

    Prevents Gemini Omni Flash from rendering spoken dialogue as on-screen subtitles.
    """
    clean_line = _TIMECODE_PREFIX_RE.sub("", dialogue_text or "").strip()
    clean_line = _SURROUNDING_QUOTES_RE.sub("", clean_line).strip()
    # Strip internal double-quotes that could trigger subtitle rendering while keeping apostrophes
    clean_line = clean_line.replace('"', "").replace("“", "").replace("”", "").strip()
    if not clean_line:
        return ""

    if enable_sanitization:
        clean_line = sanitize_real_names(clean_line)
        speaker_descriptor = sanitize_real_names(speaker_descriptor)
        voice_style = sanitize_real_names(voice_style)

    spk = (speaker_descriptor or "the speaker").strip().rstrip(":")
    style = (voice_style or "").strip().rstrip(".")
    if style:
        style_lower = style[0].lower() + style[1:] if len(style) > 1 else style.lower()
        prefix = f"In a {style_lower}" if not style_lower.startswith(("in ", "with ")) else style
        return f"{prefix}, {spk} says: {clean_line}"
    return f"{spk} says: {clean_line}"


def convert_legacy_tags_to_omni_1_2_natural_language(prompt_text: str) -> str:
    """Converts Omni 1.1 legacy tags (<FIRST_FRAME>, <IMAGE_REF_*>, [# Sources ...]) into natural-language positional references."""
    if not prompt_text:
        return prompt_text

    converted = _BRACKET_SOURCES_RE.sub("", prompt_text)
    converted = _INLINE_BRACKET_SOURCES_RE.sub("", converted)

    # Remove redundant parenthetical legacy anchors right after Attached Image #N
    converted = re.sub(
        r"(Attached Image #\d+)\s*\(<(?:FIRST|LAST)_FRAME>(?:@[^\s\)]+)?\)",
        r"\1",
        converted,
        flags=re.IGNORECASE,
    )

    converted = re.sub(
        r"<FIRST_FRAME>(?:@(?:KeyframeSeed|Image\d+))?",
        "the starting frame (first image)",
        converted,
        flags=re.IGNORECASE,
    )
    converted = re.sub(
        r"<LAST_FRAME>(?:@(?:EndKeyframe|KeyframeSeed|Image\d+))?",
        "the ending frame",
        converted,
        flags=re.IGNORECASE,
    )

    def _replace_image_ref(match: re.Match[str]) -> str:
        ref_idx = int(match.group(1))
        img_idx = match.group(2)
        ordinal = int(img_idx) if img_idx else (ref_idx + 1)
        return f"reference image {ordinal}"

    converted = re.sub(
        r"<IMAGE_REF_(\d+)>(?:@Image(\d+))?",
        _replace_image_ref,
        converted,
        flags=re.IGNORECASE,
    )
    converted = re.sub(
        r"@Image(\d+)",
        lambda m: f"image {m.group(1)}",
        converted,
        flags=re.IGNORECASE,
    )
    converted = re.sub(
        r"<VIDEO_REF_\d+>(?:@VideoReference\d+)?|@VideoReference\d+",
        "the reference video",
        converted,
        flags=re.IGNORECASE,
    )

    # Remove empty ### INPUT ROLES & REFERENCES header if all metadata lines were stripped
    converted = re.sub(
        r"### INPUT ROLES(?: & REFERENCES)?\s*\n+(?=(?:### |\Z))",
        "",
        converted,
        flags=re.IGNORECASE,
    )
    converted = re.sub(r"\n{3,}", "\n\n", converted).strip()
    return converted


class KeyframeModularPromptSpec(BaseModel):
    """4-Subblock verbatim keyframe prompt specification."""

    camera_block: str = Field(
        ...,
        description="Shot size, off-axis placement, lens focal length/aperture, subject frame-height %, and foreground depth",
    )
    fixed_character_block: str = Field(
        default="",
        description="Verbatim character appearance, flat-ink tattoo locks, and hand-assigned prop spec",
    )
    wetness_lighting_block: str = Field(
        default="",
        description="Positive physical surface state (damp strands, skin sheen, water beads) and motivating light sources",
    )
    matched_location_block: str = Field(
        ...,
        description="Shared verbatim architectural and environmental specification across shots in the same scene",
    )

    def compile(self) -> str:
        """Joins the 4 modular keyframe blocks in canonical order."""
        blocks = [
            b.strip().rstrip(".") + "."
            for b in (
                self.camera_block,
                self.fixed_character_block,
                self.wetness_lighting_block,
                self.matched_location_block,
            )
            if b and b.strip()
        ]
        body = " ".join(blocks)
        if not body.lower().startswith(
            ("create an image", "generate an image", "wide ", "medium ", "close-up ")
        ):
            return f"Create an image of: {body}"
        return body


class I2VDeltaPromptSpec(BaseModel):
    """Lean Delta-Only Image-to-Video specification for single-keyframe Omni 1.2 Flash renders."""

    camera_motion: str = Field(
        ...,
        description="Concrete camera movement and 3D parallax directive, e.g. 'Locked-off camera with a very slow push in.'",
    )
    subject_action: str = Field(
        ...,
        description="Sequential physical motion of the subject from the starting frame without re-describing static wardrobe",
    )
    speaker_descriptor: str = Field(
        default="",
        description="Visual handle of the on-camera speaker, e.g. 'the tattooed man in the blue aviator sunglasses'",
    )
    voice_style: str = Field(
        default="",
        description="Vocal delivery & regional accent, e.g. 'cold, unhurried, deadpan Glasgow Scottish accent'",
    )
    spoken_dialogue: str = Field(
        default="",
        description="Untimed spoken dialogue line (will be emitted unquoted after 'says:')",
    )
    post_dialogue_hold: str = Field(
        default="After the line he holds still with a faint smirk.",
        description="Physical hold during the final 1.0-1.5s room-tone exit buffer",
    )
    environmental_motion: str = Field(
        default="",
        description="Background environmental physics, e.g. 'Rain falls steadily through the cool storm backlight behind him.'",
    )
    ambient_noise: str = Field(
        default="steady room tone",
        description="Ambient noise bed description",
    )
    explicit_sound_whitelist: list[str] = Field(
        default_factory=list,
        description="Exhaustive list of permitted audio elements for 'The only sounds are...'",
    )
    include_starting_frame_binding: bool = Field(
        default=True,
        description="Whether to append 'Use this image as the starting frame.' binding sentence",
    )
    enable_sanitization: bool = True

    def compile(self) -> str:
        """Compiles a single untimed Delta-Only paragraph for Image-to-Video generation."""
        sentences: list[str] = []

        cam = _TIMECODE_PREFIX_RE.sub("", self.camera_motion or "").strip()
        if cam:
            sentences.append(cam.rstrip(".") + ".")

        act = _TIMECODE_PREFIX_RE.sub("", self.subject_action or "").strip()
        if act:
            sentences.append(act.rstrip(".") + ".")

        has_speech = False
        if self.spoken_dialogue and self.spoken_dialogue.strip():
            diag_sentence = format_unquoted_video_dialogue(
                speaker_descriptor=self.speaker_descriptor,
                voice_style=self.voice_style,
                dialogue_text=self.spoken_dialogue,
                enable_sanitization=self.enable_sanitization,
            )
            if diag_sentence:
                has_speech = True
                if not diag_sentence.endswith((".", "!", "?")):
                    diag_sentence += "."
                sentences.append(diag_sentence)
                hold = _TIMECODE_PREFIX_RE.sub("", self.post_dialogue_hold or "").strip()
                if hold:
                    sentences.append(hold.rstrip(".") + ".")

        env_motion = _TIMECODE_PREFIX_RE.sub("", self.environmental_motion or "").strip()
        if env_motion:
            sentences.append(env_motion.rstrip(".") + ".")

        amb = (self.ambient_noise or "steady room tone").strip().rstrip(".")
        sentences.append(f"Ambient noise: {amb}.")

        if self.explicit_sound_whitelist:
            allowed = [s.strip() for s in self.explicit_sound_whitelist if s.strip()]
        else:
            allowed = ["his voice", amb] if has_speech else [amb]

        if len(allowed) == 1:
            whitelist_str = allowed[0]
        elif len(allowed) == 2:
            whitelist_str = f"{allowed[0]} and {allowed[1]}"
        else:
            whitelist_str = f"{', '.join(allowed[:-1])}, and {allowed[-1]}"
        sentences.append(f"The only sounds are {whitelist_str}.")

        if self.include_starting_frame_binding:
            sentences.append("Use this image as the starting frame.")

        result = " ".join(sentences)
        return sanitize_real_names(result) if self.enable_sanitization else result


__all__ = [
    "CompilationMode",
    "I2VDeltaPromptSpec",
    "KeyframeModularPromptSpec",
    "calculate_shot_word_budget",
    "convert_legacy_tags_to_omni_1_2_natural_language",
    "format_unquoted_video_dialogue",
]
