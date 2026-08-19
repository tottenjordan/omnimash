from omnimash.prompts.compiler import (
    CumulativeShotState,
    compile_journey3_shot_prompt,
)


def test_cumulative_state_tracking_in_journey3_prompt():
    state = CumulativeShotState()
    state.add_character_state("Snape", "blindfolded with black cloth")
    state.add_scene_state("underground potion studio lit by blue neon candles")

    prompt = compile_journey3_shot_prompt(
        shot_number=3,
        action_directive="Snape reaches carefully for the sparkling beaker",
        cumulative_state=state,
        aspect_ratio="9:16",
    )

    assert "Cumulative Shot State:" in prompt
    assert "Snape: blindfolded with black cloth" in prompt
    assert "- Aspect Ratio: 9:16" in prompt


def test_cumulative_shot_state_manipulation():
    state = CumulativeShotState()
    state.add_character_state("Snape", "blindfolded with black cloth")
    state.add_character_state("Snape", "holding glowing wand")
    state.add_scene_state("dark laboratory")

    formatted = state.format_cumulative_state_block()
    assert "Character States:" in formatted
    assert "- Snape: blindfolded with black cloth" in formatted
    assert "- Snape: holding glowing wand" in formatted
    assert "Scene States:" in formatted
    assert "- dark laboratory" in formatted

    # Test removing a state
    state.remove_character_state("Snape", "blindfolded with black cloth")
    formatted_after_remove = state.format_cumulative_state_block()
    assert "blindfolded with black cloth" not in formatted_after_remove
    assert "- Snape: holding glowing wand" in formatted_after_remove

    # Removing non-existent state should not fail
    state.remove_character_state("Snape", "non_existent_state")
    state.remove_character_state("NonExistentCharacter", "some_state")


def test_compile_journey3_shot_prompt_full():
    prompt = compile_journey3_shot_prompt(
        shot_number=1,
        action_directive="Harry Potter casts Lumos",
        aspect_ratio="16:9",
        character_roster="Role A - Harry Potter",
        timeline_dialogue='Harry: "Lumos Maxima!"',
        enable_sanitization=True,
    )

    assert "### INPUT ROLES & REFERENCES" in prompt
    assert "### CHARACTER PROFILES" in prompt
    assert "### SCENE INSTRUCTIONS" in prompt
    assert "### TIMELINE" in prompt

    assert "Spectacled Wizard Bruv" in prompt  # Sanitized Harry Potter
    assert "- Shot Number: 1" in prompt
    assert "- Aspect Ratio: 16:9" in prompt
