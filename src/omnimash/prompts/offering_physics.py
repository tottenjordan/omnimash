"""First-principles Offering Physics deduction engine for OmniMash Mode 5: Commercial Soundstage.

Deduces physical scale, ergonomic human-offering role, surface branding constraints,
thermal equilibrium state, 3-act temporal causality laws, and forbidden hallucinations
for any commercial brand, product, service, or parody offering.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from omnimash.config import settings
from omnimash.prompts.genai_client import get_genai_client
from omnimash.prompts.parody import sanitize_real_names

logger = logging.getLogger(__name__)

OfferingArchetype = Literal[
    "HANDHELD_CPG_OR_OBJECT",
    "COUNTERTOP_APPLIANCE",
    "OWNED_MOTOR_VEHICLE",
    "PASSENGER_MOBILITY_OR_TRANSIT",
    "FOOD_OR_DINING_DELIVERY",
    "HOSPITALITY_OR_ARCHITECTURAL_STAY",
    "FINANCIAL_OR_MEMBERSHIP_CARD",
    "DIGITAL_APP_OR_SERVICE",
    "PARODY_PROP_OR_ARTIFACT",
]

PhysicalScale = Literal[
    "HANDHELD_10_TO_30CM",
    "TABLETOP_30_TO_60CM",
    "FULL_SCALE_VEHICLE_5M",
    "ARCHITECTURAL_SPACE_OR_VENUE",
    "POCKET_CARD_OR_DEVICE",
]

ErgonomicRole = Literal[
    "DRIVER_AT_WHEEL",
    "PASSENGER_IN_REAR_CABIN",
    "RECIPIENT_AT_DOOR_AND_TABLE",
    "GUEST_LIVING_IN_SPACE",
    "CARDHOLDER_TAPPING_AT_VENUE",
    "ACTIVE_USER_OR_CONSUMER",
    "WIELDER_OF_ARTIFACT",
]

SurfaceBrandingMode = Literal[
    "PRINTED_RETAIL_LABEL",
    "SUBTLE_OEM_EMBLEM_ONLY",
    "UNMARKED_CLEAN_EXTERIOR",
]

ThermalState = Literal["ambient", "chilled", "hot"]

VALID_ARCHETYPES: frozenset[str] = frozenset(
    {
        "HANDHELD_CPG_OR_OBJECT",
        "COUNTERTOP_APPLIANCE",
        "OWNED_MOTOR_VEHICLE",
        "PASSENGER_MOBILITY_OR_TRANSIT",
        "FOOD_OR_DINING_DELIVERY",
        "HOSPITALITY_OR_ARCHITECTURAL_STAY",
        "FINANCIAL_OR_MEMBERSHIP_CARD",
        "DIGITAL_APP_OR_SERVICE",
        "PARODY_PROP_OR_ARTIFACT",
    }
)

VALID_PHYSICAL_SCALES: frozenset[str] = frozenset(
    {
        "HANDHELD_10_TO_30CM",
        "TABLETOP_30_TO_60CM",
        "FULL_SCALE_VEHICLE_5M",
        "ARCHITECTURAL_SPACE_OR_VENUE",
        "POCKET_CARD_OR_DEVICE",
    }
)

VALID_ERGONOMIC_ROLES: frozenset[str] = frozenset(
    {
        "DRIVER_AT_WHEEL",
        "PASSENGER_IN_REAR_CABIN",
        "RECIPIENT_AT_DOOR_AND_TABLE",
        "GUEST_LIVING_IN_SPACE",
        "CARDHOLDER_TAPPING_AT_VENUE",
        "ACTIVE_USER_OR_CONSUMER",
        "WIELDER_OF_ARTIFACT",
    }
)

VALID_SURFACE_BRANDING_MODES: frozenset[str] = frozenset(
    {"PRINTED_RETAIL_LABEL", "SUBTLE_OEM_EMBLEM_ONLY", "UNMARKED_CLEAN_EXTERIOR"}
)

VALID_THERMAL_STATES: frozenset[str] = frozenset({"ambient", "chilled", "hot"})

# Generic physical nouns allowed inside Omni-safe physical geometry descriptions
_GENERIC_PHYSICAL_NOUNS: frozenset[str] = frozenset(
    """
    aerodynamic aluminum ambient aperitif app appliance architectural artifact artisan
    bag beverage blade blender boiler botanical bottle bowl box brushed cabin can car
    card ceramic chauffeur chilled chocolate chronograph citrus classic cliffside coffee
    cold compact container countertop coupe cream credit cup cyber dark delivery device
    digital dining drink dropper dry dual electric elixir espresso executive facial
    flask food fragrance glass glowing gold handbag handheld headphones hot hotel iced
    jacket jar kettle leather lotion luxury machine matte meal membership metal metallic
    mobile modern motor motorcycle mug obsidian oil orb organic pack parfum passenger
    penthouse perfume phone pizza pocket potion pour ramen resort ride rideshare roadster
    roasted runed sanctuary sculpted sedan serum service shoe shuttle silver single
    skincare sleek smart smartphone snack sneaker sneakers soda soup spa sparkling
    spatial speaker spellbook sport sports stainless stay steaming steel streaming studio
    suite sunglasses suv sword tea titanium toaster tonic transit truck turntable vehicle
    vessel villa wand watch water
    """.split()
)

_HOT_THERMAL_CUES: tuple[str, ...] = (
    "steaming",
    "hot coffee",
    "hot pour",
    "hot tea",
    "espresso cup",
    "pour-over",
    "latte",
    "cappuccino",
    "ramen",
    "hot soup",
    "pizza",
    "hot meal",
    "hot chocolate",
    "broth",
    "freshly baked",
    "piping hot",
)
_CHILLED_THERMAL_CUES: tuple[str, ...] = (
    "iced",
    "chilled",
    "sparkling",
    "cold brew",
    "soda",
    "cola",
    "seltzer",
    "aperitif can",
    "botanical can",
    "energy drink",
    "gelato",
    "ice cream",
    "frost potion",
    "frozen",
    "tonic can",
    "lager",
)
_PARODY_CUES: tuple[str, ...] = (
    "wand",
    "potion",
    "elixir",
    "spellbook",
    "grimoire",
    "trapwarts",
    "wizard",
    "sorcerer",
    "cyber-blade",
    "laser sword",
    "mana",
    "enchanted",
    "arcane",
    "gauntlet",
    "relic",
    "cauldron",
)
_FOOD_DELIVERY_CUES: tuple[str, ...] = (
    "food delivery",
    "meal delivery",
    "dining delivery",
    "takeout",
    "courier",
    "meal courier",
    "doorstep dining",
    "ramen",
    "pizza delivery",
    "dashbite",
    "delivery bag",
    "delivery parcel",
)
_PASSENGER_MOBILITY_CUES: tuple[str, ...] = (
    "rideshare",
    "ride-hail",
    "ride hail",
    "chauffeur",
    "shuttle",
    "transit",
    "taxi",
    "passenger cabin",
    "rear cabin",
    "metrohail",
    "autonomous ride",
    "town car service",
)
_HOSPITALITY_CUES: tuple[str, ...] = (
    "villa",
    "hotel",
    "resort",
    "architectural stay",
    "penthouse stay",
    "boutique suite",
    "sanctuary",
    "lodge",
    "spa retreat",
    "vacation rental",
    "hospitality",
)
_MOTOR_VEHICLE_CUES: tuple[str, ...] = (
    "coupe",
    "sedan",
    "suv",
    "roadster",
    "sportscar",
    "sports car",
    "hypercar",
    "grand tourer",
    "motor vehicle",
    "electric vehicle",
    "ev",
    "pickup truck",
    "motorcycle",
    "motors",
    "automotive",
)
_FINANCIAL_CARD_CUES: tuple[str, ...] = (
    "credit card",
    "debit card",
    "membership card",
    "titanium card",
    "metal card",
    "platinum card",
    "black card",
    "payment card",
    "tap-to-pay",
    "cardholder",
)
_DIGITAL_APP_CUES: tuple[str, ...] = (
    "app",
    "mobile app",
    "streaming app",
    "software",
    "saas",
    "cloud platform",
    "digital service",
    "fintech app",
    "audio app",
    "ai assistant",
)
_APPLIANCE_CUES: tuple[str, ...] = (
    "espresso machine",
    "coffee machine",
    "coffee maker",
    "countertop",
    "blender",
    "toaster",
    "stand mixer",
    "air fryer",
    "turntable",
    "smart speaker",
    "dual-boiler",
)
_LUXURY_HARDGOOD_CUES: tuple[str, ...] = (
    "watch",
    "chronograph",
    "timepiece",
    "sneaker",
    "sunglasses",
    "headphones",
    "fragrance",
    "parfum",
    "perfume",
)


def extract_brand_scrub_tokens(subject: str, offering: str = "") -> list[str]:
    """Extracts brand, trademark, and model designator tokens to scrub from Omni-safe video prompts."""
    phrases: list[str] = []
    subj_clean = (subject or "").strip()
    off_clean = (offering or "").strip()

    if len(subj_clean) >= 2:
        phrases.append(subj_clean)
    if len(off_clean) >= 3 and off_clean.lower() not in _GENERIC_PHYSICAL_NOUNS:
        phrases.append(off_clean)

    stop_words = {"the", "and", "for", "with", "from"}
    for source_text in (subj_clean, off_clean):
        for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-']*", source_text):
            t_low = tok.lower()
            if len(t_low) >= 2 and t_low not in stop_words and t_low not in _GENERIC_PHYSICAL_NOUNS:
                phrases.append(tok)

    return sorted(set(phrases), key=len, reverse=True)


def scrub_offering_trademarks(text: str, subject: str = "", offering: str = "") -> str:
    """Scrubs celebrity/parody names and dynamic brand/model tokens from Omni-safe text."""
    if not text:
        return text

    cleaned = sanitize_real_names(text)
    for tok in extract_brand_scrub_tokens(subject=subject, offering=offering):
        pattern = re.compile(rf"(?<![A-Za-z0-9#]){re.escape(tok)}(?![A-Za-z0-9])", re.IGNORECASE)
        cleaned = pattern.sub("", cleaned)

    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"([(\[])\s+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([)\]])", r"\1", cleaned)
    return cleaned.strip()


class OfferingPhysicsSpec(BaseModel):
    """First-principles physical specification and 3-act causality contract for a commercial offering."""

    subject: str = Field(..., description="Brand, label, or franchise display name")
    offering: str = Field(..., description="Specific product, service, or parody offering name")
    archetype: OfferingArchetype
    physical_scale: PhysicalScale
    ergonomic_role: ErgonomicRole
    surface_branding_mode: SurfaceBrandingMode
    thermal_state: ThermalState = "ambient"
    canonical_anchor_spec: str = Field(
        ...,
        description="1:1 physical geometry and material anchor description scrubbed of raw trademark tokens",
    )
    act_causality_laws: dict[int, str] = Field(
        default_factory=dict,
        description="3-act temporal causality laws keyed by act number (1, 2, 3)",
    )
    forbidden_hallucinations: list[str] = Field(
        default_factory=list,
        description="Explicit physical and ergonomic hallucination prohibitions",
    )


class OfferingPhysicsAnalyzer:
    """Deduces first-principles OfferingPhysicsSpec deterministically or via Gemini Flash JSON reasoning."""

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
            logger.warning("OfferingPhysicsAnalyzer could not initialize GenAI client: %s", exc)
            self._genai_client = None

    @staticmethod
    def _matches_any_keyword(text_lower: str, keywords: tuple[str, ...]) -> bool:
        """Word-boundary keyword match preventing substring collisions (e.g. 'audi' in 'audio')."""
        return any(re.search(rf"\b{re.escape(kw)}s?\b", text_lower) is not None for kw in keywords)

    @classmethod
    def _detect_thermal_state(
        cls,
        combined_lower: str,
        default: ThermalState = "ambient",
    ) -> ThermalState:
        if cls._matches_any_keyword(combined_lower, _HOT_THERMAL_CUES):
            return "hot"
        if cls._matches_any_keyword(combined_lower, _CHILLED_THERMAL_CUES):
            return "chilled"
        return default

    @staticmethod
    def _build_default_causality_laws(
        archetype: OfferingArchetype,
        ergonomic_role: ErgonomicRole,
    ) -> dict[int, str]:
        role_phrase_map: dict[ErgonomicRole, str] = {
            "DRIVER_AT_WHEEL": "hands settling onto the sculpted steering wheel rim and tactile cockpit controls",
            "PASSENGER_IN_REAR_CABIN": "settling effortlessly into the rear passenger sanctuary seat as the cabin glides forward",
            "RECIPIENT_AT_DOOR_AND_TABLE": "receiving the sealed craft parcel at threshold and unveiling the plated hero presentation at table",
            "GUEST_LIVING_IN_SPACE": "crossing the architectural threshold and running fingertips along natural stone and timber joinery",
            "CARDHOLDER_TAPPING_AT_VENUE": "presenting the precision-milled metal card for a crisp contactless tap at the venue counter",
            "ACTIVE_USER_OR_CONSUMER": "lifting and engaging the hero object with poised single-gesture ergonomic precision",
            "WIELDER_OF_ARTIFACT": "gripping the sculpted artifact hilt as subtle practical light responds to first tactile alignment",
        }
        contact_phrase = role_phrase_map[ergonomic_role]
        return {
            1: (
                "Act 1 Temporal Lock: Lead performer appears empty-handed in pre-interaction anticipation "
                "within the architectural world pulse; zero premature consumption, zero sipping, and zero early "
                "hand contact with the hero offering."
            ),
            2: (
                f"Act 2 Temporal Lock: Initiate tactile first contact ({contact_phrase}), isolate craft detail in "
                "a dedicated has_person=false 100mm zero-hand optical macro beat of the hero offering texture, "
                "and conclude with a single authentic signature experience reaction."
            ),
            3: (
                f"Act 3 Temporal Lock ({archetype}): Deliver composed post-experience lifestyle payoff without "
                "repeated consumption or redundant tasting, concluding on a motionless human-free solo hero "
                "anchor packshot frame."
            ),
        }

    @staticmethod
    def _build_forbidden_hallucinations(
        archetype: OfferingArchetype,
        thermal_state: ThermalState,
    ) -> list[str]:
        rules: list[str] = [
            "Never shrink full-scale vehicles or architectural spaces onto tabletops or pedestals.",
            "Never add unauthorized ice droplets, condensation, or hot steam to dry ambient containers or hardware.",
            "Never paint promotional typography, slogans, or giant logos across vehicle doors or residential walls.",
            "Never place passenger-mobility or rideshare riders in the driver seat or behind the steering wheel.",
            "Never render floating holographic UI HUDs or burned-in subtitles inside the live-action camera frame.",
        ]
        archetype_rules: dict[OfferingArchetype, str] = {
            "PASSENGER_MOBILITY_OR_TRANSIT": (
                "Passenger must remain exclusively in the rear cabin seat; exterior doors remain clean and unmarked."
            ),
            "OWNED_MOTOR_VEHICLE": (
                "Maintain true 1:1 5-meter wheelbase proportions on real roadway surfaces with subtle emblem-only trim."
            ),
            "FOOD_OR_DINING_DELIVERY": (
                "Maintain human-scale doorstep handoff and dining table presentation without miniature vehicle props."
            ),
            "HOSPITALITY_OR_ARCHITECTURAL_STAY": (
                "Stage performer naturally inside full-scale architectural rooms rather than viewing scale-model maquettes."
            ),
            "FINANCIAL_OR_MEMBERSHIP_CARD": (
                "Keep ISO-85mm pocket card proportions accurate in hand with unreadable micro-engraving only."
            ),
            "DIGITAL_APP_OR_SERVICE": (
                "Keep mobile screen graphics abstract and wordless without floating AR projections outside the glass."
            ),
            "COUNTERTOP_APPLIANCE": (
                "Keep countertop machine anchored on stable architectural cabinetry at true 1:1 kitchen scale."
            ),
            "PARODY_PROP_OR_ARTIFACT": (
                "Ground fantastical prop lighting in tactile physical materials rather than weightless CGI particle clouds."
            ),
            "HANDHELD_CPG_OR_OBJECT": (
                "Maintain natural single-hand ergonomic grip proportions without oversized novelty scaling."
            ),
        }
        rules.append(archetype_rules[archetype])

        if thermal_state == "ambient":
            rules.append(
                "Enforce dry room-temperature surface physics with zero condensation beads and zero rising vapor."
            )
        elif thermal_state == "chilled":
            rules.append(
                "Enforce chilled thermal physics: never render hot steam, rising vapor plumes, or boiling heat haze on chilled vessels."
            )
        elif thermal_state == "hot":
            rules.append(
                "Enforce warm thermal physics: never render frost crystals, ice-cold condensation droplets, or frozen exterior rime on hot offerings."
            )
        return rules

    def deduce_first_principles_fallback(
        self,
        subject: str,
        offering: str = "",
        territory: str = "",
    ) -> OfferingPhysicsSpec:
        """Deterministically classifies offering archetype, physical scale, ergonomics, and causality laws."""
        subj_clean = (subject or "").strip() or "Artisan Studio"
        off_clean = (offering or "").strip() or "Signature Edition"
        combined = f"{subj_clean} {off_clean}".lower()

        if self._matches_any_keyword(combined, _PARODY_CUES):
            archetype: OfferingArchetype = "PARODY_PROP_OR_ARTIFACT"
            physical_scale: PhysicalScale = "HANDHELD_10_TO_30CM"
            ergonomic_role: ErgonomicRole = "WIELDER_OF_ARTIFACT"
            branding_mode: SurfaceBrandingMode = "UNMARKED_CLEAN_EXTERIOR"
            thermal = self._detect_thermal_state(combined, default="ambient")
            anchor = (
                "1:1 handheld 28cm sculpted obsidian-and-brushed-brass artisan artifact with finely "
                "engraved geometric fluting, balanced grip proportions, and subtle practical internal glow"
            )
        elif self._matches_any_keyword(combined, _FOOD_DELIVERY_CUES):
            archetype = "FOOD_OR_DINING_DELIVERY"
            physical_scale = "TABLETOP_30_TO_60CM"
            ergonomic_role = "RECIPIENT_AT_DOOR_AND_TABLE"
            branding_mode = "PRINTED_RETAIL_LABEL"
            thermal = self._detect_thermal_state(combined, default="hot")
            anchor = (
                "1:1 structured kraft-and-linen culinary delivery parcel alongside an artisan ceramic "
                "serving vessel arranged on a clean architectural dining surface"
            )
        elif self._matches_any_keyword(combined, _PASSENGER_MOBILITY_CUES):
            archetype = "PASSENGER_MOBILITY_OR_TRANSIT"
            physical_scale = "FULL_SCALE_VEHICLE_5M"
            ergonomic_role = "PASSENGER_IN_REAR_CABIN"
            branding_mode = "UNMARKED_CLEAN_EXTERIOR"
            thermal = "ambient"
            anchor = (
                "1:1 full-scale 5-meter executive town-car exterior with unmarked clean metallic coachwork "
                "and a serene acoustic leather-and-alcantara rear passenger cabin"
            )
        elif self._matches_any_keyword(combined, _HOSPITALITY_CUES):
            archetype = "HOSPITALITY_OR_ARCHITECTURAL_STAY"
            physical_scale = "ARCHITECTURAL_SPACE_OR_VENUE"
            ergonomic_role = "GUEST_LIVING_IN_SPACE"
            branding_mode = "UNMARKED_CLEAN_EXTERIOR"
            thermal = "ambient"
            anchor = (
                "1:1 architectural hospitality pavilion crafted from board-formed travertine stone, "
                "warm cedar joinery, and floor-to-ceiling frameless horizon glazing"
            )
        elif self._matches_any_keyword(combined, _MOTOR_VEHICLE_CUES):
            archetype = "OWNED_MOTOR_VEHICLE"
            physical_scale = "FULL_SCALE_VEHICLE_5M"
            ergonomic_role = "DRIVER_AT_WHEEL"
            branding_mode = "SUBTLE_OEM_EMBLEM_ONLY"
            thermal = "ambient"
            anchor = (
                "1:1 full-scale 4.6-meter low-slung aerodynamic grand-touring coupe with sculpted metallic "
                "fenders, precision LED light blade, forged alloy wheels, and unmarked coachwork"
            )
        elif self._matches_any_keyword(combined, _FINANCIAL_CARD_CUES):
            archetype = "FINANCIAL_OR_MEMBERSHIP_CARD"
            physical_scale = "POCKET_CARD_OR_DEVICE"
            ergonomic_role = "CARDHOLDER_TAPPING_AT_VENUE"
            branding_mode = "SUBTLE_OEM_EMBLEM_ONLY"
            thermal = "ambient"
            anchor = (
                "1:1 ISO-standard 85mm brushed-titanium pocket payment card with chamfered diamond-cut "
                "bezel edges, matte anodized face, and precision metallic contact chip"
            )
        elif self._matches_any_keyword(combined, _DIGITAL_APP_CUES):
            archetype = "DIGITAL_APP_OR_SERVICE"
            physical_scale = "POCKET_CARD_OR_DEVICE"
            ergonomic_role = "ACTIVE_USER_OR_CONSUMER"
            branding_mode = "UNMARKED_CLEAN_EXTERIOR"
            thermal = "ambient"
            anchor = (
                "1:1 ultra-thin machined aluminum-and-glass pocket handset displaying a clean minimalist "
                "geometric light-mode waveform interface with zero readable text"
            )
        elif self._matches_any_keyword(combined, _APPLIANCE_CUES):
            archetype = "COUNTERTOP_APPLIANCE"
            physical_scale = "TABLETOP_30_TO_60CM"
            ergonomic_role = "ACTIVE_USER_OR_CONSUMER"
            branding_mode = "SUBTLE_OEM_EMBLEM_ONLY"
            thermal = self._detect_thermal_state(combined, default="ambient")
            anchor = (
                "1:1 42cm architectural countertop machine crafted from satin stainless steel and matte "
                "anodized aluminum with precision knurled tactile rotary controls"
            )
        else:
            archetype = "HANDHELD_CPG_OR_OBJECT"
            physical_scale = "HANDHELD_10_TO_30CM"
            ergonomic_role = "ACTIVE_USER_OR_CONSUMER"
            thermal = self._detect_thermal_state(combined, default="ambient")
            is_luxury = self._matches_any_keyword(combined, _LUXURY_HARDGOOD_CUES)
            branding_mode = "SUBTLE_OEM_EMBLEM_ONLY" if is_luxury else "PRINTED_RETAIL_LABEL"
            if thermal == "chilled":
                anchor = (
                    "1:1 handheld 250ml satin-matte aluminum beverage vessel with crisp micro-condensation "
                    "droplets, precision pull-tab crown, and clean geometric color-blocked wrap"
                )
            elif thermal == "hot":
                anchor = (
                    "1:1 handheld double-walled stoneware ceramic tasting cup cradling rich dark aromatic "
                    "crema with delicate natural thermal vapor wisps"
                )
            elif is_luxury:
                anchor = (
                    "1:1 precision-crafted 18cm sculptural luxury object in brushed 316L steel, sapphire "
                    "crystal bevels, and tactile satin-matte artisan finish without wordmarks"
                )
            else:
                anchor = (
                    "1:1 handheld 15cm architectural frosted-glass apothecary vessel with anodized metallic "
                    "collar, clean minimalist color-blocked band, and dry room-temperature finish"
                )

        clean_anchor = scrub_offering_trademarks(anchor, subject=subj_clean, offering=off_clean)
        laws = self._build_default_causality_laws(
            archetype=archetype, ergonomic_role=ergonomic_role
        )
        forbidden = self._build_forbidden_hallucinations(archetype=archetype, thermal_state=thermal)

        return OfferingPhysicsSpec(
            subject=subj_clean,
            offering=off_clean,
            archetype=archetype,
            physical_scale=physical_scale,
            ergonomic_role=ergonomic_role,
            surface_branding_mode=branding_mode,
            thermal_state=thermal,
            canonical_anchor_spec=clean_anchor,
            act_causality_laws=laws,
            forbidden_hallucinations=forbidden,
        )

    @staticmethod
    def _extract_json_dict(raw_text: str) -> dict[str, Any] | None:
        if not raw_text or not raw_text.strip():
            return None
        cleaned = raw_text.strip()
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1)
        else:
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                cleaned = cleaned[start : end + 1]
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    def analyze(
        self,
        subject: str,
        offering: str = "",
        territory: str = "",
    ) -> OfferingPhysicsSpec:
        """Deduces OfferingPhysicsSpec, enriching via Gemini Flash when live and sanitizing against fallback."""
        fallback = self.deduce_first_principles_fallback(
            subject=subject,
            offering=offering,
            territory=territory,
        )
        if self.mock_mode or self._genai_client is None:
            return fallback

        prompt = (
            "You are a commercial film physical continuity supervisor.\n"
            f"Subject / Brand: {fallback.subject}\n"
            f"Offering: {fallback.offering}\n"
            f"Territory: {territory or 'Global Metropolitan'}\n\n"
            "Return ONLY a JSON object with keys:\n"
            f"- archetype: one of {sorted(VALID_ARCHETYPES)}\n"
            f"- physical_scale: one of {sorted(VALID_PHYSICAL_SCALES)}\n"
            f"- ergonomic_role: one of {sorted(VALID_ERGONOMIC_ROLES)}\n"
            f"- surface_branding_mode: one of {sorted(VALID_SURFACE_BRANDING_MODES)}\n"
            f"- thermal_state: one of {sorted(VALID_THERMAL_STATES)}\n"
            "- canonical_anchor_spec: 1:1 physical geometry & material description with ZERO brand names\n"
            "- act_causality_laws: object with keys '1', '2', '3'\n"
            "- forbidden_hallucinations: list of 4-6 physical guardrail strings\n"
        )

        try:
            model_id = getattr(settings, "flash_model_id", "gemini-3.8-flash")
            try:
                resp = self._genai_client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                    config={"response_mime_type": "application/json"},
                )
            except TypeError:
                resp = self._genai_client.models.generate_content(model=model_id, contents=prompt)

            payload = self._extract_json_dict(getattr(resp, "text", "") or "")
            if not payload:
                return fallback

            raw_arch = str(payload.get("archetype", "")).strip()
            archetype = (
                cast(OfferingArchetype, raw_arch)
                if raw_arch in VALID_ARCHETYPES
                else fallback.archetype
            )
            raw_scale = str(payload.get("physical_scale", "")).strip()
            physical_scale = (
                cast(PhysicalScale, raw_scale)
                if raw_scale in VALID_PHYSICAL_SCALES
                else fallback.physical_scale
            )
            raw_role = str(payload.get("ergonomic_role", "")).strip()
            ergonomic_role = (
                cast(ErgonomicRole, raw_role)
                if raw_role in VALID_ERGONOMIC_ROLES
                else fallback.ergonomic_role
            )
            raw_brand_mode = str(payload.get("surface_branding_mode", "")).strip()
            surface_branding_mode = (
                cast(SurfaceBrandingMode, raw_brand_mode)
                if raw_brand_mode in VALID_SURFACE_BRANDING_MODES
                else fallback.surface_branding_mode
            )
            raw_thermal = str(payload.get("thermal_state", "")).strip().lower()
            thermal_state = (
                cast(ThermalState, raw_thermal)
                if raw_thermal in VALID_THERMAL_STATES
                else fallback.thermal_state
            )

            raw_anchor = str(payload.get("canonical_anchor_spec", "")).strip()
            clean_anchor = (
                scrub_offering_trademarks(
                    raw_anchor, subject=fallback.subject, offering=fallback.offering
                )
                if raw_anchor
                else fallback.canonical_anchor_spec
            )
            if len(clean_anchor) < 12:
                clean_anchor = fallback.canonical_anchor_spec

            raw_laws = payload.get("act_causality_laws")
            merged_laws: dict[int, str] = {}
            for act_idx in (1, 2, 3):
                candidate_law = ""
                if isinstance(raw_laws, dict):
                    candidate_law = str(
                        raw_laws.get(act_idx) or raw_laws.get(str(act_idx)) or ""
                    ).strip()
                clean_law = scrub_offering_trademarks(
                    candidate_law, subject=fallback.subject, offering=fallback.offering
                )
                merged_laws[act_idx] = (
                    clean_law if len(clean_law) >= 10 else fallback.act_causality_laws[act_idx]
                )

            raw_forbidden = payload.get("forbidden_hallucinations")
            forbidden_list: list[str] = []
            if isinstance(raw_forbidden, list):
                forbidden_list = [
                    scrub_offering_trademarks(
                        str(item).strip(), subject=fallback.subject, offering=fallback.offering
                    )
                    for item in raw_forbidden
                    if str(item).strip()
                ]
            if not forbidden_list:
                forbidden_list = list(fallback.forbidden_hallucinations)

            return OfferingPhysicsSpec(
                subject=fallback.subject,
                offering=fallback.offering,
                archetype=archetype,
                physical_scale=physical_scale,
                ergonomic_role=ergonomic_role,
                surface_branding_mode=surface_branding_mode,
                thermal_state=thermal_state,
                canonical_anchor_spec=clean_anchor,
                act_causality_laws=merged_laws,
                forbidden_hallucinations=forbidden_list,
            )
        except Exception as exc:
            logger.warning(
                "OfferingPhysicsAnalyzer LLM deduction fell back to deterministic rules: %s", exc
            )
            return fallback


__all__ = [
    "ErgonomicRole",
    "OfferingArchetype",
    "OfferingPhysicsAnalyzer",
    "OfferingPhysicsSpec",
    "PhysicalScale",
    "SurfaceBrandingMode",
    "ThermalState",
    "extract_brand_scrub_tokens",
    "scrub_offering_trademarks",
]
