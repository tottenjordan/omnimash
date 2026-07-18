from omnimash.prompts.taxonomy import PromptTaxonomyEngine, StylePreset


def test_compose_blend_prompt():
    engine = PromptTaxonomyEngine()
    composed = engine.build_initial_prompt(
        base_character="Severus Snape from Harry Potter",
        style_preset=StylePreset.NINETIES_RAP_VIDEO,
        custom_instructions="rapping about potions in a dungeon with green neon lights",
    )
    assert "Severus Snape" in composed
    assert "90s fisheye lens" in composed or "boom-bap" in composed
    assert "720p 10-second cinematic" in composed


def test_taxonomy_engine_uses_prompt_compiler():
    engine = PromptTaxonomyEngine()
    composed = engine.build_initial_prompt(
        base_character="Severus Snape",
        style_preset=StylePreset.NINETIES_RAP_VIDEO,
        custom_instructions="rapping in dungeon",
    )
    assert "[SUBJECT ANCHOR]:" in composed
    assert "gaunt man with a hooked nose" in composed
