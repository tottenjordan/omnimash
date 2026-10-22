from __future__ import annotations

import json
import logging
import re
import time
from typing import TYPE_CHECKING, Any


from omnimash.config import settings
from omnimash.prompts.character_roles import CharacterRole
from omnimash.prompts.image_tags import (
    build_character_image_ref_tags,
    get_character_identifier,
    replace_character_in_text_image_tags,
    sort_characters_by_role_id,
)
from omnimash.prompts.models import (
    CompiledDeltaPrompt,
    CompiledPromptParts,
    DeconstructedCharacterSchema,
    DeconstructedConceptSchema,
    DeconstructedSceneSchema,
    MetaPromptTags,
    SceneDirective,
)
from omnimash.prompts.optimizer import PromptOptimizer
from omnimash.prompts.genai_client import get_genai_client
from omnimash.prompts.journey3 import (
    CumulativeShotState,
    compile_journey3_shot_prompt,
    validate_compiled_prompt,
)
from omnimash.prompts.parody import (
    REAL_NAME_MAPPINGS,
    REAL_NAME_PARODY_MAP,
    _COMPILED_PARODY_PATTERNS,
    sanitize_real_names,
)
from omnimash.prompts.screenplay import (
    MAX_CONCEPT_CHARS,
    MAX_SCREENPLAY_CHARS,
    SCREENPLAY_AUDIO_KEYWORDS,
    parse_directors_notes,
    parse_screenplay_script,
    parse_timecoded_script,
    validate_prompt_input_lengths,
)
from omnimash.prompts.voice import (
    apply_conversational_voice_edits,
    enrich_timeline_dialogue_speakers,
    ensure_character_voice_style,
)

if TYPE_CHECKING:
    from omnimash.prompts.taxonomy import StylePreset

GEMINI_OMNI_FLASH_INSTR: str = """\
GEMINI OMNI FLASH PROMPT BEST PRACTICES & COMPILER SPECIFICATION

Gemini Omni Flash 1.1 (gemini-omni-1.1-flash-preview / gemini-omni-flash-preview) is the sole video+audio generation engine across all scenes, initial clips, and conversational interaction diffs in Omnimash.

1. 4-Block Meta-Prompt Architecture (4-Block Anchor & Inject):
   - Block 1: ### INPUT ROLES & REFERENCES
     Declares all image, character, product, and style inputs using strict positional tags (<IMAGE_REF_0>@Image1, <IMAGE_REF_1>@Image2, <FIRST_FRAME>@KeyframeSeed, <LAST_FRAME>@EndKeyframe, etc.).
   - Block 2: ### CHARACTER PROFILES
     Defines detailed visual features, aesthetic wardrobe tags, and vocal style parameters mapped symmetrically to each input role identifier. When a character reference sheet (<IMAGE_REF_0>@Image1) is attached, enforce Zero Wardrobe Redundancy by omitting conflicting prose clothing descriptions so visual identity remains locked to the reference sheet.
   - Block 3: ### SCENE INSTRUCTIONS
     Establishes overall visual environment, camera motion/lighting directives, title card overlays, and dual-layer audio ducking rules.
     - Dual-Layer Audio Ducking: Background beat tracks MUST use an 'instrumental' prefix (e.g. 'instrumental 140 BPM Heavy 808 Trap') and explicitly state: "Ensure the background music ducks under the spoken dialogue so the voice is clear, front-and-center, and intelligible."
     - On-Screen Displayed Text / Title Card: Explicitly formats diegetic or non-diegetic text overlays as:
       - On-Screen Displayed Text / Title Card: "TITLE_TEXT" (Subtitle: "SUBTITLE_TEXT")
   - Block 4: ### TIMELINE
     Chronological time-coded directives ([0-3s], [3-6s], [6-10s]) enforcing a single continuous shot without jump cuts, integrating theatrical spoken dialogue (Role A [Voice Style: ...]: "Line") and off-screen narrator tags ((off-screen)) directly into temporal sequence blocks.

2. Multimodal Reference Anchors, Dual Keyframes & Stateful Upscaling:
   - Reference image inputs use clean ordinal anchors such as @Image1, @Image2, @Image3, and keyframe image anchors like <FIRST_FRAME>@KeyframeSeed and <LAST_FRAME>@EndKeyframe.
   - Never embed direct file paths, cloud storage URLs (gs://), or raw HTTP URLs within the prompt string itself; map them via input role reference headers.
   - Conversational Diffs use [PRESERVATION LOCK] & [ISOLATED DIFF] with "Keep everything else the same." Re-anchor via a fresh keyframe seed after 4–6 conversational diff turns.
   - Use 360p Draft-First exploration and stateful 4K Master upscaling via previous_interaction_id ("Upscale to master quality. Keep everything else the same.").

3. Safety Sanitization & Parody Abstraction:
   - Real public figure and celebrity names are automatically sanitized into descriptive visual parody role identifiers.
   - Trademarked items and brand names are abstracted into generic visual descriptions to ensure policy compliance while preserving stylistic aesthetics.
"""


logger = logging.getLogger(__name__)

__all__ = [
    "AESTHETIC_SIGNIFIERS",
    "CHARACTER_LORE_ANCHORS",
    "CompiledDeltaPrompt",
    "CompiledPromptParts",
    "CumulativeShotState",
    "DeconstructedCharacterSchema",
    "DeconstructedConceptSchema",
    "DeconstructedSceneSchema",
    "GEMINI_OMNI_FLASH_INSTR",
    "MAX_CONCEPT_CHARS",
    "MAX_SCREENPLAY_CHARS",
    "MetaPromptTags",
    "PromptCompiler",
    "PromptOptimizer",
    "REAL_NAME_MAPPINGS",
    "REAL_NAME_PARODY_MAP",
    "SCREENPLAY_AUDIO_KEYWORDS",
    "SceneDirective",
    "_COMPILED_PARODY_PATTERNS",
    "apply_conversational_voice_edits",
    "build_character_image_ref_tags",
    "compile_journey3_shot_prompt",
    "enrich_timeline_dialogue_speakers",
    "ensure_character_voice_style",
    "get_character_identifier",
    "parse_directors_notes",
    "parse_screenplay_script",
    "parse_timecoded_script",
    "replace_character_in_text_image_tags",
    "sanitize_real_names",
    "sort_characters_by_role_id",
    "validate_and_repair_role_bindings",
    "validate_compiled_prompt",
    "validate_prompt_input_lengths",
]


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
    "blockbuster_movie_trailer": {
        "wardrobe": "dramatic cinematic costume with heavy atmospheric weathering, metallic armor accents, or dark velvet cape",
        "camera": "In a single continuous shot. High-contrast anamorphic widescreen 2.39:1, dramatic volumetric rim lighting, lens flares, and epic slow-motion tracking shot",
        "motion": "epic slow-motion heroic stance with dynamic embers and smoke particles floating in the air for 10 seconds",
        "audio": "Deep cinematic trailer braam horn, rising orchestral risers, thunderous sub-bass drop, and epic theatrical soundscape",
    },
}


def validate_and_repair_role_bindings(
    compiled_prompt: str,
    characters: list[CharacterRole] | None = None,
) -> str:
    """Validates and repairs role bindings in a compiled 4-block Omni Flash prompt.

    1. Extracts declared `Role X` identifiers and their `<IMAGE_REF_N>` tags from
       `characters` and `### CHARACTER PROFILES`.
    2. Replaces any empty `- Scene N []:` or `- [0-10s] Scene N []:` headers in
       `### TIMELINE` with the declared active roles and their `<IMAGE_REF_N>` tags.
    3. Remaps any unbound `Role <Y>` references (e.g., `Role B` when only `Role C`
       and `Role A` are declared) to a declared role and attaches its `<IMAGE_REF_N>`
       tag where appropriate.
    """
    if not compiled_prompt or not compiled_prompt.strip():
        return compiled_prompt

    declared_roles: list[str] = []
    role_to_tag: dict[str, str] = {}

    if characters:
        _, _, char_tag_map = build_character_image_ref_tags(
            characters=characters,
            starting_index=1,
            has_keyframe_seed=("<FIRST_FRAME>" in compiled_prompt),
            enable_sanitization=False,
        )
        for char in characters:
            if getattr(char, "is_offscreen_narrator", False):
                continue
            img_role = (
                getattr(char, "image_role", "Character Reference")
                if not isinstance(char, dict)
                else char.get("image_role", "Character Reference")
            )
            if img_role in (
                "Starting Frame",
                "Keyframe Seed Anchor",
                "Ending Frame",
                "Keyframe Last Anchor",
            ):
                continue
            c_id = get_character_identifier(char, enable_sanitization=False, use_role_id=True)
            if c_id and c_id not in declared_roles:
                declared_roles.append(c_id)
            tag = char_tag_map.get(c_id)
            if tag:
                role_to_tag[c_id] = tag

    # Also parse ### CHARACTER PROFILES for explicit `- Role X <IMAGE_REF_N>:` lines
    profile_matches = re.findall(
        r"^-\s*(Role\s+[A-Za-z0-9_]+)(?:\s+(<IMAGE_REF_\d+>))?\s*:",
        compiled_prompt,
        flags=re.MULTILINE,
    )
    for r_id, r_tag in profile_matches:
        r_clean = re.sub(r"\s+", " ", r_id.strip())
        if r_clean not in declared_roles:
            declared_roles.append(r_clean)
        if r_tag:
            role_to_tag[r_clean] = r_tag.strip()

    if not declared_roles:
        return compiled_prompt

    # Build active roles header string (e.g. "Role C <IMAGE_REF_1>, Role A <IMAGE_REF_0>")
    active_header_items: list[str] = []
    for r_id in declared_roles:
        tag = role_to_tag.get(r_id, "")
        active_header_items.append(f"{r_id} {tag}".strip())
    active_header_str = ", ".join(active_header_items)

    repaired = compiled_prompt

    # 1. Repair empty `- Scene N []:` or `- [0-10s] Scene N []:` headers
    if active_header_str:
        repaired = re.sub(
            r"(-\s*(?:\[[^\]]+\]\s*)?Scene\s+\d+\s*)\[\s*\]",
            rf"\1[{active_header_str}]",
            repaired,
        )

    # 2. Identify unbound `Role X` mentions outside CHARACTER PROFILES
    all_role_mentions = re.findall(r"\bRole\s+[A-Z0-9]\b", repaired)
    declared_set = {r.lower(): r for r in declared_roles}
    unbound_roles: list[str] = []
    for mention in all_role_mentions:
        norm = re.sub(r"\s+", " ", mention.strip())
        if norm.lower() not in declared_set and norm not in unbound_roles:
            unbound_roles.append(norm)

    if unbound_roles:
        # Prefer mapping unbound roles to declared roles that are least mentioned in TIMELINE/SCENE INSTRUCTIONS,
        # or fallback to declared roles in order.
        timeline_split = repaired.split("### SCENE INSTRUCTIONS", 1)
        body_text = timeline_split[1] if len(timeline_split) > 1 else repaired

        candidate_roles = sorted(
            declared_roles,
            key=lambda r: len(re.findall(rf"\b{re.escape(r)}\b", body_text)),
        )
        for idx, unbound in enumerate(unbound_roles):
            target_role = candidate_roles[idx % len(candidate_roles)]
            target_tag = role_to_tag.get(target_role, "")
            target_with_tag = f"{target_role} {target_tag}".strip()

            # Replace `Role B:` in dialogue speaker positions with `Role C <IMAGE_REF_1>:`
            repaired = re.sub(
                rf"\b{re.escape(unbound)}\b(?=\s*:)",
                target_with_tag,
                repaired,
            )
            # Replace remaining `Role B` mentions with `Role C <IMAGE_REF_1>` if not already followed by <IMAGE_REF_
            repaired = re.sub(
                rf"\b{re.escape(unbound)}\b(?!\s*<IMAGE_REF_)",
                target_with_tag,
                repaired,
            )

    return repaired


class PromptCompiler:
    def __init__(self, mock_mode: bool | None = None) -> None:
        from omnimash.config import settings

        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self._pro_global_client: Any = None
        self._flash_regional_client: Any = None
        if not self.mock_mode:
            self._init_deconstructor_clients()

    def optimize_prompt_for_omni_flash(self, compiled_prompt: str, use_llm: bool = False) -> str:
        """Optimizes a compiled prompt string for Gemini Omni Flash generation."""
        optimizer = PromptOptimizer(compiler=self)
        return optimizer.optimize(compiled_prompt, use_llm=use_llm)

    def _init_deconstructor_clients(self) -> None:
        self._pro_global_client = get_genai_client(location="global")
        self._flash_regional_client = get_genai_client(
            location=getattr(settings, "gemini_location", "global")
        )

    @staticmethod
    def _ensure_temporal_micro_beats(
        action_text: str,
        char_label: str = "Role A",
        env_tag: str = "",
        cam_tag: str = "",
    ) -> str:
        clean = (action_text or "").strip()
        if "[0-3s]" in clean and "[3-6s]" in clean and "[6-10s]" in clean:
            return clean
        env_phrase = f" in {env_tag}" if env_tag else ""
        cam_phrase = f" under {cam_tag}" if cam_tag else ""
        beat_2_default = f"[3-6s] {char_label} escalates the performance with dynamic kinetic motion{cam_phrase}."
        beat_3_default = (
            f"[6-10s] {char_label} locks into a high-impact climactic pose as lighting peaks."
        )
        if "[0-3s]" in clean:
            result = clean.rstrip(".") + "."
        else:
            stripped_leading = re.sub(r"^\[\d+(?:\.\d+)?-\d+(?:\.\d+)?s?\]\s*", "", clean).rstrip(
                "."
            )
            base_action = (
                stripped_leading
                if stripped_leading
                else f"{char_label} enters the frame{env_phrase}"
            )
            result = f"[0-3s] {base_action}."
        if "[3-6s]" not in result:
            result = f"{result} {beat_2_default}"
        if "[6-10s]" not in result:
            result = f"{result} {beat_3_default}"
        return result

    @staticmethod
    def _synthesize_scene_and_script_defaults(
        concept: str,
        chars: list[CharacterRole],
        aesthetic_tags: list[str],
        env_tag: str,
        cam_tag: str,
        audio_beat: str,
    ) -> tuple[str, str, list[SceneDirective], str]:
        clean_concept = (concept or "").strip() or "Cinematic parody scene"
        active_roles = [c.role_id for c in chars] or ["Role A"]
        if len(chars) >= 2:
            char_a = f"{chars[0].role_id} ({chars[0].name})"
            char_b = f"{chars[1].role_id} ({chars[1].name})"
            beat_1_desc = (
                f"Establishing tracking shot in {env_tag} as {char_a} steps forward into the spotlight "
                f"while {char_b} locks eyes from across the set ({clean_concept})."
            )
            beat_2_desc = (
                f"{char_a} gestures emphatically toward the lens as {char_b} counters "
                f"with kinetic energy under {cam_tag}."
            )
            beat_3_desc = (
                f"Both {char_a} and {char_b} hit a synchronized high-impact climactic pose "
                f"as atmospheric rim lighting peaks."
            )
            dialogue_line = (
                f'{chars[0].name}: "Watch the masterclass unfold right now!" / '
                f'{chars[1].name}: "Turn the energy up, this stage is mine!"'
            )
        else:
            lead = (
                chars[0]
                if chars
                else CharacterRole(
                    role_id="Role A",
                    name="Lead Subject",
                    description="A distinct cinematic character",
                )
            )
            char_a = f"{lead.role_id} ({lead.name})"
            beat_1_desc = (
                f"Establishing tracking shot in {env_tag} as {char_a} enters frame and commands "
                f"the spotlight ({clean_concept})."
            )
            beat_2_desc = (
                f"{char_a} performs expressive dynamic motion toward the camera under {cam_tag}."
            )
            beat_3_desc = (
                f"{char_a} locks into a bold hero resolution pose as volumetric rim lights peak."
            )
            dialogue_line = f'{lead.name}: "Every beat hits different when you own the frame!"'

        action_beats = f"[0-3s] {beat_1_desc} [3-6s] {beat_2_desc} [6-10s] {beat_3_desc}"
        screenplay_script = (
            f"[0-3s]\nACTION: {beat_1_desc}\nAUDIO: {audio_beat}\n\n"
            f"[3-6s]\nACTION: {beat_2_desc}\nAUDIO: {audio_beat}\n\n"
            f"[6-10s]\nACTION: {beat_3_desc}\nAUDIO: {audio_beat}\nDIALOGUE: {dialogue_line}"
        )
        char_summary = ", ".join(f"{c.name} ({c.description})" for c in chars)
        keyframe_image_prompt = (
            f"Cinematic 16:9 keyframe anchor for '{clean_concept}': {char_summary} in {env_tag}. "
            f"Style: {', '.join(aesthetic_tags)}. Camera & Lighting: {cam_tag}."
        )
        scenes = [
            SceneDirective(
                scene_number=1,
                active_roles=active_roles,
                action=action_beats,
                dialogue=dialogue_line,
                audio_cues=audio_beat,
                timecode="0-10s",
                duration_seconds=10.0,
            )
        ]
        return keyframe_image_prompt, screenplay_script, scenes, dialogue_line

    def _try_gemini_deconstruction(
        self, client: Any, model_name: str, concept: str, tier_name: str
    ) -> MetaPromptTags | None:
        if not client:
            return None

        system_instruction = (
            "You are an AI Director and cinematic video concept deconstructor for Gemini Omni Flash 1.1. "
            "Transform any minimal 1-sentence concept into a complete production specification: "
            "1. Characters (Role A, Role B, etc.) with detailed visual descriptions, wardrobe aesthetic_tags, and voice_style. "
            "2. Global aesthetic_tags, environment_tag, camera_lighting_tag (single continuous shot, no scene cuts), audio_beat (with BPM), and vocal_delivery. "
            "3. keyframe_image_prompt: A vivid starting keyframe image generation prompt anchoring subjects, wardrobe, lighting, and setting. "
            '4. screenplay_script and scenes: Choreograph a 10-second continuous shot explicitly structured into [0-3s], [3-6s], and [6-10s] micro-action beats with theatrical spoken dialogue (Speaker: "Line").'
        )
        prompt_text = (
            f"Deconstruct and expand the following minimal video concept into optimal structured prompt tags, keyframe image prompt, screenplay script, and [0-3s] / [3-6s] / [6-10s] scene directives:\n"
            f'Concept: "{concept}"\n\n'
            f"Provide intuitive vision defaults for wardrobe, voice style, environment lighting, camera motion, aspect ratio, audio beat, vocal delivery, keyframe_image_prompt, screenplay_script, and scenes with [0-3s], [3-6s], and [6-10s] micro-action beats and theatrical dialogue."
        )

        for attempt in range(1, 4):
            try:
                from google.genai import types

                # Enforce Structured Outputs via response_schema and system_instruction
                # Source: https://ai.google.dev/gemini-api/docs/structured-output?lang=python
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=DeconstructedConceptSchema,
                )
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt_text,
                    config=config,
                )

                parsed_obj = getattr(response, "parsed", None)
                if isinstance(parsed_obj, DeconstructedConceptSchema):
                    data = parsed_obj.model_dump()
                elif isinstance(parsed_obj, dict):
                    data = DeconstructedConceptSchema.model_validate(parsed_obj).model_dump()
                else:
                    raw_text = getattr(response, "text", "") or ""
                    clean_text = raw_text.strip()
                    if clean_text.startswith("```json"):
                        clean_text = clean_text[7:]
                    if clean_text.startswith("```"):
                        clean_text = clean_text[3:]
                    if clean_text.endswith("```"):
                        clean_text = clean_text[:-3]
                    clean_text = clean_text.strip()
                    raw_dict = json.loads(clean_text)
                    data = DeconstructedConceptSchema.model_validate(raw_dict).model_dump()

                fallback_tags = self._deconstruct_fallback(concept)

                chars: list[CharacterRole] = []
                raw_chars = data.get("characters", [])
                if not raw_chars:
                    chars = fallback_tags.characters
                else:
                    for idx, c_data in enumerate(raw_chars):
                        fb_char = (
                            fallback_tags.characters[idx]
                            if idx < len(fallback_tags.characters)
                            else None
                        )
                        c_aesthetic = c_data.get("aesthetic_tags", [])
                        if not c_aesthetic and fb_char:
                            c_aesthetic = fb_char.aesthetic_tags
                        if not c_aesthetic:
                            c_aesthetic = ["Stylized Wardrobe", "Cinematic Attire"]

                        c_voice = c_data.get("voice_style", "")
                        if not c_voice and fb_char:
                            c_voice = fb_char.voice_style
                        if not c_voice:
                            c_voice = "Cinematic theatrical voice with distinct expressive delivery"

                        chars.append(
                            CharacterRole(
                                role_id=c_data.get("role_id", f"Role {chr(65 + idx)}"),
                                name=c_data.get(
                                    "name",
                                    fb_char.name if fb_char else "Lead Subject",
                                ),
                                description=c_data.get(
                                    "description",
                                    fb_char.description
                                    if fb_char
                                    else "A distinct cinematic character",
                                ),
                                reference_url=c_data.get("reference_url"),
                                aesthetic_tags=c_aesthetic,
                                voice_style=c_voice,
                            )
                        )

                aesthetic_tags = data.get("aesthetic_tags") or fallback_tags.aesthetic_tags
                env_tag = data.get("environment_tag") or fallback_tags.environment_tag
                cam_tag = data.get("camera_lighting_tag") or fallback_tags.camera_lighting_tag
                audio_beat = data.get("audio_beat") or fallback_tags.audio_beat
                vocal_delivery = data.get("vocal_delivery") or fallback_tags.vocal_delivery

                synth_keyframe, synth_script, synth_scenes, synth_dialogue = (
                    self._synthesize_scene_and_script_defaults(
                        concept=concept,
                        chars=chars,
                        aesthetic_tags=aesthetic_tags,
                        env_tag=env_tag,
                        cam_tag=cam_tag,
                        audio_beat=audio_beat,
                    )
                )

                keyframe_image_prompt = (
                    str(data.get("keyframe_image_prompt") or "").strip() or synth_keyframe
                )
                raw_script = str(data.get("screenplay_script") or "").strip()
                if (
                    raw_script
                    and "[0-3s]" in raw_script
                    and "[3-6s]" in raw_script
                    and "[6-10s]" in raw_script
                ):
                    screenplay_script = raw_script
                else:
                    screenplay_script = synth_script

                active_role_ids = [c.role_id for c in chars] or ["Role A"]
                char_label = (
                    f"{chars[0].role_id} ({chars[0].name})" if chars else "Role A (Lead Subject)"
                )

                scenes: list[SceneDirective] = []
                raw_scenes = data.get("scenes", [])
                if raw_scenes:
                    for s_idx, s_data in enumerate(raw_scenes):
                        s_action = self._ensure_temporal_micro_beats(
                            str(s_data.get("action") or ""),
                            char_label=char_label,
                            env_tag=env_tag,
                            cam_tag=cam_tag,
                        )
                        s_dialogue = str(s_data.get("dialogue") or "").strip() or synth_dialogue
                        s_roles = s_data.get("active_roles") or active_role_ids
                        scenes.append(
                            SceneDirective(
                                scene_number=int(s_data.get("scene_number") or (s_idx + 1)),
                                active_roles=list(s_roles),
                                action=s_action,
                                dialogue=s_dialogue,
                                audio_cues=str(s_data.get("audio_cues") or audio_beat),
                                timecode=str(s_data.get("timecode") or "0-10s"),
                                duration_seconds=float(s_data.get("duration_seconds") or 10.0),
                            )
                        )
                else:
                    scenes = synth_scenes

                return MetaPromptTags(
                    characters=chars,
                    aesthetic_tags=aesthetic_tags,
                    environment_tag=env_tag,
                    camera_lighting_tag=cam_tag,
                    audio_beat=audio_beat,
                    vocal_delivery=vocal_delivery,
                    keyframe_image_prompt=keyframe_image_prompt,
                    screenplay_script=screenplay_script,
                    scenes=scenes,
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
        preset_key = str(style_preset)
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
        validate_prompt_input_lengths(
            screenplay_script=screenplay_text,
            raw_prompt=raw_prompt,
        )
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

        raw_prompt_clean = raw_prompt
        extracted_raw_dialogue: str | None = None
        if raw_prompt and ("dialogue" in raw_prompt.lower() or "voiceover" in raw_prompt.lower()):
            match = re.search(
                r"-\s*(?:Dialogue\s*/\s*Text\s*Overlay|Dialogue|Voiceover):\s*(.*)",
                raw_prompt,
                re.IGNORECASE,
            )
            if match:
                raw_vo = match.group(1).strip()
                if (raw_vo.startswith('"') and raw_vo.endswith('"')) or (
                    raw_vo.startswith("'") and raw_vo.endswith("'")
                ):
                    raw_vo = raw_vo[1:-1].strip()
                if raw_vo:
                    extracted_raw_dialogue = raw_vo
                raw_prompt_clean = re.sub(
                    r"-\s*(?:Dialogue\s*/\s*Text\s*Overlay|Dialogue|Voiceover):\s*.*(?:\n|$)",
                    "",
                    raw_prompt,
                    flags=re.IGNORECASE,
                ).strip()

        action_components = [
            comp
            for comp in [raw_prompt_clean, scene_action, parsed_action]
            if comp and comp.strip()
        ]
        effective_raw_prompt = (
            ". ".join(action_components) if action_components else "Cinematic shot"
        )

        audio_components = [
            comp for comp in [audio_stem, scene_audio, parsed_audio] if comp and comp.strip()
        ]
        effective_audio_stem = ". ".join(audio_components) if audio_components else None

        dialogue_components = [
            comp
            for comp in [
                voiceover,
                extracted_raw_dialogue,
                scene_dialogue,
                parsed_dialogue,
            ]
            if comp and comp.strip()
        ]
        effective_voiceover = " / ".join(dialogue_components) if dialogue_components else None

        parts = self.compile(
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

        sources_items, references_items, char_tag_map = build_character_image_ref_tags(
            characters=characters,
            starting_index=1,
            has_keyframe_seed=False,
        )

        input_roles: list[str] = []
        if sources_items:
            input_roles.append(f"[# Sources {' '.join(sources_items)}]")
        if references_items:
            input_roles.append(f"[# References {' '.join(references_items)}]")

        char_profiles: list[str] = []
        char_refs: list[str] = []
        if characters:
            for char in characters:
                char_id = get_character_identifier(char, use_role_id=True)
                tag = char_tag_map.get(char_id)
                tag_str = f" {tag}" if tag else ""

                if char.reference_url and char.reference_url.strip():
                    char_refs.append(
                        f"[Visual Reference: {tag or 'Attached Image'}] {char_id}: {char.description}"
                    )

                if getattr(char, "is_offscreen_narrator", False):
                    char_profiles.append(
                        f"- {char_id}: Visual: Off-screen (Voiceover only). Do not show."
                    )
                else:
                    style_str = (
                        f" [Style: {', '.join(char.aesthetic_tags)}]" if char.aesthetic_tags else ""
                    )
                    char_profiles.append(f"- {char_id}{tag_str}: {char.description}{style_str}")

        parts.input_roles = input_roles
        parts.character_profiles = char_profiles
        parts.character_references = char_refs

        tc_blocks: list[str] = []
        lower_audio = (effective_audio_stem or parts.audio_track).lower().strip()
        if is_silent or lower_audio in ("none", "mute", "silent"):
            sound_desc = "Silent video. No background music, no audio."
        else:
            audio_track_clean = parts.audio_track.strip()
            if not audio_track_clean.lower().startswith("instrumental"):
                instr_audio = f"instrumental {audio_track_clean}"
            else:
                instr_audio = audio_track_clean

            if parts.voiceover and parts.voiceover.strip():
                sound_desc = (
                    f"Sound design: Foreground spoken voiceover/dialogue is dominant, crystal-clear, and front-of-mix. "
                    f"Background beat ({instr_audio}) is subtly ducked in the background beneath dialogue."
                )
            else:
                sound_desc = f"Sound design: {instr_audio}."

        if script and script.strip():
            parsed_blocks = parse_timecoded_script(
                script, characters=characters, char_tag_map=char_tag_map
            )
            for pb in parsed_blocks:
                tc = pb["timecode"]
                act = pb["action"] or parts.motion
                aud_cue = pb["audio_cues"] or effective_audio_stem or sound_desc
                diag = pb["dialogue"]

                audio_str = f" Audio: {aud_cue}." if aud_cue else f" Audio: {sound_desc}."
                diag_str = ""
                if diag:
                    if "narrator" in diag.lower():
                        clean_d = re.sub(
                            r"^(?:(?:Role\s*\w+\s*\()?Narrator(?:\s*VO\))?\)?:\s*)[\"']?|[\"']?$",
                            "",
                            diag,
                            flags=re.IGNORECASE,
                        ).strip()
                        diag_str = f' Dialogue: Narrator (VO) says: "{clean_d}".'
                    else:
                        diag_str = f" Dialogue: {diag}."
                tc_blocks.append(f"{tc} Action: {act}.{audio_str}{diag_str}")

        if not tc_blocks:
            vo_info = ""
            if parts.voiceover and parts.voiceover.strip():
                if "narrator" in parts.voiceover.lower():
                    clean_vo = re.sub(
                        r"^(?:Narrator\s*(?:\(VO\))?:?\s*)[\"']?|[\"']?$",
                        "",
                        parts.voiceover,
                        flags=re.IGNORECASE,
                    ).strip()
                    vo_info = f' Dialogue: Narrator (VO) says: "{clean_vo}".'
                elif ":" in parts.voiceover or "\n" in parts.voiceover:
                    vo_info = f" Dialogue between subjects: {parts.voiceover}."
                else:
                    vo_clean = parts.voiceover.rstrip(".")
                    vo_info = f" Voiceover: {vo_clean}."

            action_anchor = parts.subject_anchor
            motion_anchor = parts.motion
            if char_tag_map:
                sorted_keys = sorted(char_tag_map.keys(), key=len, reverse=True)
                for c_id in sorted_keys:
                    tag = char_tag_map[c_id]
                    if tag not in action_anchor and c_id in action_anchor:
                        action_anchor = action_anchor.replace(c_id, f"{c_id} {tag}")
                    if tag not in motion_anchor and c_id in motion_anchor:
                        motion_anchor = motion_anchor.replace(c_id, f"{c_id} {tag}")

            parts.motion = motion_anchor
            motion_part = (
                f". {parts.motion}"
                if parts.motion and parts.motion.lower() not in action_anchor.lower()
                else ""
            )
            tc_blocks = [
                f"[0-3s] Action: {action_anchor}{motion_part}. Audio: {sound_desc}.{vo_info}",
                f"[3-6s] Action: Continuation of action and motion. Audio: {sound_desc}.",
                f"[6-10s] Action: Dynamic resolution. Audio: {sound_desc}.",
            ]

        parts.timecode_blocks = tc_blocks
        return parts

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
        has_keyframe_seed: bool = False,
        keyframe_image_url: str | None = None,
        enable_sanitization: bool = True,
        aspect_ratio: str = "16:9",
        style_preset: str | None = None,
        is_seamless_loop: bool = False,
    ) -> str:
        validate_prompt_input_lengths(concept=concept)
        apply_conversational_voice_edits(concept, characters)
        start_idx = 1
        effective_has_keyframe = has_keyframe_seed or bool(keyframe_image_url)
        sources_items, references_items, char_tag_map = build_character_image_ref_tags(
            characters=characters,
            starting_index=start_idx,
            has_keyframe_seed=effective_has_keyframe,
            enable_sanitization=enable_sanitization,
        )
        if (
            is_seamless_loop
            and effective_has_keyframe
            and not any(s.startswith("<LAST_FRAME>") for s in sources_items)
        ):
            sources_items.append("<LAST_FRAME>@KeyframeSeed")

        input_roles: list[str] = []
        if sources_items:
            input_roles.append(f"[# Sources {' '.join(sources_items)}]")
        if references_items:
            input_roles.append(f"[# References {' '.join(references_items)}]")

        char_profiles: list[str] = []
        for char in characters:
            char_id = get_character_identifier(
                char, enable_sanitization=enable_sanitization, use_role_id=True
            )
            tag = char_tag_map.get(char_id)
            tag_str = f" {tag}" if tag else ""

            if getattr(char, "is_offscreen_narrator", False):
                char_profiles.append(
                    f"- {char_id}: Visual: Off-screen (Voiceover only). Do not show."
                )
            else:
                style_str = (
                    f" [Style: {', '.join(char.aesthetic_tags)}]" if char.aesthetic_tags else ""
                )
                if enable_sanitization:
                    desc_clean = sanitize_real_names(char.description) if char.description else ""
                else:
                    desc_clean = char.description or ""
                v_style = ensure_character_voice_style(char, concept)
                voice_str = f" [Voice Style: {v_style.strip()}]"
                char_profiles.append(f"- {char_id}{tag_str}: {desc_clean}{style_str}{voice_str}")

        input_roles_str = "\n".join(input_roles).strip() if input_roles else "None."
        char_profiles_str = "\n".join(char_profiles).strip() if char_profiles else "None."

        scene_inst_parts: list[str] = []
        if concept and concept.strip():
            scene_inst_parts.append(f"Concept: {concept.strip()}")
        if aesthetic_tags:
            scene_inst_parts.append(f"Aesthetic Tags: {', '.join(aesthetic_tags)}")
        if environment_tag and environment_tag.strip():
            scene_inst_parts.append(f"Environment: {environment_tag.strip()}")

        if style_preset and style_preset.strip():
            sp_clean = style_preset.strip()
            if enable_sanitization:
                sp_clean = sanitize_real_names(sp_clean)
            scene_inst_parts.append(
                f"- Medium & Aesthetic Style: Shot strictly in the exact artistic medium of Attached Image #1 (<FIRST_FRAME>@KeyframeSeed): {sp_clean}. Maintain 100% visual texture and animation medium continuity with <FIRST_FRAME>@KeyframeSeed, rendering all movement, characters, and environment strictly in {sp_clean} with zero photorealistic texture bleeding."
            )

        scene_inst_parts.append("Camera & Lighting: In a single continuous shot. No scene cuts.")
        if aspect_ratio and aspect_ratio.strip():
            scene_inst_parts.append(f"- Aspect Ratio: {aspect_ratio.strip()}")

        if is_seamless_loop:
            if effective_has_keyframe:
                scene_inst_parts.append(
                    "- Seamless Infinite Loop Mode: Seamless continuous infinite loop directive. Mirror start frame <FIRST_FRAME>@KeyframeSeed and end frame <LAST_FRAME>@KeyframeSeed so the final frame smoothly, imperceptibly loops back to the beginning with identical character posture, camera position, and ambient lighting."
                )
            else:
                scene_inst_parts.append(
                    "- Seamless Infinite Loop Mode: Seamless continuous infinite loop directive so the final frame smoothly, imperceptibly loops back to the beginning with identical character posture, camera position, and ambient lighting."
                )

        has_dialogue = False
        for scene in scenes:
            diag = (
                scene.get("dialogue")
                if isinstance(scene, dict)
                else getattr(scene, "dialogue", None)
            )
            sp_text = (
                (scene.get("screenplay_text") or scene.get("screenplay_script"))
                if isinstance(scene, dict)
                else (
                    getattr(scene, "screenplay_text", None)
                    or getattr(scene, "screenplay_script", None)
                )
            )
            narrator = (
                scene.get("narrator_text")
                if isinstance(scene, dict)
                else getattr(scene, "narrator_text", None)
            )
            if (
                (diag and str(diag).strip())
                or (sp_text and str(sp_text).strip())
                or (narrator and str(narrator).strip())
            ):
                has_dialogue = True
                break

        if not has_dialogue:
            if any(getattr(c, "voice_style", None) for c in characters) or (
                vocal_delivery and vocal_delivery.strip()
            ):
                has_dialogue = True

        custom_audio_soundscape: str | None = None
        if concept:
            match = re.search(
                r"-\s*Audio\s*Soundscape:\s*(.*)|-\s*Audio:\s*(.*)|(?:^|\n)\s*Audio\s*Soundscape:\s*(.*)|(?:^|\n)\s*Audio:\s*(.*)",
                concept,
                re.IGNORECASE,
            )
            if match:
                raw_extracted = (
                    match.group(1) or match.group(2) or match.group(3) or match.group(4) or ""
                ).strip()
                if raw_extracted:
                    custom_audio_soundscape = raw_extracted

        if custom_audio_soundscape:
            if has_dialogue:
                sound_desc = (
                    f"Sound design: Foreground spoken voiceover/dialogue is dominant, crystal-clear, and front-of-mix. "
                    f"Background beat ({custom_audio_soundscape}) is subtly ducked in the background beneath dialogue."
                )
            else:
                sound_desc = f"Sound design: {custom_audio_soundscape}."
            scene_inst_parts.append(f"Audio: {sound_desc}")
        elif audio_beat and audio_beat.strip():
            audio_beat_clean = audio_beat.strip()
            if audio_beat_clean.lower() in (
                "none",
                "mute",
                "silent",
                "silent video. no background music, no audio.",
            ) or audio_beat_clean.lower().startswith("silent video"):
                sound_desc = "Sound design: Silent video. No background music, no audio."
                scene_inst_parts.append(f"Audio: {sound_desc}")
            else:
                if "seamless acoustic progression" in audio_beat_clean.lower():
                    clean_dir = (
                        re.sub(r"^Audio:\s*", "", audio_beat_clean, flags=re.IGNORECASE)
                        .strip()
                        .rstrip(".")
                    )
                    sound_desc = f"{clean_dir}."
                else:
                    if not audio_beat_clean.lower().startswith("instrumental"):
                        instr_audio = f"instrumental {audio_beat_clean}"
                    else:
                        instr_audio = audio_beat_clean

                    if has_dialogue:
                        sound_desc = (
                            f"Sound design: Foreground spoken voiceover/dialogue is dominant, crystal-clear, and front-of-mix. "
                            f"Background beat ({instr_audio}) is subtly ducked in the background beneath dialogue."
                        )
                    else:
                        sound_desc = f"Sound design: {instr_audio}."
                scene_inst_parts.append(f"Audio: {sound_desc}")
        elif has_dialogue:
            scene_inst_parts.append(
                "Audio: Sound design: Foreground spoken voiceover/dialogue is dominant, crystal-clear, and front-of-mix."
            )

        for char in characters:
            if not getattr(char, "is_offscreen_narrator", False):
                char_id = get_character_identifier(
                    char, enable_sanitization=enable_sanitization, use_role_id=True
                )
                tag = char_tag_map.get(char_id)
                tag_str = f" {tag}" if tag else ""
                v_style = ensure_character_voice_style(char, concept)
                scene_inst_parts.append(f"Voice Style ({char_id}{tag_str}): {v_style.strip()}")
        if vocal_delivery and vocal_delivery.strip():
            scene_inst_parts.append(
                f"Global Vocal Delivery: {vocal_delivery.strip()} (Note: Individual character Voice Styles take precedence over global delivery)."
            )
        scene_inst_parts.append(
            "- Audio Accent & Voice Lock: Maintain strict vocal accent separation between characters. Each character must keep their distinct regional vocal timbre and pronunciation without bleeding into other characters' accents."
        )

        scene_instructions_str = (
            "\n".join(scene_inst_parts) if scene_inst_parts else "Default Scene Instructions."
        )

        timeline_lines: list[str] = []
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
            if not raw_roles and characters:
                raw_roles = [
                    get_character_identifier(
                        c, enable_sanitization=enable_sanitization, use_role_id=True
                    )
                    for c in characters
                    if not getattr(c, "is_offscreen_narrator", False)
                    and (
                        getattr(c, "image_role", "Character Reference")
                        if not isinstance(c, dict)
                        else c.get("image_role", "Character Reference")
                    )
                    not in (
                        "Starting Frame",
                        "Keyframe Seed Anchor",
                        "Ending Frame",
                        "Keyframe Last Anchor",
                    )
                ]
            roles_list: list[str] = []
            for r in raw_roles if isinstance(raw_roles, (list, tuple)) else []:
                r_str = str(r)
                matched_c = None
                if characters:
                    for c in characters:
                        c_role = (
                            getattr(c, "role_id", "")
                            if not isinstance(c, dict)
                            else c.get("role_id", "")
                        )
                        c_name = (
                            getattr(c, "name", "") if not isinstance(c, dict) else c.get("name", "")
                        )
                        c_id = get_character_identifier(
                            c, enable_sanitization=enable_sanitization, use_role_id=True
                        )
                        if r_str.lower() in (
                            str(c_role).lower(),
                            str(c_name).lower(),
                            c_id.lower(),
                        ):
                            matched_c = c
                            break
                if matched_c:
                    c_id = get_character_identifier(
                        matched_c, enable_sanitization=enable_sanitization, use_role_id=True
                    )
                    tag = char_tag_map.get(c_id)
                    tag_str = f" {tag}" if tag else ""
                    roles_list.append(f"{c_id}{tag_str}")
                else:
                    roles_list.append(r_str)
            roles_str = ", ".join(roles_list)

            sp_text = (
                (scene.get("screenplay_text") or scene.get("screenplay_script"))
                if isinstance(scene, dict)
                else (
                    getattr(scene, "screenplay_text", None)
                    or getattr(scene, "screenplay_script", None)
                )
            )

            dur_val = (
                scene.get("duration_seconds")
                if isinstance(scene, dict)
                else getattr(scene, "duration_seconds", 10.0)
            )
            tc_val = (
                scene.get("timecode")
                if isinstance(scene, dict)
                else getattr(scene, "timecode", None)
            )
            timecode_prefix = ""
            if tc_val and str(tc_val).strip():
                tc_clean = str(tc_val).strip()
                timecode_prefix = f"{tc_clean} " if tc_clean.startswith("[") else f"[{tc_clean}] "
            elif len(scenes) == 1:
                dur_int = (
                    int(dur_val)
                    if dur_val and isinstance(dur_val, (int, float)) and dur_val > 0
                    else 10
                )
                timecode_prefix = f"[0-{dur_int}s] "

            if sp_text and isinstance(sp_text, str) and sp_text.strip():
                parsed = parse_screenplay_script(
                    sp_text, characters=characters, char_tag_map=char_tag_map
                )
                if parsed.get("audio_cues"):
                    timeline_lines.append(f"Scene {scene_num} Audio Cues: {parsed['audio_cues']}")
                enriched_sp_text, _ = enrich_timeline_dialogue_speakers(
                    sp_text.strip(),
                    characters,
                    char_tag_map,
                    enable_sanitization=enable_sanitization,
                )
                indented_script = "\n".join(
                    f"  {line}" for line in enriched_sp_text.strip().splitlines()
                )
                timeline_lines.append(
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
                title_card_text = (
                    scene.get("title_card_text")
                    if isinstance(scene, dict)
                    else getattr(scene, "title_card_text", None)
                )
                title_card_subtitle = (
                    scene.get("title_card_subtitle")
                    if isinstance(scene, dict)
                    else getattr(scene, "title_card_subtitle", None)
                )
                narrator_text = (
                    scene.get("narrator_text")
                    if isinstance(scene, dict)
                    else getattr(scene, "narrator_text", None)
                )

                action_str = str(action or "").strip()
                if title_card_text and str(title_card_text).strip():
                    tc_t = str(title_card_text).strip()
                    if title_card_subtitle and str(title_card_subtitle).strip():
                        tc_s = str(title_card_subtitle).strip()
                        card_tag = f'[Title Screen: "{tc_t}" - "{tc_s}"]'
                    else:
                        card_tag = f'[Title Screen: "{tc_t}"]'
                    if action_str:
                        action_str = f"{action_str} {card_tag}"
                    else:
                        action_str = card_tag

                diag_str = ""
                diag_raw = str(dialogue or "").strip()
                narrator_raw = str(narrator_text or "").strip() if narrator_text else ""

                diag_parts: list[str] = []
                if diag_raw:
                    if "narrator" in diag_raw.lower():
                        clean_d = re.sub(
                            r"^(?:(?:Role\s*\w+\s*\()?Narrator(?:\s*(?:VO|Voiceover\)))?\)?:\s*)[\"']?|[\"']?$",
                            "",
                            diag_raw,
                            flags=re.IGNORECASE,
                        ).strip()
                        diag_parts.append(f'Narrator (VO) says: "{clean_d}"')
                    else:
                        enriched_diag, replaced_speakers = enrich_timeline_dialogue_speakers(
                            diag_raw=diag_raw,
                            characters=characters,
                            char_tag_map=char_tag_map,
                            enable_sanitization=enable_sanitization,
                        )
                        if replaced_speakers:
                            diag_parts.append(enriched_diag)
                        else:
                            diag_parts.append(f'"{diag_raw}"')

                if narrator_raw:
                    diag_parts.append(f'Narrator (Voiceover): "{narrator_raw}"')

                if diag_parts:
                    diag_str = " | Dialogue: " + " / ".join(diag_parts)

                if action_str.startswith("["):
                    timeline_lines.append(
                        f"- Scene {scene_num} [{roles_str}]: {action_str}{diag_str}"
                    )
                else:
                    timeline_lines.append(
                        f"- {timecode_prefix}Scene {scene_num} [{roles_str}]: {action_str}{diag_str}"
                    )

        timeline_str = "\n".join(timeline_lines) if timeline_lines else "- No scenes"

        compiled_result = (
            f"### INPUT ROLES & REFERENCES\n{input_roles_str}\n\n"
            f"### CHARACTER PROFILES\n{char_profiles_str}\n\n"
            f"### SCENE INSTRUCTIONS\n{scene_instructions_str}\n\n"
            f"### TIMELINE\n{timeline_str}"
        )
        compiled_result = validate_and_repair_role_bindings(compiled_result, characters)
        if enable_sanitization:
            return sanitize_real_names(compiled_result)
        return compiled_result

    def compile_turn0_prompt(
        self,
        concept: str,
        characters: list[CharacterRole],
        scenes: list[SceneDirective],
        **kwargs: Any,
    ) -> str:
        """Compiles a clean Turn-0 storyboard prompt with validated role bindings."""
        compiled = self.compile_storyboard(
            concept=concept,
            characters=characters,
            scenes=scenes,
            **kwargs,
        )
        return validate_and_repair_role_bindings(compiled, characters)

    def compile_storyboard(
        self,
        concept: str,
        characters: list[CharacterRole],
        scenes: list[SceneDirective],
        aesthetic_tags: list[str] | None = None,
        environment_tag: str | None = None,
        audio_beat: str | None = None,
        vocal_delivery: str | None = None,
        has_keyframe_seed: bool = False,
        keyframe_image_url: str | None = None,
        last_frame_image_url: str | None = None,
        edit_instruction: str | None = None,
        enable_sanitization: bool = True,
        aspect_ratio: str = "16:9",
        style_preset: str | None = None,
        is_seamless_loop: bool = False,
    ) -> str:
        if (
            is_seamless_loop
            and keyframe_image_url
            and keyframe_image_url.strip()
            and not (last_frame_image_url and last_frame_image_url.strip())
        ):
            last_frame_image_url = keyframe_image_url.strip()

        if last_frame_image_url and last_frame_image_url.strip():
            if characters is None:
                characters = []
            else:
                characters = list(characters)
            has_last = any(
                (
                    getattr(c, "image_role", "")
                    if not isinstance(c, dict)
                    else c.get("image_role", "")
                )
                in ("Ending Frame", "Keyframe Last Anchor")
                for c in characters
            )
            if not has_last:
                characters.append(
                    CharacterRole(
                        role_id="Ending Frame",
                        name="Ending Frame Anchor",
                        description="Ending Frame Anchor concept image",
                        reference_url=last_frame_image_url.strip(),
                        image_role="Ending Frame",
                    )
                )

        base_prompt = self.compile_multi_role_prompt(
            concept=concept,
            characters=characters,
            scenes=scenes,
            aesthetic_tags=aesthetic_tags,
            environment_tag=environment_tag,
            audio_beat=audio_beat,
            vocal_delivery=vocal_delivery,
            has_keyframe_seed=has_keyframe_seed,
            keyframe_image_url=keyframe_image_url,
            enable_sanitization=enable_sanitization,
            aspect_ratio=aspect_ratio,
            style_preset=style_preset,
            is_seamless_loop=is_seamless_loop,
        )
        base_prompt = validate_and_repair_role_bindings(base_prompt, characters)
        if edit_instruction and edit_instruction.strip():
            clean_instruction = edit_instruction.strip()
            directive_block = (
                "### CONVERSATIONAL EDIT DIRECTIVE\n"
                "- Original Scene Baseline: You must retain 95% of the visual character likeness, setting, camera angle, lighting, dialogue, and soundscape from <FIRST_FRAME>@KeyframeSeed.\n"
                f'- Required Change: Modify only the following aspect: "{clean_instruction}". Keep all other elements identical.'
            )
            return f"{base_prompt}\n\n{directive_block}"
        return base_prompt

    def deconstruct_concept(self, concept: str) -> MetaPromptTags:
        """Parses concept using 3-tier deconstructor engine."""
        if self.mock_mode:
            return self._deconstruct_fallback(concept)

        if self._pro_global_client:
            res = self._try_gemini_deconstruction(
                client=self._pro_global_client,
                model_name=getattr(settings, "pro_model_id", "gemini-4-argon"),
                concept=concept,
                tier_name="Tier 1 Pro Global",
            )
            if res is not None:
                return res

        if self._flash_regional_client:
            res = self._try_gemini_deconstruction(
                client=self._flash_regional_client,
                model_name=getattr(settings, "flash_model_id", "gemini-3.8-flash"),
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
            elif any(
                t in lower
                for t in (
                    "gothic",
                    "horror",
                    "vampire",
                    "dark fantasy",
                    "ritual",
                    "witch",
                )
            ):
                tag_map = {
                    "harry": ["Embroidered Velvet Robes", "Silver Wire-Rim Glasses"],
                    "draco": ["High-Collar Aristocratic Cloak", "Platinum Hair"],
                    "snape": ["Flowing Gothic Trench Cloak", "Severe Dark Attire"],
                    "dumbledore": ["Ornate Runed Robes", "Half-Moon Spectacles"],
                    "voldemort": ["Dark Ritual Robes", "Serpentine Crest"],
                }
                return tag_map.get(k, ["Flowing Dark Cloak", "Victorian Velvet Attire"])
            elif any(t in lower for t in ("western", "cowboy", "outlaw", "saloon")):
                tag_map = {
                    "harry": ["Worn Leather Stetson", "Round Wire Glasses"],
                    "draco": ["Tailored Outlaw Vest", "Silver Spurs"],
                    "snape": ["Black Leather Duster", "Broad Brim Hat"],
                }
                return tag_map.get(k, ["Worn Leather Stetson", "Dusty Duster Coat"])
            elif any(t in lower for t in ("noir", "detective", "mystery")):
                tag_map = {
                    "harry": ["Vintage Trench Coat", "Round Glasses"],
                    "draco": ["Tailored Double-Breasted Suit", "Silk Tie"],
                    "snape": ["High-Collar Dark Trench Coat", "Fedora"],
                }
                return tag_map.get(k, ["Vintage Trench Coat", "Custom Fedora Hat"])
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
            elif any(
                t in lower
                for t in (
                    "gothic",
                    "horror",
                    "vampire",
                    "dark fantasy",
                    "ritual",
                    "witch",
                )
            ):
                return "Deep resonant vocal tone with deliberate theatrical emphasis"
            elif any(t in lower for t in ("western", "cowboy", "outlaw", "saloon")):
                return "Low raspy western drawl with measured calm tone"
            elif any(t in lower for t in ("noir", "detective", "mystery")):
                return "Hard-boiled low baritone voiceover with dry sardonic tone"
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
                "Fiery Chef Ramsay",
                "A fiery master chef with sharp blond hair, intense focused gaze, and crisp white chef jacket",
            ),
            "julia": (
                "Vintage Chef Julia",
                "An iconic tall cheerful culinary master with curly brown hair, expressive warm smile, and classic vintage apron",
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

        known_lore_aliases: dict[str, tuple[str, ...]] = {
            "harry": ("harry", "spectacled wizard"),
            "draco": ("draco", "platinum rival", "rival wizard"),
            "snape": ("snape", "potion master"),
            "dumbledore": ("dumbledore", "venerable high wizard"),
            "voldemort": ("voldemort", "dark sorcerer"),
            "ramsay": ("ramsay", "fiery chef"),
            "julia": ("julia", "classic chef"),
            "samurai": ("samurai",),
            "ninja": ("ninja",),
        }

        matched_keys = [
            k
            for k in known_lore
            if any(alias in lower for alias in known_lore_aliases.get(k, (k,)))
        ]
        if matched_keys:
            for idx, k in enumerate(matched_keys):
                name, desc = known_lore[k]
                chars.append(
                    CharacterRole(
                        role_id=role_labels[min(idx, len(role_labels) - 1)],
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
                if any(
                    w in lower
                    for w in (
                        "harry",
                        "draco",
                        "hogwarts",
                        "snape",
                        "spectacled wizard",
                        "platinum rival",
                        "rival wizard",
                        "potion master",
                        "gothic academy",
                    )
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
        elif any(
            t in lower
            for t in (
                "gothic",
                "horror",
                "vampire",
                "dark fantasy",
                "ritual",
                "witch",
            )
        ):
            aesthetic_tags = [
                "Gothic Dark Fantasy",
                "Victorian Velvet Attire",
                "Moody Candlelight",
                "Atmospheric Haze",
            ]
            audio_beat = "90 BPM Dark Atmospheric Ambient Synth"
            vocal_delivery = (
                "Low brooding resonant delivery with solemn theatrical pauses and dark echo"
            )
            env_tag = (
                "Ancient stone castle chamber illuminated by flickering candlelight and moonlit fog"
            )
            cam_tag = "Cinematic 16:9 slow push-in tracking shot with high-contrast shadows and moody rim lighting"
        elif any(t in lower for t in ("western", "cowboy", "outlaw", "saloon")):
            aesthetic_tags = [
                "Gritty 19th-Century Western",
                "Dusty Leather Duster",
                "Sun-Drenched Color Grading",
                "Vintage Sepia Tone",
            ]
            audio_beat = "100 BPM Spaghetti Western Guitar & Whistle"
            vocal_delivery = "Grit-textured drawl with quiet intense projection and slow cadence"
            env_tag = (
                "Sun-scorched frontier desert town with dusty wooden storefronts and harsh sunlight"
            )
            cam_tag = (
                "Widescreen 2.39:1 low-angle tracking shot with intense sun flares and heat shimmer"
            )
        elif any(t in lower for t in ("noir", "detective", "mystery")):
            aesthetic_tags = [
                "1940s Classic Film Noir",
                "Vintage Trench Coat & Fedora",
                "Chiaroscuro High-Contrast",
                "Venetian Blind Shadows",
            ]
            audio_beat = "75 BPM Smoky Jazz Saxophone & Slow Drums"
            vocal_delivery = "Cynical hard-boiled voiceover monologue with weary rhythmic pacing"
            env_tag = "Rain-slicked urban street at midnight lit by flickering neon signage and streetlamps"
            cam_tag = "Dutch-angle 16:9 tracking shot with deep shadow contrast and moody rain reflections"
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

        keyframe_image_prompt, screenplay_script, scenes, _ = (
            self._synthesize_scene_and_script_defaults(
                concept=concept,
                chars=chars,
                aesthetic_tags=aesthetic_tags,
                env_tag=env_tag,
                cam_tag=cam_tag,
                audio_beat=audio_beat,
            )
        )

        return MetaPromptTags(
            characters=chars,
            aesthetic_tags=aesthetic_tags,
            environment_tag=env_tag,
            camera_lighting_tag=cam_tag,
            audio_beat=audio_beat,
            vocal_delivery=vocal_delivery,
            keyframe_image_prompt=keyframe_image_prompt,
            screenplay_script=screenplay_script,
            scenes=scenes,
        )
