from omnimash.prompts.compiler import (
    CharacterRole,
    CompiledDeltaPrompt,
    CompiledPromptParts,
    PromptCompiler,
    SceneDirective,
    parse_screenplay_script,
)
from omnimash.prompts.taxonomy import StylePreset


def test_prompt_compiler_anchor_and_inject():
    compiler = PromptCompiler()
    parts = compiler.compile(
        raw_prompt="Severus Snape in a 90s rap video",
        style_preset=StylePreset.NINETIES_RAP_VIDEO,
        custom_instructions="rapping in the dungeon",
    )
    assert isinstance(parts, CompiledPromptParts)
    assert "gaunt" in parts.subject_anchor or "hooked nose" in parts.subject_anchor
    assert (
        "puffer jacket" in parts.aesthetic_injection
        or "Cuban link" in parts.aesthetic_injection
    )
    assert "dungeon" in parts.environment
    assert "fisheye lens" in parts.camera_lighting
    assert "10-second" in parts.motion or "bopping" in parts.motion
    assert "120 BPM" in parts.audio_track or "boom-bap" in parts.audio_track

    full_prompt = parts.to_full_prompt()
    assert "[SUBJECT ANCHOR]:" in full_prompt
    assert "[AESTHETIC INJECTION]:" in full_prompt
    assert "[AUDIO TRACK]:" in full_prompt
    assert "Sound design:" in full_prompt
    assert "No text, no subtitles, no captions on screen" in full_prompt


def test_prompt_compiler_with_custom_on_screen_text():
    compiler = PromptCompiler()
    parts = compiler.compile(
        raw_prompt="Severus Snape",
        style_preset=StylePreset.NINETIES_RAP_VIDEO,
        on_screen_text="SNAPE 1994 DISSTRACK",
    )
    full_prompt = parts.to_full_prompt()
    assert "On-screen text: 'SNAPE 1994 DISSTRACK'" in full_prompt


def test_prompt_compiler_voiceover_and_dialogue():
    compiler = PromptCompiler()

    # 1. Single-Speaker Voiceover
    parts_vo = compiler.compile(
        raw_prompt="Severus Snape",
        style_preset=StylePreset.NINETIES_RAP_VIDEO,
        voiceover="Gaunt wizard speaking with a deep sarcastic British drawl",
    )
    full_vo = parts_vo.to_full_prompt()
    assert (
        "Voiceover: Gaunt wizard speaking with a deep sarcastic British drawl."
        in full_vo
    )

    # 2. Multi-Subject Dialogue
    parts_diag = compiler.compile(
        raw_prompt="Snape and Harry",
        style_preset=StylePreset.NINETIES_RAP_VIDEO,
        voiceover='Snape: "Potter, explain." / Harry: "It was the beat!"',
    )
    full_diag = parts_diag.to_full_prompt()
    assert (
        'Dialogue between subjects: Snape: "Potter, explain." / Harry: "It was the beat!".'
        in full_diag
    )


def test_prompt_compiler_silent_video():
    compiler = PromptCompiler()
    parts_silent = compiler.compile(
        raw_prompt="Severus Snape",
        style_preset=StylePreset.NINETIES_RAP_VIDEO,
        is_silent=True,
    )
    full_silent = parts_silent.to_full_prompt()
    assert "Sound design: Silent video. No background music, no audio." in full_silent


def test_prompt_compiler_lock_and_isolate_delta():
    compiler = PromptCompiler()
    delta = compiler.compile_delta(delta_instruction="make his chain bigger")
    assert isinstance(delta, CompiledDeltaPrompt)
    assert "[PRESERVATION LOCK]:" in delta.to_delta_prompt()
    assert "Maintain exact subject face" in delta.preservation_lock
    assert "audio stem rhythm" in delta.preservation_lock
    assert "[ISOLATED DIFF]:" in delta.to_delta_prompt()
    assert "make his chain bigger" in delta.isolated_diff


def test_compiler_applies_audio_ducking_when_voiceover_present():
    compiler = PromptCompiler()
    parts = compiler.compile(
        "Snape rap", voiceover="Gaunt wizard speaking: Potter explain"
    )
    prompt = parts.to_full_prompt()
    assert "ducked" in prompt.lower() or "foreground" in prompt.lower()
    assert "Voiceover:" in prompt or "Dialogue between subjects:" in prompt


def test_compiler_vibe_slider_and_drip_props():
    compiler = PromptCompiler()
    parts = compiler.compile(
        "Harry Potter rap",
        drip_props=["Diamond Lightning Bolt Chain", "Vintage Gucci Tracksuit"],
        vibe_intensity=85,
    )
    prompt = parts.to_full_prompt()
    assert "Diamond Lightning Bolt Chain" in prompt
    assert "Vintage Gucci Tracksuit" in prompt
    assert "High-gloss neon lighting" in prompt or "anamorphic" in prompt


def test_character_role_specific_aesthetic_tags():
    from omnimash.prompts.compiler import CharacterRole, PromptCompiler, SceneDirective

    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Harry",
            description="Wizard with round glasses",
            reference_url="gs://bucket/harry.jpg",
            aesthetic_tags=["Red Gucci Tracksuit", "Cartier Glasses"],
        )
    ]
    scenes = [
        SceneDirective(
            scene_number=1, active_roles=["Role A"], action="Cooking potions"
        )
    ]
    prompt = compiler.compile_storyboard(
        concept="Harry Trap",
        characters=chars,
        scenes=scenes,
    )
    assert "[Style: Red Gucci Tracksuit, Cartier Glasses]" in prompt
    assert (
        "- Role A (Harry): Wizard with round glasses [Style: Red Gucci Tracksuit, Cartier Glasses]"
        in prompt
    )
    assert "- [IMAGE 1]: Reference image for Role A (Harry)." in prompt


def test_compile_storyboard_with_audio_and_vocal_direction():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Harry",
            description="Harry Potter, young wizard",
            aesthetic_tags=["Red Gucci Tracksuit", "Cartier Glasses"],
            reference_url="gs://bucket/harry.jpg",
            voice_style="Fast-paced confident Atlanta rap flow with autotune",
        ),
        CharacterRole(
            role_id="Role B",
            name="Draco",
            description="Draco Malfoy, rival wizard",
            aesthetic_tags=["Platinum Slicked Hair"],
            reference_url="gs://bucket/draco.jpg",
            voice_style="Pompous, cynical British drawl with aggressive cadence",
        ),
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A"],
            action="Standing over potion stove",
            dialogue="I been cooking potions since first year. Burrr!",
        )
    ]
    compiled = compiler.compile_storyboard(
        concept="Harry vs Draco rap battle",
        characters=chars,
        scenes=scenes,
        aesthetic_tags=["2000s Atlanta Trap Disstrack"],
        environment_tag="Hogwarts courtyard",
        audio_beat="140 BPM Heavy 808 Trap",
        vocal_delivery="High-energy back-and-forth rap battle delivery with synchronized lip-sync",
    )

    assert "[AUDIO & VOCAL DIRECTION]" in compiled
    assert (
        "Background Beat: 140 BPM Heavy 808 Trap (subtly ducked in the background beneath dialogue)"
        in compiled
    )
    assert (
        "Voice Style (Role A): Fast-paced confident Atlanta rap flow with autotune"
        in compiled
    )
    assert (
        "Voice Style (Role B): Pompous, cynical British drawl with aggressive cadence"
        in compiled
    )
    assert (
        "Vocal Delivery: High-energy back-and-forth rap battle delivery with synchronized lip-sync"
        in compiled
    )


def test_prompt_optimizer():
    from omnimash.prompts.compiler import PromptCompiler, PromptOptimizer

    compiler = PromptCompiler(mock_mode=True)
    optimizer = PromptOptimizer(compiler=compiler)

    raw = "Background Beat: 140 BPM Trap (ducked at 15% volume under dialogue)"
    optimized = optimizer.optimize(raw)
    assert "(subtly ducked in the background beneath dialogue)" in optimized
    assert "15% volume" not in optimized

    compiler_opt = compiler.optimize_prompt_for_omni_flash(raw)
    assert "(subtly ducked in the background beneath dialogue)" in compiler_opt


def test_deconstruct_concept_3_tier_fallback():
    from unittest.mock import MagicMock, patch

    from omnimash.config import settings
    from omnimash.prompts.compiler import MetaPromptTags, PromptCompiler

    # 1. Verify mock_mode=True bypasses client init and uses fallback
    compiler_mock = PromptCompiler(mock_mode=True)
    assert compiler_mock.mock_mode is True
    assert compiler_mock._pro_global_client is None
    assert compiler_mock._flash_regional_client is None

    tags_mock = compiler_mock.deconstruct_concept(
        "Harry Potter vs Draco Malfoy rap battle"
    )
    assert isinstance(tags_mock, MetaPromptTags)
    assert len(tags_mock.characters) >= 2

    # 2. Verify client initialization under mock_mode=False
    with (
        patch.dict("os.environ", {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}),
        patch.object(settings, "gemini_api_key", None),
        patch.object(settings, "google_api_key", None),
        patch("google.genai.Client") as mock_genai_client_cls,
    ):
        mock_pro_client = MagicMock()
        mock_flash_client = MagicMock()
        mock_genai_client_cls.side_effect = [mock_pro_client, mock_flash_client]

        compiler = PromptCompiler(mock_mode=False)
        assert compiler._pro_global_client == mock_pro_client
        assert compiler._flash_regional_client == mock_flash_client

        # Verify call args for global vs us-central1
        assert mock_genai_client_cls.call_count == 2
        call1_kwargs = mock_genai_client_cls.call_args_list[0].kwargs
        call2_kwargs = mock_genai_client_cls.call_args_list[1].kwargs
        assert call1_kwargs.get("location") == "global"
        assert call1_kwargs.get("vertexai") is True
        assert call2_kwargs.get("location") == "us-central1"
        assert call2_kwargs.get("vertexai") is True

        # 3. Test Tier 1 success parsing structured JSON
        json_payload = """{
            "characters": [
                {
                    "role_id": "Role A",
                    "name": "Harry Potter",
                    "description": "Young wizard with scar",
                    "aesthetic_tags": ["Red Gucci Tracksuit"],
                    "voice_style": "Atlanta rap flow"
                }
            ],
            "aesthetic_tags": ["Atlanta Trap"],
            "environment_tag": "Hogwarts dungeon",
            "camera_lighting_tag": "Fisheye low angle",
            "audio_beat": "140 BPM Trap",
            "vocal_delivery": "Fast rap battle"
        }"""
        mock_pro_response = MagicMock()
        mock_pro_response.text = json_payload
        mock_pro_client.models.generate_content.return_value = mock_pro_response

        tags_t1 = compiler.deconstruct_concept("Harry Potter in trap video")
        assert tags_t1.characters[0].name == "Harry Potter"
        assert tags_t1.environment_tag == "Hogwarts dungeon"
        assert tags_t1.audio_beat == "140 BPM Trap"
        mock_pro_client.models.generate_content.assert_called_once()

        # 4. Test Tier 1 failure -> Tier 2 fallback success
        mock_pro_client.models.generate_content.reset_mock()
        mock_pro_client.models.generate_content.side_effect = RuntimeError(
            "Quota exceeded on Pro"
        )

        mock_flash_response = MagicMock()
        mock_flash_response.text = json_payload.replace(
            "Hogwarts dungeon", "Flash regional stage"
        )
        mock_flash_client.models.generate_content.return_value = mock_flash_response

        tags_t2 = compiler.deconstruct_concept("Harry Potter in trap video")
        assert tags_t2.environment_tag == "Flash regional stage"
        mock_flash_client.models.generate_content.assert_called_once()

        # 5. Test Tier 1 failure & Tier 2 failure -> Tier 3 fallback
        mock_pro_client.models.generate_content.side_effect = RuntimeError("Pro error")
        mock_flash_client.models.generate_content.side_effect = RuntimeError(
            "Flash error"
        )

        tags_t3 = compiler.deconstruct_concept(
            "Harry Potter vs Draco Malfoy rap battle"
        )
        assert isinstance(tags_t3, MetaPromptTags)
        assert len(tags_t3.characters) >= 2


def test_parse_screenplay_script():
    characters = [
        CharacterRole(
            role_id="Role A", name="Severus Snape", description="Gaunt wizard"
        ),
        CharacterRole(
            role_id="Role B", name="Harry Potter", description="Young wizard"
        ),
    ]

    script_text = (
        'Snape: (Standing in the dark dungeon. Heavy thunder rumbles.) "Silence, Potter!"\n'
        'Harry: (Bopping head to 120 BPM beat.) "It was the beat, professor!"'
    )

    result = parse_screenplay_script(script_text, characters=characters)

    assert isinstance(result, dict)
    assert "active_roles" in result
    assert "action" in result
    assert "audio_cues" in result
    assert "dialogue" in result

    # Character matching mapped Snape -> Role A and Harry -> Role B
    assert "Role A" in result["active_roles"]
    assert "Role B" in result["active_roles"]

    # Action extraction
    assert "Standing in the dark dungeon" in result["action"]
    assert "Bopping head" in result["action"]

    # Parenthetical audio cues extraction
    assert (
        "thunder" in result["audio_cues"].lower()
        or "beat" in result["audio_cues"].lower()
    )

    # Spoken dialogue extraction and formatting
    assert 'Snape: "Silence, Potter!"' in result["dialogue"]
    assert 'Harry: "It was the beat, professor!"' in result["dialogue"]


def test_compile_prompt_with_screenplay_text():
    compiler = PromptCompiler()
    characters = [
        CharacterRole(
            role_id="Role A", name="Severus Snape", description="Gaunt wizard"
        )
    ]
    scene = SceneDirective(
        scene_number=1,
        active_roles=["Role A"],
        action="Default action",
        screenplay_text='Snape: (Stepping out from shadows. Low synth bass drone.) "Always."',
    )

    parts = compiler.compile_prompt(scene=scene, characters=characters)
    assert isinstance(parts, CompiledPromptParts)
    prompt = parts.to_full_prompt()

    assert "Stepping out from shadows" in prompt
    assert "Always" in prompt


def test_compile_multi_role_prompt_with_clean_image_role_tags():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Harry",
            description="Young wizard with round glasses",
            reference_url="gs://bucket/harry.jpg",
            aesthetic_tags=["Red Gucci Tracksuit"],
        ),
        CharacterRole(
            role_id="Role B",
            name="Ollivander",
            description="Elder wandmaker",
            reference_url="http://example.com/ollivander.jpg",
            aesthetic_tags=["Vintage Apron"],
        ),
        CharacterRole(
            role_id="Role C",
            name="Voldemort",
            description="Pale serpentine figure",
            reference_url=None,
        ),
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A", "Role B"],
            action="Examining wands in shop",
        )
    ]

    compiled = compiler.compile_multi_role_prompt(
        concept="Harry and Ollivander",
        characters=chars,
        scenes=scenes,
    )

    assert compiled.startswith("[IMAGE ROLES]\n")
    assert "- [IMAGE 1]: Reference image for Role A (Harry)." in compiled
    assert "- [IMAGE 2]: Reference image for Role B (Ollivander)." in compiled
    assert "[ROLE DEFINITIONS]" in compiled
    assert compiled.index("[IMAGE ROLES]") < compiled.index("[ROLE DEFINITIONS]")

    assert "gs://bucket/harry.jpg" not in compiled
    assert "http://example.com/ollivander.jpg" not in compiled
    assert "(Ref:" not in compiled


def test_compile_multi_role_prompt_with_screenplay_text():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Snape",
            description="Gaunt wizard",
        ),
        CharacterRole(
            role_id="Role B",
            name="Harry",
            description="Young wizard",
        ),
    ]
    sp_text = (
        'Snape: (Standing in the dungeon. Low bass rumble.) "Silence, Potter!"\n'
        'Harry: (Bopping head to 120 BPM beat.) "No!"'
    )
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A", "Role B"],
            action="Confrontation in dungeon",
            screenplay_text=sp_text,
        )
    ]
    prompt = compiler.compile_multi_role_prompt(
        concept="Dungeon confrontation",
        characters=chars,
        scenes=scenes,
    )

    assert "- Scene 1 [Role A, Role B] (Screenplay Script):" in prompt
    assert (
        '  Snape: (Standing in the dungeon. Low bass rumble.) "Silence, Potter!"'
        in prompt
    )
    assert '  Harry: (Bopping head to 120 BPM beat.) "No!"' in prompt
    assert "Scene 1 Audio Cues:" in prompt
