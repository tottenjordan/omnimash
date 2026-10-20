from omnimash.prompts.character_roles import CharacterRole
from omnimash.prompts.voice import (
    apply_conversational_voice_edits,
    enrich_timeline_dialogue_speakers,
    ensure_character_voice_style,
)


def test_ensure_character_voice_style_preserves_custom():
    char = CharacterRole(
        role_id="Role A",
        name="Custom Speaker",
        description="Speaker with custom voice",
        voice_style="Fast Brooklyn street slang with gritty inflection",
    )
    assert ensure_character_voice_style(char) == "Fast Brooklyn street slang with gritty inflection"


def test_ensure_character_voice_style_infers_from_keywords():
    wizard = CharacterRole(
        role_id="Role A",
        name="Severus Snape",
        description="Gaunt potion master",
    )
    assert (
        ensure_character_voice_style(wizard)
        == "Pompous Queen's English British drawl with theatrical cadence"
    )

    rapper = CharacterRole(
        role_id="Role B",
        name="Yo Totti",
        description="Atlanta trap star",
    )
    assert (
        ensure_character_voice_style(rapper)
        == "Smooth Atlanta rap flow with distinct rhythmic trap cadence"
    )

    chef = CharacterRole(
        role_id="Role C",
        name="Chef Gordon",
        description="Head restaurant chef",
    )
    assert (
        ensure_character_voice_style(chef)
        == "Fiery intense British accent with rapid explosive delivery"
    )


def test_apply_conversational_voice_edits():
    char_a = CharacterRole(role_id="Role A", name="Wizard", description="A magical wizard")
    char_b = CharacterRole(role_id="Role B", name="Giant", description="A gentle giant")
    characters = [char_a, char_b]

    directive = (
        "Make Role A have a Scottish brogue accent and give Role B a deep Jamaican patois flow"
    )
    apply_conversational_voice_edits(directive, characters)

    assert "Scottish brogue accent" in char_a.voice_style
    assert "Jamaican patois flow" in char_b.voice_style


def test_enrich_timeline_dialogue_speakers():
    characters = [
        CharacterRole(role_id="Role A", name="Dumble Dior", description="Headmaster"),
        CharacterRole(role_id="Role B", name="Harry Gucci", description="Young wizard"),
    ]
    char_tag_map = {
        "Dumble Dior": "<IMAGE_REF_0>",
        "Harry Gucci": "<IMAGE_REF_1>",
    }

    dialogue = 'Dumble Dior: "Welcome to Dripwarts!" / Harry Gucci: "Let\'s brew."'
    enriched, replaced = enrich_timeline_dialogue_speakers(
        dialogue, characters=characters, char_tag_map=char_tag_map
    )

    assert replaced is True
    assert "<IMAGE_REF_0>" in enriched
    assert "<IMAGE_REF_1>" in enriched
    assert "[Voice Style: " in enriched


def test_enrich_timeline_dialogue_narrator_fallback():
    dialogue = 'Narrator (VO) says: "In a world of magic..."'
    enriched, replaced = enrich_timeline_dialogue_speakers(dialogue, characters=None)
    assert replaced is True
    assert "Narrator (Voiceover):" in enriched
