"""Mode 4: Director's Co-Pilot (Intent Auto-Orchestrator) Prompt Engine.

Provides 7-slot intent gap analysis, clarifying questions, and cohesive production
plan auto-filling into canonical 4-block Gemini Omni Flash prompts.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from omnimash.api.models import (
    AnalyzeIntentGapsResponse,
    AutoFillIntentPlanResponse,
    CharacterRoleModel,
    ClarificationQuestion,
    ClarificationQuestionOption,
    CohesiveProductionPlan,
    DeconstructedSceneModel,
    IntentSlotInputs,
)
from omnimash.config import settings
from omnimash.prompts.genai_client import get_genai_client
from omnimash.prompts.parody import REAL_NAME_PARODY_MAP, sanitize_real_names

logger = logging.getLogger(__name__)

KNOWN_VAULT_PROFILES: dict[str, dict[str, Any]] = {
    "dumble dior": {
        "name": "Dumble Dior",
        "description": "Elderly high-fashion wizard headmaster with a long silver beard, diamond half-moon spectacles, black-diamond pinky ring, heavy DD diamond chain, and a floor-length custom silk monogram wizard robe",
        "reference_url": "gs://omnimash-media-hybrid-vertex/projects/trapwarts/sessions/dd_office_v13/character_sheets/dumble_dior_office_sheet_v13.png",
        "wardrobe": "Floor-length custom silk monogram wizard robe, diamond half-moon spectacles, DD diamond chain",
        "voice_style": "Sharp, vigorous Oxford English cadence",
        "aesthetic_tags": [
            "long silver beard",
            "floor-length silk monogram robe",
            "black-diamond pinky ring",
            "diamond half-moon spectacles",
            "championship-style rings",
            "DD diamond chain",
        ],
    },
    "yototti": {
        "name": "YoTotti",
        "description": "Confident young wizard with styled blonde hair, open black tracksuit, 'Panic' chest tattoo, radiating unfazed zen energy, wearing blue-shaded oversized aviator sunglasses, heavy diamond chains, and massive diamond rings",
        "reference_url": "gs://omnimash-media-hybrid-vertex/projects/trapwarts/sessions/dd_office_v13/character_sheets/yototti_office_sheet_v13.png",
        "wardrobe": "Tailored open black designer tracksuit, blue-shaded oversized aviator sunglasses, heavy diamond chains, chest tattoo",
        "voice_style": "Calm, unfazed East London cadence",
        "aesthetic_tags": [
            "styled blonde hair",
            "diamond chains",
            "big diamond rings",
            "blue shaded large aviator sunglasses",
            "black designer track suit",
            "chest tattoo",
        ],
    },
    "bee allison": {
        "name": "Bee Allison",
        "description": "Gritty, thin-faced, fit, high-energy trap wizard with short buzzcut dark hair, wearing a designer monogram bucket hat, black tracksuit with white side stripes, gold 1017 pendant chain, and holding a double foam cup. He directs his swarm of magical bees with small, sharp flicks of his wand",
        "reference_url": "gs://omnimash-media-hybrid-vertex/projects/trapwarts/sessions/nola_drop_v2/character_sheets/bee_allison_nola_sheet_v2.png",
        "wardrobe": "Designer monogram bucket hat, black tracksuit with white side stripes, gold 1017 pendant chain",
        "voice_style": "Fast-paced confident Atlanta rap cadence with crisp enunciated swagger",
        "aesthetic_tags": [
            "designer monogram bucket hat",
            "black tracksuit with white side stripes",
            "gold 1017 pendant",
            "double foam cup",
            "swarm of magical bees",
        ],
    },
    "accountant elves": {
        "name": "Accountant Elves",
        "description": "Small busy fantasy house elves dressed in tiny tailored business suits and green accountant visors, operating high-speed mechanical coin-counting machines and sorting piles of jewels",
        "reference_url": "gs://omnimash-media-hybrid-vertex/projects/trapwarts/sessions/dd_office_v13/character_sheets/accountant_elves_office_sheet_v13.png",
        "wardrobe": "Tiny tailored business suits, green accountant visors, spectacles",
        "voice_style": "Fast-paced, high-pitched muttering and frantic whispering",
        "aesthetic_tags": [
            "tiny tailored suits",
            "green visors",
            "spectacles",
            "fantasy accountant",
        ],
    },
}


class IntentGapAnalyzer:
    """Analyzes user premise/intent across 7 production slots and generates targeted clarification questions."""

    def __init__(self, mock_mode: bool | None = None) -> None:
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self._genai_client: Any = None
        if not self.mock_mode:
            self._init_genai_client()

    def _init_genai_client(self) -> None:
        try:
            self._genai_client = get_genai_client(
                location=getattr(settings, "gemini_location", "global")
            )
        except Exception as exc:
            logger.warning("IntentGapAnalyzer could not initialize GenAI client: %s", exc)
            self._genai_client = None

    def analyze(
        self,
        intent: str,
        inputs: IntentSlotInputs | None = None,
        session_name: str | None = None,
    ) -> AnalyzeIntentGapsResponse:
        """Analyzes missing slots and returns 2 to 3 clarifying question cards."""
        inputs = inputs or IntentSlotInputs()
        intent_clean = (intent or "").strip()

        filled_slots: dict[str, Any] = {}
        missing_slots: list[str] = []

        # 1. Intent slot
        if intent_clean:
            filled_slots["intent"] = intent_clean
        else:
            missing_slots.append("intent")

        # 2. Characters slot
        if inputs.character_profiles:
            filled_slots["characters"] = [c.name or c.role_id for c in inputs.character_profiles]
            filled_slots["character_profiles"] = [c.model_dump() for c in inputs.character_profiles]
        elif inputs.characters:
            filled_slots["characters"] = list(inputs.characters)
        else:
            # Check if intent mentions identifiable celebrity/character entities
            found_entities: list[str] = []
            for pattern, parody_name in REAL_NAME_PARODY_MAP.items():
                if re.search(pattern, intent_clean, flags=re.IGNORECASE):
                    found_entities.append(parody_name)
            if found_entities:
                filled_slots["characters"] = found_entities
            else:
                missing_slots.append("characters")

        # 3. Setting slot
        if inputs.setting and inputs.setting.strip():
            filled_slots["setting"] = inputs.setting.strip()
        else:
            missing_slots.append("setting")

        # 4. Style & Lighting / Camera slot
        if inputs.style_tone and inputs.style_tone.strip():
            filled_slots["style_tone"] = inputs.style_tone.strip()
        else:
            missing_slots.append("style_tone")

        # 5. Audio Beat slot
        if inputs.audio_beat and inputs.audio_beat.strip():
            filled_slots["audio_beat"] = inputs.audio_beat.strip()
        else:
            missing_slots.append("audio_beat")

        # 6. Sound Effects slot
        if inputs.sound_effects and inputs.sound_effects.strip():
            filled_slots["sound_effects"] = inputs.sound_effects.strip()
        else:
            missing_slots.append("sound_effects")

        # 7. Dialogue & Dialogue Direction slot
        has_dialogue_input = False
        if inputs.dialogue and inputs.dialogue.strip():
            filled_slots["dialogue"] = inputs.dialogue.strip()
            has_dialogue_input = True
        if inputs.dialogue_direction and inputs.dialogue_direction.strip():
            filled_slots["dialogue_direction"] = inputs.dialogue_direction.strip()
            has_dialogue_input = True
        if not has_dialogue_input:
            missing_slots.append("dialogue")

        # Generate 2 to 3 clarification questions prioritizing high-impact missing slots
        questions = self._build_clarification_questions(
            intent=intent_clean,
            missing_slots=missing_slots,
            filled_slots=filled_slots,
        )

        return AnalyzeIntentGapsResponse(
            success=True,
            intent=intent_clean,
            filled_slots=filled_slots,
            missing_slots=missing_slots,
            questions=questions,
            can_auto_fill_immediately=True,
        )

    def _build_clarification_questions(
        self,
        intent: str,
        missing_slots: list[str],
        filled_slots: dict[str, Any],
    ) -> list[ClarificationQuestion]:
        """Constructs 2-3 focused clarification questions based on intent context."""
        lower_intent = intent.lower()
        questions: list[ClarificationQuestion] = []

        # Determine theme/genre cues
        is_cyberpunk = any(
            w in lower_intent
            for w in ("cyber", "neon", "hacker", "tokyo", "matrix", "future", "sci-fi", "droid")
        )
        is_wizard = any(
            w in lower_intent
            for w in ("wizard", "magic", "spell", "potion", "hogwarts", "sorcerer", "tavern")
        )
        is_cooking = any(
            w in lower_intent
            for w in ("cook", "chef", "kitchen", "culinary", "recipe", "dish", "food")
        )
        is_noir = any(
            w in lower_intent
            for w in ("detective", "noir", "crime", "investigat", "rain", "whiskey", "shadow")
        )

        # Candidate Questions Map
        candidates: dict[str, ClarificationQuestion] = {}

        # 1. Audio Beat Question
        if "audio_beat" in missing_slots:
            if is_cyberpunk:
                audio_opts = [
                    ClarificationQuestionOption(
                        id="audio_dark_synth",
                        label="135 BPM Dark Cyber Synthwave",
                        description="Pulsing analog arpeggios with distorted basslines and sirens",
                    ),
                    ClarificationQuestionOption(
                        id="audio_industrial",
                        label="Industrial Cyber EBM",
                        description="Metallic pounding rhythms and glitchy synthetic textures",
                    ),
                    ClarificationQuestionOption(
                        id="audio_lofi_neon",
                        label="Neon Ambient Dystopia",
                        description="Slow atmospheric synthesizer pads with ambient rain foley",
                    ),
                ]
            elif is_wizard:
                audio_opts = [
                    ClarificationQuestionOption(
                        id="audio_trap_808",
                        label="140 BPM Heavy 808 Trap Beat",
                        description="Aggressive sub-bass 808 glides with punchy hi-hats and pipe organ",
                    ),
                    ClarificationQuestionOption(
                        id="audio_boombap",
                        label="90s Gritty Boom-Bap Hip Hop",
                        description="Dusty vinyl drum break with warm jazz keys and scratching",
                    ),
                    ClarificationQuestionOption(
                        id="audio_orchestral_trap",
                        label="Epic Gothic Orchestral Trap",
                        description="Soaring gothic choir and brass stabs over rolling 808 bass",
                    ),
                ]
            elif is_cooking:
                audio_opts = [
                    ClarificationQuestionOption(
                        id="audio_funk_groove",
                        label="Upbeat Culinary Funk Beat",
                        description="Snappy bassline and brisk rhythm guitar with lively brass",
                    ),
                    ClarificationQuestionOption(
                        id="audio_chef_battle",
                        label="Intense Kitchen Percussion Riser",
                        description="Dramatic orchestral percussion with ticking clock tension",
                    ),
                    ClarificationQuestionOption(
                        id="audio_bistro_jazz",
                        label="Warm Parisian Bistro Jazz",
                        description="Acoustic upright bass and lively accordion swing",
                    ),
                ]
            elif is_noir:
                audio_opts = [
                    ClarificationQuestionOption(
                        id="audio_noir_sax",
                        label="Melancholic Slow Jazz & Tenor Sax",
                        description="Muted trumpet, slow brush drums, and smoky bar saxophone",
                    ),
                    ClarificationQuestionOption(
                        id="audio_dark_ambient",
                        label="Dark Ambient Low Drone",
                        description="Sub-bass cello drone with echoing rain against windowpanes",
                    ),
                ]
            else:
                audio_opts = [
                    ClarificationQuestionOption(
                        id="audio_cinematic_trap",
                        label="140 BPM Cinematic Trap Beat",
                        description="Heavy rolling bass with crisp modern trap percussion",
                    ),
                    ClarificationQuestionOption(
                        id="audio_orchestral",
                        label="High-Octane Cinematic Score",
                        description="Dynamic orchestral brass and driving strings",
                    ),
                    ClarificationQuestionOption(
                        id="audio_synthwave",
                        label="Pulsing Synthwave Electronic",
                        description="Retro-futuristic analog synthesizer rhythms",
                    ),
                ]
            candidates["audio_beat"] = ClarificationQuestion(
                question_id="q_audio",
                slot_target="audio_beat",
                title="What musical vibe & tempo should drive the scene?",
                subtitle="Music will automatically duck under spoken dialogue for vocal clarity.",
                options=audio_opts,
                allow_custom=True,
            )

        # 2. Setting Question
        if "setting" in missing_slots:
            if is_cyberpunk:
                setting_opts = [
                    ClarificationQuestionOption(
                        id="setting_neo_tokyo",
                        label="Neo Tokyo Rainy Alleyway",
                        description="Puddles reflecting glowing neon signage and steam rising from grates",
                    ),
                    ClarificationQuestionOption(
                        id="setting_server_vault",
                        label="Underground Data Vault",
                        description="Racks of blinking fiber-optic towers and sub-zero cooling mist",
                    ),
                    ClarificationQuestionOption(
                        id="setting_sky_penthouse",
                        label="Megacorp Sky Penthouse",
                        description="Floor-to-ceiling glass overlooking endless cybernetic skyscrapers",
                    ),
                ]
            elif is_wizard:
                setting_opts = [
                    ClarificationQuestionOption(
                        id="setting_tavern_stage",
                        label="Smoky Medieval Tavern Stage",
                        description="Wooden tables, flickering torches, and an energetic cheering crowd",
                    ),
                    ClarificationQuestionOption(
                        id="setting_gothic_courtyard",
                        label="Gothic Academy High Courtyard",
                        description="Ancient gargoyles, carved stone arches, and arcane purple lightning",
                    ),
                    ClarificationQuestionOption(
                        id="setting_potion_dungeon",
                        label="Underground Potion Laboratory",
                        description="Bubbling cauldrons, mossy stonework, and glowing amber vials",
                    ),
                ]
            elif is_cooking:
                setting_opts = [
                    ClarificationQuestionOption(
                        id="setting_michelin_kitchen",
                        label="Michelin-Star Stainless Steel Kitchen",
                        description="Gleaming copper pans, roaring gas flames, and pristine plating stations",
                    ),
                    ClarificationQuestionOption(
                        id="setting_rustic_bistro",
                        label="Rustic Brick-Oven Trattoria",
                        description="Open wood-fired oven with flour dust hanging in warm light",
                    ),
                ]
            else:
                setting_opts = [
                    ClarificationQuestionOption(
                        id="setting_neon_urban",
                        label="Neon-Lit Urban Alleyway",
                        description="Damp asphalt, dramatic shadows, and colorful overhead streetlamps",
                    ),
                    ClarificationQuestionOption(
                        id="setting_grand_interior",
                        label="Atmospheric Grand Interior",
                        description="High vaulted ceilings with dramatic shafts of volumetric light",
                    ),
                    ClarificationQuestionOption(
                        id="setting_golden_exterior",
                        label="Cinematic Exterior at Golden Hour",
                        description="Warm sunset backlighting with long dramatic silhouette shadows",
                    ),
                ]
            candidates["setting"] = ClarificationQuestion(
                question_id="q_setting",
                slot_target="setting",
                title="Where should the continuous shot take place?",
                subtitle="Select the primary environment and backdrop atmosphere.",
                options=setting_opts,
                allow_custom=True,
            )

        # 3. Style & Lighting / Camera Question
        if "style_tone" in missing_slots:
            if is_cyberpunk:
                style_opts = [
                    ClarificationQuestionOption(
                        id="style_neon_anamorphic",
                        label="Anamorphic 35mm Neon Noir",
                        description="Rain-slicked reflections, teal and magenta neon rims, horizontal lens flares",
                    ),
                    ClarificationQuestionOption(
                        id="style_gritty_vhs",
                        label="Glitchy Retro-Futurism",
                        description="CRT scanline aesthetic, subtle chromatic aberration, handheld surveillance feel",
                    ),
                ]
            elif is_wizard:
                style_opts = [
                    ClarificationQuestionOption(
                        id="style_gothic_rim",
                        label="Gothic Dramatic Rim Lighting",
                        description="Emerald and violet backlights slicing through dense theatrical mist",
                    ),
                    ClarificationQuestionOption(
                        id="style_90s_fisheye",
                        label="90s Music Video Fisheye",
                        description="Ultra wide-angle lens with low-angle tracking and vibrant saturation",
                    ),
                ]
            else:
                style_opts = [
                    ClarificationQuestionOption(
                        id="style_cinematic_35mm",
                        label="Anamorphic 35mm Cinema",
                        description="Shallow depth of field with directional cinematic rim lighting",
                    ),
                    ClarificationQuestionOption(
                        id="style_dynamic_steadicam",
                        label="Dynamic Tracking Steadicam",
                        description="Smooth continuous camera choreography with crisp vivid contrast",
                    ),
                ]
            candidates["style_tone"] = ClarificationQuestion(
                question_id="q_style",
                slot_target="style_tone",
                title="What camera motion & lighting aesthetic fits best?",
                subtitle="Enforces a single continuous shot with no scene cuts.",
                options=style_opts,
                allow_custom=True,
            )

        # 4. Characters Question
        if "characters" in missing_slots:
            char_opts = [
                ClarificationQuestionOption(
                    id="char_rivals",
                    label="Two Fierce Rivals Locking Horns",
                    description="High-energy opposing forces confronting each other head-to-head",
                ),
                ClarificationQuestionOption(
                    id="char_partners",
                    label="Contrasting Dynamic Duo",
                    description="A methodical strategist paired with an impulsive wild card",
                ),
                ClarificationQuestionOption(
                    id="char_mentor_student",
                    label="Master & Prodigy Apprentice",
                    description="An experienced veteran testing a confident new talent",
                ),
            ]
            candidates["characters"] = ClarificationQuestion(
                question_id="q_characters",
                slot_target="characters",
                title="What character dynamic drives the scene?",
                subtitle="Choose the roles and chemistry between the key performers.",
                options=char_opts,
                allow_custom=True,
            )

        # 5. Dialogue Question
        if "dialogue" in missing_slots:
            dialogue_opts = [
                ClarificationQuestionOption(
                    id="diag_sharp_banter",
                    label="Sharp, Fast-Paced Theatrical Banter",
                    description="Rapid back-and-forth dialogue exchanges with sharp wit",
                ),
                ClarificationQuestionOption(
                    id="diag_dramatic_monologue",
                    label="Intense Dramatic Declaration",
                    description="Powerful spoken lines building to a high-stakes climax",
                ),
            ]
            candidates["dialogue"] = ClarificationQuestion(
                question_id="q_dialogue",
                slot_target="dialogue",
                title="How should the spoken dialogue be delivered?",
                subtitle="Determines the vocal rhythm, projection, and attitude.",
                options=dialogue_opts,
                allow_custom=True,
            )

        # Prioritize picking 2 to 3 questions in high-impact order
        priority_order = ["audio_beat", "setting", "style_tone", "characters", "dialogue"]
        for slot in priority_order:
            if slot in candidates and len(questions) < 3:
                questions.append(candidates[slot])

        # Ensure we always provide between 2 and 3 questions
        if len(questions) < 2:
            fallback_keys = ["audio_beat", "style_tone", "setting"]
            for fk in fallback_keys:
                if fk in candidates and candidates[fk] not in questions:
                    questions.append(candidates[fk])
                if len(questions) >= 2:
                    break

        if len(questions) < 2:
            # If all else fails (e.g. all slots filled), provide creative tuning questions
            questions.append(
                ClarificationQuestion(
                    question_id="q_tuning_style",
                    slot_target="style_tone",
                    title="Fine-tune the lighting and camera style:",
                    subtitle="Customize visual treatment for the continuous shot.",
                    options=[
                        ClarificationQuestionOption(
                            id="opt_anamorphic",
                            label="Anamorphic Widescreen 35mm",
                            description="Cinematic widescreen with rich directional rim light",
                        ),
                        ClarificationQuestionOption(
                            id="opt_vivid_color",
                            label="Hyper-Saturated Vivid Color Grade",
                            description="Punchy primary tones and bold high contrast",
                        ),
                    ],
                    allow_custom=True,
                )
            )
            questions.append(
                ClarificationQuestion(
                    question_id="q_tuning_audio",
                    slot_target="audio_beat",
                    title="Fine-tune the musical accompaniment:",
                    subtitle="Set the musical texture under the spoken audio.",
                    options=[
                        ClarificationQuestionOption(
                            id="opt_trap_beat",
                            label="140 BPM Heavy 808 Trap Beat",
                            description="Punchy modern bass rhythm with ducking",
                        ),
                        ClarificationQuestionOption(
                            id="opt_orchestral_hybrid",
                            label="Cinematic Orchestral Hybrid",
                            description="Dynamic brass and driving rhythmic percussion",
                        ),
                    ],
                    allow_custom=True,
                )
            )

        return questions[:3]


class IntentAutoFiller:
    """Auto-fills missing production dimensions into a cohesive plan and 4-block prompt."""

    def __init__(self, mock_mode: bool | None = None) -> None:
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self._genai_client: Any = None
        if not self.mock_mode:
            self._init_genai_client()

    def _init_genai_client(self) -> None:
        try:
            self._genai_client = get_genai_client(
                location=getattr(settings, "gemini_location", "global")
            )
        except Exception as exc:
            logger.warning("IntentAutoFiller could not initialize GenAI client: %s", exc)
            self._genai_client = None

    def generate_plan(
        self,
        intent: str,
        inputs: IntentSlotInputs | None = None,
        answers: dict[str, str] | None = None,
        resolution: str = "720p",
        aspect_ratio: str = "16:9",
        session_name: str | None = None,
        enable_safety_sanitization: bool = True,
    ) -> AutoFillIntentPlanResponse:
        """Generates a cohesive production plan and canonical 4-block Gemini Omni Flash prompt."""
        inputs = inputs or IntentSlotInputs()
        answers = answers or {}
        raw_intent = (intent or "").strip()

        if not raw_intent:
            raw_intent = (
                "Two visionary creators demonstrating an epic concept in a high-tech studio"
            )

        # Match theme / genre
        lower_intent = raw_intent.lower()
        is_cyberpunk = any(
            w in lower_intent
            for w in ("cyber", "neon", "hacker", "tokyo", "matrix", "future", "sci-fi", "mainframe")
        )
        is_wizard = any(
            w in lower_intent
            for w in ("wizard", "magic", "spell", "potion", "hogwarts", "sorcerer", "tavern", "rap")
        )
        is_cooking = any(
            w in lower_intent
            for w in ("cook", "chef", "kitchen", "culinary", "recipe", "dish", "food")
        )
        is_samurai = any(
            w in lower_intent
            for w in ("samurai", "katana", "ninja", "bamboo", "dojo", "ronin", "bushido")
        )
        is_noir = any(
            w in lower_intent
            for w in ("detective", "noir", "crime", "investigat", "whiskey", "shadow")
        )

        # 1. Resolve Audio Beat (inputs > answers > genre harmonic default)
        audio_beat = self._resolve_answer(
            slot_name="audio_beat",
            explicit_val=inputs.audio_beat,
            answers=answers,
            question_keys=("q_audio", "audio", "music", "audio_beat"),
        )
        if not audio_beat:
            if is_cyberpunk:
                audio_beat = "135 BPM Dark Cyber Synthwave with pulsing analog arpeggios"
            elif is_wizard:
                audio_beat = "140 BPM Heavy 808 Trap Beat with pipe organ stabs"
            elif is_cooking:
                audio_beat = "Upbeat Culinary Funk Beat with snappy bass and brass"
            elif is_samurai:
                audio_beat = "Traditional Taiko Drums with ambient bamboo flute and heavy sub-bass"
            elif is_noir:
                audio_beat = "Melancholic Slow Jazz with tenor saxophone and brush drums"
            else:
                audio_beat = "140 BPM Dynamic Cinematic Trap Beat with driving 808 glides"

        # 2. Resolve Setting / Environment
        environment = self._resolve_answer(
            slot_name="setting",
            explicit_val=inputs.setting,
            answers=answers,
            question_keys=("q_setting", "setting", "env", "environment", "location"),
        )
        if not environment:
            if is_cyberpunk:
                environment = "Neo Tokyo rainy alleyway with glowing holographic billboards and wet asphalt reflections"
            elif is_wizard:
                environment = (
                    "Smoky medieval tavern stage with flickering torchlight and wooden timber beams"
                )
            elif is_cooking:
                environment = (
                    "Michelin-star stainless steel kitchen with roaring gas burners and copper pans"
                )
            elif is_samurai:
                environment = "Misty bamboo forest at sunset with amber sunbeams slicing through bamboo stalks"
            elif is_noir:
                environment = "Dimly lit 1940s private investigator office with rain beating against windowpanes"
            else:
                environment = "Atmospheric neon-lit urban stage with dramatic volumetric haze"

        # 3. Resolve Camera & Lighting / Style Tone
        style_tone = self._resolve_answer(
            slot_name="style_tone",
            explicit_val=inputs.style_tone,
            answers=answers,
            question_keys=("q_style", "style", "style_tone", "camera", "lighting", "q_camera"),
        )
        if not style_tone:
            if is_cyberpunk:
                style_tone = "Anamorphic 35mm lens with cyan and magenta neon rim lighting, low-angle dynamic push-in"
            elif is_wizard:
                style_tone = "Gothic dramatic rim lighting with emerald and violet backlight slicing through dense fog"
            elif is_cooking:
                style_tone = "High-end culinary macro lens with shallow depth of field and warm tungsten glow"
            elif is_samurai:
                style_tone = "Cinematic 50mm tracking shot with golden hour sunset flare and natural rim light"
            elif is_noir:
                style_tone = "High-contrast chiaroscuro black and white film lighting with harsh Venetian blind shadows"
            else:
                style_tone = "Anamorphic 35mm cinema with directional rim lighting and fluid Steadicam motion"

        camera_lighting = f"In a single continuous shot. No scene cuts. {style_tone}."

        # 4. Resolve Characters (prioritizing saved Vault character_profiles)
        characters: list[CharacterRoleModel] = []
        role_letters = ["Role A", "Role B", "Role C", "Role D"]

        if inputs.character_profiles:
            for idx, prof in enumerate(inputs.character_profiles[:4]):
                r_id = role_letters[idx] if idx < len(role_letters) else f"Role {idx + 1}"
                raw_name = (prof.name or prof.role_id or f"Character {idx + 1}").strip()
                vault_fallback = KNOWN_VAULT_PROFILES.get(raw_name.lower(), {})

                ref_url = prof.reference_url or vault_fallback.get("reference_url")
                wardrobe = (
                    prof.wardrobe
                    or vault_fallback.get("wardrobe")
                    or self._generate_wardrobe(raw_name, idx, is_cyberpunk, is_wizard, is_cooking)
                )
                voice_style = (
                    prof.voice_style
                    or vault_fallback.get("voice_style")
                    or self._generate_voice_style(
                        raw_name, idx, is_cyberpunk, is_wizard, is_cooking
                    )
                )
                desc = (
                    prof.description
                    or vault_fallback.get("description")
                    or self._generate_char_description(
                        raw_name, idx, is_cyberpunk, is_wizard, is_cooking
                    )
                )
                tags = (
                    list(prof.aesthetic_tags)
                    if prof.aesthetic_tags
                    else list(
                        vault_fallback.get(
                            "aesthetic_tags", ["Cinematic", "High Definition", "Omni Flash"]
                        )
                    )
                )

                if enable_safety_sanitization:
                    if not vault_fallback and not prof.reference_url:
                        raw_name = sanitize_real_names(raw_name)
                        desc = sanitize_real_names(desc)
                        wardrobe = sanitize_real_names(wardrobe)
                        voice_style = sanitize_real_names(voice_style)

                characters.append(
                    CharacterRoleModel(
                        role_id=r_id,
                        name=raw_name,
                        description=desc,
                        reference_url=ref_url,
                        wardrobe=wardrobe,
                        voice_style=voice_style,
                        aesthetic_tags=tags,
                        image_role=prof.image_role or "Character Reference",
                        is_offscreen_narrator=prof.is_offscreen_narrator,
                    )
                )

        existing_names_lower = {c.name.lower() for c in characters}
        char_names = [
            n.strip()
            for n in (inputs.characters or [])
            if n and n.strip() and n.strip().lower() not in existing_names_lower
        ]

        if not characters and not char_names:
            # Check answers for characters
            char_ans = self._resolve_answer(
                slot_name="characters",
                explicit_val=None,
                answers=answers,
                question_keys=("q_characters", "characters", "char", "roles"),
            )
            if char_ans:
                char_names = [c.strip() for c in char_ans.split(",") if c.strip()]

        if not characters and not char_names:
            # Check intent for parody / real names
            for pattern, parody_name in REAL_NAME_PARODY_MAP.items():
                if re.search(pattern, raw_intent, flags=re.IGNORECASE):
                    if parody_name not in char_names:
                        char_names.append(parody_name)

        if not characters and not char_names:
            # Archetype defaults based on genre
            if is_cyberpunk:
                char_names = ["Detective K", "Officer Vex"]
            elif is_wizard:
                char_names = ["Spectacled Wizard Bruv", "Platinum Rival Blood"]
            elif is_cooking:
                char_names = ["Chef Gordon", "Chef Julia"]
            elif is_samurai:
                char_names = ["Ronin Kensei", "Shadow Shinobi"]
            elif is_noir:
                char_names = ["Gritty Detective", "Mysterious Informant"]
            else:
                char_names = ["Lead Protagonist", "Rival Counterpart"]

        # Append any string-named characters
        for name in char_names:
            if len(characters) >= 4:
                break
            idx = len(characters)
            r_id = role_letters[idx] if idx < len(role_letters) else f"Role {idx + 1}"
            vault_match = KNOWN_VAULT_PROFILES.get(name.strip().lower(), {})
            ref_url = vault_match.get("reference_url")
            wardrobe = vault_match.get("wardrobe") or self._generate_wardrobe(
                name, idx, is_cyberpunk, is_wizard, is_cooking
            )
            voice_style = vault_match.get("voice_style") or self._generate_voice_style(
                name, idx, is_cyberpunk, is_wizard, is_cooking
            )
            desc = vault_match.get("description") or self._generate_char_description(
                name, idx, is_cyberpunk, is_wizard, is_cooking
            )
            tags = list(
                vault_match.get("aesthetic_tags", ["Cinematic", "High Definition", "Omni Flash"])
            )

            clean_name = (
                vault_match.get("name", name)
                if (vault_match or ref_url)
                else (sanitize_real_names(name) if enable_safety_sanitization else name)
            )
            if enable_safety_sanitization:
                if not vault_match and not ref_url:
                    desc = sanitize_real_names(desc)
                    wardrobe = sanitize_real_names(wardrobe)
                    voice_style = sanitize_real_names(voice_style)

            characters.append(
                CharacterRoleModel(
                    role_id=r_id,
                    name=clean_name,
                    description=desc,
                    reference_url=ref_url,
                    wardrobe=wardrobe,
                    voice_style=voice_style,
                    aesthetic_tags=tags,
                    image_role="Character Reference",
                    is_offscreen_narrator=False,
                )
            )

        # Ensure at least 2 characters for two-hander scene choreography
        if len(characters) == 1:
            first_lower = characters[0].name.lower()
            partner_name = "YoTotti" if first_lower == "dumble dior" else "Allied Partner"
            partner_vault = KNOWN_VAULT_PROFILES.get(partner_name.lower(), {})
            characters.append(
                CharacterRoleModel(
                    role_id="Role B",
                    name=partner_vault.get("name", partner_name),
                    description=partner_vault.get("description")
                    or self._generate_char_description(
                        partner_name, 1, is_cyberpunk, is_wizard, is_cooking
                    ),
                    reference_url=partner_vault.get("reference_url"),
                    wardrobe=partner_vault.get("wardrobe")
                    or self._generate_wardrobe(
                        partner_name, 1, is_cyberpunk, is_wizard, is_cooking
                    ),
                    voice_style=partner_vault.get("voice_style")
                    or self._generate_voice_style(
                        partner_name, 1, is_cyberpunk, is_wizard, is_cooking
                    ),
                    aesthetic_tags=list(
                        partner_vault.get(
                            "aesthetic_tags", ["Cinematic", "High Definition", "Omni Flash"]
                        )
                    ),
                    image_role="Character Reference",
                    is_offscreen_narrator=False,
                )
            )

        # 5. Resolve Sound Effects
        sound_effects = self._resolve_answer(
            slot_name="sound_effects",
            explicit_val=inputs.sound_effects,
            answers=answers,
            question_keys=("q_sfx", "sound_effects", "sfx"),
        )
        if not sound_effects:
            if is_cyberpunk:
                sound_effects = (
                    "(rain splashing on wet asphalt, subtle electronic hum of cyberware)"
                )
            elif is_wizard:
                sound_effects = (
                    "(crackle of magical spark, heavy wooden tavern footsteps, mug clinking)"
                )
            elif is_cooking:
                sound_effects = (
                    "(sizzling oil on hot pan, knife rhythmic chopping on cutting board)"
                )
            elif is_samurai:
                sound_effects = "(wind whistling through bamboo, blade subtle metallic ring)"
            else:
                sound_effects = "(ambient room reverberation, subtle foot movement)"

        # 6. Resolve Dialogue Direction, Vocal Delivery & Spoken Lines
        dialogue_direction = (
            self._resolve_answer(
                slot_name="dialogue_direction",
                explicit_val=inputs.dialogue_direction,
                answers=answers,
                question_keys=("q_dialogue_direction", "dialogue_direction", "direction"),
            )
            or ""
        )
        dialogue_custom = (
            inputs.dialogue.strip() if (inputs.dialogue and inputs.dialogue.strip()) else None
        )
        if not dialogue_custom and not dialogue_direction:
            ans_diag = self._resolve_answer(
                slot_name="dialogue",
                explicit_val=None,
                answers=answers,
                question_keys=("q_dialogue", "dialogue", "lines", "script"),
            )
            if ans_diag:
                # If the answer is a direction preset or has no quotation marks, treat it as dialogue_direction
                if '"' not in ans_diag and ":" not in ans_diag:
                    dialogue_direction = ans_diag
                else:
                    dialogue_custom = ans_diag

        if dialogue_direction:
            vocal_delivery = (
                f"Dialogue Direction: {dialogue_direction}. "
                "Rhythmic, confident, clear front-and-center vocal projection."
            )
        else:
            vocal_delivery = "Rhythmic, confident, clear front-and-center vocal projection."

        diag_map: dict[str, str] = {}
        if dialogue_custom:
            diag_map[characters[0].name] = dialogue_custom
            fallback_resps = [
                "Standing ground with unwavering conviction!",
                "Everything proceeding exactly as ordained.",
                "The line holds, no exceptions.",
            ]
            for idx, c in enumerate(characters[1:], 0):
                diag_map[c.name] = fallback_resps[min(idx, len(fallback_resps) - 1)]
        elif dialogue_direction:
            diag_map = self._synthesize_multicharacter_dialogue(
                characters=characters,
                raw_intent=raw_intent,
                environment=environment,
                dialogue_direction=dialogue_direction,
                is_wizard=is_wizard,
                is_cyberpunk=is_cyberpunk,
                is_cooking=is_cooking,
                is_samurai=is_samurai,
            )
        elif is_wizard:
            wizard_lines = [
                "I've been brewing formulas while you were still studying scrolls!",
                "Your spells are ancient history—this is a new era, Bruv!",
                "Quiet, both of you—true mastery speaks without shouting.",
                "The wards are active, let's keep it steady.",
            ]
            for idx, c in enumerate(characters):
                diag_map[c.name] = wizard_lines[min(idx, len(wizard_lines) - 1)]
        elif is_cyberpunk:
            cyber_lines = [
                "System anomaly detected in Sector 4. Keep your eyes sharp.",
                "Already patched into the feed. Let's move before they purge the logs.",
                "Signal secured. Trace protocol bypassed.",
                "Sub-net offline. We're clear.",
            ]
            for idx, c in enumerate(characters):
                diag_map[c.name] = cyber_lines[min(idx, len(cyber_lines) - 1)]
        elif is_cooking:
            cook_lines = [
                "The seasoning is raw! You need discipline on this line!",
                "Taste the glaze—that is pure technique and precision.",
                "Plates leaving the window—hands on deck now!",
                "Check the oven temp, timers running!",
            ]
            for idx, c in enumerate(characters):
                diag_map[c.name] = cook_lines[min(idx, len(cook_lines) - 1)]
        elif is_samurai:
            samurai_lines = [
                "Our paths meet at dusk. Draw your steel.",
                "The wind favors neither blade today.",
                "Honor guides the edge of truth.",
                "Stand ready.",
            ]
            for idx, c in enumerate(characters):
                diag_map[c.name] = samurai_lines[min(idx, len(samurai_lines) - 1)]
        else:
            default_lines = [
                "We came here to make history, not excuses.",
                "Then let's show them what real mastery looks like!",
                "Nothing stands in our way today.",
                "All in, no looking back.",
            ]
            for idx, c in enumerate(characters):
                diag_map[c.name] = default_lines[min(idx, len(default_lines) - 1)]

        if enable_safety_sanitization:
            for k in diag_map:
                line = diag_map[k]
                for idx, c in enumerate(characters):
                    if (c.reference_url or c.name.lower() in KNOWN_VAULT_PROFILES) and c.name:
                        line = line.replace(c.name, f"__VCHAR_{idx}__")
                line = sanitize_real_names(line)
                for idx, c in enumerate(characters):
                    if (c.reference_url or c.name.lower() in KNOWN_VAULT_PROFILES) and c.name:
                        line = line.replace(f"__VCHAR_{idx}__", c.name)
                diag_map[k] = line
            if dialogue_direction:
                dialogue_direction = sanitize_real_names(dialogue_direction)

        direction_acting_note = (
            f" [Dialogue Direction: {dialogue_direction}]" if dialogue_direction else ""
        )

        # 7. Choreograph 10-second continuous shot screenplay script
        num_chars = len(characters)
        if num_chars == 1:
            c0 = characters[0]
            d0 = diag_map[c0.name]
            screenplay_script = (
                f"[0-4s] Action: {c0.name} ({c0.role_id}) commands the frame in {environment}, "
                f"moving with purposeful intensity.{direction_acting_note} Audio: {audio_beat} build-up {sound_effects}. "
                f'Dialogue: {c0.name}: "{d0}"\n'
                f"[4-7s] Action: Camera glides smoothly in a continuous tracking shot around {c0.name} ({c0.role_id}), "
                f"highlighting commanding presence and environment details. Audio: {audio_beat} beat drop.\n"
                f"[7-10s] Action: {c0.name} ({c0.role_id}) holds a decisive dynamic pose as lighting pulses, "
                f"holding continuous dramatic tension as the shot concludes. Audio: {audio_beat} crescendo."
            )
        elif num_chars == 2:
            c0, c1 = characters[0], characters[1]
            d0, d1 = diag_map[c0.name], diag_map[c1.name]
            screenplay_script = (
                f"[0-3s] Action: {c0.name} ({c0.role_id}) steps into frame in {environment}, "
                f"initiating action with focused intensity.{direction_acting_note} Audio: {audio_beat} build-up {sound_effects}. "
                f'Dialogue: {c0.name}: "{d0}"\n'
                f"[3-6s] Action: Camera glides smoothly in a continuous tracking shot toward {c1.name} ({c1.role_id}), "
                f"who confronts {c0.name} with commanding presence.{direction_acting_note} Audio: {audio_beat} beat drop. "
                f'Dialogue: {c1.name}: "{d1}"\n'
                f"[6-10s] Action: Both performers lock into a high-energy dynamic tableau as lighting pulses, "
                f"holding continuous dramatic tension as the shot concludes. Audio: {audio_beat} crescendo. "
                f'Dialogue: Both: "We run this domain!"'
            )
        elif num_chars == 3:
            c0, c1, c2 = characters[0], characters[1], characters[2]
            d0, d1, d2 = diag_map[c0.name], diag_map[c1.name], diag_map[c2.name]
            screenplay_script = (
                f"[0-3s] Action: {c0.name} ({c0.role_id}) takes center focus in {environment}, "
                f"gesturing with energy alongside {c1.name} ({c1.role_id}) and {c2.name} ({c2.role_id}).{direction_acting_note} "
                f"Audio: {audio_beat} build-up {sound_effects}. "
                f'Dialogue: {c0.name}: "{d0}"\n'
                f"[3-6s] Action: Camera pans smoothly across to {c1.name} ({c1.role_id}), "
                f"who reacts with calm confidence while {c2.name} ({c2.role_id}) observes with commanding authority.{direction_acting_note} "
                f"Audio: {audio_beat} beat drop. "
                f'Dialogue: {c1.name}: "{d1}"\n'
                f"[6-10s] Action: Camera pulls back to reveal all three performers ({c0.name}, {c1.name}, and {c2.name}) "
                f"framed together in a powerful unified composition, exuding collective mastery as the shot concludes. "
                f"Audio: {audio_beat} crescendo. "
                f'Dialogue: {c2.name}: "{d2}"'
            )
        else:
            c0, c1, c2, c3 = characters[0], characters[1], characters[2], characters[3]
            d0, d1, d2, d3 = (
                diag_map[c0.name],
                diag_map[c1.name],
                diag_map[c2.name],
                diag_map[c3.name],
            )
            screenplay_script = (
                f"[0-3s] Action: {c0.name} ({c0.role_id}) and {c1.name} ({c1.role_id}) initiate the scene in {environment}, "
                f"flanked by {c2.name} ({c2.role_id}) and {c3.name} ({c3.role_id}).{direction_acting_note} "
                f"Audio: {audio_beat} build-up {sound_effects}. "
                f'Dialogue: {c0.name}: "{d0}"\n'
                f"[3-6s] Action: Camera tracks dynamically to {c1.name} ({c1.role_id}) and {c2.name} ({c2.role_id}), "
                f"capturing their sharp interplay while {c3.name} coordinates in the background.{direction_acting_note} "
                f"Audio: {audio_beat} beat drop. "
                f'Dialogue: {c1.name}: "{d1}"\n'
                f"[6-10s] Action: All four performers ({c0.name}, {c1.name}, {c2.name}, and {c3.name}) "
                f"lock into an imposing ensemble tableau under dramatic pulsing lighting as the shot concludes. "
                f"Audio: {audio_beat} crescendo. "
                f'Dialogue: {c2.name}: "{d2}" / {c3.name}: "{d3}"'
            )

        # 8. Deconstructed Scene Model
        all_char_names = ", ".join(c.name for c in characters)
        dialogue_summary = " / ".join(f'{c.name}: "{diag_map[c.name]}"' for c in characters)
        scenes = [
            DeconstructedSceneModel(
                scene_number=1,
                active_roles=[c.role_id for c in characters[:4]],
                action=f"{all_char_names} engage in a continuous dramatic encounter in {environment}.{direction_acting_note}",
                dialogue=dialogue_summary,
                audio_cues=audio_beat,
                timecode="0-10s",
                duration_seconds=10.0,
            )
        ]

        # 9. Keyframe Image Prompt
        if len(characters) == 1:
            chars_str = characters[0].name
        elif len(characters) == 2:
            chars_str = f"{characters[0].name} and {characters[1].name}"
        else:
            chars_str = f"{', '.join(c.name for c in characters[:-1])}, and {characters[-1].name}"
        keyframe_image_prompt = (
            f"Cinematic keyframe shot of {chars_str} in {environment}. "
            f"{style_tone}, 8k resolution, highly detailed, dramatic rim lighting, award-winning cinematography."
        )
        if enable_safety_sanitization:
            for idx, c in enumerate(characters):
                if (c.reference_url or c.name.lower() in KNOWN_VAULT_PROFILES) and c.name:
                    keyframe_image_prompt = keyframe_image_prompt.replace(
                        c.name, f"__VCHAR_{idx}__"
                    )
            keyframe_image_prompt = sanitize_real_names(keyframe_image_prompt)
            for idx, c in enumerate(characters):
                if (c.reference_url or c.name.lower() in KNOWN_VAULT_PROFILES) and c.name:
                    keyframe_image_prompt = keyframe_image_prompt.replace(
                        f"__VCHAR_{idx}__", c.name
                    )

        # 10. Canonical 4-Block Gemini Omni Flash Prompt
        raw_compiled_prompt = self._compile_canonical_four_block_prompt(
            characters=characters,
            environment=environment,
            camera_lighting=camera_lighting,
            audio_beat=audio_beat,
            sound_effects=sound_effects,
            screenplay_script=screenplay_script,
            aspect_ratio=aspect_ratio,
            enable_safety_sanitization=enable_safety_sanitization,
            dialogue_direction=dialogue_direction,
            vocal_delivery=vocal_delivery,
        )

        plan = CohesiveProductionPlan(
            intent=raw_intent,
            style_tone=style_tone,
            characters=characters,
            environment=environment,
            camera_lighting=camera_lighting,
            audio_beat=audio_beat,
            sound_effects=sound_effects,
            vocal_delivery=vocal_delivery,
            dialogue_direction=dialogue_direction,
            screenplay_script=screenplay_script,
            scenes=scenes,
            keyframe_image_prompt=keyframe_image_prompt,
            raw_compiled_prompt=raw_compiled_prompt,
        )

        return AutoFillIntentPlanResponse(
            success=True,
            plan=plan,
            raw_compiled_prompt=raw_compiled_prompt,
            details="Cohesive production plan compiled successfully with 4-block Omni Flash prompt.",
        )

    def _resolve_answer(
        self,
        slot_name: str,
        explicit_val: str | None,
        answers: dict[str, str],
        question_keys: tuple[str, ...],
    ) -> str | None:
        """Resolves slot value prioritizing explicit inputs, then matching answers."""
        if explicit_val and explicit_val.strip():
            return explicit_val.strip()

        # Check direct key match
        for key in question_keys:
            if key in answers and answers[key] and str(answers[key]).strip():
                return str(answers[key]).strip()

        # Check substring matches in answers keys
        for ans_k, ans_v in answers.items():
            if ans_v and str(ans_v).strip():
                k_lower = ans_k.lower()
                if any(qk in k_lower for qk in question_keys) or slot_name in k_lower:
                    return str(ans_v).strip()

        return None

    def _generate_wardrobe(
        self, name: str, index: int, is_cyberpunk: bool, is_wizard: bool, is_cooking: bool
    ) -> str:
        if is_cyberpunk:
            return (
                "Black ballistic trench coat with glowing cyan neon trim and tactical cyber-boots"
                if index == 0
                else "Matte-black combat jumpsuit with chrome shoulder plating and optic visor"
            )
        if is_wizard:
            return (
                "Crimson velvet hooded tracksuit with gold wire-rim glasses"
                if index == 0
                else "Platinum tailored frock coat with emerald lapels and silver chain"
            )
        if is_cooking:
            return (
                "Crisp white executive chef coat with black rolled-up sleeves"
                if index == 0
                else "Vintage linen culinary apron with brass hardware and check neckerchief"
            )
        return (
            "Custom tailored designer jacket with subtle metallic embroidery"
            if index == 0
            else "Sleek monochromatic streetwear with utility accents"
        )

    def _generate_voice_style(
        self, name: str, index: int, is_cyberpunk: bool, is_wizard: bool, is_cooking: bool
    ) -> str:
        if is_cyberpunk:
            return (
                "Calm, gravelly synthetic baritone with subtle vocal resonance"
                if index == 0
                else "Sharp, rapid tactical vocal delivery with confident modulation"
            )
        if is_wizard:
            return (
                "Fast-paced confident Atlanta rap cadence with crisp enunciated swagger"
                if index == 0
                else "Pompous aristocratic British drawl with theatrical cadence"
            )
        if is_cooking:
            return (
                "Passionate, intense British baritone with commanding tempo"
                if index == 0
                else "Warm, melodic and authoritative classical culinary voice"
            )
        return (
            "Clear, resonant vocal projection with dynamic cinematic emphasis"
            if index == 0
            else "Punchy, expressive vocal delivery with intense conviction"
        )

    def _generate_char_description(
        self, name: str, index: int, is_cyberpunk: bool, is_wizard: bool, is_cooking: bool
    ) -> str:
        if is_cyberpunk:
            return (
                f"{name}, a seasoned street investigator with subtle cybernetic facial enhancements."
                if index == 0
                else f"{name}, an agile netrunner specialist with sharp calculating eyes."
            )
        if is_wizard:
            return (
                f"{name}, a young magical prodigy with confident posture and spectacles."
                if index == 0
                else f"{name}, an aristocratic sorcery scholar with sleek combed hair and diamond accent."
            )
        if is_cooking:
            return (
                f"{name}, a world-renowned master chef with intense perfectionist focus."
                if index == 0
                else f"{name}, a classical culinary virtuoso with effortless kitchen finesse."
            )
        return (
            f"{name}, a charismatic and determined leader in command of the stage."
            if index == 0
            else f"{name}, a formidable counterpart with sharp instincts and dynamic presence."
        )

    def _synthesize_multicharacter_dialogue(
        self,
        characters: list[CharacterRoleModel],
        raw_intent: str,
        environment: str,
        dialogue_direction: str,
        is_wizard: bool,
        is_cyberpunk: bool,
        is_cooking: bool,
        is_samurai: bool,
    ) -> dict[str, str]:
        """Synthesizes in-character spoken lines for all characters guided by dialogue_direction."""
        if not self.mock_mode and self._genai_client is not None:
            try:
                char_desc_lines = "\n".join(
                    f"Character {idx + 1} ({c.name}, {c.voice_style}): {c.description}"
                    for idx, c in enumerate(characters)
                )
                format_lines = "\n".join(
                    f"LINE_{idx + 1}: <line for {c.name}>" for idx, c in enumerate(characters)
                )
                prompt = (
                    f"You are a film dialogue writer for a 10-second continuous shot.\n"
                    f"Premise: {raw_intent}\n"
                    f"Environment: {environment}\n"
                    f"{char_desc_lines}\n"
                    f"Dialogue Direction / Guidance: {dialogue_direction}\n\n"
                    f"Write exactly {len(characters)} short, punchy spoken dialogue lines (max 15 words each) "
                    f"following the Dialogue Direction above.\n"
                    f"Format strictly as:\n"
                    f"{format_lines}"
                )
                resp = self._genai_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                text = getattr(resp, "text", "") or ""
                parsed: dict[str, str] = {}
                for idx, c in enumerate(characters):
                    m = re.search(rf"LINE_{idx + 1}:\s*(.+)", text)
                    if m:
                        val = m.group(1).strip().strip('"').strip("'")
                        if val:
                            parsed[c.name] = val
                if len(parsed) == len(characters):
                    return parsed
            except Exception as exc:
                logger.warning("Multicharacter guided dialogue LLM synthesis fallback: %s", exc)

        dir_lower = dialogue_direction.lower()
        intent_lower = raw_intent.lower()

        if any(
            w in dir_lower or w in intent_lower
            for w in ("audit", "ledger", "galleon", "vault", "corporate")
        ):
            cues = [
                "The quarterly vault ledger is immaculate, fam—every stack is accounted for.",
                "Light work, Headmaster. Tell the elves to double the count before closing.",
                "Double-checked and verified—all gold sealed in the deep vault!",
                "The registers balance to the single galleon, sir!",
            ]
        elif any(w in dir_lower for w in ("rhyme", "rhyming", "rap", "diss", "couplet", "bars")):
            cues = [
                "My bars hit harder than arcane thunder, watch your whole strategy fall asunder!",
                "Talk is cheap when the crown is mine, I've been running this stage since the start of time!",
                "Stacking verses like enchanted stone, neither of you takes this throne!",
                "Beat drops heavy, rhythm stays true, nobody matches what we do!",
            ]
        elif any(w in dir_lower for w in ("sarcastic", "deadpan", "dry", "unfazed", "banter")):
            cues = [
                "Oh brilliant, another catastrophic emergency right before our lunch break.",
                "Relax, I've seen worse on a Tuesday—just press the override and look confident.",
                "I'd look confident if either of you had any idea what you're doing.",
                "Fabulous teamwork as always, gentlemen.",
            ]
        elif is_wizard:
            cues = [
                "Every spell in the grimoire bows to precision—watch how a master works the room.",
                "Calm energy, bruv. The magic speaks for itself without raising a voice.",
                "Gentlemen, the ancient standards of this house remain supreme.",
                "Enchantments holding steady across the perimeter.",
            ]
        elif is_cyberpunk:
            cues = [
                "Firewall's breached on Sector 9—keep your optics locked on the main terminal.",
                "Already inside the sub-grid. Grab the drive and let's ghost.",
                "Telemetry stream confirmed clean—grab the drive before the trace locks.",
                "Perimeter drone dispatched, extraction window clear.",
            ]
        elif is_cooking:
            cues = [
                "That reduction needs thirty more seconds of heat—perfection is in the timing!",
                "Plate's already resting, Chef. One taste and the judges are ours.",
                "Garnish positioned, pass is moving now—table four ready!",
                "Flawless execution on the line tonight!",
            ]
        elif is_samurai:
            cues = [
                "Steel remembers every promise spoken under these bamboo shadows.",
                "Then let one strike settle the debt between us.",
                "The wind carries our ancestors' judgment.",
                "Blades drawn, fate decided.",
            ]
        else:
            c0_name = characters[0].name if characters else "Leader"
            c1_name = characters[1].name if len(characters) > 1 else "Partner"
            cues = [
                f"Focus up, {c1_name}—everything we planned comes down to this next move.",
                f"Say less, {c0_name}. I was born ready for this moment.",
                "Then let's take control and finish what we started.",
                "All positions locked, execute on my signal!",
            ]

        res_dict: dict[str, str] = {}
        for idx, c in enumerate(characters):
            res_dict[c.name] = cues[min(idx, len(cues) - 1)]
        return res_dict

    def _synthesize_guided_dialogue(
        self,
        raw_intent: str,
        char_a: CharacterRoleModel,
        char_b: CharacterRoleModel,
        environment: str,
        dialogue_direction: str,
        is_wizard: bool,
        is_cyberpunk: bool,
        is_cooking: bool,
        is_samurai: bool,
    ) -> tuple[str, str]:
        """Synthesizes two in-character spoken lines guided by the user's dialogue_direction."""
        res_map = self._synthesize_multicharacter_dialogue(
            characters=[char_a, char_b],
            raw_intent=raw_intent,
            environment=environment,
            dialogue_direction=dialogue_direction,
            is_wizard=is_wizard,
            is_cyberpunk=is_cyberpunk,
            is_cooking=is_cooking,
            is_samurai=is_samurai,
        )
        return res_map.get(char_a.name, ""), res_map.get(char_b.name, "")

    def _compile_canonical_four_block_prompt(
        self,
        characters: list[CharacterRoleModel],
        environment: str,
        camera_lighting: str,
        audio_beat: str,
        sound_effects: str,
        screenplay_script: str,
        aspect_ratio: str,
        enable_safety_sanitization: bool,
        dialogue_direction: str = "",
        vocal_delivery: str = "",
    ) -> str:
        """Assembles the canonical 4-block Gemini Omni Flash prompt string."""
        # Block 1: INPUT ROLES & REFERENCES
        ref_lines: list[str] = []
        ref_meta_tags: list[str] = []
        for idx, char in enumerate(characters):
            img_num = idx + 1
            ref_meta_tags.append(f"<IMAGE_REF_{idx}>@Image{img_num}")
            wardrobe_tag = f" [Wardrobe: {char.wardrobe}]" if char.wardrobe else ""
            ref_lines.append(
                f"- {char.role_id} ({char.image_role}): {char.name} (@Image{img_num}){wardrobe_tag}"
            )

        block1_header = "### INPUT ROLES & REFERENCES"
        meta_line = f"[# References {', '.join(ref_meta_tags)}]"
        block1 = f"{block1_header}\n{meta_line}\n" + "\n".join(ref_lines)

        # Block 2: CHARACTER PROFILES
        profile_lines: list[str] = []
        for idx, char in enumerate(characters):
            img_num = idx + 1
            voice_tag = f" [Voice Style: {char.voice_style}]" if char.voice_style else ""
            profile_lines.append(
                f"- {char.role_id} ({char.name}) (Reference Image: @Image{img_num}): {char.description}{voice_tag}"
            )
        block2 = "### CHARACTER PROFILES\n" + "\n".join(profile_lines)

        # Block 3: SCENE INSTRUCTIONS
        scene_inst = [
            "- Shot Number: 1",
            f"- Action Directive: {camera_lighting}",
            f"- Aspect Ratio: {aspect_ratio}",
            f"- Environment: {environment}",
            f"- Camera & Lighting: {camera_lighting}",
            f"- Audio Beat & Ducking: instrumental {audio_beat}. Ensure the background music ducks under the spoken dialogue so the voice is clear, front-and-center, and intelligible.",
        ]
        if dialogue_direction:
            scene_inst.append(
                f"- Dialogue Direction & Vocal Guidance: {dialogue_direction} (Ensure spoken lines and vocal cadence follow this direction)."
            )
        elif vocal_delivery:
            scene_inst.append(f"- Vocal Delivery: {vocal_delivery}")

        block3 = "### SCENE INSTRUCTIONS\n" + "\n".join(scene_inst)

        # Block 4: TIMELINE
        # Split screenplay script into lines or preserve
        block4 = f"### TIMELINE\n{screenplay_script}"

        full_prompt = f"{block1}\n\n{block2}\n\n{block3}\n\n{block4}"

        if enable_safety_sanitization:
            # Preserve explicit Vault character names with placeholders during sanitization
            vault_placeholders: list[tuple[str, str]] = []
            for idx, char in enumerate(characters):
                if (char.reference_url or char.name.lower() in KNOWN_VAULT_PROFILES) and char.name:
                    token = f"__VAULT_CHAR_{idx}__"
                    vault_placeholders.append((token, char.name))
                    full_prompt = full_prompt.replace(char.name, token)
            full_prompt = sanitize_real_names(full_prompt)
            for token, orig_name in vault_placeholders:
                full_prompt = full_prompt.replace(token, orig_name)

        return full_prompt


__all__ = ["IntentAutoFiller", "IntentGapAnalyzer"]
