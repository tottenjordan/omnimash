"""Mode 5: Commercial Soundstage Discovery Engine, Dual-Layer Identity Abstractor, and 3-Act Planner.

Implements:
- 60/30/10 Production Design Color-Lock (`Palette603010`)
- Territory & Atmosphere Metadata (`TerritoryAtmosphereSpec`)
- Dual-Layer Brand & Cast Safety Abstraction (`DualLayerIdentityAbstractor`)
- 10-Step Intake Discovery Engine (`SoundstageDiscoveryEngine`)
- 3-Act x 3-Beat (9-Shot) Commercial Soundstage Planner (`SoundstageThreeActPlanner`)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from omnimash.api.models import CharacterRoleModel
from omnimash.config import settings
from omnimash.prompts.genai_client import get_genai_client
from omnimash.prompts.offering_physics import (
    OfferingArchetype,
    OfferingPhysicsAnalyzer,
    OfferingPhysicsSpec,
    extract_brand_scrub_tokens,
    scrub_offering_trademarks,
)
from omnimash.prompts.parody import sanitize_real_names
from omnimash.prompts.preflight_linter import PreFlightGatekeeper

logger = logging.getLogger(__name__)

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Safe single-word stylized commercial cast handles recognized when casting personas
_SAFE_ROLE_HANDLES: tuple[str, ...] = (
    "Architect",
    "Vanguard",
    "Chef",
    "Sommelier",
    "Botanist",
    "Netrunner",
    "Alchemist",
    "Artisan",
    "Curator",
    "Voyager",
    "Navigator",
    "Barista",
    "Sculptor",
    "Maestro",
    "Nomad",
    "Patron",
    "Pilot",
    "Founder",
    "Creator",
    "Stylist",
    "Horologist",
    "Sorcerer",
    "Couturier",
    "Director",
)

_ARCHETYPE_DEFAULT_HANDLE: dict[OfferingArchetype, str] = {
    "OWNED_MOTOR_VEHICLE": "Vanguard",
    "PASSENGER_MOBILITY_OR_TRANSIT": "Voyager",
    "FOOD_OR_DINING_DELIVERY": "Curator",
    "HOSPITALITY_OR_ARCHITECTURAL_STAY": "Architect",
    "FINANCIAL_OR_MEMBERSHIP_CARD": "Patron",
    "DIGITAL_APP_OR_SERVICE": "Creator",
    "COUNTERTOP_APPLIANCE": "Artisan",
    "PARODY_PROP_OR_ARTIFACT": "Alchemist",
    "HANDHELD_CPG_OR_OBJECT": "Curator",
}


class Palette603010(BaseModel):
    """60/30/10 architectural production design color-lock specification."""

    primary_hex: str = Field(..., description="60% architectural and set surfaces (#RRGGBB)")
    primary_name: str
    secondary_hex: str = Field(..., description="30% wardrobe and practical props (#RRGGBB)")
    secondary_name: str
    neutral_hex: str = Field(..., description="10% foundational hero surface (#RRGGBB)")
    neutral_name: str
    production_design_directive: str = ""

    @field_validator("primary_hex", "secondary_hex", "neutral_hex")
    @classmethod
    def _validate_hex(cls, value: str) -> str:
        cleaned = (value or "").strip().upper()
        if not _HEX_COLOR_RE.match(cleaned):
            raise ValueError(f"Expected #RRGGBB hex color code, got '{value}'")
        return cleaned

    @model_validator(mode="after")
    def _populate_directive(self) -> Palette603010:
        if not self.production_design_directive or not self.production_design_directive.strip():
            self.production_design_directive = (
                f"60% {self.primary_name} ({self.primary_hex}) architectural & set surfaces / "
                f"30% {self.secondary_name} ({self.secondary_hex}) wardrobe & practical props / "
                f"10% {self.neutral_name} ({self.neutral_hex}) foundational hero surface"
            )
        return self


class TerritoryAtmosphereSpec(BaseModel):
    """Place, micro-climate, lighting, and cultural pulse for a commercial territory."""

    place_name: str
    temperature_c: int
    condition: str
    lighting_directive: str
    cultural_pulse: str


class DualLayerIdentitySpec(BaseModel):
    """Separates verbatim UI/FFmpeg end-card brand strings from trademark-scrubbed Omni Flash descriptors."""

    display_subject: str
    display_offering: str
    display_tagline: str
    omni_safe_offering_descriptor: str
    omni_safe_cast_handle: str
    omni_safe_cast_description: str
    omni_safe_world_descriptor: str


class SoundstageDiscoveryResult(BaseModel):
    """10-step intake discovery payload returned by SoundstageDiscoveryEngine."""

    subject: str
    suggested_offerings: list[dict[str, str]] = Field(default_factory=list)
    suggested_territories: list[TerritoryAtmosphereSpec] = Field(default_factory=list)
    palette: Palette603010
    cultural_moments: list[dict[str, str]] = Field(default_factory=list)
    spoken_languages: list[dict[str, str]] = Field(default_factory=list)
    tagline: str
    emblem_prompt: str
    packshot_prompt: str
    physics: OfferingPhysicsSpec
    identity: DualLayerIdentitySpec


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
    """10-second continuous-shot act plan with 3 storyboard tiles and PreFlight-linted 4-block Omni prompt."""

    act_number: int
    title: str
    time_window: str
    narrative_summary: str
    voiceover_line: str
    audio_score: str
    sound_effects: str
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


class DualLayerIdentityAbstractor:
    """Builds DualLayerIdentitySpec preserving verbatim UI labels while scrubbing Omni-safe prompts."""

    @staticmethod
    def _derive_single_word_cast_handle(
        lead_name: str | None,
        physics: OfferingPhysicsSpec,
        subject: str,
        offering: str,
    ) -> str:
        default_handle = _ARCHETYPE_DEFAULT_HANDLE.get(physics.archetype, "Vanguard")
        if not lead_name or not lead_name.strip():
            return default_handle

        raw = lead_name.strip()
        sanitized = sanitize_real_names(raw)
        brand_tokens_lower = {
            t.lower() for t in extract_brand_scrub_tokens(subject=subject, offering=offering)
        }

        # 1. If sanitize_real_names mutated the input, a celebrity/public-figure pattern matched.
        # Map via thematic cue to a safe single-word stylized handle.
        if sanitized != raw:
            san_lower = sanitized.lower()
            if "chef" in san_lower or "culinary" in san_lower:
                return "Chef"
            if "wizard" in san_lower or "potion" in san_lower or "sorcerer" in san_lower:
                return "Alchemist"
            if "rap" in san_lower or "pop" in san_lower or "melodic" in san_lower:
                return "Maestro"
            if "entrepreneur" in san_lower or "executive" in san_lower or "statesman" in san_lower:
                return "Founder"
            return default_handle

        # 2. Check if any token in lead_name matches a curated stylized role handle
        words = re.findall(r"[A-Za-z]+", raw)
        if not words:
            return default_handle

        safe_lookup = {h.lower(): h for h in _SAFE_ROLE_HANDLES}
        for word in reversed(words):
            w_low = word.lower()
            if w_low in safe_lookup and w_low not in brand_tokens_lower:
                return safe_lookup[w_low]

        # 3. If single word and not a brand token, allow stylized single-word moniker
        if len(words) == 1 and len(words[0]) >= 3 and words[0].lower() not in brand_tokens_lower:
            return words[0].capitalize()

        # 4. Multi-word unrecognized human name (e.g., "Marcus Vance") -> deterministic single-word handle
        # without leaking either first or surname token.
        fallback_pool = ("Vanguard", "Architect", "Curator", "Artisan", "Navigator", "Nomad")
        if default_handle not in fallback_pool:
            return default_handle
        checksum = sum(ord(ch) for ch in raw)
        return fallback_pool[checksum % len(fallback_pool)]

    @classmethod
    def abstract(
        cls,
        subject: str,
        offering: str,
        physics: OfferingPhysicsSpec,
        palette: Palette603010,
        lead_name: str | None = None,
        lead_wardrobe: str | None = None,
        tagline: str | None = None,
    ) -> DualLayerIdentitySpec:
        """Preserves exact display names for UI/end-cards while scrubbing Omni-safe descriptors."""
        display_subject = (subject or "").strip() or physics.subject or "Artisan Studio"
        display_offering = (offering or "").strip() or physics.offering or "Signature Edition"
        display_tagline = (
            tagline or ""
        ).strip() or f"Crafted for the quiet pulse of {display_offering}."

        cast_handle = cls._derive_single_word_cast_handle(
            lead_name=lead_name,
            physics=physics,
            subject=display_subject,
            offering=display_offering,
        )

        # Build Omni-safe offering descriptor from physical geometry + 60/30/10 palette finish
        raw_offering_desc = (
            f"{physics.canonical_anchor_spec}, finished with {palette.neutral_name} "
            f"({palette.neutral_hex}) foundational accents and subtle {palette.primary_name} "
            f"({palette.primary_hex}) tonal trim, completely free of printed wordmarks"
        )
        omni_safe_offering_descriptor = scrub_offering_trademarks(
            raw_offering_desc,
            subject=display_subject,
            offering=display_offering,
        )

        # Build Omni-safe cast description scrubbing real names and raw brand strings
        wardrobe_clause = (lead_wardrobe or "").strip()
        if wardrobe_clause:
            wardrobe_clause = scrub_offering_trademarks(
                wardrobe_clause,
                subject=display_subject,
                offering=display_offering,
            )
        if lead_name and lead_name.strip():
            for name_tok in re.findall(r"[A-Za-z]{2,}", lead_name):
                if name_tok.lower() != cast_handle.lower():
                    wardrobe_clause = re.sub(
                        rf"\b{re.escape(name_tok)}\b",
                        "",
                        wardrobe_clause,
                        flags=re.IGNORECASE,
                    ).strip()

        if not wardrobe_clause:
            wardrobe_clause = (
                f"tailored architectural outerwear in {palette.secondary_name} "
                f"({palette.secondary_hex}) layered over matte neutral knitwear"
            )
        elif palette.secondary_hex.lower() not in wardrobe_clause.lower():
            wardrobe_clause = (
                f"{wardrobe_clause} accented in {palette.secondary_name} ({palette.secondary_hex})"
            )

        raw_cast_desc = (
            f"{cast_handle}, composed charismatic commercial lead with expressive cinematic poise, "
            f"styled in {wardrobe_clause} with subtle {palette.neutral_name} ({palette.neutral_hex}) trim"
        )
        omni_safe_cast_description = scrub_offering_trademarks(
            raw_cast_desc,
            subject=display_subject,
            offering=display_offering,
        )

        raw_world_desc = (
            f"Architectural commercial soundstage environment anchored in 60% {palette.primary_name} "
            f"({palette.primary_hex}) spatial surfaces, 30% {palette.secondary_name} "
            f"({palette.secondary_hex}) practical set accents, and 10% {palette.neutral_name} "
            f"({palette.neutral_hex}) hero presentation plinth"
        )
        omni_safe_world_descriptor = scrub_offering_trademarks(
            raw_world_desc,
            subject=display_subject,
            offering=display_offering,
        )

        return DualLayerIdentitySpec(
            display_subject=display_subject,
            display_offering=display_offering,
            display_tagline=display_tagline,
            omni_safe_offering_descriptor=omni_safe_offering_descriptor,
            omni_safe_cast_handle=cast_handle,
            omni_safe_cast_description=omni_safe_cast_description,
            omni_safe_world_descriptor=omni_safe_world_descriptor,
        )


_CURATED_TERRITORIES: dict[str, TerritoryAtmosphereSpec] = {
    "tokyo": TerritoryAtmosphereSpec(
        place_name="Tokyo · Shibuya",
        temperature_c=16,
        condition="Crisp twilight · Golden-hour wet asphalt reflections",
        lighting_directive="Anamorphic 35mm cinema lens, warm tungsten storefront glow against slate twilight blue",
        cultural_pulse="Precision evening rhythm where quiet architectural minimalism meets kinetic metropolitan flow",
    ),
    "new york": TerritoryAtmosphereSpec(
        place_name="New York · SoHo",
        temperature_c=18,
        condition="Clear autumn dusk · Cast-iron facade rim light",
        lighting_directive="35mm prime lens, directional golden-hour street canyon shafts with soft bounce fill",
        cultural_pulse="Creative loft energy across cobblestone blocks and gallery thresholds",
    ),
    "paris": TerritoryAtmosphereSpec(
        place_name="Paris · Le Marais",
        temperature_c=19,
        condition="Luminous morning · Soft limestone courtyard diffusion",
        lighting_directive="50mm cinema prime, diffused natural skylight across warm Haussmann stone",
        cultural_pulse="Effortless atelier refinement and unhurried morning cafe poise",
    ),
    "milan": TerritoryAtmosphereSpec(
        place_name="Milan · Brera",
        temperature_c=21,
        condition="Warm late afternoon · Sunlit travertine colonnade",
        lighting_directive="Anamorphic 40mm lens, rich amber architectural chiaroscuro and polished stone speculars",
        cultural_pulse="Tactile industrial design heritage and aperitivo-hour elegance",
    ),
    "kyoto": TerritoryAtmosphereSpec(
        place_name="Kyoto · Higashiyama",
        temperature_c=15,
        condition="Misty dawn · Cedar eaves and damp slate flagstones",
        lighting_directive="50mm cinema lens, tranquil silver-amber dawn light filtering through timber lattices",
        cultural_pulse="Contemplative artisanal mastery and timeless material harmony",
    ),
    "london": TerritoryAtmosphereSpec(
        place_name="London · Soho",
        temperature_c=14,
        condition="Blue-hour drizzle · Warm brass doorway reflections",
        lighting_directive="35mm cinema lens, moody blue-hour ambience balanced by warm practical interior spill",
        cultural_pulse="Tailored heritage craft colliding with contemporary nocturnal culture",
    ),
}

_SPOKEN_LANGUAGES: list[dict[str, str]] = [
    {
        "code": "en",
        "label": "English",
        "vocal_cadence": "Measured, intimate international cinema baritone with crisp articulation",
    },
    {
        "code": "ja",
        "label": "Japanese",
        "vocal_cadence": "Poised, resonant Tokyo editorial narration with calm rhythmic pauses",
    },
    {
        "code": "fr",
        "label": "French",
        "vocal_cadence": "Warm Parisian atelier cadence with effortless velvet phrasing",
    },
    {
        "code": "it",
        "label": "Italian",
        "vocal_cadence": "Expressive Milanese architectural warmth with crisp consonant poise",
    },
    {
        "code": "es",
        "label": "Spanish",
        "vocal_cadence": "Luminous contemporary cinema narration with confident rhythmic cadence",
    },
]


def _resolve_territory(territory_hint: str) -> TerritoryAtmosphereSpec:
    hint_clean = (territory_hint or "").strip()
    if not hint_clean:
        return _CURATED_TERRITORIES["tokyo"]

    lower = hint_clean.lower()
    for key, spec in _CURATED_TERRITORIES.items():
        if key in lower or spec.place_name.lower() == lower:
            if hint_clean and spec.place_name.lower() != lower and "·" in hint_clean:
                return spec.model_copy(update={"place_name": hint_clean})
            return spec

    return TerritoryAtmosphereSpec(
        place_name=hint_clean,
        temperature_c=18,
        condition="Crisp golden hour · Architectural directional rim light",
        lighting_directive="Anamorphic 35mm cinema lens, warm directional key light with natural atmospheric depth",
        cultural_pulse=f"Distinctive local architectural character and contemporary rhythm of {hint_clean}",
    )


def _select_palette_for_archetype(
    archetype: OfferingArchetype,
    custom_hexes: list[str] | None = None,
) -> Palette603010:
    presets: dict[OfferingArchetype, tuple[str, str, str, str, str, str]] = {
        "OWNED_MOTOR_VEHICLE": (
            "#1A222D",
            "Obsidian Slate",
            "#C4633B",
            "Sienna Saddle",
            "#EAE6DF",
            "Chalk Travertine",
        ),
        "PASSENGER_MOBILITY_OR_TRANSIT": (
            "#1E2631",
            "Nocturne Graphite",
            "#B88B4A",
            "Warm Brass",
            "#F1EFEA",
            "Alabaster Linen",
        ),
        "FOOD_OR_DINING_DELIVERY": (
            "#2A211B",
            "Roasted Walnut",
            "#D46A38",
            "Terracotta Saffron",
            "#F5EFE6",
            "Warm Ceramic",
        ),
        "HOSPITALITY_OR_ARCHITECTURAL_STAY": (
            "#2C332E",
            "Cypress Basalt",
            "#B98352",
            "Aged Cedar",
            "#F2EDE4",
            "Honed Travertine",
        ),
        "FINANCIAL_OR_MEMBERSHIP_CARD": (
            "#181D24",
            "Titanium Charcoal",
            "#A88958",
            "Champagne Bronze",
            "#ECEAE4",
            "Platinum Stone",
        ),
        "DIGITAL_APP_OR_SERVICE": (
            "#192334",
            "Deep Cobalt Slate",
            "#3B82C4",
            " Cerulean Accent",
            "#F3F5F8",
            "Frosted Quartz",
        ),
        "COUNTERTOP_APPLIANCE": (
            "#23272B",
            "Brushed Gunmetal",
            "#B86B3A",
            "Espresso Copper",
            "#EFECE6",
            "Carrara Matte",
        ),
        "PARODY_PROP_OR_ARTIFACT": (
            "#1B1826",
            "Arcane Obsidian",
            "#B68D40",
            "Gilded Brass",
            "#EAE5DC",
            "Ancient Parchment Stone",
        ),
        "HANDHELD_CPG_OR_OBJECT": (
            "#202A28",
            "Botanical Mineral",
            "#D1883E",
            "Citrus Amber",
            "#F4F1EA",
            "Satin Alabaster",
        ),
    }
    p_hex, p_name, s_hex, s_name, n_hex, n_name = presets.get(
        archetype, presets["HANDHELD_CPG_OR_OBJECT"]
    )
    s_name = s_name.strip()

    if custom_hexes and len(custom_hexes) >= 3:
        if _HEX_COLOR_RE.match(custom_hexes[0].strip()):
            p_hex = custom_hexes[0].strip().upper()
        if _HEX_COLOR_RE.match(custom_hexes[1].strip()):
            s_hex = custom_hexes[1].strip().upper()
        if _HEX_COLOR_RE.match(custom_hexes[2].strip()):
            n_hex = custom_hexes[2].strip().upper()

    return Palette603010(
        primary_hex=p_hex,
        primary_name=p_name,
        secondary_hex=s_hex,
        secondary_name=s_name,
        neutral_hex=n_hex,
        neutral_name=n_name,
    )


class SoundstageDiscoveryEngine:
    """10-step intake discovery engine generating offerings, territories, 60/30/10 palette, and physics."""

    def __init__(self, mock_mode: bool | None = None) -> None:
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self._physics_analyzer = OfferingPhysicsAnalyzer(mock_mode=self.mock_mode)
        self._genai_client: Any = None
        if not self.mock_mode:
            self._init_genai_client()

    def _init_genai_client(self) -> None:
        try:
            self._genai_client = get_genai_client(
                location=getattr(settings, "gemini_location", "global")
            )
        except Exception as exc:
            logger.warning("SoundstageDiscoveryEngine could not initialize GenAI client: %s", exc)
            self._genai_client = None

    @staticmethod
    def _build_suggested_offerings(
        subject: str,
        offering_hint: str,
        archetype: OfferingArchetype,
    ) -> list[dict[str, str]]:
        primary_name = (offering_hint or "").strip() or f"{subject} Signature Edition"
        by_archetype: dict[OfferingArchetype, list[dict[str, str]]] = {
            "OWNED_MOTOR_VEHICLE": [
                {
                    "name": primary_name,
                    "category": "Flagship Grand Touring Coupe",
                    "description": "Sculpted full-scale performance coupe engineered for nocturnal metropolitan grand touring.",
                },
                {
                    "name": "Electric Sportback Edition",
                    "category": "Zero-Emission Performance",
                    "description": "Low-slung aerodynamic fastback with silent instant torque and acoustic cabin calm.",
                },
                {
                    "name": "Track Heritage Targa",
                    "category": "Open-Top Collector Series",
                    "description": "Precision open-air silhouette pairing brushed alloy roll hoop with handcrafted cockpit.",
                },
            ],
            "PARODY_PROP_OR_ARTIFACT": [
                {
                    "name": primary_name,
                    "category": "Masterwork Arcane Artifact",
                    "description": "Hand-carved obsidian and gilded brass hero artifact balanced for precision spellcraft.",
                },
                {
                    "name": "Luminous Mana Elixir Flask",
                    "category": "Alchemical Reserve",
                    "description": "Faceted crystal apothecary vial housing swirling bioluminescent botanical essence.",
                },
                {
                    "name": "Runed Brass Chrono-Compass",
                    "category": "Guild Navigation Relic",
                    "description": "Pocket astronomical astrolabe machined with rotating concentric brass rings.",
                },
            ],
            "FOOD_OR_DINING_DELIVERY": [
                {
                    "name": primary_name,
                    "category": "Chef-Crafted Doorstep Service",
                    "description": "Sealed thermal artisan parcel delivering restaurant-plated culinary craft to table.",
                },
                {
                    "name": "Late-Night Omakase Box",
                    "category": "Curated Tasting Delivery",
                    "description": "Architectural cedar bento presentation prepared minutes before threshold arrival.",
                },
                {
                    "name": " Artisanal Espresso & Pastry Drop",
                    "category": "Morning Ritual Courier",
                    "description": "Warm laminated pastry box paired with single-origin pour-over thermal carafe.",
                },
            ],
        }
        if archetype in by_archetype:
            items = by_archetype[archetype]
            return [
                {
                    "name": item["name"].strip(),
                    "category": item["category"].strip(),
                    "description": item["description"].strip(),
                }
                for item in items
            ]

        return [
            {
                "name": primary_name,
                "category": "Flagship Hero Edition",
                "description": f"Signature hero offering representing {subject} material precision and daily ritual.",
            },
            {
                "name": "Limited Reserve Collection",
                "category": "Artisan Small-Batch Release",
                "description": "Numbered architectural vessel crafted with elevated tactile finishes.",
            },
            {
                "name": "Travel Companion Format",
                "category": "On-The-Move Edition",
                "description": "Compact ergonomic form designed for seamless metropolitan transitions.",
            },
        ]

    @staticmethod
    def _build_cultural_moments(territory: TerritoryAtmosphereSpec) -> list[dict[str, str]]:
        return [
            {
                "title": "Twilight Threshold Ritual",
                "description": f"Transitioning from kinetic street rhythm into calm intentional focus in {territory.place_name}.",
            },
            {
                "title": "Golden-Hour Craft Pause",
                "description": "An unhurried sensory interlude bathed in directional late-afternoon architectural light.",
            },
            {
                "title": "After-Hours Studio Solitude",
                "description": "Quiet nocturnal mastery when the city settles and tactile craftsmanship takes center stage.",
            },
        ]

    def discover(
        self,
        subject: str,
        offering_hint: str = "",
        territory_hint: str = "",
        custom_dna: str = "",
    ) -> SoundstageDiscoveryResult:
        """Executes deterministic + optional Gemini Flash enriched 10-step Soundstage discovery."""
        subj_clean = (subject or "").strip() or "Artisan Studio"
        primary_territory = _resolve_territory(territory_hint)
        physics = self._physics_analyzer.analyze(
            subject=subj_clean,
            offering=offering_hint or f"{subj_clean} Signature Edition",
            territory=primary_territory.place_name,
        )
        palette = _select_palette_for_archetype(physics.archetype)
        tagline = f"Precision crafted for the quiet pulse of {primary_territory.place_name.split('·')[0].strip()}."
        if custom_dna and custom_dna.strip():
            tagline = f"Designed around {custom_dna.strip().rstrip('.')}."

        if not self.mock_mode and self._genai_client is not None:
            try:
                enrich_prompt = (
                    "Return ONLY a JSON object with keys 'tagline' (max 10 words) and "
                    "'palette' ({primary_hex, primary_name, secondary_hex, secondary_name, neutral_hex, neutral_name}) "
                    f"for commercial subject '{subj_clean}', offering '{physics.offering}', "
                    f"territory '{primary_territory.place_name}', DNA '{custom_dna}'."
                )
                resp = self._genai_client.models.generate_content(
                    model=getattr(settings, "flash_model_id", "gemini-3.8-flash"),
                    contents=enrich_prompt,
                )
                raw_text = getattr(resp, "text", "") or ""
                fence = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
                if fence:
                    parsed = json.loads(fence.group(0))
                    if isinstance(parsed, dict):
                        cand_tag = str(parsed.get("tagline", "")).strip()
                        if 4 <= len(cand_tag) <= 90:
                            tagline = cand_tag
                        cand_pal = parsed.get("palette")
                        if isinstance(cand_pal, dict):
                            palette = Palette603010(**cand_pal)
            except Exception as exc:
                logger.warning("SoundstageDiscoveryEngine live enrichment fallback: %s", exc)

        identity = DualLayerIdentityAbstractor.abstract(
            subject=subj_clean,
            offering=physics.offering,
            physics=physics,
            palette=palette,
            tagline=tagline,
        )

        territories: list[TerritoryAtmosphereSpec] = [primary_territory]
        for spec in _CURATED_TERRITORIES.values():
            if spec.place_name != primary_territory.place_name and len(territories) < 4:
                territories.append(spec)

        emblem_prompt = (
            f"Minimalist geometric vector emblem mark on a solid {palette.neutral_name} "
            f"({palette.neutral_hex}) flat background, rendered in crisp {palette.primary_name} "
            f"({palette.primary_hex}) and {palette.secondary_name} ({palette.secondary_hex}) lines, "
            "pure abstract modernist symbol, zero letters, zero words, studio graphic design."
        )
        packshot_prompt = (
            f"1:1 commercial studio hero product photograph of {identity.omni_safe_offering_descriptor}, "
            f"resting centered on a {palette.neutral_name} ({palette.neutral_hex}) architectural plinth "
            f"against a soft {palette.primary_name} ({palette.primary_hex}) gradient backdrop, "
            "100mm macro cinema prime lens, crisp rim lighting, zero hands, zero text."
        )

        return SoundstageDiscoveryResult(
            subject=subj_clean,
            suggested_offerings=self._build_suggested_offerings(
                subject=subj_clean,
                offering_hint=offering_hint,
                archetype=physics.archetype,
            ),
            suggested_territories=territories,
            palette=palette,
            cultural_moments=self._build_cultural_moments(primary_territory),
            spoken_languages=list(_SPOKEN_LANGUAGES),
            tagline=tagline,
            emblem_prompt=emblem_prompt,
            packshot_prompt=packshot_prompt,
            physics=physics,
            identity=identity,
        )


class SoundstageThreeActPlanner:
    """Compiles 3-Act x 3-Beat (9-Shot) Mode 5 Commercial Soundstage plans and linted 4-Block Meta-Prompts."""

    def __init__(self, mock_mode: bool | None = None) -> None:
        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self._physics_analyzer = OfferingPhysicsAnalyzer(mock_mode=self.mock_mode)
        self._genai_client: Any = None
        if not self.mock_mode:
            self._init_genai_client()

    def _init_genai_client(self) -> None:
        try:
            self._genai_client = get_genai_client(
                location=getattr(settings, "gemini_location", "global")
            )
        except Exception as exc:
            logger.warning("SoundstageThreeActPlanner could not initialize GenAI client: %s", exc)
            self._genai_client = None

    @staticmethod
    def _resolve_language_cadence(language: str) -> str:
        lang_low = (language or "English").strip().lower()
        for entry in _SPOKEN_LANGUAGES:
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
                f"{cast_handle} (@Image1) settles into the sculpted driver cockpit and places poised hands "
                f"onto the steering wheel rim of the {offering_desc} (@Image2) in smooth tactile alignment."
            )
        if role == "PASSENGER_IN_REAR_CABIN":
            return (
                f"{cast_handle} (@Image1) relaxes exclusively in the serene rear passenger cabin seat of the "
                f"{offering_desc} (@Image2) as city light glides across the glass."
            )
        if role == "RECIPIENT_AT_DOOR_AND_TABLE":
            return (
                f"{cast_handle} (@Image1) receives and unveils the {offering_desc} (@Image2) onto the "
                "architectural dining table in a poised first-contact gesture."
            )
        if role == "GUEST_LIVING_IN_SPACE":
            return (
                f"{cast_handle} (@Image1) steps across the threshold of the {offering_desc} (@Image2), "
                "tracing fingertips along honed travertine and warm timber joinery."
            )
        if role == "CARDHOLDER_TAPPING_AT_VENUE":
            return (
                f"{cast_handle} (@Image1) presents the {offering_desc} (@Image2) in a single fluid "
                "contactless tap against the stone venue counter."
            )
        if role == "WIELDER_OF_ARTIFACT":
            return (
                f"{cast_handle} (@Image1) grips the balanced hilt of the {offering_desc} (@Image2) "
                "as warm practical light awakens along its sculpted fluting."
            )
        return (
            f"{cast_handle} (@Image1) lifts the {offering_desc} (@Image2) from the hero plinth "
            "in a single deliberate first-contact ergonomic gesture."
        )

    @staticmethod
    def _scrub_place_label(place_name: str, subject: str, offering: str) -> str:
        scrubbed = scrub_offering_trademarks(
            place_name,
            subject=subject,
            offering=offering,
        )
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
        safe_place = self._scrub_place_label(
            territory.place_name,
            subject=identity.display_subject,
            offering=identity.display_offering,
        )
        safe_condition = scrub_offering_trademarks(
            territory.condition,
            subject=identity.display_subject,
            offering=identity.display_offering,
        )
        safe_lighting = scrub_offering_trademarks(
            territory.lighting_directive,
            subject=identity.display_subject,
            offering=identity.display_offering,
        )
        safe_vo = scrub_offering_trademarks(
            voiceover_line,
            subject=identity.display_subject,
            offering=identity.display_offering,
        )

        # Block 1: INPUT ROLES & REFERENCES
        block1 = (
            "### INPUT ROLES & REFERENCES\n"
            "[# References <IMAGE_REF_0>@Image1, <IMAGE_REF_1>@Image2]\n"
            f"- {lead_character.role_id} ({lead_character.image_role}): {cast_handle} (@Image1)\n"
            f"- {hero_offering_role.role_id} ({hero_offering_role.image_role}): Hero Offering Anchor (@Image2)"
        )

        # Block 2: CHARACTER PROFILES (locked to reference sheets to uphold Zero Wardrobe Redundancy)
        block2 = (
            "### CHARACTER PROFILES\n"
            f"- {lead_character.role_id} ({cast_handle}) (Reference Image: @Image1): "
            "Composed charismatic commercial lead with expressive cinematic poise and decisive posture. "
            "Enforce Zero Wardrobe Redundancy: Visual appearance locked to reference sheet @Image1. "
            f"[Voice Style: {vocal_cadence}]\n"
            f"- {hero_offering_role.role_id} (Hero Offering Anchor) (Reference Image: @Image2): "
            f"{identity.omni_safe_offering_descriptor}. "
            "Enforce Zero Wardrobe Redundancy: Visual appearance locked to reference sheet @Image2."
        )

        # Block 3: SCENE INSTRUCTIONS
        ducking_clause = PreFlightGatekeeper.CANONICAL_DUCKING_CLAUSE
        block3_lines = [
            f"- Act Window: Act {act_number} ({time_window})",
            f"- Camera & Lighting: In a single continuous shot. No scene cuts. {safe_lighting}. No text, no subtitles on screen.",
            f"- Spatial Staging: [{lead_character.role_id}] positioned on screen-left during human performance beats, [{hero_offering_role.role_id}] positioned on screen-right focal plane to maintain clear identity separation.",
            f"- Environment: {identity.omni_safe_world_descriptor} in {safe_place} ({safe_condition}, {territory.temperature_c}C).",
            f"- Production Design Palette (60/30/10 Color Lock): {palette.production_design_directive}",
            f"- Causality Gate (Act {act_number}): {physics.act_causality_laws[act_number]}",
            f"- Audio: instrumental {audio_score} {sound_effects}. {ducking_clause}",
            "- Clean Frame Directive: No text, no subtitles on screen.",
        ]
        block3 = "### SCENE INSTRUCTIONS\n" + "\n".join(block3_lines)

        # Block 4: TIMELINE
        s1, s2, s3 = shots[0], shots[1], shots[2]
        a1 = scrub_offering_trademarks(
            s1.action,
            subject=identity.display_subject,
            offering=identity.display_offering,
        )
        a2 = scrub_offering_trademarks(
            s2.action,
            subject=identity.display_subject,
            offering=identity.display_offering,
        )
        a3 = scrub_offering_trademarks(
            s3.action,
            subject=identity.display_subject,
            offering=identity.display_offering,
        )
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
    ) -> SoundstageCommercialPlan:
        """Builds a 3-Act x 3-Beat (9-Shot) SoundstageCommercialPlan with PreFlight-linted 4-block prompts."""
        subj_clean = (subject or "").strip() or "Artisan Studio"
        off_clean = (offering or "").strip() or f"{subj_clean} Signature Edition"
        territory_spec = _resolve_territory(territory)
        if weather_condition and weather_condition.strip():
            territory_spec = territory_spec.model_copy(
                update={"condition": weather_condition.strip()}
            )

        physics = self._physics_analyzer.analyze(
            subject=subj_clean,
            offering=off_clean,
            territory=territory_spec.place_name,
        )
        palette = _select_palette_for_archetype(
            archetype=physics.archetype,
            custom_hexes=palette_hexes,
        )

        override_name = lead_character_override.name if lead_character_override else None
        override_wardrobe = lead_character_override.wardrobe if lead_character_override else None

        identity = DualLayerIdentityAbstractor.abstract(
            subject=subj_clean,
            offering=off_clean,
            physics=physics,
            palette=palette,
            lead_name=override_name,
            lead_wardrobe=override_wardrobe,
            tagline=tagline or None,
        )

        moment_clean = (moment or "").strip() or "Twilight Threshold Ritual"
        lang_clean = (language or "English").strip() or "English"
        vocal_cadence = (
            lead_character_override.voice_style
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
                f"Tailored architectural silhouette in {palette.secondary_name} ({palette.secondary_hex})"
            ),
            voice_style=vocal_cadence,
            aesthetic_tags=[
                palette.secondary_name,
                palette.secondary_hex,
                "Commercial Soundstage",
            ],
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
            aesthetic_tags=[
                palette.neutral_name,
                palette.neutral_hex,
                physics.archetype,
            ],
            image_role="Prop Reference",
            is_offscreen_narrator=False,
        )

        dna_clause = f" Guided by creative DNA: {custom_dna.strip()}." if custom_dna.strip() else ""
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

        # Voiceover lines per act (scrubbed of raw brand triggers for Omni audio synthesis; end-card locks brand)
        vo_act1 = "Before the rush claims the street, stillness sharpens every sense."
        vo_act2 = "One deliberate touch reveals where true craft lives."
        vo_act3 = "Carry the quiet pulse long after the moment settles."
        voiceover_full_script = f"[0:00] {vo_act1}\n[0:10] {vo_act2}\n[0:20] {vo_act3}"

        safe_place = self._scrub_place_label(
            territory_spec.place_name,
            subject=identity.display_subject,
            offering=identity.display_offering,
        )
        palette_prompt_suffix = (
            f"Production design locked to {palette.production_design_directive}. "
            f"{territory_spec.lighting_directive}. Shot on 35mm cinema prime for {settings.image_model_id}, "
            "photorealistic 8k commercial cinematography, zero text, zero watermarks."
        )

        # --- ACT 1 TILES (1.1, 1.2, 1.3 — 1.3 has_person=False) ---
        act1_shots = [
            StoryboardTileSpec(
                shot_id="1.1",
                act_number=1,
                beat_index=1,
                timecode_range="0.0-3.3s",
                framing="Wide Architectural Tracking Shot",
                action=(
                    f"{cast_handle} (@Image1) walks empty-handed along the {safe_place} threshold "
                    f"under {territory_spec.condition}, immersed in pre-interaction anticipation."
                ),
                has_person=True,
                image_prompt=(
                    f"Wide architectural establishing frame in {safe_place} ({territory_spec.condition}), "
                    f"{identity.omni_safe_cast_description} walking empty-handed on screen-left with poised anticipation. "
                    f"{palette_prompt_suffix}"
                ),
            ),
            StoryboardTileSpec(
                shot_id="1.2",
                act_number=1,
                beat_index=2,
                timecode_range="3.3-6.7s",
                framing="Medium Kinetic Portrait",
                action=(
                    f"Camera glides into a medium portrait of {cast_handle} (@Image1) pausing empty-handed "
                    "as warm directional rim light catches focused eyes before any offering contact."
                ),
                has_person=True,
                image_prompt=(
                    f"Medium cinema portrait of {identity.omni_safe_cast_description} in {safe_place}, "
                    f"hands empty at sides, focused anticipatory gaze toward warm architectural threshold. "
                    f"{palette_prompt_suffix}"
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
                    f"shadowed surfaces, zero people, zero hands. {palette_prompt_suffix}"
                ),
            ),
        ]

        # --- ACT 2 TILES (2.1, 2.2, 2.3 — 2.2 has_person=False 100mm zero-hand optical macro) ---
        thermal_detail = {
            "ambient": "dry room-temperature satin material finish and crisp specular bevels",
            "chilled": "fine chilled micro-condensation sheen across the cold exterior surface",
            "hot": "delicate natural aromatic thermal wisps rising softly from the warm vessel",
        }[physics.thermal_state]

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
                    f"in {safe_place}. {palette_prompt_suffix}"
                ),
            ),
            StoryboardTileSpec(
                shot_id="2.2",
                act_number=2,
                beat_index=2,
                timecode_range="3.3-6.7s",
                framing="100mm Zero-Hand Optical Craft Macro (Human-Free)",
                action=(
                    f"Dedicated 100mm zero-hand optical macro isolating {identity.omni_safe_offering_descriptor} (@Image2) "
                    f"with zero human presence, showcasing {thermal_detail}."
                ),
                has_person=False,
                image_prompt=(
                    f"100mm optical macro studio-grade cinema close-up of {identity.omni_safe_offering_descriptor} "
                    f"resting solo on {palette.neutral_name} ({palette.neutral_hex}) surface, showcasing {thermal_detail}, "
                    f"zero hands, zero people in frame. {palette_prompt_suffix}"
                ),
            ),
            StoryboardTileSpec(
                shot_id="2.3",
                act_number=2,
                beat_index=3,
                timecode_range="6.7-10.0s",
                framing="Expressive Close-Up Signature Reaction",
                action=(
                    f"Tight expressive close-up on {cast_handle} (@Image1) registering a single quiet, "
                    "authentic signature experience reaction as directional light warms the frame."
                ),
                has_person=True,
                image_prompt=(
                    f"Tight expressive 85mm cinema close-up of {identity.omni_safe_cast_description} "
                    f"experiencing a calm resonant moment of satisfaction in {safe_place}. {palette_prompt_suffix}"
                ),
            ),
        ]

        # --- ACT 3 TILES (3.1, 3.2, 3.3 — 3.3 has_person=False solo hero packshot lockup) ---
        act3_shots = [
            StoryboardTileSpec(
                shot_id="3.1",
                act_number=3,
                beat_index=1,
                timecode_range="0.0-3.3s",
                framing="Fluid Steadicam Lifestyle Payoff",
                action=(
                    f"{cast_handle} (@Image1) moves in composed post-experience equilibrium through {safe_place} "
                    "without repeated consumption, radiating effortless confidence."
                ),
                has_person=True,
                image_prompt=(
                    f"Fluid Steadicam medium-wide lifestyle payoff shot of {identity.omni_safe_cast_description} "
                    f"in {safe_place} during {moment_clean}, post-experience poise without repeated consumption. "
                    f"{palette_prompt_suffix}"
                ),
            ),
            StoryboardTileSpec(
                shot_id="3.2",
                act_number=3,
                beat_index=2,
                timecode_range="3.3-6.7s",
                framing="Low-Angle Architectural Transition",
                action=(
                    f"Camera glides past {cast_handle} (@Image1) on screen-left toward the illuminated "
                    f"{palette.neutral_name} ({palette.neutral_hex}) hero stage on screen-right."
                ),
                has_person=True,
                image_prompt=(
                    f"Low-angle 35mm cinema composition of {identity.omni_safe_cast_description} in three-quarter "
                    f"profile within {safe_place}, camera transitioning toward hero presentation plinth. "
                    f"{palette_prompt_suffix}"
                ),
            ),
            StoryboardTileSpec(
                shot_id="3.3",
                act_number=3,
                beat_index=3,
                timecode_range="6.7-10.0s",
                framing="Solo Hero Packshot Lockup (Motionless Human-Free)",
                action=(
                    f"Motionless human-free solo hero packshot lockup of {identity.omni_safe_offering_descriptor} (@Image2) "
                    f"centered cleanly on the {palette.neutral_name} ({palette.neutral_hex}) plinth with negative space for post-conform lockup."
                ),
                has_person=False,
                image_prompt=(
                    f"Motionless human-free solo commercial hero packshot of {identity.omni_safe_offering_descriptor} "
                    f"on {palette.neutral_name} ({palette.neutral_hex}) plinth against {palette.primary_name} "
                    f"({palette.primary_hex}) architectural depth, clean negative space, zero hands, zero people. "
                    f"{palette_prompt_suffix}"
                ),
            ),
        ]

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

        for (
            act_num,
            act_title,
            time_win,
            summary,
            vo_line,
            score,
            sfx,
            act_shots,
        ) in act_specs:
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
        """Rebuilds a SoundstageCommercialPlan mutating only the requested axis while locking unchanged axes."""
        val_clean = (new_value or "").strip()
        if not val_clean:
            return existing_plan

        locked_palette_hexes = [
            existing_plan.palette.primary_hex,
            existing_plan.palette.secondary_hex,
            existing_plan.palette.neutral_hex,
        ]
        territory_val = existing_plan.territory.place_name
        offering_val = existing_plan.offering
        lead_override: CharacterRoleModel | None = existing_plan.lead_character
        packshot_url = existing_plan.hero_offering_role.reference_url

        if axis == "place":
            territory_val = val_clean
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
            palette_hexes=locked_palette_hexes,
            moment=existing_plan.moment,
            language=existing_plan.language,
            tagline=existing_plan.identity.display_tagline,
            lead_character_override=lead_override,
            packshot_url=packshot_url,
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
