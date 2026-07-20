from __future__ import annotations

from dataclasses import dataclass, field
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
    audio_track: str
    voiceover: str = ""
    is_silent: bool = False
    on_screen_text: str = ""
    drip_props: list[str] = field(default_factory=list)
    vibe_intensity: int = 50

    def to_full_prompt(self) -> str:
        text_directive = (
            f"On-screen text: '{self.on_screen_text}'"
            if self.on_screen_text and self.on_screen_text.strip()
            else "No text, no subtitles, no captions on screen"
        )

        lower_audio = self.audio_track.lower().strip()
        if self.is_silent or lower_audio in ("none", "mute", "silent"):
            sound_directive = (
                "Sound design: Silent video. No background music, no audio"
            )
        elif self.voiceover and self.voiceover.strip():
            sound_directive = (
                f"Sound design: Foreground spoken voiceover/dialogue is dominant, "
                f"crystal-clear, and front-of-mix. Background beat ({self.audio_track}) "
                f"is quietly ducked at 15% volume in the background"
            )
        else:
            sound_directive = f"Sound design: {self.audio_track}"

        vocal_directive = ""
        if self.voiceover and self.voiceover.strip():
            vo = self.voiceover.strip()
            if ":" in vo or "\n" in vo:
                vocal_directive = f" Dialogue between subjects: {vo}."
            else:
                vocal_directive = f" Voiceover: {vo}."

        return (
            f"[SUBJECT ANCHOR]: {self.subject_anchor} | "
            f"[AESTHETIC INJECTION]: {self.aesthetic_injection} | "
            f"[ENVIRONMENT]: {self.environment} | "
            f"[CAMERA/LIGHTING]: {self.camera_lighting} | "
            f"[MOTION]: {self.motion} | "
            f"[AUDIO TRACK]: {self.audio_track} | "
            f"{sound_directive}.{vocal_directive} {text_directive}."
        )


@dataclass
class CompiledDeltaPrompt:
    preservation_lock: str
    isolated_diff: str

    def to_delta_prompt(self) -> str:
        return (
            f"[PRESERVATION LOCK]: {self.preservation_lock} | "
            f"[ISOLATED DIFF]: {self.isolated_diff}"
        )


@dataclass
class CharacterRole:
    role_id: str
    name: str
    description: str
    reference_url: str | None = None


@dataclass
class SceneDirective:
    scene_number: int
    active_roles: list[str]
    action: str
    dialogue: str = ""


@dataclass
class MetaPromptTags:
    characters: list[CharacterRole] = field(default_factory=list)
    aesthetic_tags: list[str] = field(default_factory=list)
    environment_tag: str = ""
    camera_lighting_tag: str = ""
    audio_beat: str = ""


CHARACTER_LORE_ANCHORS: dict[str, str] = {
    "snape": "Severus Snape, a gaunt man with a hooked nose, severe cynical expression, and shoulder-length straight greasy black hair",
    "dumbledore": "Albus Dumbledore, an elderly wizard with half-moon spectacles, long flowing silver beard, and ornate wizard robes",
    "voldemort": "Lord Voldemort, a pale serpentine figure with slit-like nostrils, no hair, chalk-white skin, and piercing cold eyes",
    "harry": "Harry Potter, a young man with round wire-rim glasses, untidy jet-black hair, and a distinct lightning bolt scar on his forehead",
}

AESTHETIC_SIGNIFIERS: dict[str, dict[str, str]] = {
    "90s_rap_video": {
        "wardrobe": "wearing an oversized shiny black puffer jacket, thick diamond Cuban link chain, and vintage Cartier glasses",
        "camera": "In a single continuous shot, no scene cuts. Shot on a 90s fisheye lens, low-angle tracking shot, high-contrast MTV rap video lighting with green and purple neon rim lights",
        "motion": "bopping head rhythmically to a 120 BPM beat while gesturing emphatically for a 10-second clip",
        "audio": "120 BPM boom-bap hip-hop beat, vinyl scratch intro, punchy kick drum, crisp snare, and rhythmic rap cadence",
    },
    "trap_disstrack": {
        "wardrobe": "wearing designer streetwear, iced-out medallions, and tinted aviator sunglasses",
        "camera": "In a single continuous shot, dark moody 808 bass lighting, heavy laser smoke, and strobe flashes",
        "motion": "aggressive lyrical hand gestures and slow walking toward the camera for 10 seconds",
        "audio": "Muffled blown-out 808 sub-bass, rapid 16th-note trap hi-hat trills, and slow dark rap beat playing in the background",
    },
    "cyberpunk_drift": {
        "wardrobe": "wearing a high-collar LED-lined techwear coat with holographic chrome accessories",
        "camera": "In a single continuous shot, no scene cuts. Anamorphic widescreen lens, rainy asphalt reflections, synthwave purple and cyan color grading",
        "motion": "slowly turning to face the camera amidst falling digital rain for 10 seconds",
        "audio": "Synthesizer arpeggios, heavy analog synth bassline, and futuristic ambient cyberpunk drone",
    },
    "vhs_anime": {
        "wardrobe": "cel-shaded retro anime styling with oversized 80s shoulder pads and vintage headbands",
        "camera": "In a single continuous shot. Retro 4:3 VHS tape grain, analog scanlines, chromatic aberration, and warm nostalgic bloom",
        "motion": "classic limited-frame anime speech animation and dynamic wind blowing through hair for 10 seconds",
        "audio": "Retro 80s city pop brass samples, lo-fi cassette tape hiss, and upbeat Japanese synth melody",
    },
}


class PromptCompiler:
    def compile(
        self,
        raw_prompt: str,
        style_preset: StylePreset | str = "90s_rap_video",
        custom_instructions: str = "",
        audio_stem: str | None = None,
        voiceover: str | None = None,
        is_silent: bool = False,
        on_screen_text: str | None = None,
        drip_props: list[str] | str | None = None,
        vibe_intensity: int = 50,
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

        # 3. Normalize Drip Props & Resolve Aesthetic Injection
        props_list: list[str] = []
        if isinstance(drip_props, str):
            props_list = [p.strip() for p in drip_props.split(",") if p.strip()]
        elif isinstance(drip_props, list):
            props_list = [str(p).strip() for p in drip_props if str(p).strip()]

        aesthetic = style_info["wardrobe"]
        if props_list:
            aesthetic = f"{aesthetic}, accessorized with {', '.join(props_list)}"

        # 4. Resolve Environment
        env = "in a stone Hogwarts dungeon lit by atmospheric fog and ambient glow"
        if custom_instructions:
            env = f"in {custom_instructions} with atmospheric environmental lighting"

        # 5. Map Vibe Intensity & Resolve Camera/Lighting
        if vibe_intensity <= 30:
            vibe_desc = "Dark moody underground lighting, heavy laser smoke, high-contrast shadows, raw 16mm grain"
        elif vibe_intensity <= 70:
            vibe_desc = "Cinematic high-contrast MTV lighting with balanced ambient color grading"
        else:
            vibe_desc = "High-gloss neon lighting, vibrant anamorphic lens flare, holographic bloom, polished commercial aesthetic"

        base_camera = style_info["camera"].rstrip(".")
        camera_lighting = f"{base_camera}. {vibe_desc}"

        # 6. Resolve Audio Track (explicit override takes precedence over preset)
        audio = audio_stem.strip() if audio_stem else style_info["audio"]

        return CompiledPromptParts(
            subject_anchor=anchor,
            aesthetic_injection=aesthetic,
            environment=env,
            camera_lighting=camera_lighting,
            motion=style_info["motion"],
            audio_track=audio,
            voiceover=voiceover.strip() if voiceover else "",
            is_silent=is_silent,
            on_screen_text=on_screen_text.strip() if on_screen_text else "",
            drip_props=props_list,
            vibe_intensity=vibe_intensity,
        )

    def compile_delta(
        self, delta_instruction: str, custom_lock: str | None = None
    ) -> CompiledDeltaPrompt:
        preservation_lock = (
            custom_lock
            if custom_lock is not None
            else (
                "Maintain exact subject face, character likeness, expression, "
                "wardrobe baseline, background environment, and audio stem rhythm from the previous turn."
            )
        )
        isolated_diff = (
            f"Alter only the specified element: {delta_instruction}. "
            "Do not modify any surrounding visual or audio features."
        )
        return CompiledDeltaPrompt(
            preservation_lock=preservation_lock,
            isolated_diff=isolated_diff,
        )

    def compile_storyboard(
        self,
        concept: str,
        characters: list[CharacterRole],
        scenes: list[SceneDirective],
        aesthetic_tags: list[str] | None = None,
        environment_tag: str | None = None,
        audio_beat: str | None = None,
    ) -> str:
        role_lines: list[str] = []
        for char in characters:
            ref_str = f" (Ref: {char.reference_url})" if char.reference_url else ""
            role_lines.append(
                f"- {char.role_id} ({char.name}): {char.description}{ref_str}"
            )
        roles_block = "\n".join(role_lines) if role_lines else "- None"

        aesthetic_parts: list[str] = []
        if concept and concept.strip():
            aesthetic_parts.append(f"Concept: {concept.strip()}")
        if aesthetic_tags:
            aesthetic_parts.append(f"Aesthetic Tags: {', '.join(aesthetic_tags)}")
        if environment_tag and environment_tag.strip():
            aesthetic_parts.append(f"Environment: {environment_tag.strip()}")
        if audio_beat and audio_beat.strip():
            aesthetic_parts.append(f"Audio Beat: {audio_beat.strip()}")
        aesthetic_block = (
            "\n".join(aesthetic_parts) if aesthetic_parts else "Default Aesthetic"
        )

        scene_lines: list[str] = []
        for scene in scenes:
            roles_str = ", ".join(scene.active_roles)
            diag_str = (
                f' | Dialogue: "{scene.dialogue}"'
                if scene.dialogue and scene.dialogue.strip()
                else ""
            )
            scene_lines.append(
                f"- Scene {scene.scene_number} [{roles_str}]: {scene.action}{diag_str}"
            )
        scenes_block = "\n".join(scene_lines) if scene_lines else "- No scenes"

        return (
            f"[ROLE DEFINITIONS]\n{roles_block}\n\n"
            f"[AESTHETIC INJECTION]\n{aesthetic_block}\n\n"
            f"[STORYBOARD SEQUENCE]\n{scenes_block}"
        )

    def deconstruct_concept(self, concept: str) -> MetaPromptTags:
        """Parses open-ended parody concept shorthand into structured MetaPromptTags with CharacterRoles, Aesthetic Tags, Environment, Camera/Lighting, and Audio Beat."""
        lower = concept.lower().strip()

        # 1. Character Extraction
        chars: list[CharacterRole] = []
        role_labels = ["Role A", "Role B", "Role C", "Role D"]

        known_lore: dict[str, tuple[str, str]] = {
            "harry": (
                "Harry",
                "Harry Potter, a young wizard with round wire-rim glasses, untidy jet-black hair, and a distinct lightning bolt scar on his forehead",
            ),
            "draco": (
                "Draco",
                "Draco Malfoy, a pale blonde rival wizard with slicked-back platinum hair, sharp sneering facial features, and tailored silver-trimmed robes",
            ),
            "snape": (
                "Severus Snape",
                "Severus Snape, a gaunt man with a hooked nose, severe cynical expression, and shoulder-length straight greasy black hair",
            ),
            "dumbledore": (
                "Albus Dumbledore",
                "Albus Dumbledore, an elderly wizard with half-moon spectacles, long flowing silver beard, and ornate wizard robes",
            ),
            "voldemort": (
                "Lord Voldemort",
                "Lord Voldemort, a pale serpentine figure with slit-like nostrils, no hair, chalk-white skin, and piercing cold eyes",
            ),
            "ramsay": (
                "Gordon Ramsay",
                "Gordon Ramsay, a fiery celebrity chef with sharp blond hair, intense focused gaze, and crisp white chef jacket",
            ),
            "julia": (
                "Julia Child",
                "Julia Child, an iconic tall cheerful culinary master with curly brown hair, expressive warm smile, and classic vintage apron",
            ),
            "samurai": (
                "Neon Samurai",
                "Neon Samurai, a stoic warrior in glowing LED armor with a razor-sharp energy katana",
            ),
            "ninja": (
                "Cyborg Ninja",
                "Cyborg Ninja, an agile cybernetic assassin with chrome mask and stealth holographic visor",
            ),
        }

        matched_keys = [k for k in known_lore if k in lower]
        if matched_keys:
            for idx, k in enumerate(matched_keys):
                name, desc = known_lore[k]
                chars.append(
                    CharacterRole(
                        role_id=role_labels[min(idx, len(role_labels) - 1)],
                        name=name,
                        description=desc,
                    )
                )
        else:
            if " vs " in lower or " versus " in lower:
                splitter = " vs " if " vs " in lower else " versus "
                parts = concept.split(splitter)
                name_a = parts[0].strip().split(" in ")[0].strip()
                name_b = parts[1].strip().split(" in ")[0].strip()
                chars.append(
                    CharacterRole(
                        role_id="Role A",
                        name=name_a.title(),
                        description=f"{name_a.title()}, a distinct cinematic character with sharp expressive features",
                    )
                )
                chars.append(
                    CharacterRole(
                        role_id="Role B",
                        name=name_b.title(),
                        description=f"{name_b.title()}, a compelling rival character with bold visual presence",
                    )
                )
            else:
                chars.append(
                    CharacterRole(
                        role_id="Role A",
                        name="Lead Subject",
                        description="A distinct cinematic character with expressive facial features and stylized attire",
                    )
                )

        # 2. Aesthetic / Style Tags Extraction
        if (
            "trap" in lower
            or "atlanta" in lower
            or "808" in lower
            or "rap" in lower
            or "hip-hop" in lower
        ):
            aesthetic_tags = [
                "2000s Atlanta Trap Disstrack",
                "Diamond Lightning Bolt Chain",
                "Vintage Streetwear",
                "Heavy 808 Bass Lighting",
            ]
            audio_beat = "140 BPM Heavy 808 Trap"
            env_tag = (
                "Gothic Hogwarts courtyard lit by neon stage lights and smoky haze"
                if (
                    "harry" in lower
                    or "draco" in lower
                    or "hogwarts" in lower
                    or "snape" in lower
                )
                else "Urban street alley with neon stage lights and atmospheric fog"
            )
            cam_tag = "Low-angle 90s fisheye tracking shot with high-contrast green and purple neon rim lights"
        elif (
            "cyberpunk" in lower
            or "neon" in lower
            or "futuristic" in lower
            or "iron chef" in lower
            or "samurai" in lower
            or "ninja" in lower
            or "arcade" in lower
        ):
            aesthetic_tags = [
                "Cyberpunk Glow",
                "Neon Cyan & Purple Color Grading",
                "Futuristic Techwear",
                "Anamorphic Lens Flare",
            ]
            audio_beat = "110 BPM Cyberpunk Synthwave Groove"
            env_tag = (
                "Futuristic neon kitchen colosseum with holographic spectator screens"
                if (
                    "chef" in lower
                    or "ramsay" in lower
                    or "julia" in lower
                    or "kitchen" in lower
                )
                else "Neon-lit cyberpunk arcade showdown arena"
            )
            cam_tag = "Anamorphic widescreen tracking shot with high-gloss neon reflections and holographic bloom"
        elif "anime" in lower or "vhs" in lower or "lo-fi" in lower:
            aesthetic_tags = [
                "Retro VHS Anime Lo-Fi",
                "Analog Scanlines",
                "Warm Nostalgic Bloom",
                "Cel-Shaded Styling",
            ]
            audio_beat = "85 BPM VHS Lo-Fi City Pop"
            env_tag = "Retro 80s anime cityscape bathed in sunset pastel lighting"
            cam_tag = (
                "Retro 4:3 VHS tape framing with chromatic aberration and warm bloom"
            )
        else:
            aesthetic_tags = [
                "High-Contrast Cinematic Parody",
                "Stylized Wardrobe",
                "Dramatic Lighting",
            ]
            audio_beat = "120 BPM Cinematic Beat"
            env_tag = "Atmospheric stage set with dramatic directional lighting and smoke effects"
            cam_tag = "Cinematic 16:9 tracking shot with balanced ambient lighting and crisp depth of field"

        return MetaPromptTags(
            characters=chars,
            aesthetic_tags=aesthetic_tags,
            environment_tag=env_tag,
            camera_lighting_tag=cam_tag,
            audio_beat=audio_beat,
        )
