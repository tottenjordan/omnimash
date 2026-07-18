from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omnimash.prompts.taxonomy import StylePreset


@dataclass
class CompiledPromptParts:
    subject_anchor: str
    aesthetic_injection: str
    environment: str
    camera_lighting: str
    motion: str

    def to_full_prompt(self) -> str:
        return (
            f"[SUBJECT ANCHOR]: {self.subject_anchor} | "
            f"[AESTHETIC INJECTION]: {self.aesthetic_injection} | "
            f"[ENVIRONMENT]: {self.environment} | "
            f"[CAMERA/LIGHTING]: {self.camera_lighting} | "
            f"[MOTION]: {self.motion}"
        )


CHARACTER_LORE_ANCHORS: dict[str, str] = {
    "snape": "Severus Snape, a gaunt man with a hooked nose, severe cynical expression, and shoulder-length straight greasy black hair",
    "dumbledore": "Albus Dumbledore, an elderly wizard with half-moon spectacles, long flowing silver beard, and ornate wizard robes",
    "voldemort": "Lord Voldemort, a pale serpentine figure with slit-like nostrils, no hair, chalk-white skin, and piercing cold eyes",
    "harry": "Harry Potter, a young man with round wire-rim glasses, untidy jet-black hair, and a distinct lightning bolt scar on his forehead",
}

AESTHETIC_SIGNIFIERS: dict[str, dict[str, str]] = {
    "90s_rap_video": {
        "wardrobe": "wearing an oversized shiny black puffer jacket, thick diamond Cuban link chain, and vintage Cartier glasses",
        "camera": "shot on a 90s fisheye lens, low-angle tracking shot, high-contrast MTV rap video lighting with green and purple neon rim lights",
        "motion": "nodding rhythmically to a boom-bap beat while gesturing emphatically for a 10-second clip",
    },
    "trap_disstrack": {
        "wardrobe": "wearing designer streetwear, iced-out medallions, and tinted aviator sunglasses",
        "camera": "rapid visual jump cuts, dark moody 808 bass lighting, heavy laser smoke, and strobe flashes",
        "motion": "aggressive lyrical hand gestures and slow walking toward the camera for 10 seconds",
    },
    "cyberpunk_drift": {
        "wardrobe": "wearing a high-collar LED-lined techwear coat with holographic chrome accessories",
        "camera": "anamorphic widescreen lens, rainy asphalt reflections, synthwave purple and cyan color grading",
        "motion": "slowly turning to face the camera amidst falling digital rain for 10 seconds",
    },
    "vhs_anime": {
        "wardrobe": "cel-shaded retro anime styling with oversized 80s shoulder pads and vintage headbands",
        "camera": "retro 4:3 VHS tape grain, analog scanlines, chromatic aberration, and warm nostalgic bloom",
        "motion": "classic limited-frame anime speech animation and dynamic wind blowing through hair for 10 seconds",
    },
}


class PromptCompiler:
    def compile(
        self,
        raw_prompt: str,
        style_preset: StylePreset | str = "90s_rap_video",
        custom_instructions: str = "",
    ) -> CompiledPromptParts:
        lower = raw_prompt.lower()

        # 1. Resolve Subject Anchor
        anchor = "A distinct cinematic character with sharp facial features and expressive eyes"
        for name, desc in CHARACTER_LORE_ANCHORS.items():
            if name in lower:
                anchor = desc
                break

        # 2. Resolve Style Signifiers
        preset_key = str(
            style_preset.value if hasattr(style_preset, "value") else style_preset
        )
        style_info = AESTHETIC_SIGNIFIERS.get(
            preset_key,
            AESTHETIC_SIGNIFIERS["90s_rap_video"],
        )

        # 3. Resolve Environment
        env = "in a stone Hogwarts dungeon lit by atmospheric fog and ambient glow"
        if custom_instructions:
            env = f"in {custom_instructions} with atmospheric environmental lighting"

        return CompiledPromptParts(
            subject_anchor=anchor,
            aesthetic_injection=style_info["wardrobe"],
            environment=env,
            camera_lighting=style_info["camera"],
            motion=style_info["motion"],
        )
