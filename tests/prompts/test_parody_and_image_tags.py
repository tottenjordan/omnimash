from omnimash.prompts.character_roles import CharacterRole
from omnimash.prompts.image_tags import (
    build_character_image_ref_tags,
    replace_character_in_text_image_tags,
    sort_characters_by_role_id,
)
from omnimash.prompts.parody import (
    REAL_NAME_PARODY_MAP,
    sanitize_real_names,
)


def test_parody_sanitization():
    raw = "Gordon Ramsay and Draco Malfoy went to Hogwarts."
    sanitized = sanitize_real_names(raw)
    assert "Gordon Ramsay" not in sanitized
    assert "Draco Malfoy" not in sanitized
    assert "Fiery Chef Blood" in sanitized
    assert "Platinum Rival Blood" in sanitized
    assert "Gothic Academy" in sanitized


def test_parody_dictionary_precompiled():
    from omnimash.prompts.parody import _COMPILED_PARODY_PATTERNS

    assert len(_COMPILED_PARODY_PATTERNS) == len(REAL_NAME_PARODY_MAP)
    assert all(hasattr(p, "sub") for p, _ in _COMPILED_PARODY_PATTERNS)


def test_image_tags_sort_characters():
    c_b = CharacterRole(role_id="Role B", name="Character B", description="Desc B")
    c_a = CharacterRole(role_id="Role A", name="Character A", description="Desc A")
    c_start = CharacterRole(
        role_id="Role C",
        name="Start",
        description="Starting frame",
        image_role="Starting Frame",
    )

    sorted_chars = sort_characters_by_role_id([c_b, c_a, c_start])
    assert sorted_chars[0].role_id == "Role C"
    assert sorted_chars[1].role_id == "Role A"
    assert sorted_chars[2].role_id == "Role B"


def test_build_character_image_ref_tags_prevents_stop_word_candidate_pollution():
    # CORR-03: Names containing stop words like "The", "A", "Bruv", "Blood"
    # must not add single generic stop-words to candidate map.
    c1 = CharacterRole(
        role_id="Role A",
        name="The Alchemist",
        description="Master potion maker",
        reference_url="http://example.com/alchemist.png",
    )
    sources, refs, tag_map = build_character_image_ref_tags([c1])
    assert "The Alchemist" in tag_map
    assert "Alchemist" in tag_map
    # "the" is a generic stop word (<3 chars or in stop words) and should not be a candidate key
    assert "the" not in tag_map


def test_replace_character_in_text_image_tags_single_pass_efficiency():
    # PERF-01: Single-pass alternation regex
    name_to_tag = {
        "Harry": "@Image1",
        "Snape": "@Image2",
    }
    text = "Harry and Snape are standing in the dungeon. Harry looks at Snape."
    replaced = replace_character_in_text_image_tags(text, name_to_tag)
    assert "Harry (@Image1)" in replaced
    assert "Snape (@Image2)" in replaced
    # Ensure already-tagged mentions are not doubled
    already_tagged = "Harry (@Image1) and Snape (@Image2)"
    assert replace_character_in_text_image_tags(already_tagged, name_to_tag) == already_tagged
