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
        if inputs.characters:
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

        # 7. Dialogue slot
        if inputs.dialogue and inputs.dialogue.strip():
            filled_slots["dialogue"] = inputs.dialogue.strip()
        else:
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

        # 4. Resolve Characters
        characters: list[CharacterRoleModel] = []
        char_names = list(inputs.characters) if inputs.characters else []

        if not char_names:
            # Check answers for characters
            char_ans = self._resolve_answer(
                slot_name="characters",
                explicit_val=None,
                answers=answers,
                question_keys=("q_characters", "characters", "char", "roles"),
            )
            if char_ans:
                char_names = [c.strip() for c in char_ans.split(",") if c.strip()]

        if not char_names:
            # Check intent for parody / real names
            for pattern, parody_name in REAL_NAME_PARODY_MAP.items():
                if re.search(pattern, raw_intent, flags=re.IGNORECASE):
                    if parody_name not in char_names:
                        char_names.append(parody_name)

        if not char_names:
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

        # Ensure at least 2 characters
        if len(char_names) == 1:
            char_names.append("Allied Partner")

        # Build CharacterRoleModel items
        role_letters = ["Role A", "Role B", "Role C", "Role D"]
        for idx, name in enumerate(char_names[:4]):
            r_id = role_letters[idx] if idx < len(role_letters) else f"Role {idx + 1}"
            wardrobe = self._generate_wardrobe(name, idx, is_cyberpunk, is_wizard, is_cooking)
            voice_style = self._generate_voice_style(name, idx, is_cyberpunk, is_wizard, is_cooking)
            desc = self._generate_char_description(name, idx, is_cyberpunk, is_wizard, is_cooking)

            if enable_safety_sanitization:
                name = sanitize_real_names(name)
                desc = sanitize_real_names(desc)
                wardrobe = sanitize_real_names(wardrobe)
                voice_style = sanitize_real_names(voice_style)

            characters.append(
                CharacterRoleModel(
                    role_id=r_id,
                    name=name,
                    description=desc,
                    wardrobe=wardrobe,
                    voice_style=voice_style,
                    aesthetic_tags=["Cinematic", "High Definition", "Omni Flash"],
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

        # 6. Resolve Vocal Delivery & Dialogue
        vocal_delivery = "Rhythmic, confident, clear front-and-center vocal projection."
        dialogue_custom = self._resolve_answer(
            slot_name="dialogue",
            explicit_val=inputs.dialogue,
            answers=answers,
            question_keys=("q_dialogue", "dialogue", "lines", "script"),
        )

        char_a = characters[0]
        char_b = characters[1]

        if dialogue_custom:
            diag_a = dialogue_custom
            diag_b = "Standing ground with unwavering conviction!"
        elif is_wizard:
            diag_a = "I've been brewing formulas while you were still studying scrolls!"
            diag_b = "Your spells are ancient history—this is a new era, Bruv!"
        elif is_cyberpunk:
            diag_a = "System anomaly detected in Sector 4. Keep your eyes sharp."
            diag_b = "Already patched into the feed. Let's move before they purge the logs."
        elif is_cooking:
            diag_a = "The seasoning is raw! You need discipline on this line!"
            diag_b = "Taste the glaze—that is pure technique and precision."
        elif is_samurai:
            diag_a = "Our paths meet at dusk. Draw your steel."
            diag_b = "The wind favors neither blade today."
        else:
            diag_a = "We came here to make history, not excuses."
            diag_b = "Then let's show them what real mastery looks like!"

        if enable_safety_sanitization:
            diag_a = sanitize_real_names(diag_a)
            diag_b = sanitize_real_names(diag_b)

        # 7. Choreograph 10-second continuous shot screenplay script
        screenplay_script = (
            f"[0-3s] Action: {char_a.name} ({char_a.role_id}) steps into frame in {environment}, "
            f"initiating action with focused intensity. Audio: {audio_beat} build-up {sound_effects}. "
            f'Dialogue: {char_a.name}: "{diag_a}"\n'
            f"[3-6s] Action: Camera glides smoothly in a continuous tracking shot toward {char_b.name} ({char_b.role_id}), "
            f"who confronts {char_a.name} with commanding presence. Audio: {audio_beat} beat drop. "
            f'Dialogue: {char_b.name}: "{diag_b}"\n'
            f"[6-10s] Action: Both performers lock into a high-energy dynamic tableau as lighting pulses, "
            f"holding continuous dramatic tension as the shot concludes. Audio: {audio_beat} crescendo. "
            f'Dialogue: Both: "We run this domain!"'
        )

        # 8. Deconstructed Scene Model
        scenes = [
            DeconstructedSceneModel(
                scene_number=1,
                active_roles=[char_a.role_id, char_b.role_id],
                action=f"{char_a.name} and {char_b.name} engage in a continuous dramatic encounter in {environment}.",
                dialogue=f'{char_a.name}: "{diag_a}" / {char_b.name}: "{diag_b}"',
                audio_cues=audio_beat,
                timecode="0-10s",
                duration_seconds=10.0,
            )
        ]

        # 9. Keyframe Image Prompt
        keyframe_image_prompt = (
            f"Cinematic keyframe shot of {char_a.name} and {char_b.name} in {environment}. "
            f"{style_tone}, 8k resolution, highly detailed, dramatic rim lighting, award-winning cinematography."
        )
        if enable_safety_sanitization:
            keyframe_image_prompt = sanitize_real_names(keyframe_image_prompt)

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
        block3 = "### SCENE INSTRUCTIONS\n" + "\n".join(scene_inst)

        # Block 4: TIMELINE
        # Split screenplay script into lines or preserve
        block4 = f"### TIMELINE\n{screenplay_script}"

        full_prompt = f"{block1}\n\n{block2}\n\n{block3}\n\n{block4}"

        if enable_safety_sanitization:
            full_prompt = sanitize_real_names(full_prompt)

        return full_prompt


__all__ = ["IntentAutoFiller", "IntentGapAnalyzer"]
