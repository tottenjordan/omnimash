from omnimash.prompts.compiler import MetaPromptTags, PromptCompiler
from omnimash.prompts.taxonomy import PromptTaxonomyEngine


def test_deconstruct_concept_shorthand():
    compiler = PromptCompiler(mock_mode=True)
    concept = "Gordon Ramsay vs Julia Child in a cyberpunk iron chef battle"
    tags = compiler.deconstruct_concept(concept)

    assert isinstance(tags, MetaPromptTags)
    assert len(tags.characters) >= 2
    assert tags.characters[0].role_id == "Role A"
    assert tags.characters[1].role_id == "Role B"
    assert any("Ramsay" in c.name or "Chef" in c.description for c in tags.characters)
    assert any("Julia" in c.name or "Child" in c.name for c in tags.characters)

    assert len(tags.aesthetic_tags) > 0
    assert any("Cyberpunk" in tag or "Neon" in tag for tag in tags.aesthetic_tags)
    assert "kitchen" in tags.environment_tag.lower() or "colosseum" in tags.environment_tag.lower()
    assert len(tags.camera_lighting_tag) > 0
    assert "BPM" in tags.audio_beat or len(tags.audio_beat) > 0


def test_deconstruct_concept_rap_battle():
    compiler = PromptCompiler(mock_mode=True)
    concept = "Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style"
    tags = compiler.deconstruct_concept(concept)

    assert len(tags.characters) >= 2
    names = [c.name for c in tags.characters]
    assert any("Harry" in n for n in names)
    assert any("Draco" in n for n in names)

    # Check rich physical/visual descriptions
    harry_char = next(c for c in tags.characters if "Harry" in c.name)
    assert len(harry_char.description) > 20

    assert any("Trap" in tag or "Streetwear" in tag for tag in tags.aesthetic_tags)
    assert "Hogwarts" in tags.environment_tag or "courtyard" in tags.environment_tag.lower()
    assert len(tags.camera_lighting_tag) > 0
    assert "Trap" in tags.audio_beat or "808" in tags.audio_beat


def test_taxonomy_engine_deconstruct_concept():
    engine = PromptTaxonomyEngine(mock_mode=True)
    concept = "Severus Snape in a 90s rap video"
    tags = engine.deconstruct_concept(concept)

    assert isinstance(tags, MetaPromptTags)
    assert len(tags.characters) >= 1
    assert tags.characters[0].role_id == "Role A"
    assert "Snape" in tags.characters[0].name or "Snape" in tags.characters[0].description
    assert len(tags.aesthetic_tags) > 0
    assert len(tags.environment_tag) > 0
    assert len(tags.camera_lighting_tag) > 0
    assert len(tags.audio_beat) > 0


def test_deconstruct_open_ended_custom_concept():
    compiler = PromptCompiler(mock_mode=True)
    concept = "A neon samurai vs a cyborg ninja in an arcade showdown"
    tags = compiler.deconstruct_concept(concept)

    assert len(tags.characters) >= 2
    assert tags.characters[0].role_id == "Role A"
    assert tags.characters[1].role_id == "Role B"
    assert len(tags.aesthetic_tags) > 0
    assert len(tags.environment_tag) > 0
    assert len(tags.camera_lighting_tag) > 0
    assert len(tags.audio_beat) > 0


def test_deconstruct_concept_populates_voice_styles():
    compiler = PromptCompiler(mock_mode=True)
    tags = compiler.deconstruct_concept(
        "Harry Potter vs Draco Malfoy rap battle in 2000s Atlanta trap style"
    )
    assert len(tags.characters) >= 2
    assert any(
        "trap" in c.voice_style.lower() or "rap" in c.voice_style.lower() for c in tags.characters
    )
    assert tags.vocal_delivery != ""
