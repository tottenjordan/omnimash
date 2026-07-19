from enum import Enum

from omnimash.prompts.compiler import CompiledPromptParts, PromptCompiler


class StylePreset(str, Enum):
    NINETIES_RAP_VIDEO = "90s_rap_video"
    TRAP_DISSTRACK = "trap_disstrack"
    CYBERPUNK_DRIFT = "cyberpunk_drift"
    VHS_ANIME = "vhs_anime"


class PromptTaxonomyEngine:
    def __init__(self) -> None:
        self.compiler = PromptCompiler()

    def build_initial_prompt(
        self,
        base_character: str,
        style_preset: StylePreset,
        custom_instructions: str,
        audio_stem: str | None = None,
        override_prompt: str | None = None,
    ) -> str:
        if override_prompt:
            return override_prompt

        parts: CompiledPromptParts = self.compiler.compile(
            raw_prompt=base_character,
            style_preset=style_preset,
            custom_instructions=custom_instructions,
            audio_stem=audio_stem,
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
