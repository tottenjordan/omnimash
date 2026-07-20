from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from omnimash.prompts.compiler import (
    AESTHETIC_SIGNIFIERS,
    CompiledPromptParts,
    MetaPromptTags,
    PromptCompiler,
)


@dataclass
class PresetContribution:
    wardrobe: str
    camera_lighting: str
    motion: str
    sound_design: str


class StylePreset(str, Enum):
    NINETIES_RAP_VIDEO = "90s_rap_video"
    TRAP_DISSTRACK = "trap_disstrack"
    CYBERPUNK_DRIFT = "cyberpunk_drift"
    VHS_ANIME = "vhs_anime"


class PromptTaxonomyEngine:
    def __init__(self) -> None:
        self.compiler = PromptCompiler()

    def get_preset_contribution(self, preset: StylePreset | str) -> PresetContribution:
        preset_key = str(preset.value if hasattr(preset, "value") else preset)
        style_info = AESTHETIC_SIGNIFIERS.get(
            preset_key,
            AESTHETIC_SIGNIFIERS["90s_rap_video"],
        )
        return PresetContribution(
            wardrobe=style_info["wardrobe"],
            camera_lighting=style_info["camera"],
            motion=style_info["motion"],
            sound_design=style_info["audio"],
        )

    def build_initial_prompt(
        self,
        base_character: str,
        style_preset: StylePreset,
        custom_instructions: str,
        audio_stem: str | None = None,
        voiceover: str | None = None,
        is_silent: bool = False,
        on_screen_text: str | None = None,
        override_prompt: str | None = None,
        drip_props: list[str] | str | None = None,
        vibe_intensity: int = 50,
    ) -> str:
        if override_prompt:
            return override_prompt

        parts: CompiledPromptParts = self.compiler.compile(
            raw_prompt=base_character,
            style_preset=style_preset,
            custom_instructions=custom_instructions,
            audio_stem=audio_stem,
            voiceover=voiceover,
            is_silent=is_silent,
            on_screen_text=on_screen_text,
            drip_props=drip_props,
            vibe_intensity=vibe_intensity,
        )
        return (
            "Generate a 720p 10-second cinematic parody video with native audio using the Anchor & Inject framework: "
            f"{parts.to_full_prompt()}"
        )

    def build_delta_prompt(
        self,
        current_clip_desc: str,
        delta_instruction: str,
        override_prompt: str | None = None,
    ) -> str:
        if override_prompt:
            return override_prompt

        compiled_delta = self.compiler.compile_delta(
            delta_instruction=delta_instruction
        )
        return (
            "Apply conversational diff to the existing video latent space using Lock & Isolate: "
            f"{compiled_delta.to_delta_prompt()}"
        )

    def deconstruct_concept(self, concept: str) -> MetaPromptTags:
        return self.compiler.deconstruct_concept(concept)
