from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from omnimash.config import settings

if TYPE_CHECKING:
    from omnimash.prompts.taxonomy import StylePreset

logger = logging.getLogger(__name__)


def _role_label(idx: int) -> str:
    """Unique, spreadsheet-style role label for character ``idx``.

    Produces ``Role A``..``Role Z``, then ``Role AA``, ``Role AB``, ... so any
    number of characters gets a distinct id (the old fixed 4-label list clamped
    everyone past the 4th to ``Role D``, silently aliasing them).
    """
    letters = ""
    n = idx
    while True:
        letters = chr(65 + n % 26) + letters
        n = n // 26 - 1
        if n < 0:
            break
    return f"Role {letters}"


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
            sound_directive = "Sound design: Silent video. No background music, no audio"
        elif self.voiceover and self.voiceover.strip():
            sound_directive = (
                f"Sound design: Foreground spoken voiceover/dialogue is dominant, "
                f"crystal-clear, and front-of-mix. Background beat ({self.audio_track}) "
                f"is subtly ducked in the background beneath dialogue"
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
            f"[PRESERVATION LOCK]: {self.preservation_lock} | [ISOLATED DIFF]: {self.isolated_diff}"
        )


@dataclass
class CharacterRole:
    role_id: str
    name: str
    description: str
    reference_url: str | None = None
    aesthetic_tags: list[str] = field(default_factory=list)
    voice_style: str = ""


@dataclass
class SceneDirective:
    scene_number: int
    active_roles: list[str]
    action: str
    dialogue: str = ""
    screenplay_text: str | None = None
    audio_cues: str = ""


@dataclass
class MetaPromptTags:
    characters: list[CharacterRole] = field(default_factory=list)
    aesthetic_tags: list[str] = field(default_factory=list)
    environment_tag: str = ""
    camera_lighting_tag: str = ""
    audio_beat: str = ""
    vocal_delivery: str = ""


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

SCREENPLAY_AUDIO_KEYWORDS: set[str] = {
    "audio",
    "sound",
    "music",
    "beat",
    "bgm",
    "sfx",
    "thunder",
    "bass",
    "boom",
    "track",
    "rumble",
    "rumbles",
    "reverb",
    "echo",
    "hiss",
    "synth",
    "drums",
    "screech",
    "whisper",
    "noise",
    "loud",
    "cue",
    "playing",
    "rhythm",
    "melody",
    "vocals",
    "singing",
    "rap",
    "808",
    "drone",
}


def parse_screenplay_script(
    script_text: str, characters: list[CharacterRole] | None = None
) -> dict[str, Any]:
    """Parses line-by-line screenplay text into structured components.

    Format: `CharacterName: (Action description. Audio cue.) "Spoken dialogue."`
    Returns a dictionary with keys: active_roles, action, audio_cues, dialogue.
    """
    if not script_text or not script_text.strip():
        return {
            "active_roles": [],
            "action": "",
            "audio_cues": "",
            "dialogue": "",
        }

    import re

    active_roles: list[str] = []
    action_parts: list[str] = []
    audio_cue_parts: list[str] = []
    dialogue_parts: list[str] = []

    lines = [line.strip() for line in script_text.splitlines() if line.strip()]

    for line in lines:
        speaker_raw: str | None = None

        if ":" in line:
            colon_idx = line.index(":")
            paren_idx = line.find("(")
            quote_idx = line.find('"')
            smart_quote_idx = line.find("“")

            delim_indices = [idx for idx in [paren_idx, quote_idx, smart_quote_idx] if idx != -1]
            first_delim = min(delim_indices) if delim_indices else len(line)

            if colon_idx < first_delim:
                speaker_raw = line[:colon_idx].strip()

        matched_role_id: str | None = None
        if speaker_raw:
            spk_lower = speaker_raw.lower()
            if characters:
                for char in characters:
                    char_role = char.role_id.strip().lower()
                    char_name = char.name.strip().lower()
                    if spk_lower in (char_role, char_name):
                        matched_role_id = char.role_id
                        break
                    if spk_lower in char_name or char_name in spk_lower:
                        matched_role_id = char.role_id
                        break
                    if char_role in spk_lower:
                        matched_role_id = char.role_id
                        break

            role_to_add = matched_role_id if matched_role_id else speaker_raw
            if role_to_add not in active_roles:
                active_roles.append(role_to_add)

        # Parenthetical extraction
        parentheticals = re.findall(r"\((.*?)\)", line)
        for ptext in parentheticals:
            ptext_clean = ptext.strip()
            if not ptext_clean:
                continue
            segments = [s.strip() for s in re.split(r"[.;]", ptext_clean) if s.strip()]
            for seg in segments:
                seg_lower = seg.lower()
                has_audio_kw = any(kw in seg_lower for kw in SCREENPLAY_AUDIO_KEYWORDS)
                is_pure_audio = seg_lower.startswith(
                    ("audio:", "sound:", "bgm:", "sfx:", "cue:")
                ) or (
                    has_audio_kw
                    and not any(
                        w in seg_lower
                        for w in [
                            "standing",
                            "bopping",
                            "walking",
                            "looking",
                            "stepping",
                            "sitting",
                            "gesturing",
                            "head",
                            "wand",
                            "hand",
                            "eye",
                            "face",
                            "wearing",
                            "facing",
                            "running",
                            "moving",
                            "turning",
                        ]
                    )
                )
                if not is_pure_audio and seg not in action_parts:
                    action_parts.append(seg)
                if has_audio_kw and seg not in audio_cue_parts:
                    audio_cue_parts.append(seg)

        # Quoted text extraction
        quotes = re.findall(r'["“]([^"”]+)["”]', line)
        if quotes:
            spoken_text = " ".join(q.strip() for q in quotes if q.strip())
            if spoken_text:
                speaker_display = speaker_raw if speaker_raw else "Speaker"
                dialogue_parts.append(f'{speaker_display}: "{spoken_text}"')

    action_str = ". ".join(action_parts).strip()
    if action_str and not action_str.endswith("."):
        action_str += "."

    audio_cues_str = ". ".join(audio_cue_parts).strip()
    if audio_cues_str and not audio_cues_str.endswith("."):
        audio_cues_str += "."

    dialogue_str = " / ".join(dialogue_parts).strip()

    return {
        "active_roles": active_roles,
        "action": action_str,
        "audio_cues": audio_cues_str,
        "dialogue": dialogue_str,
    }


class PromptOptimizer:
    """Optimizes compiled storyboards into cohesive Gemini Omni Flash directives."""

    def __init__(self, compiler: Any = None) -> None:
        self.compiler = compiler

    def optimize(self, compiled_prompt: str, use_llm: bool = False) -> str:
        """Synthesizes structured block prompts into dense, qualitative directives."""
        if not compiled_prompt or not compiled_prompt.strip():
            return compiled_prompt

        # Tier 1: Normalize quantitative audio mixing terms to qualitative descriptors
        optimized = compiled_prompt.replace(
            "(ducked at 15% volume under dialogue)",
            "(subtly ducked in the background beneath dialogue)",
        ).replace(
            "is quietly ducked at 15% volume in the background",
            "is subtly ducked in the background beneath dialogue",
        )

        # Tier 2: LLM Optimization Pass via Gemini Flash (if requested and client available)
        if use_llm and self.compiler:
            client = getattr(self.compiler, "_flash_regional_client", None) or getattr(
                self.compiler, "_pro_global_client", None
            )
            if client:
                try:
                    system_instruction = (
                        "You are an expert multimodal prompt engineer for Gemini Omni Flash. "
                        "Refine and condense the following structured storyboard prompt into a clear, "
                        "vivid, single-pass generation directive. "
                        "CRITICAL: Keep all [IMAGE ROLES] and [ROLE DEFINITIONS] blocks intact."
                    )
                    response = client.models.generate_content(
                        model=settings.deconstruct_flash_model,
                        contents=f"{system_instruction}\n\n[PROMPT TO OPTIMIZE]:\n{optimized}",
                    )
                    if response and getattr(response, "text", None):
                        llm_out = response.text.strip()
                        if llm_out and "[ROLE DEFINITIONS]" in llm_out:
                            return llm_out
                except Exception as exc:
                    logger.warning(
                        "PromptOptimizer LLM pass failed, using Tier 1 prompt: %s",
                        exc,
                    )

        return optimized


class PromptCompiler:
    def __init__(self, mock_mode: bool = False) -> None:
        self.mock_mode = mock_mode
        self._pro_global_client: Any = None
        self._flash_regional_client: Any = None
        if not self.mock_mode:
            self._init_deconstructor_clients()

    def optimize_prompt_for_omni_flash(self, compiled_prompt: str, use_llm: bool = False) -> str:
        """Optimizes a compiled prompt string for Gemini Omni Flash generation."""
        optimizer = PromptOptimizer(compiler=self)
        return optimizer.optimize(compiled_prompt, use_llm=use_llm)

    def _init_deconstructor_clients(self) -> None:
        try:
            from google import genai
        except ImportError:
            logger.warning(
                "google-genai SDK not available; deconstructor client initialization skipped."
            )
            return

        api_key = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or settings.effective_api_key
        )
        project = os.environ.get(
            "GOOGLE_CLOUD_PROJECT",
            getattr(settings, "google_cloud_project", "hybrid-vertex"),
        )

        try:
            if api_key:
                self._pro_global_client = genai.Client(api_key=api_key)
            else:
                self._pro_global_client = genai.Client(
                    vertexai=True,
                    project=project,
                    location="global",
                )
        except Exception as exc:
            logger.warning("Failed to initialize Tier 1 Pro Global client: %s", exc)

        try:
            if api_key:
                self._flash_regional_client = genai.Client(api_key=api_key)
            else:
                self._flash_regional_client = genai.Client(
                    vertexai=True,
                    project=project,
                    location="us-central1",
                )
        except Exception as exc:
            logger.warning("Failed to initialize Tier 2 Flash Regional client: %s", exc)

    def _try_gemini_deconstruction(
        self, client: Any, model_name: str, concept: str, tier_name: str
    ) -> MetaPromptTags | None:
        if not client:
            return None

        prompt_text = (
            f"Deconstruct the following video parody concept into structured prompt tags:\n"
            f'Concept: "{concept}"\n\n'
            f"Return ONLY a valid JSON object matching this exact schema:\n"
            f"{{\n"
            f'  "characters": [\n'
            f"    {{\n"
            f'      "role_id": "Role A",\n'
            f'      "name": "Character Name",\n'
            f'      "description": "Visual description of character",\n'
            f'      "aesthetic_tags": ["tag1", "tag2"],\n'
            f'      "voice_style": "Voice style description"\n'
            f"    }}\n"
            f"  ],\n"
            f'  "aesthetic_tags": ["tag1", "tag2"],\n'
            f'  "environment_tag": "Environment description",\n'
            f'  "camera_lighting_tag": "Camera & lighting description",\n'
            f'  "audio_beat": "Audio beat description",\n'
            f'  "vocal_delivery": "Vocal delivery description"\n'
            f"}}\n"
        )

        for attempt in range(1, 4):
            try:
                try:
                    from google.genai import types

                    config = types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7,
                    )
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt_text,
                        config=config,
                    )
                except Exception:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt_text,
                    )

                raw_text = getattr(response, "text", "") or ""
                clean_text = raw_text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                if clean_text.startswith("```"):
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()

                data = json.loads(clean_text)

                chars: list[CharacterRole] = []
                for c_data in data.get("characters", []):
                    chars.append(
                        CharacterRole(
                            role_id=c_data.get("role_id", "Role A"),
                            name=c_data.get("name", ""),
                            description=c_data.get("description", ""),
                            reference_url=c_data.get("reference_url"),
                            aesthetic_tags=c_data.get("aesthetic_tags", []),
                            voice_style=c_data.get("voice_style", ""),
                        )
                    )

                return MetaPromptTags(
                    characters=chars,
                    aesthetic_tags=data.get("aesthetic_tags", []),
                    environment_tag=data.get("environment_tag", ""),
                    camera_lighting_tag=data.get("camera_lighting_tag", ""),
                    audio_beat=data.get("audio_beat", ""),
                    vocal_delivery=data.get("vocal_delivery", ""),
                )
            except Exception as exc:
                logger.warning(
                    "%s (%s) attempt %d/3 failed (Quota/Limit/Error): %s",
                    tier_name,
                    model_name,
                    attempt,
                    exc,
                )
                if attempt < 3:
                    time.sleep(2 ** (attempt - 1))
        return None

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
        preset_key = str(style_preset.value if hasattr(style_preset, "value") else style_preset)
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

        motion_desc = (
            f"{raw_prompt.rstrip('.')}. {style_info['motion']}"
            if raw_prompt and raw_prompt.strip()
            else style_info["motion"]
        )

        return CompiledPromptParts(
            subject_anchor=anchor,
            aesthetic_injection=aesthetic,
            environment=env,
            camera_lighting=camera_lighting,
            motion=motion_desc,
            audio_track=audio,
            voiceover=voiceover.strip() if voiceover else "",
            is_silent=is_silent,
            on_screen_text=on_screen_text.strip() if on_screen_text else "",
            drip_props=props_list,
            vibe_intensity=vibe_intensity,
        )

    def compile_prompt(
        self,
        raw_prompt: str = "",
        scene: SceneDirective | dict[str, Any] | None = None,
        screenplay_text: str | None = None,
        characters: list[CharacterRole] | None = None,
        style_preset: StylePreset | str = "90s_rap_video",
        custom_instructions: str = "",
        audio_stem: str | None = None,
        voiceover: str | None = None,
        is_silent: bool = False,
        on_screen_text: str | None = None,
        drip_props: list[str] | str | None = None,
        vibe_intensity: int = 50,
    ) -> CompiledPromptParts:
        script: str | None = screenplay_text
        scene_action: str = ""
        scene_dialogue: str = ""
        scene_audio: str = ""

        if isinstance(scene, SceneDirective):
            if scene.screenplay_text:
                script = str(scene.screenplay_text)
            if scene.action:
                scene_action = str(scene.action)
            if scene.dialogue:
                scene_dialogue = str(scene.dialogue)
            if getattr(scene, "audio_cues", None):
                scene_audio = str(scene.audio_cues)
        elif isinstance(scene, dict):
            sp_text = scene.get("screenplay_text")
            if isinstance(sp_text, str) and sp_text:
                script = sp_text
            act = scene.get("action")
            if isinstance(act, str) and act:
                scene_action = act
            diag = scene.get("dialogue")
            if isinstance(diag, str) and diag:
                scene_dialogue = diag
            aud = scene.get("audio_cues")
            if isinstance(aud, str) and aud:
                scene_audio = aud

        parsed_action = ""
        parsed_audio = ""
        parsed_dialogue = ""

        if script and script.strip():
            parsed = parse_screenplay_script(script, characters=characters)
            parsed_action = parsed.get("action", "")
            parsed_audio = parsed.get("audio_cues", "")
            parsed_dialogue = parsed.get("dialogue", "")

        action_components = [
            comp for comp in [raw_prompt, scene_action, parsed_action] if comp and comp.strip()
        ]
        effective_raw_prompt = (
            ". ".join(action_components) if action_components else "Cinematic shot"
        )

        audio_components = [
            comp for comp in [audio_stem, scene_audio, parsed_audio] if comp and comp.strip()
        ]
        effective_audio_stem = ". ".join(audio_components) if audio_components else None

        dialogue_components = [
            comp for comp in [voiceover, scene_dialogue, parsed_dialogue] if comp and comp.strip()
        ]
        effective_voiceover = " / ".join(dialogue_components) if dialogue_components else None

        return self.compile(
            raw_prompt=effective_raw_prompt,
            style_preset=style_preset,
            custom_instructions=custom_instructions,
            audio_stem=effective_audio_stem,
            voiceover=effective_voiceover,
            is_silent=is_silent,
            on_screen_text=on_screen_text,
            drip_props=drip_props,
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

    def compile_multi_role_prompt(
        self,
        concept: str,
        characters: list[CharacterRole],
        scenes: list[SceneDirective],
        aesthetic_tags: list[str] | None = None,
        environment_tag: str | None = None,
        audio_beat: str | None = None,
        vocal_delivery: str | None = None,
    ) -> str:
        image_role_lines: list[str] = []
        role_lines: list[str] = []
        img_idx = 1

        for char in characters:
            if char.reference_url and char.reference_url.strip():
                name_suffix = f" ({char.name})" if char.name else ""
                image_role_lines.append(
                    f"- [IMAGE {img_idx}]: Reference image for {char.role_id}{name_suffix}."
                )
                img_idx += 1

            style_str = f" [Style: {', '.join(char.aesthetic_tags)}]" if char.aesthetic_tags else ""
            role_lines.append(f"- {char.role_id} ({char.name}): {char.description}{style_str}")

        image_roles_block = ""
        if image_role_lines:
            image_roles_block = "[IMAGE ROLES]\n" + "\n".join(image_role_lines) + "\n\n"

        roles_block = "\n".join(role_lines) if role_lines else "- None"

        aesthetic_parts: list[str] = []
        if concept and concept.strip():
            aesthetic_parts.append(f"Concept: {concept.strip()}")
        if aesthetic_tags:
            aesthetic_parts.append(f"Aesthetic Tags: {', '.join(aesthetic_tags)}")
        if environment_tag and environment_tag.strip():
            aesthetic_parts.append(f"Environment: {environment_tag.strip()}")
        aesthetic_block = "\n".join(aesthetic_parts) if aesthetic_parts else "Default Aesthetic"

        audio_parts: list[str] = []
        if audio_beat and audio_beat.strip():
            audio_parts.append(
                f"Background Beat: {audio_beat.strip()} (subtly ducked in the background beneath dialogue)"
            )
        for char in characters:
            if char.voice_style and char.voice_style.strip():
                audio_parts.append(f"Voice Style ({char.role_id}): {char.voice_style.strip()}")
        if vocal_delivery and vocal_delivery.strip():
            audio_parts.append(f"Vocal Delivery: {vocal_delivery.strip()}")

        scene_lines: list[str] = []
        for scene in scenes:
            scene_num = (
                scene.get("scene_number")
                if isinstance(scene, dict)
                else getattr(scene, "scene_number", None)
            )
            raw_roles = (
                scene.get("active_roles", [])
                if isinstance(scene, dict)
                else getattr(scene, "active_roles", [])
            )
            roles_list: list[str] = (
                [str(r) for r in raw_roles] if isinstance(raw_roles, (list, tuple)) else []
            )
            roles_str = ", ".join(roles_list)

            sp_text = (
                (scene.get("screenplay_text") or scene.get("screenplay_script"))
                if isinstance(scene, dict)
                else (
                    getattr(scene, "screenplay_text", None)
                    or getattr(scene, "screenplay_script", None)
                )
            )

            if sp_text and isinstance(sp_text, str) and sp_text.strip():
                parsed = parse_screenplay_script(sp_text, characters=characters)
                if parsed.get("audio_cues"):
                    audio_parts.append(f"Scene {scene_num} Audio Cues: {parsed['audio_cues']}")
                indented_script = "\n".join(f"  {line}" for line in sp_text.strip().splitlines())
                scene_lines.append(
                    f"- Scene {scene_num} [{roles_str}] (Screenplay Script):\n{indented_script}"
                )
            else:
                action = (
                    scene.get("action", "")
                    if isinstance(scene, dict)
                    else getattr(scene, "action", "")
                )
                dialogue = (
                    scene.get("dialogue", "")
                    if isinstance(scene, dict)
                    else getattr(scene, "dialogue", "")
                )
                diag_str = (
                    f' | Dialogue: "{dialogue}"' if dialogue and str(dialogue).strip() else ""
                )
                scene_lines.append(f"- Scene {scene_num} [{roles_str}]: {action}{diag_str}")

        audio_block = "\n".join(audio_parts) if audio_parts else "Default Audio & Voice Direction"
        scenes_block = "\n".join(scene_lines) if scene_lines else "- No scenes"

        return (
            f"{image_roles_block}"
            f"[ROLE DEFINITIONS]\n{roles_block}\n\n"
            f"[AESTHETIC INJECTION]\n{aesthetic_block}\n\n"
            f"[AUDIO & VOCAL DIRECTION]\n{audio_block}\n\n"
            f"[STORYBOARD SEQUENCE]\n{scenes_block}"
        )

    def compile_storyboard(
        self,
        concept: str,
        characters: list[CharacterRole],
        scenes: list[SceneDirective],
        aesthetic_tags: list[str] | None = None,
        environment_tag: str | None = None,
        audio_beat: str | None = None,
        vocal_delivery: str | None = None,
    ) -> str:
        return self.compile_multi_role_prompt(
            concept=concept,
            characters=characters,
            scenes=scenes,
            aesthetic_tags=aesthetic_tags,
            environment_tag=environment_tag,
            audio_beat=audio_beat,
            vocal_delivery=vocal_delivery,
        )

    def deconstruct_concept(self, concept: str) -> MetaPromptTags:
        """Parses concept using 3-tier deconstructor engine."""
        if self.mock_mode:
            return self._deconstruct_fallback(concept)

        if self._pro_global_client:
            res = self._try_gemini_deconstruction(
                client=self._pro_global_client,
                model_name=settings.deconstruct_pro_model,
                concept=concept,
                tier_name="Tier 1 Pro Global",
            )
            if res is not None:
                return res

        if self._flash_regional_client:
            res = self._try_gemini_deconstruction(
                client=self._flash_regional_client,
                model_name=settings.deconstruct_flash_model,
                concept=concept,
                tier_name="Tier 2 Flash Regional",
            )
            if res is not None:
                return res

        logger.info(
            "Tier 1 & Tier 2 deconstruction unavailable or failed. Using Tier 3 heuristic fallback."
        )
        return self._deconstruct_fallback(concept)

    def _deconstruct_fallback(self, concept: str) -> MetaPromptTags:
        """Parses open-ended parody concept shorthand into structured MetaPromptTags with CharacterRoles, Aesthetic Tags, Environment, Camera/Lighting, Audio Beat, and Vocal Delivery."""
        lower = concept.lower().strip()

        def get_char_tags(k: str) -> list[str]:
            if any(t in lower for t in ("trap", "atlanta", "808", "rap", "hip-hop")):
                tag_map = {
                    "harry": ["Red Gucci Tracksuit", "Cartier Glasses"],
                    "draco": ["Platinum Slicked Hair", "Diamond Iced-Out Chain"],
                    "snape": ["Black Puffer Jacket", "Cuban Link Chain"],
                    "dumbledore": ["Oversized Silk Robes", "Half-Moon Cartier Glasses"],
                    "voldemort": ["Chalk-White Techwear", "Diamond Snake Medallion"],
                    "ramsay": ["Diamond Chef Knife Chain", "Designer White Streetwear"],
                    "julia": ["Vintage Pearl Medallion", "Retro Silk Apron"],
                    "samurai": ["Diamond Katana Chain", "Streetwear Samurai Armor"],
                    "ninja": ["Iced-Out Ninja Mask", "Tactical Techwear"],
                }
                return tag_map.get(k, ["Vintage Streetwear", "Diamond Chain"])
            elif any(
                t in lower
                for t in (
                    "cyberpunk",
                    "neon",
                    "futuristic",
                    "iron chef",
                    "samurai",
                    "ninja",
                    "arcade",
                )
            ):
                tag_map = {
                    "harry": [
                        "Holographic Wire-Rim Glasses",
                        "LED-Lined Techwear Robes",
                    ],
                    "draco": ["Silver Techwear Coat", "Holographic Visor"],
                    "snape": ["High-Collar Dark Techwear", "Holographic Cyber Coat"],
                    "dumbledore": ["Neon-Embroidered Robes", "Holographic Spectacles"],
                    "voldemort": ["Chrome Cyber Armor", "Serpentine Neon Glow"],
                    "ramsay": ["Holographic Chef Jacket", "Laser Thermal Blade"],
                    "julia": ["Cybernetic Apron", "Holographic Visor"],
                    "samurai": ["Glowing LED Armor", "Energy Katana"],
                    "ninja": ["Chrome Cyber Mask", "Stealth Holographic Visor"],
                }
                return tag_map.get(k, ["Futuristic Techwear", "Holographic Visor"])
            elif any(t in lower for t in ("anime", "vhs", "lo-fi")):
                tag_map = {
                    "harry": ["Cel-Shaded Wire-Rim Glasses", "Retro Anime Robes"],
                    "draco": ["Cel-Shaded Platinum Hair", "Silver-Trimmed Uniform"],
                    "snape": ["Cel-Shaded Dark Cloak", "Analog Grain Filter"],
                    "dumbledore": ["Vintage Cel-Shaded Robes", "Flowing Silver Beard"],
                    "voldemort": ["Chalk-White Cel-Shading", "Serpentine Aura"],
                    "ramsay": ["Cel-Shaded Chef Coat", "Flame Aura"],
                    "julia": ["Retro Cel-Shaded Apron", "Vintage Kitchen Attire"],
                    "samurai": ["Cel-Shaded Samurai Armor", "Energy Katana"],
                    "ninja": ["Cel-Shaded Ninja Garb", "Stealth Visor"],
                }
                return tag_map.get(k, ["Cel-Shaded Styling", "Retro Headband"])
            else:
                tag_map = {
                    "harry": ["Red Gucci Tracksuit", "Cartier Glasses"],
                    "draco": ["Tailored Silver-Trimmed Robes", "Platinum Slicked Hair"],
                    "snape": ["Flowing Black Cloak", "Severe Dark Attire"],
                    "dumbledore": ["Ornate Wizard Robes", "Half-Moon Spectacles"],
                    "voldemort": ["Chalk-White Silk Robes", "Serpentine Aura"],
                    "ramsay": ["Crisp White Chef Jacket", "Fiery Apron"],
                    "julia": ["Classic Vintage Apron", "Warm Retro Styling"],
                    "samurai": ["Glowing LED Armor", "Energy Katana"],
                    "ninja": ["Chrome Cyber Mask", "Stealth Visor"],
                }
                return tag_map.get(k, ["Stylized Wardrobe", "Cinematic Attire"])

        def get_char_voice(k: str) -> str:
            if any(t in lower for t in ("trap", "atlanta", "808", "rap", "hip-hop")):
                voice_map = {
                    "harry": "Fast-paced confident Atlanta rap flow with autotune",
                    "draco": "Pompous, cynical British drawl with aggressive rap cadence",
                    "snape": "Deep sarcastic monotone rap cadence with heavy bass resonance",
                    "dumbledore": "Smooth authoritative elder rap flow with melodic reverb",
                    "voldemort": "Hissing raspy dark trap cadence with sinister whisper",
                    "ramsay": "Aggressive rapid-fire British rap delivery with fiery staccato",
                    "julia": "Cheerful rhythmic vintage cadence with operatic flair",
                    "samurai": "Stoic disciplined hip-hop cadence with sharp precision",
                    "ninja": "Fast whisper-rap flow with rhythmic syncopation",
                }
                return voice_map.get(k, "Fast-paced rhythmic rap cadence with confident delivery")
            elif any(
                t in lower
                for t in (
                    "cyberpunk",
                    "neon",
                    "futuristic",
                    "iron chef",
                    "samurai",
                    "ninja",
                    "arcade",
                )
            ):
                voice_map = {
                    "harry": "Youthful tech-filtered voice with energetic synthesized cadence",
                    "draco": "Cold aristocratic drawl with subtle robotic modulation",
                    "snape": "Deep resonant cyborg baritone with metallic vocoder edge",
                    "dumbledore": "Resonant holographic elder voice with ethereal synth harmonic",
                    "voldemort": "Sinister digital rasp with glitchy pitch shift",
                    "ramsay": "High-intensity barking commands with sharp electronic vocoding",
                    "julia": "Warm vintage tone with cheerful cybernetic filter",
                    "samurai": "Stoic synthesized warrior cadence with crisp electronic articulation",
                    "ninja": "Stealth filtered whisper with robotic modulation",
                }
                return voice_map.get(
                    k, "Futuristic vocoded speech with crisp electronic articulation"
                )
            elif any(t in lower for t in ("anime", "vhs", "lo-fi")):
                voice_map = {
                    "harry": "Energetic youthful anime protagonist voice with passionate delivery",
                    "draco": "Smug aristocratic rival voice with dramatic anime inflection",
                    "snape": "Brooding dramatic antagonist voice with slow deliberate pacing",
                    "dumbledore": "Wise eccentric mentor voice with warm melodic phrasing",
                    "voldemort": "Theatrical villainous rasp with dramatic echo",
                    "ramsay": "Fiery competitive anime chef delivery with explosive shouts",
                    "julia": "Whimsical motherly culinary host voice with cheerful vintage lilt",
                    "samurai": "Deep honorable warrior voice with classic anime dub inflection",
                    "ninja": "Quiet masked assassin voice with sharp dramatic whispers",
                }
                return voice_map.get(k, "Expressive retro anime dub voice with dramatic flair")
            else:
                voice_map = {
                    "harry": "Youthful British accent with determined heroic cadence",
                    "draco": "Aristocratic British drawl with sneering sarcastic tone",
                    "snape": "Deep cynical British drawl with slow menacing pauses",
                    "dumbledore": "Gentle whimsical British elder voice with grandfatherly warmth",
                    "voldemort": "Cold sibilant whisper with chilling theatrical intensity",
                    "ramsay": "Fiery passionate British chef voice with explosive intensity",
                    "julia": "High-pitched cheerful mid-Atlantic accent with warm enthusiastic lilt",
                    "samurai": "Stoic grounded warrior voice with focused intensity",
                    "ninja": "Hushed tactical voice with crisp deliberate phrasing",
                }
                return voice_map.get(
                    k, "Cinematic theatrical voice with distinct expressive delivery"
                )

        # 1. Character Extraction
        chars: list[CharacterRole] = []

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
                        role_id=_role_label(idx),
                        name=name,
                        description=desc,
                        aesthetic_tags=get_char_tags(k),
                        voice_style=get_char_voice(k),
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
                        aesthetic_tags=get_char_tags(name_a.lower()),
                        voice_style=get_char_voice(name_a.lower()),
                    )
                )
                chars.append(
                    CharacterRole(
                        role_id="Role B",
                        name=name_b.title(),
                        description=f"{name_b.title()}, a compelling rival character with bold visual presence",
                        aesthetic_tags=get_char_tags(name_b.lower()),
                        voice_style=get_char_voice(name_b.lower()),
                    )
                )
            else:
                chars.append(
                    CharacterRole(
                        role_id="Role A",
                        name="Lead Subject",
                        description="A distinct cinematic character with expressive facial features and stylized attire",
                        aesthetic_tags=get_char_tags("lead"),
                        voice_style=get_char_voice("lead"),
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
            vocal_delivery = "High-energy back-and-forth rap battle delivery with synchronized lip-sync and punchy cadence"
            env_tag = (
                "Gothic Hogwarts courtyard lit by neon stage lights and smoky haze"
                if ("harry" in lower or "draco" in lower or "hogwarts" in lower or "snape" in lower)
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
            vocal_delivery = (
                "Futuristic vocoded dialogue with sharp synthesized delivery and spatial reverb"
            )
            env_tag = (
                "Futuristic neon kitchen colosseum with holographic spectator screens"
                if ("chef" in lower or "ramsay" in lower or "julia" in lower or "kitchen" in lower)
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
            vocal_delivery = "Expressive 80s anime dub voiceover with dramatic dynamic range and emotional emphasis"
            env_tag = "Retro 80s anime cityscape bathed in sunset pastel lighting"
            cam_tag = "Retro 4:3 VHS tape framing with chromatic aberration and warm bloom"
        else:
            aesthetic_tags = [
                "High-Contrast Cinematic Parody",
                "Stylized Wardrobe",
                "Dramatic Lighting",
            ]
            audio_beat = "120 BPM Cinematic Beat"
            vocal_delivery = "Crisp cinematic dialogue with natural conversational timing and clear studio projection"
            env_tag = "Atmospheric stage set with dramatic directional lighting and smoke effects"
            cam_tag = "Cinematic 16:9 tracking shot with balanced ambient lighting and crisp depth of field"

        return MetaPromptTags(
            characters=chars,
            aesthetic_tags=aesthetic_tags,
            environment_tag=env_tag,
            camera_lighting_tag=cam_tag,
            audio_beat=audio_beat,
            vocal_delivery=vocal_delivery,
        )
