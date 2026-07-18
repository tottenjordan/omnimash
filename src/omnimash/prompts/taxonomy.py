from enum import Enum


class StylePreset(str, Enum):
    NINETIES_RAP_VIDEO = "90s_rap_video"
    TRAP_DISSTRACK = "trap_disstrack"
    CYBERPUNK_DRIFT = "cyberpunk_drift"
    VHS_ANIME = "vhs_anime"


class PromptTaxonomyEngine:
    def build_initial_prompt(
        self,
        base_character: str,
        style_preset: StylePreset,
        custom_instructions: str,
    ) -> str:
        style_descriptors = {
            StylePreset.NINETIES_RAP_VIDEO: (
                "90s fisheye lens, low-angle tracking shot, gold chains, "
                "oversized bomber jacket, boom-bap rhythm cadence"
            ),
            StylePreset.TRAP_DISSTRACK: (
                "dark 808 bass lighting, neon smoke, rapid hi-hat visual cuts, "
                "aggressive lyrical gestures"
            ),
            StylePreset.CYBERPUNK_DRIFT: (
                "holographic neon glow, rainy asphalt reflections, synthwave color grading"
            ),
            StylePreset.VHS_ANIME: (
                "retro 4:3 VHS tape grain, analog scanlines, cel-shaded animation aesthetic"
            ),
        }
        style_text = style_descriptors.get(style_preset, "")
        return (
            f"Generate a 720p 10-second cinematic parody video with native audio. "
            f"Character Lore Anchors: {base_character}. "
            f"Aesthetic Style & Audio Direction: {style_text}. "
            f"Scene Action & Lyrics: {custom_instructions}."
        )

    def build_delta_prompt(self, current_clip_desc: str, delta_instruction: str) -> str:
        return (
            f"Apply conversational diff to the existing video latent space: "
            f"Modify the active scene by applying this change: '{delta_instruction}'. "
            f"Preserve all character facial consistency, lighting anchors, and background continuity."
        )
