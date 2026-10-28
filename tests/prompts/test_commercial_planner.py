from __future__ import annotations

import json
import re
from types import SimpleNamespace

from pydantic import ValidationError
import pytest

from omnimash.agent.adk_pipeline import preflight_lint_and_repair
from omnimash.prompts.commercial_planner import (
    DualLayerIdentityAbstractor,
    Palette603010,
    SoundstageCommercialPlan,
    SoundstageDiscoveryEngine,
    SoundstageDiscoveryResult,
    SoundstageThreeActPlanner,
)
from omnimash.prompts.offering_physics import OfferingPhysicsAnalyzer
from omnimash.prompts.preflight_linter import PreFlightGatekeeper


HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def test_palette_60_30_10_validates_hex_and_builds_directive() -> None:
    """Palette603010 validates #RRGGBB hex codes and formats explicit 60/30/10 directive."""
    palette = Palette603010(
        primary_hex="#1b263b",
        primary_name="Midnight Slate",
        secondary_hex="#e09f3e",
        secondary_name="Warm Ochre",
        neutral_hex="#f4f1ea",
        neutral_name="Alabaster Stone",
    )

    assert HEX_RE.match(palette.primary_hex)
    assert HEX_RE.match(palette.secondary_hex)
    assert HEX_RE.match(palette.neutral_hex)
    assert "60%" in palette.production_design_directive
    assert "30%" in palette.production_design_directive
    assert "10%" in palette.production_design_directive

    with pytest.raises(ValidationError):
        Palette603010(
            primary_hex="invalid-hex",
            primary_name="Bad",
            secondary_hex="#E09F3E",
            secondary_name="Ochre",
            neutral_hex="#F4F1EA",
            neutral_name="Stone",
        )


def test_dual_layer_identity_abstractor_preserves_display_and_scrubs_omni_safe_fields() -> None:
    """Display layer retains exact brand/offering while Omni-safe layer scrubs trademarks and two-word names."""
    physics = OfferingPhysicsAnalyzer(mock_mode=True).analyze(
        subject="Velox Motors",
        offering="GT9 Stradale Coupe",
        territory="Tokyo · Shibuya",
    )
    palette = Palette603010(
        primary_hex="#1A1F2C",
        primary_name="Obsidian Asphalt",
        secondary_hex="#C85A32",
        secondary_name="Terracotta Suede",
        neutral_hex="#ECE8E1",
        neutral_name="Chalk Travertine",
    )

    identity = DualLayerIdentityAbstractor.abstract(
        subject="Velox Motors",
        offering="GT9 Stradale Coupe",
        physics=physics,
        palette=palette,
        lead_name="Gordon Ramsay",
        lead_wardrobe="Tailored jacket over knit crew",
        tagline="Precision shaped by midnight.",
    )

    # Display layer stays 100% verbatim for UI & FFmpeg end-card
    assert identity.display_subject == "Velox Motors"
    assert identity.display_offering == "GT9 Stradale Coupe"
    assert identity.display_tagline == "Precision shaped by midnight."

    # Omni-safe offering descriptor contains zero raw brand tokens
    lower_offering_desc = identity.omni_safe_offering_descriptor.lower()
    assert "velox" not in lower_offering_desc
    assert "gt9" not in lower_offering_desc
    assert "stradale" not in lower_offering_desc

    # Omni-safe cast handle is a single stylized word, never a two-word real human name
    assert " " not in identity.omni_safe_cast_handle.strip()
    assert len(identity.omni_safe_cast_handle.strip()) >= 3
    assert "gordon" not in identity.omni_safe_cast_handle.lower()
    assert "ramsay" not in identity.omni_safe_cast_handle.lower()

    # Omni-safe cast description anchors to secondary_hex and scrubs real name + brand
    lower_cast_desc = identity.omni_safe_cast_description.lower()
    assert "#c85a32" in lower_cast_desc
    assert "gordon" not in lower_cast_desc
    assert "ramsay" not in lower_cast_desc
    assert "velox" not in lower_cast_desc

    # Arbitrary two-word real human name is also converted into a single-word handle
    identity_two_word = DualLayerIdentityAbstractor.abstract(
        subject="Chronos Geneve",
        offering="Mariner Steel Chronograph",
        physics=OfferingPhysicsAnalyzer(mock_mode=True).analyze(
            "Chronos Geneve", "Mariner Steel Chronograph"
        ),
        palette=palette,
        lead_name="Marcus Vance",
    )
    assert " " not in identity_two_word.omni_safe_cast_handle.strip()
    assert "marcus" not in identity_two_word.omni_safe_cast_handle.lower()
    assert "vance" not in identity_two_word.omni_safe_cast_handle.lower()
    assert "marcus vance" not in identity_two_word.omni_safe_cast_description.lower()
    assert "chronos" not in identity_two_word.omni_safe_offering_descriptor.lower()
    assert "mariner" not in identity_two_word.omni_safe_offering_descriptor.lower()


def test_soundstage_discovery_engine_for_brand_and_parody_inputs() -> None:
    """SoundstageDiscoveryEngine returns complete 10-step intake candidates for brands and parodies."""
    engine = SoundstageDiscoveryEngine(mock_mode=True)

    brand_res = engine.discover(
        subject="Maison Verve",
        offering_hint="Sparkling Yuzu Aperitif Can",
        territory_hint="Tokyo · Shibuya",
    )
    assert isinstance(brand_res, SoundstageDiscoveryResult)
    assert brand_res.subject == "Maison Verve"
    assert len(brand_res.suggested_offerings) >= 3
    for item in brand_res.suggested_offerings:
        assert {"name", "category", "description"} <= set(item.keys())
    assert len(brand_res.suggested_territories) >= 3
    assert HEX_RE.match(brand_res.palette.primary_hex)
    assert HEX_RE.match(brand_res.palette.secondary_hex)
    assert HEX_RE.match(brand_res.palette.neutral_hex)
    assert len(brand_res.cultural_moments) >= 3
    assert len(brand_res.spoken_languages) >= 3
    for lang in brand_res.spoken_languages:
        assert {"code", "label", "vocal_cadence"} <= set(lang.keys())
    assert brand_res.tagline.strip()
    assert brand_res.emblem_prompt.strip()
    assert brand_res.packshot_prompt.strip()
    assert brand_res.physics.archetype == "HANDHELD_CPG_OR_OBJECT"
    assert brand_res.physics.thermal_state == "chilled"

    parody_res = engine.discover(
        subject="Trapwarts Alchemy Guild",
        offering_hint="Obsidian Runed Elder Wand",
    )
    assert parody_res.physics.archetype == "PARODY_PROP_OR_ARTIFACT"
    assert "trapwarts" not in parody_res.identity.omni_safe_offering_descriptor.lower()

    # Live GenAI enrichment overrides tagline & palette when valid JSON is returned
    live_engine = SoundstageDiscoveryEngine(mock_mode=True)
    live_engine.mock_mode = False
    enriched_payload = {
        "tagline": "Quiet geometry in every drop.",
        "palette": {
            "primary_hex": "#122334",
            "primary_name": "Harbor Nocturne",
            "secondary_hex": "#D4883A",
            "secondary_name": "Amber Suede",
            "neutral_hex": "#F3F0E8",
            "neutral_name": "Limestone Mist",
        },
    }
    live_engine._genai_client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda model, contents: SimpleNamespace(
                text=json.dumps(enriched_payload)
            )
        )
    )
    enriched_res = live_engine.discover(
        subject="Atelier Verre",
        offering_hint="Botanical Glass Facial Serum",
    )
    assert enriched_res.tagline == "Quiet geometry in every drop."
    assert enriched_res.palette.primary_hex == "#122334"


def test_soundstage_three_act_planner_builds_3_acts_9_boards_and_canonical_prompts() -> None:
    """SoundstageThreeActPlanner produces 3 acts, 9 tiles (1.3/2.2/3.3 person-free), and lint-clean 4-block prompts."""
    planner = SoundstageThreeActPlanner(mock_mode=True)

    plan = planner.build_plan(
        subject="Velox Motors",
        offering="GT9 Stradale Coupe",
        territory="Tokyo · Shibuya",
        moment="Midnight Rain Expressway Pulse",
        language="Japanese",
        tagline="Precision shaped by midnight.",
    )

    assert isinstance(plan, SoundstageCommercialPlan)
    assert plan.subject == "Velox Motors"
    assert plan.offering == "GT9 Stradale Coupe"
    assert plan.identity.display_subject == "Velox Motors"
    assert plan.identity.display_offering == "GT9 Stradale Coupe"
    assert plan.hero_offering_role.image_role == "Prop Reference"

    # Timed full VO script
    assert "[0:00]" in plan.voiceover_full_script
    assert "[0:10]" in plan.voiceover_full_script
    assert "[0:20]" in plan.voiceover_full_script

    # Exactly 3 acts and 9 flattened boards
    assert len(plan.acts) == 3
    assert len(plan.boards) == 9
    assert [b.shot_id for b in plan.boards] == [
        "1.1",
        "1.2",
        "1.3",
        "2.1",
        "2.2",
        "2.3",
        "3.1",
        "3.2",
        "3.3",
    ]

    boards_by_id = {b.shot_id: b for b in plan.boards}
    for macro_or_packshot_id in ("1.3", "2.2", "3.3"):
        assert boards_by_id[macro_or_packshot_id].has_person is False
    for human_shot_id in ("1.1", "1.2", "2.1", "2.3", "3.1", "3.2"):
        assert boards_by_id[human_shot_id].has_person is True

    expected_windows = {1: "0:00-0:10", 2: "0:10-0:20", 3: "0:20-0:30"}
    for act in plan.acts:
        assert act.time_window == expected_windows[act.act_number]
        assert len(act.shots) == 3
        prompt = act.compiled_omni_prompt

        # Canonical 4-Block Meta-Prompt sections
        assert "### INPUT ROLES & REFERENCES" in prompt
        assert "### CHARACTER PROFILES" in prompt
        assert "### SCENE INSTRUCTIONS" in prompt
        assert "### TIMELINE" in prompt
        assert "No text, no subtitles on screen." in prompt

        # Zero raw brand tokens in Omni Flash prompt
        lower_prompt = prompt.lower()
        assert "velox" not in lower_prompt
        assert "gt9" not in lower_prompt
        assert "stradale" not in lower_prompt

        # Re-linting compiled prompt passes PreFlightGatekeeper cleanly with zero remaining violations
        lint_res = PreFlightGatekeeper.lint_and_repair(
            prompt,
            has_dialogue=bool(act.voiceover_line),
            offering_physics=plan.physics,
            palette_60_30_10=plan.palette,
            act_number=act.act_number,
        )
        assert lint_res.is_valid is True
        assert lint_res.violations == []


def test_repoint_plan_for_variation_across_place_cast_and_offering_axes() -> None:
    """repoint_plan_for_variation updates only the target variation axis while locking unchanged axes."""
    planner = SoundstageThreeActPlanner(mock_mode=True)
    base_plan = planner.build_plan(
        subject="Atelier Verre",
        offering="Botanical Glass Facial Serum",
        territory="Paris · Le Marais",
        moment="Morning Ritual Light",
        language="French",
        tagline="Pure light on skin.",
    )

    # 1. Place variation
    place_plan = planner.repoint_plan_for_variation(
        existing_plan=base_plan,
        axis="place",
        new_value="Kyoto · Higashiyama",
    )
    assert place_plan.territory.place_name == "Kyoto · Higashiyama"
    assert place_plan.offering == base_plan.offering
    assert place_plan.identity.omni_safe_cast_handle == base_plan.identity.omni_safe_cast_handle

    # 2. Cast variation
    cast_plan = planner.repoint_plan_for_variation(
        existing_plan=base_plan,
        axis="cast",
        new_value="Master Botanist",
    )
    assert cast_plan.identity.omni_safe_cast_handle == "Botanist"
    assert cast_plan.territory.place_name == base_plan.territory.place_name
    assert cast_plan.offering == base_plan.offering

    # 3. Offering variation
    offering_plan = planner.repoint_plan_for_variation(
        existing_plan=base_plan,
        axis="offering",
        new_value="Iced Yuzu Sparkling Botanical Can",
    )
    assert offering_plan.offering == "Iced Yuzu Sparkling Botanical Can"
    assert offering_plan.physics.thermal_state == "chilled"
    assert offering_plan.territory.place_name == base_plan.territory.place_name


def test_preflight_gatekeeper_pass6_palette_causality_and_thermal_repairs() -> None:
    """PreFlightGatekeeper Pass 6 preserves backward compatibility and enforces 60/30/10, causality, and thermal laws."""
    raw_prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "None.\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (Curator): Calm poised presence.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: In a single continuous shot. No scene cuts. 35mm cinema lens.\n"
        "Environment: Sunlit limestone gallery.\n"
        "Audio: instrumental ambient piano.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Curator walks past display plinth.\n"
        "[3-6s] Action: Close view of dry glass serum bottle covered in ice-cold condensation and frosty droplets while steaming hot.\n"
        "[6-10s] Action: Quiet atmospheric hold."
    )

    # Backward compatibility when offering_physics and palette_60_30_10 are omitted
    unchanged_text, no_violations = PreFlightGatekeeper.repair_offering_physics_and_causality(
        raw_prompt
    )
    assert unchanged_text == raw_prompt
    assert no_violations == []

    physics = OfferingPhysicsAnalyzer(mock_mode=True).analyze(
        subject="Atelier Verre",
        offering="Dry Botanical Glass Facial Serum",
    )
    assert physics.thermal_state == "ambient"

    palette = Palette603010(
        primary_hex="#2B303A",
        primary_name="Charcoal Limestone",
        secondary_hex="#B87D4B",
        secondary_name="Sienna Linen",
        neutral_hex="#F5F2EB",
        neutral_name="Warm Chalk",
    )

    lint_result = PreFlightGatekeeper.lint_and_repair(
        raw_prompt,
        offering_physics=physics,
        palette_60_30_10=palette,
        act_number=1,
    )

    rule_ids = {v.rule_id for v in lint_result.violations}
    assert "PALETTE_60_30_10_LOCK" in rule_ids
    assert "TEMPORAL_CAUSALITY_GATE" in rule_ids
    assert "OFFERING_THERMAL_PHYSICS" in rule_ids

    repaired = lint_result.repaired_prompt
    assert "60%" in repaired and "30%" in repaired and "10%" in repaired
    assert physics.act_causality_laws[1] in repaired
    assert "ice-cold condensation" not in repaired.lower()
    assert "frosty droplets" not in repaired.lower()
    assert "steaming hot" not in repaired.lower()

    # Idempotency check & ADK tool dict-payload compatibility
    tool_res = preflight_lint_and_repair(
        prompt=repaired,
        offering_physics=physics.model_dump(),
        palette_60_30_10=palette.model_dump(),
        act_number=1,
    )
    assert tool_res["is_valid"] is True
    assert tool_res["violations"] == []
