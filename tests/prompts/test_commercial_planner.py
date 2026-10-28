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

    # Live GenAI enrichment overrides tagline, palette, offerings, territories, and cultural moments
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
        "suggested_offerings": [
            {
                "name": "Nocturne Glass Elixir",
                "category": "Botanical Reserve",
                "description": "Cold-pressed midnight botanical facial oil in smoked glass.",
            },
            {
                "name": "Dawn Mineral Mist",
                "category": "Hydration Veil",
                "description": "Micro-atomized alpine mineral tonic.",
            },
            {
                "name": "Sculpted Gua Sha Stone",
                "category": "Tactile Ritual Tool",
                "description": "Hand-honed basalt contour tool.",
            },
        ],
        "suggested_territories": [
            {
                "place_name": "Seoul · Hannam",
                "temperature_c": 13,
                "condition": "Crisp autumn evening · Subtle river mist",
                "lighting_directive": "40mm anamorphic prime, warm gallery spill over slate concrete",
                "cultural_pulse": "Architectural skincare ateliers and nocturnal design calm",
            },
            {
                "place_name": "Copenhagen · Bredgade",
                "temperature_c": 11,
                "condition": "Pale Nordic morning · Diffused harbor light",
                "lighting_directive": "50mm prime, soft overcast skylight across pale oak",
                "cultural_pulse": "Tactile minimalism and quiet morning ritual",
            },
            {
                "place_name": "Zurich · Seefeld",
                "temperature_c": 14,
                "condition": "Clear alpine twilight · Crisp lake reflections",
                "lighting_directive": "35mm cinema prime, cool twilight bounce against warm stone",
                "cultural_pulse": "Precision formulation and serene lakeside architecture",
            },
        ],
        "cultural_moments": [
            {
                "title": "Evening Gallery Unwind",
                "description": "Stepping out of city velocity into a quiet architectural sanctuary.",
            },
            {
                "title": "First-Light Studio Reset",
                "description": "Unhurried morning sensory calibration before the studio opens.",
            },
            {
                "title": "Rain-Glass Pause",
                "description": "Watching dusk rain trace tall gallery windows in stillness.",
            },
        ],
    }
    live_engine._genai_client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda model, contents, **kwargs: SimpleNamespace(
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
    assert enriched_res.suggested_offerings[0]["name"] == "Nocturne Glass Elixir"
    assert enriched_res.suggested_territories[0].place_name == "Seoul · Hannam"
    assert enriched_res.cultural_moments[0]["title"] == "Evening Gallery Unwind"


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
    expected_first_shots = {1: "1.1", 2: "2.1", 3: "3.1"}
    expected_last_shots = {1: "1.3", 2: "2.3", 3: "3.3"}
    for act in plan.acts:
        assert act.time_window == expected_windows[act.act_number]
        assert act.first_frame_shot_id == expected_first_shots[act.act_number]
        assert act.last_frame_shot_id == expected_last_shots[act.act_number]
        assert act.first_frame_tag == "<FIRST_FRAME>"
        assert act.last_frame_tag == "<LAST_FRAME>"
        assert act.reference_tags == ["<IMAGE_REF_0>", "<IMAGE_REF_1>"]
        assert len(act.shots) == 3
        prompt = act.compiled_omni_prompt

        # Canonical 4-Block Meta-Prompt sections + dual-keyframe & reference anchoring
        assert "### INPUT ROLES & REFERENCES" in prompt
        assert "[# Sources <FIRST_FRAME>@KeyframeSeed <LAST_FRAME>@EndKeyframe]" in prompt
        assert "[# References <IMAGE_REF_0>@Image3, <IMAGE_REF_1>@Image4]" in prompt
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
    """repoint_plan_for_variation updates only the target variation axis while locking weather and palette names."""
    planner = SoundstageThreeActPlanner(mock_mode=True)
    base_plan = planner.build_plan(
        subject="Atelier Verre",
        offering="Botanical Glass Facial Serum",
        territory="Paris · Le Marais",
        weather_condition="Monsoon twilight drizzle · Mirror cobblestone reflections",
        moment="Morning Ritual Light",
        language="French",
        tagline="Pure light on skin.",
    )
    assert (
        base_plan.territory.condition == "Monsoon twilight drizzle · Mirror cobblestone reflections"
    )

    # 1. Place variation updates territory while locking offering, cast, and exact Palette603010 names + hexes
    place_plan = planner.repoint_plan_for_variation(
        existing_plan=base_plan,
        axis="place",
        new_value="Kyoto · Higashiyama",
    )
    assert place_plan.territory.place_name == "Kyoto · Higashiyama"
    assert place_plan.offering == base_plan.offering
    assert place_plan.identity.omni_safe_cast_handle == base_plan.identity.omni_safe_cast_handle
    assert place_plan.palette == base_plan.palette

    # 2. Cast variation preserves custom territory weather/lighting AND locked Palette603010
    cast_plan = planner.repoint_plan_for_variation(
        existing_plan=base_plan,
        axis="cast",
        new_value="Master Botanist",
    )
    assert cast_plan.identity.omni_safe_cast_handle == "Botanist"
    assert cast_plan.territory == base_plan.territory
    assert cast_plan.offering == base_plan.offering
    assert cast_plan.palette == base_plan.palette

    # 3. Offering variation (even across a different archetype!) preserves custom territory AND locked Palette603010 names
    offering_plan = planner.repoint_plan_for_variation(
        existing_plan=base_plan,
        axis="offering",
        new_value="Obsidian Runed Elder Wand",
    )
    assert offering_plan.offering == "Obsidian Runed Elder Wand"
    assert offering_plan.physics.archetype == "PARODY_PROP_OR_ARTIFACT"
    assert offering_plan.territory == base_plan.territory
    assert offering_plan.palette == base_plan.palette


def test_three_act_planner_live_genai_enrichment_and_trademark_scrubbing() -> None:
    """Live _genai_client in SoundstageThreeActPlanner enriches brief, localized VO, and 9 beat actions safely."""
    planner = SoundstageThreeActPlanner(mock_mode=True)
    planner.mock_mode = False

    captured_kwargs: dict[str, object] = {}

    def _stub_generate_content(model: str, contents: str, **kwargs: object) -> SimpleNamespace:
        captured_kwargs.update(kwargs)
        payload = {
            "brief": {
                "title": "Nocturnal Precision Study",
                "objective": "Showcase nocturnal grand touring serenity across rain-slicked Shibuya avenues.",
                "audience": "Architectural automotive collectors.",
                "key_tension": "Urban neon chaos versus acoustic cockpit stillness.",
                "proposition": "Precision shaped by midnight.",
                "sonic_and_visual_direction": "Anamorphic 35mm twilight minimalism with Japanese editorial VO.",
            },
            "voiceover_lines": {
                "1": "静寂が夜の街を研ぎ澄ます。",
                "2": "ひと触れで、真の工芸が目覚める。",
                "3": "余韻だけが、静かに走り続ける。",
            },
            "beat_actions": {
                "1.1": "Vanguard (@Image3) walks empty-handed past rain-washed Shibuya stone columns.",
                "1.2": "Medium tracking portrait of Vanguard (@Image3) pausing empty-handed under amber neon spill.",
                "1.3": "Human-free architectural macro of rain droplets shimmering on dark basalt stone.",
                "2.1": "Vanguard (@Image3) grips the sculpted steering wheel inside Velox GT9 Stradale (@Image4).",
                "2.2": "100mm zero-hand optical macro across Velox GT9 Stradale (@Image4) brushed alloy contours.",
                "2.3": "Close-up of Vanguard (@Image3) exhaling in quiet recognition.",
                "3.1": "Fluid Steadicam glide as Vanguard (@Image3) stands composed beside the twilight avenue.",
                "3.2": "Low-angle architectural pan toward the illuminated travertine display stage.",
                "3.3": "Motionless human-free solo hero packshot of Velox GT9 Stradale (@Image4) on neutral plinth.",
            },
        }
        return SimpleNamespace(text=json.dumps(payload))

    planner._genai_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=_stub_generate_content)
    )

    plan = planner.build_plan(
        subject="Velox Motors",
        offering="GT9 Stradale Coupe",
        territory="Tokyo · Shibuya",
        language="Japanese",
    )

    assert captured_kwargs.get("config") == {"response_mime_type": "application/json"}
    assert plan.brief.title == "Nocturnal Precision Study"
    assert "静寂が夜の街を研ぎ澄ます" in plan.voiceover_full_script
    assert plan.acts[0].voiceover_line == "静寂が夜の街を研ぎ澄ます。"
    # Leaked brand strings in LLM beat_actions must be scrubbed from board actions & compiled Omni prompts
    for act in plan.acts:
        low = act.compiled_omni_prompt.lower()
        assert "velox" not in low
        assert "gt9" not in low
        assert "stradale" not in low
        relint = PreFlightGatekeeper.lint_and_repair(
            act.compiled_omni_prompt,
            has_dialogue=bool(act.voiceover_line),
            offering_physics=plan.physics,
            palette_60_30_10=plan.palette,
            act_number=act.act_number,
        )
        assert relint.is_valid is True
        assert relint.violations == []


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


def test_preflight_pass6_chilled_hot_no_text_and_hex_verification() -> None:
    """Pass 6 scrubs steam on chilled offerings, frost on hot offerings, enforces clean frame no-text, and verifies hexes."""
    analyzer = OfferingPhysicsAnalyzer(mock_mode=True)

    # 1. Chilled offering must scrub steam & hot-vapor hallucinations
    chilled_physics = analyzer.analyze("YuzuPop", "Iced Sparkling Citrus Botanical Can")
    assert chilled_physics.thermal_state == "chilled"
    chilled_prompt = (
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: 35mm prime. No text, no subtitles on screen.\n\n"
        "### TIMELINE\n"
        "[0-5s] Action: Macro of chilled can steaming hot with billowing steam and steam rising."
    )
    chilled_res = PreFlightGatekeeper.lint_and_repair(
        chilled_prompt,
        offering_physics=chilled_physics,
    )
    assert any(v.rule_id == "OFFERING_THERMAL_PHYSICS" for v in chilled_res.violations)
    assert "steaming hot" not in chilled_res.repaired_prompt.lower()
    assert "billowing steam" not in chilled_res.repaired_prompt.lower()
    assert "steam rising" not in chilled_res.repaired_prompt.lower()

    # 2. Hot offering must scrub frost & ice-condensation hallucinations
    hot_physics = analyzer.analyze("RoastCraft", "Steaming Hot Pour-Over Espresso Cup")
    assert hot_physics.thermal_state == "hot"
    hot_prompt = (
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: 50mm prime. No text, no subtitles on screen.\n\n"
        "### TIMELINE\n"
        "[0-5s] Action: Macro of espresso cup with ice-cold condensation, frosty droplets, and chilled condensation."
    )
    hot_res = PreFlightGatekeeper.lint_and_repair(
        hot_prompt,
        offering_physics=hot_physics,
    )
    assert any(v.rule_id == "OFFERING_THERMAL_PHYSICS" for v in hot_res.violations)
    assert "ice-cold condensation" not in hot_res.repaired_prompt.lower()
    assert "frosty droplets" not in hot_res.repaired_prompt.lower()
    assert "chilled condensation" not in hot_res.repaired_prompt.lower()

    # 3. Clean-frame 'No text, no subtitles on screen.' enforced when any Mode 5 arg is passed, no-op when all None
    bare_prompt = "### SCENE INSTRUCTIONS\nCamera & Lighting: 35mm cinema lens.\n### TIMELINE\n[0-5s] Action: Walk."
    noop_res = PreFlightGatekeeper.lint_and_repair(bare_prompt)
    assert "no text, no subtitles on screen" not in noop_res.repaired_prompt.lower()

    act_only_res = PreFlightGatekeeper.lint_and_repair(bare_prompt, act_number=1)
    assert "no text, no subtitles on screen." in act_only_res.repaired_prompt.lower()
    assert len(act_only_res.violations) == 1

    # 4. PALETTE_60_30_10_LOCK verifies actual hex codes (not merely 60%/30%/10% percentages)
    missing_hex_prompt = (
        "### SCENE INSTRUCTIONS\n"
        "- Production Design: 60% dark walls / 30% warm jacket / 10% light stone.\n"
        "- Clean Frame Directive: No text, no subtitles on screen.\n\n"
        "### TIMELINE\n"
        "[0-5s] Action: Quiet hold."
    )
    dict_palette = {
        "neutral_hex_60": "#1D242B",
        "secondary_hex_30": "#C27D44",
        "primary_hex_10": "#F3EFE8",
    }
    hex_res = PreFlightGatekeeper.lint_and_repair(
        missing_hex_prompt,
        palette_60_30_10=dict_palette,
    )
    assert any(v.rule_id == "PALETTE_60_30_10_LOCK" for v in hex_res.violations)
    for expected_hex in ("#1d242b", "#c27d44", "#f3efe8"):
        assert expected_hex in hex_res.repaired_prompt.lower()

    # Re-running is idempotent with zero violations
    hex_relint = PreFlightGatekeeper.lint_and_repair(
        hex_res.repaired_prompt,
        palette_60_30_10=dict_palette,
    )
    assert hex_relint.is_valid is True
    assert hex_relint.violations == []
