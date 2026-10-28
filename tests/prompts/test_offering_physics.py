from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from omnimash.prompts.offering_physics import (
    OfferingPhysicsAnalyzer,
    OfferingPhysicsSpec,
    scrub_offering_trademarks,
)


def test_classify_owned_motor_vehicle_archetype() -> None:
    """Owned motor vehicles deduce full-scale 5m geometry, driver at wheel, and brand-free anchor spec."""
    analyzer = OfferingPhysicsAnalyzer(mock_mode=True)

    spec = analyzer.analyze(
        subject="Velox Motors",
        offering="GT9 Aero Coupe",
        territory="Tokyo · Shibuya",
    )

    assert isinstance(spec, OfferingPhysicsSpec)
    assert spec.subject == "Velox Motors"
    assert spec.offering == "GT9 Aero Coupe"
    assert spec.archetype == "OWNED_MOTOR_VEHICLE"
    assert spec.physical_scale == "FULL_SCALE_VEHICLE_5M"
    assert spec.ergonomic_role == "DRIVER_AT_WHEEL"
    assert spec.surface_branding_mode == "SUBTLE_OEM_EMBLEM_ONLY"
    assert spec.thermal_state == "ambient"
    assert "velox" not in spec.canonical_anchor_spec.lower()
    assert "gt9" not in spec.canonical_anchor_spec.lower()


def test_classify_passenger_mobility_rideshare_archetype() -> None:
    """Passenger rideshare/transit offerings place the human in the rear cabin with unmarked clean exterior."""
    analyzer = OfferingPhysicsAnalyzer(mock_mode=True)

    spec = analyzer.analyze(
        subject="MetroHail",
        offering="Executive Chauffeur Rideshare",
        territory="London · Soho",
    )

    assert spec.archetype == "PASSENGER_MOBILITY_OR_TRANSIT"
    assert spec.physical_scale == "FULL_SCALE_VEHICLE_5M"
    assert spec.ergonomic_role == "PASSENGER_IN_REAR_CABIN"
    assert spec.surface_branding_mode == "UNMARKED_CLEAN_EXTERIOR"
    assert spec.thermal_state == "ambient"
    joined_forbidden = " ".join(spec.forbidden_hallucinations).lower()
    assert "driver seat" in joined_forbidden
    assert "vehicle doors" in joined_forbidden or "promotional" in joined_forbidden


def test_classify_food_delivery_archetype() -> None:
    """Food delivery offerings classify as tabletop delivery received at door and table with hot thermal state."""
    analyzer = OfferingPhysicsAnalyzer(mock_mode=True)

    spec = analyzer.analyze(
        subject="DashBite",
        offering="Late-Night Hot Ramen Meal Delivery",
        territory="New York · SoHo",
    )

    assert spec.archetype == "FOOD_OR_DINING_DELIVERY"
    assert spec.physical_scale == "TABLETOP_30_TO_60CM"
    assert spec.ergonomic_role == "RECIPIENT_AT_DOOR_AND_TABLE"
    assert spec.surface_branding_mode == "PRINTED_RETAIL_LABEL"
    assert spec.thermal_state == "hot"


def test_classify_hospitality_architectural_stay_archetype() -> None:
    """Hospitality and architectural stays classify as architectural venues where the guest lives in space."""
    analyzer = OfferingPhysicsAnalyzer(mock_mode=True)

    spec = analyzer.analyze(
        subject="Solstice Pavilions",
        offering="Cliffside Architectural Villa Stay",
        territory="Kyoto · Higashiyama",
    )

    assert spec.archetype == "HOSPITALITY_OR_ARCHITECTURAL_STAY"
    assert spec.physical_scale == "ARCHITECTURAL_SPACE_OR_VENUE"
    assert spec.ergonomic_role == "GUEST_LIVING_IN_SPACE"
    assert spec.surface_branding_mode == "UNMARKED_CLEAN_EXTERIOR"
    assert spec.thermal_state == "ambient"


def test_classify_financial_membership_card_archetype() -> None:
    """Financial and membership cards classify as pocket card devices tapped at venue."""
    analyzer = OfferingPhysicsAnalyzer(mock_mode=True)

    spec = analyzer.analyze(
        subject="Meridian Reserve",
        offering="Brushed Titanium Membership Credit Card",
        territory="Milan · Brera",
    )

    assert spec.archetype == "FINANCIAL_OR_MEMBERSHIP_CARD"
    assert spec.physical_scale == "POCKET_CARD_OR_DEVICE"
    assert spec.ergonomic_role == "CARDHOLDER_TAPPING_AT_VENUE"
    assert spec.surface_branding_mode == "SUBTLE_OEM_EMBLEM_ONLY"
    assert spec.thermal_state == "ambient"


def test_classify_digital_app_and_countertop_appliance() -> None:
    """Digital apps classify as pocket devices while kitchen machines classify as countertop appliances."""
    analyzer = OfferingPhysicsAnalyzer(mock_mode=True)

    app_spec = analyzer.analyze(
        subject="PulseWave",
        offering="Spatial Audio Mobile Streaming App",
    )
    assert app_spec.archetype == "DIGITAL_APP_OR_SERVICE"
    assert app_spec.physical_scale == "POCKET_CARD_OR_DEVICE"
    assert app_spec.ergonomic_role == "ACTIVE_USER_OR_CONSUMER"

    appliance_spec = analyzer.analyze(
        subject="CremaForge",
        offering="Dual-Boiler Countertop Espresso Machine",
    )
    assert appliance_spec.archetype == "COUNTERTOP_APPLIANCE"
    assert appliance_spec.physical_scale == "TABLETOP_30_TO_60CM"
    assert appliance_spec.ergonomic_role == "ACTIVE_USER_OR_CONSUMER"


def test_classify_parody_prop_or_artifact() -> None:
    """Fantasy and parody artifacts classify as wielded handheld props with brand-scrubbed anchors."""
    analyzer = OfferingPhysicsAnalyzer(mock_mode=True)

    spec = analyzer.analyze(
        subject="Trapwarts",
        offering="Obsidian Runed Elder Wand",
        territory="Gothic Courtyard",
    )

    assert spec.archetype == "PARODY_PROP_OR_ARTIFACT"
    assert spec.physical_scale == "HANDHELD_10_TO_30CM"
    assert spec.ergonomic_role == "WIELDER_OF_ARTIFACT"
    assert "trapwarts" not in spec.canonical_anchor_spec.lower()


@pytest.mark.parametrize(
    ("subject", "offering", "expected_thermal"),
    [
        ("RoastCraft", "Steaming Hot Pour-Over Espresso Cup", "hot"),
        ("YuzuPop", "Iced Sparkling Citrus Botanical Can", "chilled"),
        ("AtelierVerre", "Botanical Glass Facial Serum Bottle", "ambient"),
    ],
)
def test_classify_handheld_cpg_thermal_states(
    subject: str,
    offering: str,
    expected_thermal: str,
) -> None:
    """Handheld CPG offerings accurately detect hot, chilled, and ambient thermal states."""
    analyzer = OfferingPhysicsAnalyzer(mock_mode=True)

    spec = analyzer.analyze(subject=subject, offering=offering)

    assert spec.archetype == "HANDHELD_CPG_OR_OBJECT"
    assert spec.physical_scale == "HANDHELD_10_TO_30CM"
    assert spec.ergonomic_role == "ACTIVE_USER_OR_CONSUMER"
    assert spec.thermal_state == expected_thermal


def test_three_act_causality_laws_and_forbidden_hallucinations() -> None:
    """Every physics spec populates integer-keyed 3-act causality laws (1, 2, 3) and forbidden hallucinations."""
    analyzer = OfferingPhysicsAnalyzer(mock_mode=True)
    spec = analyzer.analyze(subject="AtelierVerre", offering="Glass Facial Serum")

    assert set(spec.act_causality_laws.keys()) == {1, 2, 3}
    assert "empty-handed" in spec.act_causality_laws[1].lower()
    assert "100mm" in spec.act_causality_laws[2].lower()
    assert "macro" in spec.act_causality_laws[2].lower()
    assert (
        "motionless" in spec.act_causality_laws[3].lower()
        or "human-free" in spec.act_causality_laws[3].lower()
    )
    assert len(spec.forbidden_hallucinations) >= 4
    joined = " ".join(spec.forbidden_hallucinations).lower()
    assert "tabletop" in joined
    assert "condensation" in joined


def test_forbidden_hallucinations_decouples_archetype_and_all_thermal_states() -> None:
    """Archetype-specific and thermal-specific forbidden_hallucinations both populate for ambient, chilled, and hot."""
    analyzer = OfferingPhysicsAnalyzer(mock_mode=True)

    vehicle_ambient = analyzer.analyze("Velox Motors", "GT9 Stradale Coupe")
    assert vehicle_ambient.archetype == "OWNED_MOTOR_VEHICLE"
    assert vehicle_ambient.thermal_state == "ambient"
    veh_joined = " ".join(vehicle_ambient.forbidden_hallucinations).lower()
    assert "wheelbase" in veh_joined
    assert "dry room-temperature" in veh_joined

    chilled_cpg = analyzer.analyze("YuzuPop", "Iced Sparkling Citrus Botanical Can")
    assert chilled_cpg.thermal_state == "chilled"
    chilled_joined = " ".join(chilled_cpg.forbidden_hallucinations).lower()
    assert "chilled thermal physics" in chilled_joined
    assert "steam" in chilled_joined

    hot_delivery = analyzer.analyze("DashBite", "Hot Ramen Meal Delivery")
    assert hot_delivery.archetype == "FOOD_OR_DINING_DELIVERY"
    assert hot_delivery.thermal_state == "hot"
    hot_joined = " ".join(hot_delivery.forbidden_hallucinations).lower()
    assert "warm thermal physics" in hot_joined
    assert "frost" in hot_joined


def test_live_genai_json_parsing_and_invalid_enum_fallback_sanitization() -> None:
    """Live LLM responses parse valid JSON while sanitizing invalid enums and leaked brand names."""
    analyzer = OfferingPhysicsAnalyzer(mock_mode=True)
    analyzer.mock_mode = False

    class _StubModels:
        def __init__(self, response_text: str) -> None:
            self._text = response_text

        def generate_content(self, model: str, contents: str) -> SimpleNamespace:
            return SimpleNamespace(text=self._text)

    # Case 1: Valid LLM JSON enums override ambiguous offering title while still scrubbing brand tokens
    valid_payload = {
        "archetype": "COUNTERTOP_APPLIANCE",
        "physical_scale": "TABLETOP_30_TO_60CM",
        "ergonomic_role": "ACTIVE_USER_OR_CONSUMER",
        "surface_branding_mode": "SUBTLE_OEM_EMBLEM_ONLY",
        "thermal_state": "hot",
        "canonical_anchor_spec": "A brushed steel Kinetix X7precision thermal brewer on honed stone.",
        "act_causality_laws": {
            "1": "Act 1 empty-handed counter approach.",
            "2": "Act 2 tactile lever pull and 100mm zero-hand optical macro.",
            "3": "Act 3 quiet morning poise and solo motionless hero anchor.",
        },
        "forbidden_hallucinations": ["Never float virtual UI labels over steel body."],
    }
    analyzer._genai_client = SimpleNamespace(models=_StubModels(json.dumps(valid_payload)))
    valid_spec = analyzer.analyze(subject="Kinetix", offering="X700 Reserve")
    assert valid_spec.archetype == "COUNTERTOP_APPLIANCE"
    assert valid_spec.physical_scale == "TABLETOP_30_TO_60CM"
    assert valid_spec.thermal_state == "hot"
    assert "kinetix" not in valid_spec.canonical_anchor_spec.lower()

    # Case 2: LLM returns invalid enum values and leaks raw brand name in canonical_anchor_spec
    malformed_payload = {
        "archetype": "SPACE_SHIP_INVALID_ENUM",
        "physical_scale": "GALACTIC_SCALE",
        "ergonomic_role": "CAPTAIN_ON_BRIDGE",
        "surface_branding_mode": "NEON_BILLBOARD_EVERYWHERE",
        "thermal_state": "lukewarm_invalid",
        "canonical_anchor_spec": "A sleek Velox GT9 aerodynamic metallic coupe body with sculpted fenders.",
        "act_causality_laws": {"1": "Act 1 custom empty-handed setup."},
        "forbidden_hallucinations": [],
    }
    raw_fenced = f"```json\n{json.dumps(malformed_payload)}\n```"
    analyzer._genai_client = SimpleNamespace(models=_StubModels(raw_fenced))

    spec = analyzer.analyze(subject="Velox Motors", offering="GT9 Coupe")

    # Invalid enums fall back to deterministic vehicle classification
    assert spec.archetype == "OWNED_MOTOR_VEHICLE"
    assert spec.physical_scale == "FULL_SCALE_VEHICLE_5M"
    assert spec.ergonomic_role == "DRIVER_AT_WHEEL"
    assert spec.surface_branding_mode == "SUBTLE_OEM_EMBLEM_ONLY"
    assert spec.thermal_state == "ambient"
    # Leaked brand strings are scrubbed from canonical_anchor_spec
    assert "velox" not in spec.canonical_anchor_spec.lower()
    assert "gt9" not in spec.canonical_anchor_spec.lower()
    # Missing acts 2 & 3 and empty hallucinations are populated from fallback
    assert set(spec.act_causality_laws.keys()) == {1, 2, 3}
    assert spec.act_causality_laws[1] == "Act 1 custom empty-handed setup."
    assert len(spec.forbidden_hallucinations) >= 4

    # Case 3: LLM raises exception -> falls back cleanly
    class _FailingModels:
        def generate_content(self, model: str, contents: str) -> SimpleNamespace:
            raise RuntimeError("transient network error")

    analyzer._genai_client = SimpleNamespace(models=_FailingModels())
    fallback_spec = analyzer.analyze(subject="Velox Motors", offering="GT9 Coupe")
    assert fallback_spec.archetype == "OWNED_MOTOR_VEHICLE"


def test_unicode_brand_scrubbing_and_image_tag_protection() -> None:
    """Unicode accented brand names scrub cleanly without fragmenting, and @ImageN tags stay intact."""
    raw = "A sleek Café Kitsuné ceramic cup beside L'Oréal botanical glass serum."
    scrubbed_1 = scrub_offering_trademarks(raw, subject="Café Kitsuné", offering="L'Oréal Serum")
    low_1 = scrubbed_1.lower()
    assert "café" not in low_1
    assert "kitsuné" not in low_1
    assert "l'oréal" not in low_1
    assert " sleek é " not in f" {low_1} "
    assert " al " not in f" {low_1} "

    # Offering containing 'Image4' must scrub standalone 'Image4' while preserving '@Image4'
    img_text = "Hero camera (@Image4) captures crisp Image4 OptiLens studio light."
    scrubbed_2 = scrub_offering_trademarks(
        img_text,
        subject="OptiLens",
        offering="Image4 Cinema Camera",
    )
    assert "(@Image4)" in scrubbed_2
    assert "optilens" not in scrubbed_2.lower()
    assert "crisp studio light" in scrubbed_2.lower()


def test_es_plural_luxury_hardgood_cues_and_null_json_guards() -> None:
    """Pre-compiled cue regexes match -es plurals ('Watches') and live JSON guards against null/empty items."""
    analyzer = OfferingPhysicsAnalyzer(mock_mode=True)
    watches_spec = analyzer.analyze(subject="Helvetia", offering="Swiss Dive Watches")
    assert watches_spec.archetype == "HANDHELD_CPG_OR_OBJECT"
    assert watches_spec.surface_branding_mode == "SUBTLE_OEM_EMBLEM_ONLY"
    assert "316l steel" in watches_spec.canonical_anchor_spec.lower()

    # Live mode JSON with null values and brand-only forbidden_hallucinations entry
    analyzer.mock_mode = False
    null_payload = {
        "archetype": None,
        "canonical_anchor_spec": None,
        "act_causality_laws": {"1": None, "2": "Velox", "3": None},
        "forbidden_hallucinations": [None, "Velox"],
    }
    analyzer._genai_client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda model, contents, **kwargs: SimpleNamespace(
                text=json.dumps(null_payload)
            )
        )
    )
    guarded_spec = analyzer.analyze(subject="Velox", offering="GT9 Coupe")
    assert guarded_spec.archetype == "OWNED_MOTOR_VEHICLE"
    assert "none" not in guarded_spec.canonical_anchor_spec.lower()
    assert all(item and item.lower() != "none" for item in guarded_spec.forbidden_hallucinations)
    assert len(guarded_spec.forbidden_hallucinations) >= 4
