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
    assert "### CHARACTER PROFILES" in compiled
    assert "Role A - Spectacled Wizard Bruv" in compiled
    assert "Role B - Rival Wizard Blood" in compiled
    assert "### SCENE INSTRUCTIONS" in compiled
    assert "2000s Atlanta Trap" in compiled
    assert "### TIMELINE" in compiled
    assert "Scene 1 [Role A - Spectacled Wizard Bruv]" in compiled
    assert "Scene 2 [Role B - Rival Wizard Blood]" in compiled
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
    assert "### CHARACTER PROFILES" in compiled
    assert "Role A - Spectacled Wizard Bruv" in compiled
    assert "### SCENE INSTRUCTIONS" in compiled
    assert "### TIMELINE" in compiled
    assert "Scene 1 [Role A - Spectacled Wizard Bruv]" in compiled


def test_character_role_voice_profile():
    char = CharacterRole(
        role_id="Role A",
        name="Harry",
        description="Young wizard",
        voice_profile="Deep baritone with authoritative tone",
    )
    assert char.voice_profile == "Deep baritone with authoritative tone"


def test_character_role_voice_profile_default():
    char = CharacterRole(
        role_id="Role A",
        name="Harry",
        description="Young wizard",
    )
    assert char.voice_profile == ""


def test_character_role_image_role_and_narrator():
    char = CharacterRole(
        role_id="Role A",
        name="Harry",
        description="Young wizard",
    )
    assert char.image_role == "Character Reference"
    assert char.is_offscreen_narrator is False

    for valid_role in [
        "Character Reference",
        "Product Reference",
        "Starting Frame",
        "Style Reference",
    ]:
        char_valid = CharacterRole(
            role_id="Role A",
            name="Harry",
            description="Young wizard",
            image_role=valid_role,
            is_offscreen_narrator=True,
        )
        assert char_valid.image_role == valid_role
        assert char_valid.is_offscreen_narrator is True


