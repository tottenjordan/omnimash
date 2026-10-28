"""Mode 5 Commercial Soundstage Discovery Engine, 60/30/10 Palette, and Dual-Layer Identity Abstractor.

Implements:
- 60/30/10 Production Design Color-Lock (`Palette603010`)
- Territory & Atmosphere Metadata (`TerritoryAtmosphereSpec`)
- Dual-Layer Brand & Cast Safety Abstraction (`DualLayerIdentityAbstractor`)
- 10-Step Intake Discovery Engine (`SoundstageDiscoveryEngine`)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

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

logger = logging.getLogger(__name__)

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

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

        words = re.findall(r"[A-Za-z]+", raw)
        if not words:
            return default_handle

        safe_lookup = {h.lower(): h for h in _SAFE_ROLE_HANDLES}
        for word in reversed(words):
            w_low = word.lower()
            if w_low in safe_lookup and w_low not in brand_tokens_lower:
                return safe_lookup[w_low]

        if len(words) == 1 and len(words[0]) >= 3 and words[0].lower() not in brand_tokens_lower:
            return words[0].capitalize()

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

        raw_offering_desc = (
            f"{physics.canonical_anchor_spec}, finished with {palette.neutral_name} "
            f"({palette.neutral_hex}) foundational accents and subtle {palette.primary_name} "
            f"({palette.primary_hex}) tonal trim, completely free of printed wordmarks"
        )
        omni_safe_offering_descriptor = scrub_offering_trademarks(
            raw_offering_desc, subject=display_subject, offering=display_offering
        )

        wardrobe_clause = (lead_wardrobe or "").strip()
        if wardrobe_clause:
            wardrobe_clause = scrub_offering_trademarks(
                wardrobe_clause, subject=display_subject, offering=display_offering
            )
        if lead_name and lead_name.strip():
            for name_tok in re.findall(r"[A-Za-z]{2,}", lead_name):
                if name_tok.lower() != cast_handle.lower():
                    wardrobe_clause = re.sub(
                        rf"\b{re.escape(name_tok)}\b", "", wardrobe_clause, flags=re.IGNORECASE
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
            raw_cast_desc, subject=display_subject, offering=display_offering
        )

        raw_world_desc = (
            f"Architectural commercial soundstage environment anchored in 60% {palette.primary_name} "
            f"({palette.primary_hex}) spatial surfaces, 30% {palette.secondary_name} "
            f"({palette.secondary_hex}) practical set accents, and 10% {palette.neutral_name} "
            f"({palette.neutral_hex}) hero presentation plinth"
        )
        omni_safe_world_descriptor = scrub_offering_trademarks(
            raw_world_desc, subject=display_subject, offering=display_offering
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


CURATED_TERRITORIES: dict[str, TerritoryAtmosphereSpec] = {
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

SPOKEN_LANGUAGES: list[dict[str, str]] = [
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


def resolve_territory(territory_hint: str) -> TerritoryAtmosphereSpec:
    """Resolves a territory hint into a curated or synthesized TerritoryAtmosphereSpec."""
    hint_clean = (territory_hint or "").strip()
    if not hint_clean:
        return CURATED_TERRITORIES["tokyo"]

    lower = hint_clean.lower()
    for key, spec in CURATED_TERRITORIES.items():
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


def select_palette_for_archetype(
    archetype: OfferingArchetype,
    custom_hexes: list[str] | None = None,
) -> Palette603010:
    """Selects a deterministic 60/30/10 palette for an offering archetype with optional hex overrides."""
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
            "Cerulean Accent",
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


def invoke_flash_json_dict(genai_client: Any, prompt: str) -> dict[str, Any] | None:
    """Invokes settings.flash_model_id with JSON MIME config and parses a JSON dict safely."""
    model_id = getattr(settings, "flash_model_id", "gemini-3.8-flash")
    try:
        resp = genai_client.models.generate_content(
            model=model_id,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
    except TypeError:
        resp = genai_client.models.generate_content(model=model_id, contents=prompt)

    raw_text = (getattr(resp, "text", "") or "").strip()
    if not raw_text:
        return None
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, flags=re.DOTALL)
    candidate = fence_match.group(1) if fence_match else raw_text
    if not fence_match:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = candidate[start : end + 1]
    parsed = json.loads(candidate)
    return parsed if isinstance(parsed, dict) else None


class SoundstageDiscoveryEngine:
    """10-step intake discovery engine generating offerings, territories, 60/30/10 palette, and physics."""

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
                logger.warning("SoundstageDiscoveryEngine could not init GenAI client: %s", exc)

    @staticmethod
    def _build_suggested_offerings(
        subject: str,
        offering_hint: str,
        archetype: OfferingArchetype,
    ) -> list[dict[str, str]]:
        primary_name = (offering_hint or "").strip() or f"{subject} Signature Edition"
        if archetype == "OWNED_MOTOR_VEHICLE":
            return [
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
            ]
        if archetype == "PARODY_PROP_OR_ARTIFACT":
            return [
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
            ]
        if archetype == "FOOD_OR_DINING_DELIVERY":
            return [
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
                    "name": "Artisanal Espresso & Pastry Drop",
                    "category": "Morning Ritual Courier",
                    "description": "Warm laminated pastry box paired with single-origin pour-over thermal carafe.",
                },
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
        primary_territory = resolve_territory(territory_hint)
        physics = self._physics_analyzer.analyze(
            subject=subj_clean,
            offering=offering_hint or f"{subj_clean} Signature Edition",
            territory=primary_territory.place_name,
        )
        palette = select_palette_for_archetype(physics.archetype)
        tagline = f"Precision crafted for the quiet pulse of {primary_territory.place_name.split('·')[0].strip()}."
        if custom_dna and custom_dna.strip():
            tagline = f"Designed around {custom_dna.strip().rstrip('.')}."

        suggested_offerings = self._build_suggested_offerings(
            subject=subj_clean, offering_hint=offering_hint, archetype=physics.archetype
        )
        territories: list[TerritoryAtmosphereSpec] = [primary_territory]
        for spec in CURATED_TERRITORIES.values():
            if spec.place_name != primary_territory.place_name and len(territories) < 4:
                territories.append(spec)
        cultural_moments = self._build_cultural_moments(primary_territory)

        if not self.mock_mode and self._genai_client is not None:
            try:
                enrich_prompt = (
                    "Return ONLY a JSON object for a 30-second commercial soundstage discovery intake.\n"
                    f"Subject: {subj_clean} | Offering: {physics.offering} | "
                    f"Territory Hint: {primary_territory.place_name} | Creative DNA: {custom_dna}\n"
                    "Required JSON keys:\n"
                    "- tagline: crisp commercial tagline (max 10 words)\n"
                    "- palette: {primary_hex, primary_name, secondary_hex, secondary_name, neutral_hex, neutral_name}\n"
                    "- suggested_offerings: list of 3 objects {name, category, description}\n"
                    "- suggested_territories: list of 3 objects {place_name, temperature_c, condition, lighting_directive, cultural_pulse}\n"
                    "- cultural_moments: list of 3 objects {title, description}\n"
                )
                parsed = invoke_flash_json_dict(self._genai_client, enrich_prompt)
                if parsed:
                    cand_tag = str(parsed.get("tagline", "")).strip()
                    if 4 <= len(cand_tag) <= 100:
                        tagline = cand_tag
                    cand_pal = parsed.get("palette")
                    if isinstance(cand_pal, dict):
                        try:
                            palette = Palette603010(**cand_pal)
                        except Exception:
                            pass
                    cand_off = parsed.get("suggested_offerings")
                    if isinstance(cand_off, list):
                        valid_off = [
                            {
                                "name": str(item["name"]).strip(),
                                "category": str(item["category"]).strip(),
                                "description": str(item["description"]).strip(),
                            }
                            for item in cand_off
                            if isinstance(item, dict)
                            and str(item.get("name", "")).strip()
                            and str(item.get("category", "")).strip()
                            and str(item.get("description", "")).strip()
                        ]
                        if valid_off:
                            for fb_item in suggested_offerings:
                                if len(valid_off) >= 3:
                                    break
                                valid_off.append(fb_item)
                            suggested_offerings = valid_off
                    cand_terr = parsed.get("suggested_territories")
                    if isinstance(cand_terr, list):
                        valid_terr: list[TerritoryAtmosphereSpec] = []
                        for item in cand_terr:
                            if isinstance(item, dict):
                                try:
                                    valid_terr.append(TerritoryAtmosphereSpec(**item))
                                except Exception:
                                    continue
                        if valid_terr:
                            for fb_t in territories:
                                if len(valid_terr) >= 3:
                                    break
                                valid_terr.append(fb_t)
                            territories = valid_terr
                    cand_mom = parsed.get("cultural_moments")
                    if isinstance(cand_mom, list):
                        valid_mom = [
                            {
                                "title": str(item["title"]).strip(),
                                "description": str(item["description"]).strip(),
                            }
                            for item in cand_mom
                            if isinstance(item, dict)
                            and str(item.get("title", "")).strip()
                            and str(item.get("description", "")).strip()
                        ]
                        if valid_mom:
                            for fb_m in cultural_moments:
                                if len(valid_mom) >= 3:
                                    break
                                valid_mom.append(fb_m)
                            cultural_moments = valid_mom
            except Exception as exc:
                logger.warning("SoundstageDiscoveryEngine live enrichment fallback: %s", exc)

        identity = DualLayerIdentityAbstractor.abstract(
            subject=subj_clean,
            offering=physics.offering,
            physics=physics,
            palette=palette,
            tagline=tagline,
        )

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
            suggested_offerings=suggested_offerings,
            suggested_territories=territories,
            palette=palette,
            cultural_moments=cultural_moments,
            spoken_languages=list(SPOKEN_LANGUAGES),
            tagline=tagline,
            emblem_prompt=emblem_prompt,
            packshot_prompt=packshot_prompt,
            physics=physics,
            identity=identity,
        )


__all__ = [
    "CURATED_TERRITORIES",
    "DualLayerIdentityAbstractor",
    "DualLayerIdentitySpec",
    "Palette603010",
    "SPOKEN_LANGUAGES",
    "SoundstageDiscoveryEngine",
    "SoundstageDiscoveryResult",
    "TerritoryAtmosphereSpec",
    "invoke_flash_json_dict",
    "resolve_territory",
    "select_palette_for_archetype",
]
