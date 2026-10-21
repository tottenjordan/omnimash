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


def test_deconstruct_concept_synthesizes_keyframe_script_and_temporal_scenes():
    compiler = PromptCompiler(mock_mode=True)
    tags = compiler.deconstruct_concept("A cyberpunk chef cooking neon ramen")

    assert tags.keyframe_image_prompt != ""
    assert "cyberpunk chef cooking neon ramen" in tags.keyframe_image_prompt.lower()
    assert tags.screenplay_script != ""
    assert "[0-3s]" in tags.screenplay_script
    assert "[3-6s]" in tags.screenplay_script
    assert "[6-10s]" in tags.screenplay_script
    assert "DIALOGUE:" in tags.screenplay_script

    assert len(tags.scenes) >= 1
    scene = tags.scenes[0]
    assert scene.scene_number == 1
    assert "[0-3s]" in scene.action
    assert "[3-6s]" in scene.action
    assert "[6-10s]" in scene.action
    assert scene.dialogue != ""
    assert ":" in scene.dialogue


def test_deconstruct_concept_live_gemini_synthesizes_scenes_and_enforces_temporal_beats():
    from unittest.mock import MagicMock

    from omnimash.prompts.models import (
        DeconstructedCharacterSchema,
        DeconstructedConceptSchema,
        DeconstructedSceneSchema,
    )

    compiler = PromptCompiler(mock_mode=True)
    compiler.mock_mode = False
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.parsed = DeconstructedConceptSchema(
        characters=[
            DeconstructedCharacterSchema(
                role_id="Role A",
                name="Neon Samurai",
                description="Stoic cyber warrior in glowing armor",
                aesthetic_tags=["Glowing LED Armor"],
                voice_style="Stoic synthesized warrior cadence",
            )
        ],
        aesthetic_tags=["Cyberpunk Glow"],
        environment_tag="Rainy neon rooftop",
        camera_lighting_tag="Low-angle anamorphic tracking shot",
        audio_beat="110 BPM Synthwave",
        vocal_delivery="Crisp vocoded delivery",
        keyframe_image_prompt="Neon Samurai standing on a rainy neon rooftop at midnight",
        screenplay_script="[0-3s] Draws blade\n[3-6s] Slashes rain\n[6-10s] Sheathes katana",
        scenes=[
            DeconstructedSceneSchema(
                scene_number=1,
                active_roles=["Role A"],
                action="Role A (Neon Samurai) draws a glowing katana in the rain",
                dialogue='Neon Samurai: "The circuit ends tonight."',
            )
        ],
    )
    mock_client.models.generate_content.return_value = mock_resp
    compiler._pro_global_client = None
    compiler._flash_regional_client = mock_client

    tags = compiler.deconstruct_concept("Neon samurai on a rainy rooftop")
    assert tags.keyframe_image_prompt == "Neon Samurai standing on a rainy neon rooftop at midnight"
    assert "[0-3s]" in tags.screenplay_script
    assert len(tags.scenes) == 1
    assert "[0-3s]" in tags.scenes[0].action
    assert "[3-6s]" in tags.scenes[0].action
    assert "[6-10s]" in tags.scenes[0].action
    assert 'Neon Samurai: "The circuit ends tonight."' in tags.scenes[0].dialogue


def test_deconstruct_concept_empty_and_whitespace_edge_cases():
    compiler = PromptCompiler(mock_mode=True)
    for empty_val in ("", "   "):
        tags = compiler.deconstruct_concept(empty_val)
        assert len(tags.characters) >= 1
        assert tags.keyframe_image_prompt != ""
        assert "[0-3s]" in tags.screenplay_script
        assert len(tags.scenes) == 1
        assert "[0-3s]" in tags.scenes[0].action
        assert "[3-6s]" in tags.scenes[0].action
        assert "[6-10s]" in tags.scenes[0].action
        assert tags.scenes[0].dialogue != ""
