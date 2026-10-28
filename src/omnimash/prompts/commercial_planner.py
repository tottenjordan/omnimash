"""Mode 5: Commercial Soundstage 3-Act x 3-Beat (9-Shot) Planner & Canonical 4-Block Prompt Compiler.

Re-exports discovery and dual-layer identity models from `soundstage_discovery` for unified
public access while keeping each module focused and compact.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from omnimash.api.models import CharacterRoleModel
from omnimash.config import settings
from omnimash.prompts.genai_client import get_genai_client
from omnimash.prompts.offering_physics import (
    OfferingPhysicsAnalyzer,
    OfferingPhysicsSpec,
    clean_json_str,
    sanitize_single_line_field,
    scrub_offering_trademarks,
)
from omnimash.prompts.preflight_linter import PreFlightGatekeeper
from omnimash.prompts.soundstage_discovery import (
    SPOKEN_LANGUAGES,
    DualLayerIdentityAbstractor,
    DualLayerIdentitySpec,
    Palette603010,
    SoundstageDiscoveryEngine,
    SoundstageDiscoveryResult,
    TerritoryAtmosphereSpec,
    invoke_flash_json_dict,
    resolve_territory,
    select_palette_for_archetype,
)

logger = logging.getLogger(__name__)


class ExecutiveCreativeBrief(BaseModel):
    """Executive creative agency brief anchoring the 30-second 3-act commercial spot."""

    title: str
    objective: str
    audience: str
    key_tension: str
    proposition: str
    sonic_and_visual_direction: str


class StoryboardTileSpec(BaseModel):
    """Individual storyboard tile within the 3-Act x 3-Beat (9-tile) Soundstage grid."""

    shot_id: str
    act_number: int
    beat_index: int
    timecode_range: str
    framing: str
    action: str
    has_person: bool
    image_prompt: str


class SoundstageActPlan(BaseModel):
    """10-second continuous-shot act plan with dual-keyframe anchoring and linted 4-block Omni prompt."""

    act_number: int
    title: str
    time_window: str
    narrative_summary: str
    voiceover_line: str
    audio_score: str
    sound_effects: str
    first_frame_shot_id: str
    last_frame_shot_id: str
    first_frame_tag: str = "<FIRST_FRAME>"
    last_frame_tag: str = "<LAST_FRAME>"
    reference_tags: list[str] = Field(default_factory=lambda: ["<IMAGE_REF_0>", "<IMAGE_REF_1>"])
    shots: list[StoryboardTileSpec] = Field(default_factory=list)
    compiled_omni_prompt: str


class SoundstageCommercialPlan(BaseModel):
    """Complete 30-second 3-Act Mode 5 Commercial Soundstage production plan."""

    subject: str
    offering: str
    territory: TerritoryAtmosphereSpec
    moment: str
    language: str
    palette: Palette603010
    physics: OfferingPhysicsSpec
    identity: DualLayerIdentitySpec
    brief: ExecutiveCreativeBrief
    lead_character: CharacterRoleModel
    hero_offering_role: CharacterRoleModel
    voiceover_full_script: str
    acts: list[SoundstageActPlan] = Field(default_factory=list)
    boards: list[StoryboardTileSpec] = Field(default_factory=list)


class SoundstageThreeActPlanner:
    """Compiles 3-Act x 3-Beat (9-Shot) Mode 5 Commercial Soundstage plans and linted 4-Block Meta-Prompts."""

    def __init__(self, mock_mode: bool | None = None) -> None:
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self._physics_analyzer = OfferingPhysicsAnalyzer(mock_mode=self.mock_mode)
        self._genai_client: Any = None
        if not self.mock_mode:
            try:
                self._genai_client = get_genai_client(
                    location=getattr(settings, "gemini_location", "global")
                )
            except Exception as exc:
                logger.warning("SoundstageThreeActPlanner could not init GenAI client: %s", exc)

    @staticmethod
    def _resolve_language_cadence(language: str) -> str:
        lang_low = (language or "English").strip().lower()
        for entry in SPOKEN_LANGUAGES:
            if entry["label"].lower() == lang_low or entry["code"].lower() == lang_low:
                return entry["vocal_cadence"]
        return (
            f"Measured, resonant {language.strip()} commercial cinema voiceover with crisp diction"
        )

    @staticmethod
    def _ergonomic_act2_action(
        cast_handle: str,
        offering_desc: str,
        physics: OfferingPhysicsSpec,
    ) -> str:
        role = physics.ergonomic_role
        if role == "DRIVER_AT_WHEEL":
            return (
                f"{cast_handle} (@Image3) settles into the sculpted driver cockpit and places poised hands "
                f"onto the steering wheel rim of the {offering_desc} (@Image4) in smooth tactile alignment."
            )
        if role == "PASSENGER_IN_REAR_CABIN":
            return (
                f"{cast_handle} (@Image3) relaxes exclusively in the serene rear passenger cabin seat of the "
                f"{offering_desc} (@Image4) as city light glides across the glass."
            )
        if role == "RECIPIENT_AT_DOOR_AND_TABLE":
            return (
                f"{cast_handle} (@Image3) receives and unveils the {offering_desc} (@Image4) onto the "
                "architectural dining table in a poised first-contact gesture."
            )
        if role == "GUEST_LIVING_IN_SPACE":
            return (
                f"{cast_handle} (@Image3) steps across the threshold of the {offering_desc} (@Image4), "
                "tracing fingertips along honed travertine and warm timber joinery."
            )
        if role == "CARDHOLDER_TAPPING_AT_VENUE":
            return (
                f"{cast_handle} (@Image3) presents the {offering_desc} (@Image4) in a single fluid "
                "contactless tap against the stone venue counter."
            )
        if role == "WIELDER_OF_ARTIFACT":
            return (
                f"{cast_handle} (@Image3) grips the balanced hilt of the {offering_desc} (@Image4) "
                "as warm practical light awakens along its sculpted fluting."
            )
        return (
            f"{cast_handle} (@Image3) lifts the {offering_desc} (@Image4) from the hero plinth "
            "in a single deliberate first-contact ergonomic gesture."
        )

    @staticmethod
    def _scrub_place_label(place_name: str, subject: str, offering: str) -> str:
        scrubbed = scrub_offering_trademarks(place_name, subject=subject, offering=offering)
        scrubbed = re.sub(r"^\s*·\s*|\s*·\s*$", "", scrubbed).strip()
        return scrubbed or "Metropolitan District"

    def _compile_act_omni_prompt(
        self,
        act_number: int,
        time_window: str,
        cast_handle: str,
        vocal_cadence: str,
        identity: DualLayerIdentitySpec,
        territory: TerritoryAtmosphereSpec,
        palette: Palette603010,
        physics: OfferingPhysicsSpec,
        audio_score: str,
        sound_effects: str,
        voiceover_line: str,
        shots: list[StoryboardTileSpec],
        lead_character: CharacterRoleModel,
        hero_offering_role: CharacterRoleModel,
    ) -> str:
        subj, off = identity.display_subject, identity.display_offering
        safe_place = self._scrub_place_label(territory.place_name, subject=subj, offering=off)
        safe_condition = scrub_offering_trademarks(territory.condition, subject=subj, offering=off)
        safe_lighting = scrub_offering_trademarks(
            territory.lighting_directive, subject=subj, offering=off
        )
        safe_vo = scrub_offering_trademarks(voiceover_line, subject=subj, offering=off)

        # Block 1: INPUT ROLES & REFERENCES (dual-keyframe anchors occupy slots 1-2; refs start at @Image3)
        block1 = (
            "### INPUT ROLES & REFERENCES\n"
            "[# Sources <FIRST_FRAME>@KeyframeSeed <LAST_FRAME>@EndKeyframe]\n"
            "[# References <IMAGE_REF_0>@Image3, <IMAGE_REF_1>@Image4]\n"
            f"- {lead_character.role_id} ({lead_character.image_role}): {cast_handle} (@Image3)\n"
            f"- {hero_offering_role.role_id} ({hero_offering_role.image_role}): Hero Offering Anchor (@Image4)"
        )

        # Block 2: CHARACTER PROFILES (locked to @Image3 / @Image4 reference sheets)
        block2 = (
            "### CHARACTER PROFILES\n"
            f"- {lead_character.role_id} ({cast_handle}) (Reference Image: @Image3): "
            "Composed charismatic commercial lead with expressive cinematic poise and decisive posture. "
            "Enforce Zero Wardrobe Redundancy: Visual appearance locked to reference sheet @Image3. "
            f"[Voice Style: {vocal_cadence}]\n"
            f"- {hero_offering_role.role_id} (Hero Offering Anchor) (Reference Image: @Image4): "
            f"{identity.omni_safe_offering_descriptor}. "
            "Enforce Zero Wardrobe Redundancy: Visual appearance locked to reference sheet @Image4."
        )

        # Block 3: SCENE INSTRUCTIONS
        ducking_clause = PreFlightGatekeeper.CANONICAL_DUCKING_CLAUSE
        block3 = "\n".join(
            [
                "### SCENE INSTRUCTIONS",
                f"- Act Window: Act {act_number} ({time_window})",
                f"- Camera & Lighting: In a single continuous shot. No scene cuts. {safe_lighting}. No text, no subtitles on screen.",
                f"- Spatial Staging: [{lead_character.role_id}] positioned on screen-left during human performance beats, [{hero_offering_role.role_id}] positioned on screen-right focal plane to maintain clear identity separation.",
                f"- Environment: {identity.omni_safe_world_descriptor} in {safe_place} ({safe_condition}, {territory.temperature_c}C).",
                f"- Production Design Palette (60/30/10 Color Lock): {palette.production_design_directive}",
                f"- Causality Gate (Act {act_number}): {physics.act_causality_laws[act_number]}",
                f"- Audio: instrumental {audio_score} {sound_effects}. {ducking_clause}",
                "- Clean Frame Directive: No text, no subtitles on screen.",
            ]
        )

        # Block 4: TIMELINE
        s1, s2, s3 = shots[0], shots[1], shots[2]
        a1 = scrub_offering_trademarks(s1.action, subject=subj, offering=off)
        a2 = scrub_offering_trademarks(s2.action, subject=subj, offering=off)
        a3 = scrub_offering_trademarks(s3.action, subject=subj, offering=off)
        vo_segment = f' Dialogue: Narrator (VO) says: "{safe_vo}"' if safe_vo else ""
        block4 = (
            "### TIMELINE\n"
            f"[{s1.timecode_range}] Action: ({s1.framing}) {a1} Audio: instrumental {audio_score} {sound_effects}.{vo_segment}\n"
            f"[{s2.timecode_range}] Action: ({s2.framing}) {a2} Audio: instrumental {audio_score} progression.\n"
            f"[{s3.timecode_range}] Action: ({s3.framing}) {a3} No text, no subtitles on screen. Audio: instrumental {audio_score} cadence."
        )

        assembled = f"{block1}\n\n{block2}\n\n{block3}\n\n{block4}"
        lint_res = PreFlightGatekeeper.lint_and_repair(
            assembled,
            characters=[lead_character, hero_offering_role],
            has_dialogue=bool(safe_vo),
            offering_physics=physics,
            palette_60_30_10=palette,
            act_number=act_number,
        )
        return lint_res.repaired_prompt

    def _enrich_plan_with_genai(
        self,
        identity: DualLayerIdentitySpec,
        territory_spec: TerritoryAtmosphereSpec,
        palette: Palette603010,
        physics: OfferingPhysicsSpec,
        moment_clean: str,
        lang_clean: str,
        custom_dna: str,
        default_brief: ExecutiveCreativeBrief,
        default_vo: tuple[str, str, str],
        all_tiles: list[StoryboardTileSpec],
    ) -> tuple[ExecutiveCreativeBrief, tuple[str, str, str]]:
        """Enriches brief, localized VO lines, and 9 beat actions via Gemini Flash JSON mode."""
        if self.mock_mode or self._genai_client is None:
            return default_brief, default_vo

        prompt = (
            "You are an executive commercial film director planning a 30-second 3-Act Soundstage spot.\n"
            f"Brand Subject: {identity.display_subject} | Offering: {identity.display_offering}\n"
            f"Territory: {territory_spec.place_name} ({territory_spec.condition}) | Moment: {moment_clean}\n"
            f"Spoken Language: {lang_clean} | Creative DNA: {custom_dna or 'Architectural poise'}\n"
            f"Cast Handle: {identity.omni_safe_cast_handle} (@Image3) | Hero Prop: (@Image4)\n"
            f"Palette: {palette.production_design_directive}\n"
            f"Causality Laws: {physics.act_causality_laws}\n\n"
            "Return ONLY a JSON object with keys:\n"
            "- brief: {title, objective, audience, key_tension, proposition, sonic_and_visual_direction}\n"
            f"- voiceover_lines: {{'1': '...', '2': '...', '3': '...'}} written naturally in {lang_clean}\n"
            "- beat_actions: {'1.1': '...', '1.2': '...', '1.3': '...', '2.1': '...', '2.2': '...', "
            "'2.3': '...', '3.1': '...', '3.2': '...', '3.3': '...'} with ZERO brand/trademark words "
            "(shots 1.3, 2.2, 3.3 MUST be human-free).\n"
        )
        try:
            parsed = invoke_flash_json_dict(self._genai_client, prompt)
            if not parsed:
                return default_brief, default_vo

            brief = default_brief
            raw_brief = parsed.get("brief")
            if isinstance(raw_brief, dict):
                merged_brief = default_brief.model_dump()
                for key in merged_brief:
                    val = clean_json_str(raw_brief.get(key))
                    if val:
                        merged_brief[key] = sanitize_single_line_field(val)
                brief = ExecutiveCreativeBrief(**merged_brief)

            vo_list = list(default_vo)
            raw_vo = parsed.get("voiceover_lines")
            if isinstance(raw_vo, dict):
                for idx, act_idx in enumerate((1, 2, 3)):
                    raw_val = (
                        raw_vo.get(str(act_idx))
                        if raw_vo.get(str(act_idx)) is not None
                        else raw_vo.get(act_idx)
                    )
                    cv = sanitize_single_line_field(clean_json_str(raw_val))
                    if cv:
                        vo_list[idx] = cv

            raw_beats = parsed.get("beat_actions")
            if isinstance(raw_beats, dict):
                cast_re = re.compile(
                    rf"(?<![^\W_]){re.escape(identity.omni_safe_cast_handle)}(?![^\W_])",
                    re.IGNORECASE,
                )
                for tile in all_tiles:
                    cand_act = clean_json_str(raw_beats.get(tile.shot_id))
                    if not cand_act:
                        continue
                    clean_act = sanitize_single_line_field(
                        scrub_offering_trademarks(
                            cand_act,
                            subject=identity.display_subject,
                            offering=identity.display_offering,
                        )
                    )
                    if len(clean_act) < 8:
                        continue
                    if not tile.has_person:
                        if re.search(
                            r"@Image[13]\b", clean_act, flags=re.IGNORECASE
                        ) or cast_re.search(clean_act):
                            continue
                        clean_act = re.sub(r"@Image2\b", "@Image4", clean_act, flags=re.IGNORECASE)
                    else:
                        clean_act = re.sub(r"@Image2\b", "@Image4", clean_act, flags=re.IGNORECASE)
                        clean_act = re.sub(r"@Image1\b", "@Image3", clean_act, flags=re.IGNORECASE)
                    tile.action = clean_act

            return brief, (vo_list[0], vo_list[1], vo_list[2])
        except Exception as exc:
            logger.warning("SoundstageThreeActPlanner live enrichment fallback: %s", exc)
            return default_brief, default_vo

    def build_plan(
        self,
        subject: str,
        offering: str = "",
        territory: str = "",
        weather_condition: str = "",
        palette_hexes: list[str] | None = None,
        moment: str = "",
        language: str = "English",
        tagline: str = "",
        custom_dna: str = "",
        lead_character_override: CharacterRoleModel | None = None,
        packshot_url: str | None = None,
        emblem_url: str | None = None,
        territory_override: TerritoryAtmosphereSpec | None = None,
        palette_override: Palette603010 | None = None,
    ) -> SoundstageCommercialPlan:
        """Builds a 3-Act x 3-Beat (9-Shot) SoundstageCommercialPlan with PreFlight-linted 4-block prompts."""
        subj_clean = sanitize_single_line_field(subject) or "Artisan Studio"
        off_clean = sanitize_single_line_field(offering) or f"{subj_clean} Signature Edition"
        terr_clean = sanitize_single_line_field(territory)
        weather_clean = sanitize_single_line_field(weather_condition)
        moment_clean = sanitize_single_line_field(moment) or "Twilight Threshold Ritual"
        lang_clean = sanitize_single_line_field(language) or "English"
        tagline_clean = sanitize_single_line_field(tagline)
        dna_clean = sanitize_single_line_field(custom_dna)

        territory_spec = (
            territory_override.model_copy()
            if territory_override is not None
            else resolve_territory(terr_clean)
        )
        if weather_clean:
            territory_spec = territory_spec.model_copy(update={"condition": weather_clean})

        physics = self._physics_analyzer.analyze(
            subject=subj_clean,
            offering=off_clean,
            territory=territory_spec.place_name,
        )
        palette = (
            palette_override.model_copy()
            if palette_override is not None
            else select_palette_for_archetype(
                archetype=physics.archetype,
                custom_hexes=palette_hexes,
            )
        )

        custom_wardrobe = (
            sanitize_single_line_field(lead_character_override.wardrobe)
            if lead_character_override
            else ""
        )
        identity = DualLayerIdentityAbstractor.abstract(
            subject=subj_clean,
            offering=off_clean,
            physics=physics,
            palette=palette,
            lead_name=lead_character_override.name if lead_character_override else None,
            lead_wardrobe=custom_wardrobe or None,
            tagline=tagline_clean or None,
        )

        vocal_cadence = (
            sanitize_single_line_field(lead_character_override.voice_style)
            if (lead_character_override and lead_character_override.voice_style)
            else self._resolve_language_cadence(lang_clean)
        )

        cast_handle = identity.omni_safe_cast_handle
        lead_ref_url = (
            lead_character_override.reference_url
            if (lead_character_override and lead_character_override.reference_url)
            else f"gs://{settings.gcs_bucket_name}/soundstage/cast/{cast_handle.lower()}_sheet.png"
        )
        hero_ref_url = (
            packshot_url
            or emblem_url
            or f"gs://{settings.gcs_bucket_name}/soundstage/offerings/hero_packshot.png"
        )

        lead_character = CharacterRoleModel(
            role_id="Role A",
            name=cast_handle,
            description=identity.omni_safe_cast_description,
            reference_url=lead_ref_url,
            wardrobe=(
                custom_wardrobe
                or f"Tailored architectural silhouette in {palette.secondary_name} ({palette.secondary_hex})"
            ),
            voice_style=vocal_cadence,
            aesthetic_tags=[palette.secondary_name, palette.secondary_hex, "Commercial Soundstage"],
            image_role="Character Reference",
            is_offscreen_narrator=False,
        )
        hero_offering_role = CharacterRoleModel(
            role_id="Role B",
            name="Hero Offering Anchor",
            description=identity.omni_safe_offering_descriptor,
            reference_url=hero_ref_url,
            wardrobe="",
            voice_style="",
            aesthetic_tags=[palette.neutral_name, palette.neutral_hex, physics.archetype],
            image_role="Prop Reference",
            is_offscreen_narrator=False,
        )

        dna_clause = f" Guided by creative DNA: {dna_clean}." if dna_clean else ""
        brief = ExecutiveCreativeBrief(
            title=f"{identity.display_subject} · {identity.display_offering} ({territory_spec.place_name})",
            objective=(
                f"Stage a 30-second 3-act cinema commercial elevating {identity.display_offering} "
                f"within {territory_spec.place_name} during {moment_clean}.{dna_clause}"
            ),
            audience="Design-literate global cultural tastemakers seeking authentic material craft.",
            key_tension="Kinetic metropolitan noise versus composed tactile mastery and quiet precision.",
            proposition=identity.display_tagline,
            sonic_and_visual_direction=(
                f"{palette.production_design_directive}. {territory_spec.lighting_directive}. "
                f"Voiceover delivered in {lang_clean} ({vocal_cadence})."
            ),
        )

        default_vo = (
            "Before the rush claims the street, stillness sharpens every sense.",
            "One deliberate touch reveals where true craft lives.",
            "Carry the quiet pulse long after the moment settles.",
        )

        safe_place = self._scrub_place_label(
            territory_spec.place_name,
            subject=identity.display_subject,
            offering=identity.display_offering,
        )
        safe_condition = scrub_offering_trademarks(
            territory_spec.condition,
            subject=identity.display_subject,
            offering=identity.display_offering,
        )
        safe_lighting = scrub_offering_trademarks(
            territory_spec.lighting_directive,
            subject=identity.display_subject,
            offering=identity.display_offering,
        )
        safe_moment = scrub_offering_trademarks(
            moment_clean,
            subject=identity.display_subject,
            offering=identity.display_offering,
        )
        palette_suffix = (
            f"Production design locked to {palette.production_design_directive}. "
            f"{safe_lighting}. Shot on 35mm cinema prime for {settings.image_model_id}, "
            "photorealistic 8k commercial cinematography, zero text, zero watermarks."
        )
        thermal_detail = {
            "ambient": "dry room-temperature satin material finish and crisp specular bevels",
            "chilled": "fine chilled micro-condensation sheen across the cold exterior surface",
            "hot": "delicate natural aromatic thermal wisps rising softly from the warm vessel",
        }[physics.thermal_state]

        act1_shots = [
            StoryboardTileSpec(
                shot_id="1.1",
                act_number=1,
                beat_index=1,
                timecode_range="0.0-3.3s",
                framing="Wide Architectural Tracking Shot",
                action=(
                    f"{cast_handle} (@Image3) walks empty-handed along the {safe_place} threshold "
                    f"under {safe_condition}, immersed in pre-interaction anticipation."
                ),
                has_person=True,
                image_prompt=(
                    f"Wide architectural establishing frame in {safe_place} ({safe_condition}), "
                    f"{identity.omni_safe_cast_description} walking empty-handed on screen-left with poised anticipation. {palette_suffix}"
                ),
            ),
            StoryboardTileSpec(
                shot_id="1.2",
                act_number=1,
                beat_index=2,
                timecode_range="3.3-6.7s",
                framing="Medium Kinetic Portrait",
                action=(
                    f"Camera glides into a medium portrait of {cast_handle} (@Image3) pausing empty-handed "
                    "as warm directional rim light catches focused eyes before any offering contact."
                ),
                has_person=True,
                image_prompt=(
                    f"Medium cinema portrait of {identity.omni_safe_cast_description} in {safe_place}, "
                    f"hands empty at sides, focused anticipatory gaze toward warm architectural threshold. {palette_suffix}"
                ),
            ),
            StoryboardTileSpec(
                shot_id="1.3",
                act_number=1,
                beat_index=3,
                timecode_range="6.7-10.0s",
                framing="Sensory Architectural Surface Macro (Human-Free)",
                action=(
                    f"Human-free sensory macro across {palette.neutral_name} ({palette.neutral_hex}) "
                    f"and {palette.primary_name} ({palette.primary_hex}) architectural textures catching twilight reflections."
                ),
                has_person=False,
                image_prompt=(
                    f"Human-free architectural sensory macro in {safe_place}, honed {palette.neutral_name} "
                    f"({palette.neutral_hex}) stone plane meeting {palette.primary_name} ({palette.primary_hex}) "
                    f"shadowed surfaces, zero people, zero hands. {palette_suffix}"
                ),
            ),
        ]

        act2_shots = [
            StoryboardTileSpec(
                shot_id="2.1",
                act_number=2,
                beat_index=1,
                timecode_range="0.0-3.3s",
                framing="Medium-Close Tactile First Contact",
                action=self._ergonomic_act2_action(
                    cast_handle=cast_handle,
                    offering_desc=identity.omni_safe_offering_descriptor,
                    physics=physics,
                ),
                has_person=True,
                image_prompt=(
                    f"Medium-close commercial cinema frame of {identity.omni_safe_cast_description} "
                    f"initiating first tactile interaction with {identity.omni_safe_offering_descriptor} "
                    f"in {safe_place}. {palette_suffix}"
                ),
            ),
            StoryboardTileSpec(
                shot_id="2.2",
                act_number=2,
                beat_index=2,
                timecode_range="3.3-6.7s",
                framing="100mm Zero-Hand Optical Craft Macro (Human-Free)",
                action=(
                    f"Dedicated 100mm zero-hand optical macro isolating {identity.omni_safe_offering_descriptor} (@Image4) "
                    f"with zero human presence, showcasing {thermal_detail}."
                ),
                has_person=False,
                image_prompt=(
                    f"100mm optical macro studio-grade cinema close-up of {identity.omni_safe_offering_descriptor} "
                    f"resting solo on {palette.neutral_name} ({palette.neutral_hex}) surface, showcasing {thermal_detail}, "
                    f"zero hands, zero people in frame. {palette_suffix}"
                ),
            ),
            StoryboardTileSpec(
                shot_id="2.3",
                act_number=2,
                beat_index=3,
                timecode_range="6.7-10.0s",
                framing="Expressive Close-Up Signature Reaction",
                action=(
                    f"Tight expressive close-up on {cast_handle} (@Image3) registering a single quiet, "
                    "authentic signature experience reaction as directional light warms the frame."
                ),
                has_person=True,
                image_prompt=(
                    f"Tight expressive 85mm cinema close-up of {identity.omni_safe_cast_description} "
                    f"experiencing a calm resonant moment of satisfaction in {safe_place}. {palette_suffix}"
                ),
            ),
        ]

        act3_shots = [
            StoryboardTileSpec(
                shot_id="3.1",
                act_number=3,
                beat_index=1,
                timecode_range="0.0-3.3s",
                framing="Fluid Steadicam Lifestyle Payoff",
                action=(
                    f"{cast_handle} (@Image3) moves in composed post-experience equilibrium through {safe_place} "
                    "without repeated consumption, radiating effortless confidence."
                ),
                has_person=True,
                image_prompt=(
                    f"Fluid Steadicam medium-wide lifestyle payoff shot of {identity.omni_safe_cast_description} "
                    f"in {safe_place} during {safe_moment}, post-experience poise without repeated consumption. {palette_suffix}"
                ),
            ),
            StoryboardTileSpec(
                shot_id="3.2",
                act_number=3,
                beat_index=2,
                timecode_range="3.3-6.7s",
                framing="Low-Angle Architectural Transition",
                action=(
                    f"Camera glides past {cast_handle} (@Image3) on screen-left toward the illuminated "
                    f"{palette.neutral_name} ({palette.neutral_hex}) hero stage on screen-right."
                ),
                has_person=True,
                image_prompt=(
                    f"Low-angle 35mm cinema composition of {identity.omni_safe_cast_description} in three-quarter "
                    f"profile within {safe_place}, camera transitioning toward hero presentation plinth. {palette_suffix}"
                ),
            ),
            StoryboardTileSpec(
                shot_id="3.3",
                act_number=3,
                beat_index=3,
                timecode_range="6.7-10.0s",
                framing="Solo Hero Packshot Lockup (Motionless Human-Free)",
                action=(
                    f"Motionless human-free solo hero packshot lockup of {identity.omni_safe_offering_descriptor} (@Image4) "
                    f"centered cleanly on the {palette.neutral_name} ({palette.neutral_hex}) plinth with negative space for post-conform lockup."
                ),
                has_person=False,
                image_prompt=(
                    f"Motionless human-free solo commercial hero packshot of {identity.omni_safe_offering_descriptor} "
                    f"on {palette.neutral_name} ({palette.neutral_hex}) plinth against {palette.primary_name} "
                    f"({palette.primary_hex}) architectural depth, clean negative space, zero hands, zero people. {palette_suffix}"
                ),
            ),
        ]

        brief, (vo_act1, vo_act2, vo_act3) = self._enrich_plan_with_genai(
            identity=identity,
            territory_spec=territory_spec,
            palette=palette,
            physics=physics,
            moment_clean=moment_clean,
            lang_clean=lang_clean,
            custom_dna=dna_clean,
            default_brief=brief,
            default_vo=default_vo,
            all_tiles=[*act1_shots, *act2_shots, *act3_shots],
        )
        voiceover_full_script = f"[0:00] {vo_act1}\n[0:10] {vo_act2}\n[0:20] {vo_act3}"

        act_specs = [
            (
                1,
                "Act I · Anticipation & World Pulse",
                "0:00-0:10",
                f"Establishes {territory_spec.place_name} atmosphere and empty-handed pre-interaction anticipation.",
                vo_act1,
                "92 BPM minimalist analog pulse with warm felt-piano harmonics",
                "(subtle metropolitan dusk ambience, measured footsteps on stone)",
                act1_shots,
            ),
            (
                2,
                "Act II · Tactile Reveal & Craft Macro",
                "0:10-0:20",
                "Captures tactile first contact, 100mm zero-hand craft macro, and signature reaction.",
                vo_act2,
                "96 BPM warm cello swell layered over crisp tactile sub-bass pulse",
                "(tactile precision material contact, delicate acoustic room resonance)",
                act2_shots,
            ),
            (
                3,
                "Act III · Lifestyle Payoff & Hero Anchor",
                "0:20-0:30",
                "Resolves into composed lifestyle payoff and motionless human-free solo hero packshot lockup.",
                vo_act3,
                "96 BPM resolved architectural synth-and-strings harmonic cadence",
                "(calm evening air resonance, clean studio stillness on final hold)",
                act3_shots,
            ),
        ]

        acts: list[SoundstageActPlan] = []
        boards: list[StoryboardTileSpec] = []
        for act_num, act_title, time_win, summary, vo_line, score, sfx, act_shots in act_specs:
            compiled_prompt = self._compile_act_omni_prompt(
                act_number=act_num,
                time_window=time_win,
                cast_handle=cast_handle,
                vocal_cadence=vocal_cadence,
                identity=identity,
                territory=territory_spec,
                palette=palette,
                physics=physics,
                audio_score=score,
                sound_effects=sfx,
                voiceover_line=vo_line,
                shots=act_shots,
                lead_character=lead_character,
                hero_offering_role=hero_offering_role,
            )
            acts.append(
                SoundstageActPlan(
                    act_number=act_num,
                    title=act_title,
                    time_window=time_win,
                    narrative_summary=summary,
                    voiceover_line=vo_line,
                    audio_score=score,
                    sound_effects=sfx,
                    first_frame_shot_id=act_shots[0].shot_id,
                    last_frame_shot_id=act_shots[-1].shot_id,
                    shots=act_shots,
                    compiled_omni_prompt=compiled_prompt,
                )
            )
            boards.extend(act_shots)

        return SoundstageCommercialPlan(
            subject=subj_clean,
            offering=off_clean,
            territory=territory_spec,
            moment=moment_clean,
            language=lang_clean,
            palette=palette,
            physics=physics,
            identity=identity,
            brief=brief,
            lead_character=lead_character,
            hero_offering_role=hero_offering_role,
            voiceover_full_script=voiceover_full_script,
            acts=acts,
            boards=boards,
        )

    def repoint_plan_for_variation(
        self,
        existing_plan: SoundstageCommercialPlan,
        axis: Literal["place", "cast", "offering"],
        new_value: str,
    ) -> SoundstageCommercialPlan:
        """Rebuilds a SoundstageCommercialPlan mutating only the target axis while locking all unchanged axes."""
        val_clean = sanitize_single_line_field(new_value)
        if not val_clean:
            return existing_plan

        territory_val = existing_plan.territory.place_name
        territory_override: TerritoryAtmosphereSpec | None = existing_plan.territory
        offering_val = existing_plan.offering
        lead_override: CharacterRoleModel | None = existing_plan.lead_character
        packshot_url = existing_plan.hero_offering_role.reference_url

        if axis == "place":
            territory_val = val_clean
            territory_override = None
        elif axis == "cast":
            lead_override = CharacterRoleModel(
                role_id="Role A",
                name=val_clean,
                description="",
                reference_url=None,
                wardrobe=existing_plan.lead_character.wardrobe,
                voice_style=existing_plan.lead_character.voice_style,
                aesthetic_tags=list(existing_plan.lead_character.aesthetic_tags),
                image_role="Character Reference",
                is_offscreen_narrator=False,
            )
        elif axis == "offering":
            offering_val = val_clean
            packshot_url = None
        else:
            raise ValueError(f"Unsupported variation axis: {axis}")

        return self.build_plan(
            subject=existing_plan.subject,
            offering=offering_val,
            territory=territory_val,
            moment=existing_plan.moment,
            language=existing_plan.language,
            tagline=existing_plan.identity.display_tagline,
            lead_character_override=lead_override,
            packshot_url=packshot_url,
            territory_override=territory_override,
            palette_override=existing_plan.palette,
        )


__all__ = [
    "DualLayerIdentityAbstractor",
    "DualLayerIdentitySpec",
    "ExecutiveCreativeBrief",
    "Palette603010",
    "SoundstageActPlan",
    "SoundstageCommercialPlan",
    "SoundstageDiscoveryEngine",
    "SoundstageDiscoveryResult",
    "SoundstageThreeActPlanner",
    "StoryboardTileSpec",
    "TerritoryAtmosphereSpec",
]
