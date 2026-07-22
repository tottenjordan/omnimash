from omnimash.prompts.compiler import (
    CharacterRole,
    MetaPromptTags,
    PromptCompiler,
    SceneDirective,
)


def test_compile_with_character_roles_and_scenes():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Harry",
            description="Young wizard with round glasses and lightning scar",
            reference_url="https://example.com/harry.jpg",
        ),
        CharacterRole(
            role_id="Role B",
            name="Draco",
            description="Blonde rival wizard in silver-trimmed robes",
            reference_url="https://example.com/draco.jpg",
        ),
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A"],
            action="Arriving at foggy courtyard rapping into microphone wand",
            dialogue="I been cooking potions since first year!",
        ),
        SceneDirective(
            scene_number=2,
            active_roles=["Role B"],
            action="Stepping from shadows in high-gloss neon lighting",
            dialogue="This is Trap or Die, Potter!",
        ),
    ]
    compiled = compiler.compile_storyboard(
        concept="Harry vs Draco Atlanta Trap Disstrack",
        characters=chars,
        scenes=scenes,
        aesthetic_tags=["2000s Atlanta Trap", "Fisheye lens", "Heavy 808 bass"],
        environment_tag="Gothic Hogwarts courtyard with neon stage lights",
        audio_beat="140 BPM Heavy 808 Trap",
    )
    assert "[ROLE DEFINITIONS]" in compiled
    assert "Role A (Harry)" in compiled
    assert "Role B (Draco)" in compiled
    assert "[AESTHETIC INJECTION]" in compiled
    assert "2000s Atlanta Trap" in compiled
    assert "[STORYBOARD SEQUENCE]" in compiled
    assert "Scene 1 [Role A]" in compiled
    assert "Scene 2 [Role B]" in compiled
    assert "cooking potions" in compiled


def test_meta_prompt_tags_dataclass():
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Harry",
            description="Young wizard",
        )
    ]
    tags = MetaPromptTags(
        characters=chars,
        aesthetic_tags=["Cyberpunk", "Neon"],
        environment_tag="Futuristic Tokyo alley",
        camera_lighting_tag="Anamorphic lens flare",
        audio_beat="Synthwave 110 BPM",
    )
    assert tags.characters[0].name == "Harry"
    assert tags.characters[0].reference_url is None
    assert tags.aesthetic_tags == ["Cyberpunk", "Neon"]
    assert tags.environment_tag == "Futuristic Tokyo alley"
    assert tags.camera_lighting_tag == "Anamorphic lens flare"
    assert tags.audio_beat == "Synthwave 110 BPM"


def test_compile_storyboard_minimal_args():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Harry",
            description="Young wizard",
        )
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A"],
            action="Looking at camera",
        )
    ]
    compiled = compiler.compile_storyboard(
        concept="Minimal Test",
        characters=chars,
        scenes=scenes,
    )
    assert "[ROLE DEFINITIONS]" in compiled
    assert "Role A (Harry)" in compiled
    assert "[AESTHETIC INJECTION]" in compiled
    assert "[STORYBOARD SEQUENCE]" in compiled
    assert "Scene 1 [Role A]" in compiled


def test_fallback_assigns_unique_role_ids_for_five_characters():
    compiler = PromptCompiler(mock_mode=True)
    tags = compiler.deconstruct_concept(
        "Harry, Draco, Snape, Dumbledore, and Voldemort in a 90s rap battle"
    )
    role_ids = [c.role_id for c in tags.characters]
    # Five named characters -> five DISTINCT role ids (no clamping to Role D).
    assert len(role_ids) == 5
    assert len(set(role_ids)) == 5
    assert role_ids == ["Role A", "Role B", "Role C", "Role D", "Role E"]


def test_role_label_spreadsheet_style_overflow():
    from omnimash.prompts.compiler import _role_label

    assert _role_label(0) == "Role A"
    assert _role_label(25) == "Role Z"
    assert _role_label(26) == "Role AA"
    assert _role_label(27) == "Role AB"
