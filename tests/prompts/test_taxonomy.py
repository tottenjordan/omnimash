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


def test_taxonomy_engine_uses_lock_and_isolate_delta_compiler():
    engine = PromptTaxonomyEngine()
    delta_prompt = engine.build_delta_prompt(
        current_clip_desc="Snape rap turn 1",
        delta_instruction="make his chain bigger",
    )
    assert "[PRESERVATION LOCK]:" in delta_prompt
    assert "Maintain exact subject face" in delta_prompt
    assert "[ISOLATED DIFF]:" in delta_prompt
    assert "make his chain bigger" in delta_prompt
