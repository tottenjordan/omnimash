from omnimash.prompts.compiler import (
    CharacterRole,
    CompiledDeltaPrompt,
    CompiledPromptParts,
    PromptCompiler,
    SceneDirective,
    build_character_image_ref_tags,
    compile_journey3_shot_prompt,
    get_character_identifier,
    parse_screenplay_script,
    parse_timecoded_script,
    sanitize_real_names,
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
    assert "in a single continuous shot. no scene cuts." in full_prompt.lower()
    assert "[0-3s]" in full_prompt
    assert "120 BPM" in full_prompt or "boom-bap" in full_prompt
    assert "[AUDIO TRACK]:" not in full_prompt


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
            name="Harry Potter",
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
    assert get_character_identifier(chars[0]) in prompt
    assert "Red Gucci Tracksuit" in prompt
    assert "[# References <IMAGE_REF_0>@Image1]" in prompt


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

    assert "### SCENE INSTRUCTIONS" in compiled
    assert (
        "Background beat (instrumental 140 BPM Heavy 808 Trap) is subtly ducked in the background beneath dialogue"
        in compiled
    )
    assert (
        f"Voice Style ({get_character_identifier(chars[0])} <IMAGE_REF_0>): Fast-paced confident Atlanta rap flow with autotune"
        in compiled
    )
    assert (
        f"Voice Style ({get_character_identifier(chars[1])} <IMAGE_REF_1>): Pompous, cynical British drawl with aggressive cadence"
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
    assert (
        f'{get_character_identifier(characters[0])}: "Silence, Potter!"'
        in result["dialogue"]
    )
    assert (
        f'{get_character_identifier(characters[1])}: "It was the beat, professor!"'
        in result["dialogue"]
    )


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
            name="Harry Potter",
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

    assert compiled.startswith("### INPUT ROLES\n")
    assert "[# References <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image2]" in compiled
    assert "### CHARACTER PROFILES" in compiled
    assert compiled.index("### INPUT ROLES") < compiled.index("### CHARACTER PROFILES")

    assert "gs://bucket/harry.jpg" not in compiled
    assert "http://example.com/ollivander.jpg" not in compiled
    assert "(Ref:" not in compiled


def test_compile_multi_role_prompt_with_screenplay_text():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Severus Snape",
            description="Gaunt wizard",
        ),
        CharacterRole(
            role_id="Role B",
            name="Harry Potter",
            description="Young wizard",
        ),
    ]
    sp_text = (
        'Severus Snape: (Standing in the dungeon. Low bass rumble.) "Silence, Harry Potter!"\n'
        'Harry Potter: (Bopping head to 120 BPM beat.) "No!"'
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

    assert (
        f"- Scene 1 [{get_character_identifier(chars[0])}, {get_character_identifier(chars[1])}] (Screenplay Script):"
        in prompt
    )
    assert (
        '  Role A - Gothic Potion Master Fam says: (Standing in the dungeon. Low bass rumble.) "Silence, Spectacled Wizard Bruv!"'
        in prompt
    )
    assert '  Role B - Spectacled Wizard Bruv says: (Bopping head to 120 BPM beat.) "No!"' in prompt
    assert "Scene 1 Audio Cues:" in prompt


def test_parse_screenplay_script_bracketed_roles_and_parentheticals_before_colon():
    from omnimash.prompts.compiler import parse_screenplay_script

    chars = [
        CharacterRole(role_id="Role A", name="Mr. Ice-Vander", description="Jeweler"),
        CharacterRole(role_id="Role B", name="Harry Gucci", description="Wizard"),
        CharacterRole(role_id="Role C", name="Swagrid Tha Plug", description="Giant"),
    ]
    script = (
        '[Role A] (Resting hands on marble counter): "Ah, blood!"\n'
        '[Role B] (Steps up to counter): "You got that real gas?"\n'
        '[Role C] (looks with anticipation): "don t play"\n'
        '[Role A] (Leans in close): "type shit"'
    )
    result = parse_screenplay_script(script, characters=chars)
    assert result["active_roles"] == ["Role A", "Role B", "Role C"]
    assert f'{get_character_identifier(chars[0])}: "Ah, blood!"' in result["dialogue"]
    assert (
        f'{get_character_identifier(chars[1])}: "You got that real gas?"'
        in result["dialogue"]
    )
    assert f'{get_character_identifier(chars[2])}: "don t play"' in result["dialogue"]
    assert f'{get_character_identifier(chars[0])}: "type shit"' in result["dialogue"]


def test_parse_screenplay_script_supports_timecoded_syntax():
    script_timecoded = '[0-5s] Action: Harry waves wand. Audio: Whoosh sfx. Dialogue: Harry: "Expelliarmus!"'
    result = parse_screenplay_script(script_timecoded)
    assert result["action"] == "Harry waves wand."
    assert result["audio_cues"] == "Whoosh sfx."
    assert result["dialogue"] == 'Harry: "Expelliarmus!"'
    assert result["active_roles"] == ["Harry"]

    chars = [
        CharacterRole(role_id="Role B", name="Harry Potter", description="Wizard"),
    ]
    result_chars = parse_screenplay_script(script_timecoded, characters=chars)
    assert result_chars["action"] == "Harry waves wand."
    assert result_chars["audio_cues"] == "Whoosh sfx."
    assert (
        result_chars["dialogue"]
        == f'{get_character_identifier(chars[0])}: "Expelliarmus!"'
    )
    assert result_chars["active_roles"] == ["Role B"]

    script_theatrical_timecoded = (
        '[00:00-00:05] Harry: (waves wand. Audio: Whoosh sfx.) "Expelliarmus!"'
    )
    result_theatrical = parse_screenplay_script(script_theatrical_timecoded)
    assert result_theatrical["action"] == "waves wand."
    assert result_theatrical["audio_cues"] == "Whoosh sfx."
    assert result_theatrical["dialogue"] == 'Harry: "Expelliarmus!"'
    assert result_theatrical["active_roles"] == ["Harry"]


def test_compile_prompt_extracts_dialogue_directive_from_raw_prompt():
    compiler = PromptCompiler()
    raw_prompt = (
        "[SHOT DIRECTIVE: Shot 1]\n"
        "- Action / Subject: Rapping into microphone wand\n"
        '- Dialogue / Text Overlay: "I been cooking potions since first year. Burrr!"\n'
        "- Audio Soundscape: 140 BPM Heavy 808 Trap"
    )
    parts = compiler.compile_prompt(raw_prompt=raw_prompt)
    full_prompt = parts.to_full_prompt()
    assert parts.voiceover == "I been cooking potions since first year. Burrr!"
    assert (
        "Sound design: Foreground spoken voiceover/dialogue is dominant, crystal-clear, and front-of-mix."
        in full_prompt
    )
    assert "Voiceover: I been cooking potions since first year. Burrr!." in full_prompt


def test_parse_timecoded_script():
    chars = [
        CharacterRole(
            role_id="Role A", name="Severus Snape", description="Gaunt wizard"
        ),
        CharacterRole(
            role_id="Role B", name="Harry Potter", description="Young wizard"
        ),
    ]
    script = (
        '[0-3s] Snape: (Standing in dark dungeon. Heavy thunder rumbles.) "Silence, Potter!"\n'
        '[3-6s] Harry: (Bopping head to 120 BPM beat.) "It was the beat!"\n'
        "[6-10s] Snape: (Glaring menacingly.)"
    )
    blocks = parse_timecoded_script(script, characters=chars)
    assert len(blocks) == 3
    assert blocks[0]["timecode"] == "[0-3s]"
    assert blocks[0]["active_roles"] == ["Role A"]
    assert "Standing in dark dungeon" in blocks[0]["action"]
    assert "thunder" in blocks[0]["audio_cues"].lower()
    assert (
        f'{get_character_identifier(chars[0])}: "Silence, Potter!"'
        in blocks[0]["dialogue"]
    )

    assert blocks[1]["timecode"] == "[3-6s]"
    assert blocks[1]["active_roles"] == ["Role B"]
    assert "Bopping head" in blocks[1]["action"]

    assert blocks[2]["timecode"] == "[6-10s]"
    assert blocks[2]["active_roles"] == ["Role A"]
    assert "Glaring menacingly" in blocks[2]["action"]


def test_compile_prompt_omni_flash_timecode_format():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Severus Snape",
            description="Gaunt wizard with straight greasy black hair",
            reference_url="gs://bucket/snape.jpg",
        ),
        CharacterRole(
            role_id="Role B",
            name="Harry Potter",
            description="Young wizard with round glasses and lightning scar",
            reference_url="gs://bucket/harry.jpg",
        ),
    ]
    script = (
        '[0-3s] Snape: (Standing in dark dungeon. 140 BPM Heavy 808 Trap beat.) "Silence, Potter!"\n'
        '[3-6s] Harry: (Bopping head to 140 BPM trap beat.) "It was the beat, professor!"\n'
        "[6-10s] Snape: (Glaring menacingly while gesturing with wand.)"
    )

    parts = compiler.compile_prompt(
        screenplay_text=script,
        characters=chars,
        audio_stem="140 BPM Heavy 808 Trap",
        style_preset=StylePreset.TRAP_DISSTRACK,
    )
    full_prompt = parts.to_full_prompt()

    # 1. Continuous shot camera header
    assert "in a single continuous shot. no scene cuts." in full_prompt.lower()

    # 2. Visual character roster reference index headers
    assert "[# References <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image2]" in full_prompt

    # 3. Chronological [0-3s], [3-6s], [6-10s] timing blocks
    assert "[0-3s]" in full_prompt
    assert "[3-6s]" in full_prompt
    assert "[6-10s]" in full_prompt

    # 4. Seamless integration of spoken dialogue and background audio directly within timecode blocks
    assert "140 BPM" in full_prompt
    assert "Silence, Potter!" in full_prompt
    assert "It was the beat, professor!" in full_prompt

    # 5. Elimination of redundant isolated audio headers
    assert "[AUDIO TRACK]:" not in full_prompt


def test_compile_prompt_four_block_omni_flash_template():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Hero",
            description="Young wizard with round glasses",
            reference_url="gs://bucket/hero.jpg",
            image_role="Character Reference",
        ),
        CharacterRole(
            role_id="Role B",
            name="Golden Snitch",
            description="Enchanted golden flying ball",
            reference_url="gs://bucket/snitch.jpg",
            image_role="Product Reference",
        ),
        CharacterRole(
            role_id="Role C",
            name="Dungeon Entrance",
            description="Starting frame of dungeon corridor",
            reference_url="gs://bucket/dungeon.jpg",
            image_role="Starting Frame",
        ),
        CharacterRole(
            role_id="Role D",
            name="Retro Aesthetic",
            description="90s VHS mood reference",
            reference_url="gs://bucket/style.jpg",
            image_role="Style Reference",
        ),
        CharacterRole(
            role_id="Role E",
            name="Narrator",
            description="Voice of the dungeon keeper",
            is_offscreen_narrator=True,
        ),
    ]

    parts = compiler.compile_prompt(
        raw_prompt="Hero catching the snitch",
        characters=chars,
        voiceover='Narrator: "Welcome to the magical tournament."',
        audio_stem="120 BPM boom-bap beat",
        on_screen_text="MATCH DAY",
    )

    full_prompt = parts.to_full_prompt()

    # 1. Verify four-block section headers
    assert "### INPUT ROLES" in full_prompt
    assert "### CHARACTER PROFILES" in full_prompt
    assert "### SCENE INSTRUCTIONS" in full_prompt
    assert "### TIMELINE" in full_prompt

    # 2. Verify Image Role tagging
    assert "[# Sources <FIRST_FRAME>@Image3]" in full_prompt
    assert (
        "[# References <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image2 <IMAGE_REF_2>@Image4]"
        in full_prompt
    )

    # 3. Verify Off-Screen Narrator profile and speech formatting
    assert "Visual: Off-screen (Voiceover only). Do not show." in full_prompt
    assert 'Narrator (VO) says: "Welcome to the magical tournament."' in full_prompt

    # 4. Verify diegetic and non-diegetic written text formatting
    assert 'reading "MATCH DAY"' in full_prompt

    # 5. Verify background audio with "instrumental" prefix to prevent AI vocal overlap
    assert "instrumental 120 bpm boom-bap beat" in full_prompt.lower()


def test_compile_multi_role_prompt_four_block_structure():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Hero",
            description="Young wizard with round glasses",
            reference_url="gs://bucket/hero.jpg",
            image_role="Character Reference",
        ),
        CharacterRole(
            role_id="Role B",
            name="Golden Snitch",
            description="Enchanted golden flying ball",
            reference_url="gs://bucket/snitch.jpg",
            image_role="Product Reference",
        ),
        CharacterRole(
            role_id="Role C",
            name="Narrator",
            description="Voice of the dungeon keeper",
            is_offscreen_narrator=True,
        ),
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A", "Role B", "Role C"],
            action="Hero chasing the snitch",
            dialogue='Narrator: "Welcome to the magical tournament."',
        )
    ]

    prompt = compiler.compile_multi_role_prompt(
        concept="Magical Tournament",
        characters=chars,
        scenes=scenes,
        audio_beat="120 BPM boom-bap beat",
    )

    # 1. Four-block section headers
    assert "### INPUT ROLES" in prompt
    assert "### CHARACTER PROFILES" in prompt
    assert "### SCENE INSTRUCTIONS" in prompt
    assert "### TIMELINE" in prompt

    # 2. Explicit Image Role tags
    assert "[# References <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image2]" in prompt

    # 3. Off-Screen Narrator profile and timeline speech formatting
    assert "Visual: Off-screen (Voiceover only). Do not show." in prompt
    assert 'Narrator (VO) says: "Welcome to the magical tournament."' in prompt

    # 4. Background audio with "instrumental" prefix
    assert "instrumental 120 bpm boom-bap beat" in prompt.lower()


def test_four_block_character_identifier_symmetry():
    compiler = PromptCompiler()
    char = CharacterRole(
        role_id="Role A",
        name="Harry",
        description="Young wizard with round glasses",
        reference_url="gs://bucket/harry.jpg",
        image_role="Character Reference",
    )
    expected_id = get_character_identifier(char)

    parts = compiler.compile_prompt(
        raw_prompt="Hero catching the snitch",
        characters=[char],
        screenplay_text='Harry: (Casting a spell.) "Expelliarmus!"',
    )
    full_prompt = parts.to_full_prompt()

    assert "[# References <IMAGE_REF_0>@Image1]" in full_prompt
    assert (
        f"- {expected_id} <IMAGE_REF_0>: Young wizard with round glasses" in full_prompt
    )
    assert f'{expected_id}: "Expelliarmus!"' in full_prompt


def test_sanitize_real_names_prevents_over_sanitization():
    full_names_text = "Harry Potter, Draco Malfoy, Gordon Ramsay, Donald Trump, Elon Musk, and Waka Flocka Flame entered the room."
    sanitized_full = sanitize_real_names(full_names_text)
    assert "Harry Potter" not in sanitized_full
    assert "Draco Malfoy" not in sanitized_full
    assert "Gordon Ramsay" not in sanitized_full
    assert "Donald Trump" not in sanitized_full
    assert "Elon Musk" not in sanitized_full
    assert "Waka Flocka Flame" not in sanitized_full

    single_words_text = "Scott told Wayne that Julia, Grace, Sam, and Rob were ready."
    sanitized_single = sanitize_real_names(single_words_text)
    assert sanitized_single == single_words_text


def test_four_block_official_image_ref_tags():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role C",
            name="Dungeon Corridor",
            description="Starting frame of stone dungeon corridor",
            reference_url="gs://bucket/dungeon.jpg",
            image_role="Starting Frame",
        ),
        CharacterRole(
            role_id="Role A",
            name="Snape Dawg",
            description="Gaunt potion master wizard with sleek black hair",
            reference_url="gs://bucket/snape.jpg",
            image_role="Character Reference",
        ),
        CharacterRole(
            role_id="Role B",
            name="Harry Potter",
            description="Young wizard with round wire-rim glasses",
            reference_url="gs://bucket/harry.jpg",
            image_role="Character Reference",
        ),
    ]

    parts = compiler.compile_prompt(
        raw_prompt="Snape Dawg brewing potion with Harry Potter",
        characters=chars,
        audio_stem="120 BPM boom-bap beat",
    )
    full_prompt = parts.to_full_prompt()

    assert "### INPUT ROLES" in full_prompt
    assert "### CHARACTER PROFILES" in full_prompt
    assert "### SCENE INSTRUCTIONS" in full_prompt
    assert "### TIMELINE" in full_prompt

    # Verify official Gemini Omni Flash <IMAGE_REF_N> and <FIRST_FRAME> tags in INPUT ROLES
    assert "[# Sources <FIRST_FRAME>@Image1]" in full_prompt
    assert "[# References <IMAGE_REF_0>@Image2 <IMAGE_REF_1>@Image3]" in full_prompt

    # Verify character profile binding format
    assert (
        "- Potion Master Dawg <IMAGE_REF_0>: Gaunt potion master wizard"
        in full_prompt
    )
    assert (
        "- Spectacled Wizard Bruv <IMAGE_REF_1>: Young wizard with round wire-rim glasses"
        in full_prompt
    )
    assert (
        "- Dungeon Corridor <FIRST_FRAME>: Starting frame of stone dungeon corridor"
        in full_prompt
    )

    # Verify timeline actions include <IMAGE_REF_N> tags
    assert "<IMAGE_REF_0>" in full_prompt
    assert "<IMAGE_REF_1>" in full_prompt


def test_sanitize_real_names_pop_culture_keywords():
    text = "Snape Dawg, Draco, Voldemort, and Hogwarts."
    sanitized = sanitize_real_names(text)
    assert (
        sanitized
        == "Potion Master Dawg, Rival Wizard, Dark Sorcerer, and Academy Hall."
    )


def test_sanitize_real_names_street_slang_trademarks_tattoos():
    text = "Gucci with stepped on product wearing a Widespread Panic shirt, tear drop tattoo, face tattoos, and 1017 chain."
    sanitized = sanitize_real_names(text)
    assert "diluted" in sanitized
    assert "vintage band emblem" in sanitized
    assert "facial ink accent" in sanitized
    assert "artistic facial ink" in sanitized
    assert "gold" in sanitized


def test_sanitize_real_names_trademarked_item_abstractions():
    text = "Catching the Golden Snitch while playing Quidditch with a Lightsaber inside the Batmobile."
    sanitized = sanitize_real_names(text)
    assert "glowing golden flying orb" in sanitized
    assert "aerial magical sport" in sanitized
    assert "laser sword" in sanitized
    assert "armored tactical vehicle" in sanitized


def test_sanitize_real_names_totti():
    assert sanitize_real_names("John Totti on the court") == "a tatted wizard on the court"
    assert sanitize_real_names("Yo Totti") == "a tatted wizard"
    assert sanitize_real_names("Francesco Totti") == "a tatted wizard"
    assert sanitize_real_names("Totti") == "a tatted wizard"



def test_build_character_image_ref_tags_extracts_base_names_and_tokens():
    char1 = CharacterRole(
        role_id="Role 1",
        name="Yo Totti (Post High Security Fortress)",
        description="Yo Totti after fortress release",
        reference_url="https://example.com/yototti.png",
    )
    char2 = CharacterRole(
        role_id="Role 2",
        name="Swagrid Tha Plug",
        description="Swagrid the legendary supplier",
        reference_url="https://example.com/swagrid.png",
    )

    sources, refs, char_tag_map = build_character_image_ref_tags([char1, char2])

    assert char_tag_map.get("Yo Totti (Post High Security Fortress)") == "<IMAGE_REF_0>"
    assert char_tag_map.get("Yo Totti") == "<IMAGE_REF_0>"
    assert char_tag_map.get("Totti") == "<IMAGE_REF_0>"
    assert char_tag_map.get("yo totti") == "<IMAGE_REF_0>"

    assert char_tag_map.get("Swagrid Tha Plug") == "<IMAGE_REF_1>"
    assert char_tag_map.get("Swagrid") == "<IMAGE_REF_1>"
    assert char_tag_map.get("Plug") == "<IMAGE_REF_1>"
    assert char_tag_map.get("swagrid") == "<IMAGE_REF_1>"

    compiler = PromptCompiler()
    parts = compiler.compile_prompt(
        raw_prompt="Swagrid glides out of the forest",
        characters=[char1, char2],
    )
    full_prompt = parts.to_full_prompt()
    assert "Swagrid <IMAGE_REF_1>" in full_prompt


def test_compile_storyboard_preserves_shot_audio_soundscape():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Snape",
            description="Gothic Potion Master",
        )
    ]
    scenes = [
        SceneDirective(
            scene_number=2,
            active_roles=["Role A"],
            action="Snape brewing potions in dungeon",
        )
    ]
    concept_directive = (
        "[SHOT DIRECTIVE: Shot 2]\n"
        "- Action / Subject: Snape brewing potions in dungeon\n"
        "- Audio Soundscape: Aggressive 90s boom-bap beat"
    )
    compiled = compiler.compile_storyboard(
        concept=concept_directive,
        characters=chars,
        scenes=scenes,
        audio_beat="90s 808 Trap Beat",
    )
    assert "Sound design: Aggressive 90s boom-bap beat" in compiled
    assert "90s 808 Trap Beat" not in compiled


def test_compile_storyboard_single_shot_directive():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Harry",
            description="Young wizard with round glasses",
            aesthetic_tags=["Red Gucci Tracksuit"],
        )
    ]
    scene = SceneDirective(
        scene_number=1,
        active_roles=["Role A"],
        action="Cooking potions in Hogwarts dungeon",
        dialogue="I been cooking potions all day.",
    )
    compiled = compiler.compile_storyboard(
        concept="Harry brewing potions",
        characters=chars,
        scenes=[scene],
        aesthetic_tags=["90s Trap Video"],
        environment_tag="Hogwarts Dungeon",
    )
    assert "### INPUT ROLES" in compiled
    assert "### CHARACTER PROFILES" in compiled
    assert "### SCENE INSTRUCTIONS" in compiled
    assert "### TIMELINE" in compiled
    assert "[0-10s]" in compiled
    assert "Cooking potions in" in compiled
    assert 'Dialogue: "I been cooking potions all day."' in compiled


def test_compile_storyboard_with_keyframe_seed_offsets_image_indexes():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Char1",
            description="First character",
            reference_url="https://example.com/char1.jpg",
        ),
        CharacterRole(
            role_id="Role B",
            name="Char2",
            description="Second character",
            reference_url="https://example.com/char2.jpg",
        ),
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A", "Role B"],
            action="Interaction scene",
        )
    ]
    compiled = compiler.compile_storyboard(
        concept="Test storyboard with keyframe seed",
        characters=chars,
        scenes=scenes,
        has_keyframe_seed=True,
    )
    assert "[# Sources <FIRST_FRAME>@KeyframeSeed]" in compiled
    assert "[# References <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image2]" in compiled
    assert "- Char1 <IMAGE_REF_0>:" in compiled
    assert "- Char2 <IMAGE_REF_1>:" in compiled


def test_compile_storyboard_multi_speaker_dialogue_tag_binding():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Dumble Dior",
            description="Wizard headmaster in streetwear",
            reference_url="https://example.com/dumble.jpg",
        ),
        CharacterRole(
            role_id="Role B",
            name="Snape Dawg",
            description="Potions master in dark robes",
            reference_url="https://example.com/snape.jpg",
        ),
    ]
    scene = SceneDirective(
        scene_number=1,
        active_roles=["Role A", "Role B"],
        action="Wizard interaction in potions classroom",
        dialogue='Dumble Dior: "Welcome to Dripwarts!" | Snape Dawg: "Potions class is in session!"',
    )
    compiled = compiler.compile_storyboard(
        concept="Wizard interaction",
        characters=chars,
        scenes=[scene],
    )
    assert (
        'Role A - Dumble Dior <IMAGE_REF_0> says: "Welcome to Dripwarts!"' in compiled
    )
    assert (
        'Role B - Potion Master Dawg <IMAGE_REF_1> says: "Potions class is in session!"'
        in compiled
    )


def test_compile_storyboard_screenplay_script_injects_character_tags():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Yo Totti",
            description="Character A description",
            reference_url="https://example.com/totti.jpg",
        ),
        CharacterRole(
            role_id="Role B",
            name="Bee Allison",
            description="Character B description",
            reference_url="https://example.com/allison.jpg",
        ),
    ]
    scene = SceneDirective(
        scene_number=1,
        active_roles=["Role A", "Role B"],
        action="Scene action",
        screenplay_text='[04-07s] ACTION: Yo Totti looks around. DIALOGUE: Yo Totti: "let’s see..."',
    )
    compiled = compiler.compile_storyboard(
        concept="Test screenplay script tag injection",
        characters=chars,
        scenes=[scene],
    )
    assert "### TIMELINE" in compiled
    assert 'Role A - a tatted wizard <IMAGE_REF_0> says: "let’s see..."' in compiled


def test_compile_storyboard_with_conversational_edit_directive():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Yo Totti",
            description="Character A description",
            reference_url="https://example.com/totti.jpg",
        ),
    ]
    scene = SceneDirective(
        scene_number=1,
        active_roles=["Role A"],
        action="Yo Totti stands in the studio.",
        dialogue="Yo Totti: \"Let's go.\"",
    )
    compiled = compiler.compile_storyboard(
        concept="Test conversational edit directive",
        characters=chars,
        scenes=[scene],
        edit_instruction="make him wear sunglasses",
    )
    assert "### CONVERSATIONAL EDIT DIRECTIVE" in compiled
    assert "Original Scene Baseline:" in compiled
    assert (
        'Required Change: Modify only the following aspect: "make him wear sunglasses"'
        in compiled
    )


def test_character_profile_includes_voice_style():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            name="Snape",
            role_id="Role A",
            description="Potions Master",
            voice_style="british accent",
        )
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A"],
            action="Snape teaches class.",
        )
    ]
    compiled = compiler.compile_multi_role_prompt(
        concept="Test character voice style",
        characters=chars,
        scenes=scenes,
    )
    assert "### CHARACTER PROFILES" in compiled
    assert "[Voice Style: british accent]" in compiled


def test_timeline_dialogue_includes_parenthetical_voice_style():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            name="Snape",
            role_id="Role A",
            description="Potions Master",
            voice_style="british accent",
        )
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A"],
            action="Snape teaches class.",
            dialogue='Snape: "Turn to page 394."',
        )
    ]
    compiled = compiler.compile_multi_role_prompt(
        concept="Test timeline dialogue voice style",
        characters=chars,
        scenes=scenes,
    )
    assert "### TIMELINE" in compiled
    assert 'says: (In a british accent) "Turn to page 394."' in compiled


def test_scene_instructions_vocal_delivery_priority():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            name="Snape",
            role_id="Role A",
            description="Potions Master",
        )
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A"],
            action="Snape teaches class.",
        )
    ]
    compiled = compiler.compile_multi_role_prompt(
        concept="Test scene instructions vocal delivery priority",
        characters=chars,
        scenes=scenes,
        vocal_delivery="American accent",
    )
    assert "### SCENE INSTRUCTIONS" in compiled
    assert (
        "Global Vocal Delivery: American accent (Note: Individual character Voice Styles take precedence over global delivery)."
        in compiled
    )


def test_compiler_skips_sanitization_when_disabled():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            name="Harry Potter",
            role_id="Role A",
            description="Harry Potter with round glasses",
        )
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A"],
            action="Harry Potter casts Lumos.",
        )
    ]
    compiled_enabled = compiler.compile_storyboard(
        concept="Harry Potter parody",
        characters=chars,
        scenes=scenes,
        enable_sanitization=True,
    )
    assert "Harry Potter" not in compiled_enabled
    assert "Spectacled Wizard Bruv" in compiled_enabled

    compiled_disabled = compiler.compile_storyboard(
        concept="Harry Potter parody",
        characters=chars,
        scenes=scenes,
        enable_sanitization=False,
    )
    assert "Harry Potter" in compiled_disabled
    assert "Spectacled Wizard Bruv" not in compiled_disabled


def test_compile_storyboard_with_title_card_and_narrator_widgets():
    compiler = PromptCompiler()
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Harry",
            description="Wizard with round glasses",
        )
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A"],
            action="Waving wand over bubbling cauldron.",
            title_card_text="Trapwarts: Premium Specs",
            title_card_subtitle="Part 1",
            narrator_text="Deep within the potion studio...",
        ),
        SceneDirective(
            scene_number=2,
            active_roles=["Role A"],
            action="Mixing ingredients.",
            title_card_text="Trapwarts: Premium Specs",
            narrator_text="The potion begins to glow.",
        ),
    ]
    compiled = compiler.compile_storyboard(
        concept="Trapwarts Potion Cooking",
        characters=chars,
        scenes=scenes,
    )
    assert "### TIMELINE" in compiled
    assert '[Title Screen: "Trapwarts: Premium Specs" - "Part 1"]' in compiled
    assert '[Title Screen: "Trapwarts: Premium Specs"]' in compiled
    assert 'Narrator (Voiceover): "Deep within the potion studio..."' in compiled
    assert 'Narrator (Voiceover): "The potion begins to glow."' in compiled


def test_compile_storyboard_with_aspect_ratio():
    compiler = PromptCompiler()
    chars = [CharacterRole(role_id="Role A", name="Harry", description="Wizard")]
    scenes = [SceneDirective(scene_number=1, active_roles=["Role A"], action="Cooking")]

    for ratio in ["16:9", "9:16", "1:1", "21:9"]:
        compiled = compiler.compile_storyboard(
            concept="Aspect Ratio Test",
            characters=chars,
            scenes=scenes,
            aspect_ratio=ratio,
        )
        assert "### SCENE INSTRUCTIONS" in compiled
        assert f"- Aspect Ratio: {ratio}" in compiled


def test_compile_journey3_dual_layer_audio():
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Snape",
            description="Gaunt potion master",
            voice_style="Pompous British drawl",
        )
    ]

    # 1. Global Audio Mode
    prompt_global = compile_journey3_shot_prompt(
        shot_number=1,
        action_directive="Snape stirring potion",
        characters=chars,
        timeline_dialogue='Snape: "Silence, Potter!"',
        audio_mode="global",
        global_audio_beat="120 BPM Boom Bap Beat",
        audio_stem="Ignored Custom Stem",
    )
    assert "120 BPM Boom Bap Beat" in prompt_global
    assert "Ignored Custom Stem" not in prompt_global
    assert "Pompous British drawl" in prompt_global

    # 2. Custom Audio Mode
    prompt_custom = compile_journey3_shot_prompt(
        shot_number=2,
        action_directive="Snape casting spell",
        characters=chars,
        timeline_dialogue='Snape: "Observe!"',
        audio_mode="custom",
        audio_stem="Heavy Synthwave Bassline",
        global_audio_beat="120 BPM Boom Bap Beat",
    )
    assert "Heavy Synthwave Bassline" in prompt_custom
    assert "120 BPM Boom Bap Beat" not in prompt_custom
    assert "Pompous British drawl" in prompt_custom

    # 3. Silent Audio Mode
    prompt_silent = compile_journey3_shot_prompt(
        shot_number=3,
        action_directive="Snape staring silently",
        characters=chars,
        audio_mode="silent",
        global_audio_beat="120 BPM Boom Bap Beat",
    )
    assert "Silent video. No background music, no audio." in prompt_silent
    assert "120 BPM Boom Bap Beat" not in prompt_silent


def test_compile_journey3_shot_prompt_includes_character_wardrobe_in_block1():
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Snape",
            description="Gaunt potion master",
            wardrobe="Black Velvet Trench Coat",
            reference_url="gs://bucket/snape.jpg",
        ),
        CharacterRole(
            role_id="Role B",
            name="Harry",
            description="Young spectacled wizard",
            wardrobe="Oversized Gucci Tracksuit",
        ),
    ]

    prompt = compile_journey3_shot_prompt(
        shot_number=1,
        action_directive="Snape and Harry in potion duel",
        characters=chars,
    )

    assert "### INPUT ROLES & REFERENCES" in prompt
    assert "[Wardrobe: Black Velvet Trench Coat]" in prompt
    assert "[Wardrobe: Oversized Gucci Tracksuit]" in prompt


def test_compile_journey3_shot_prompt_character_wardrobe_in_block2():
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Snape",
            description="Gaunt potion master",
            wardrobe="Black Velvet Trench Coat",
            aesthetic_tags=["Gothic", "Dark"],
            voice_style="Pompous British drawl",
        ),
        CharacterRole(
            role_id="Role B",
            name="Harry",
            description="Young spectacled wizard",
            wardrobe="Oversized Gucci Tracksuit",
            voice_style="Fast-paced rap flow",
        ),
    ]

    prompt = compile_journey3_shot_prompt(
        shot_number=1,
        action_directive="Snape and Harry in potion duel",
        characters=chars,
    )

    assert "### CHARACTER PROFILES" in prompt
    assert "[Wardrobe: Black Velvet Trench Coat]" in prompt
    assert "[Style: Gothic, Dark]" in prompt
    assert "[Voice Style: Pompous British drawl]" in prompt
    assert "[Wardrobe: Oversized Gucci Tracksuit]" in prompt
    assert "[Voice Style: Fast-paced rap flow]" in prompt


def test_compile_journey3_shot_prompt_timeline_separates_dialogue_and_visual_action():
    chars = [
        CharacterRole(
            role_id="Role A",
            name="Snape",
            description="Gaunt potion master",
        ),
        CharacterRole(
            role_id="Role B",
            name="Harry Potter",
            description="Young wizard",
        ),
    ]

    prompt = compile_journey3_shot_prompt(
        shot_number=2,
        action_directive="Snape reaches carefully for the beaker",
        characters=chars,
        timeline_dialogue='Snape: "Silence, Harry Potter!" / Harry Potter: "Never!"',
    )

    assert "### TIMELINE" in prompt
    assert "- Visual Action: Potion Master reaches carefully for the beaker" in prompt
    assert '- Spoken Dialogue (Potion Master): "Silence, Spectacled Wizard Bruv!"' in prompt
    assert '- Spoken Dialogue (Spectacled Wizard Bruv): "Never!"' in prompt


def test_deconstruct_concept_extracts_intuitive_vision_defaults():
    compiler = PromptCompiler(mock_mode=True)

    # 1. Gothic / Dark Fantasy Concept
    gothic_tags = compiler.deconstruct_concept(
        "Gothic wizard preparing a dark ritual in an ancient stone castle"
    )
    assert gothic_tags.characters, "Characters list must be populated"
    for char in gothic_tags.characters:
        assert char.aesthetic_tags, "Character wardrobe/aesthetic tags must be populated"
        assert char.voice_style, "Character voice style must be populated"
    assert gothic_tags.aesthetic_tags, "Global aesthetic tags must be populated"
    assert gothic_tags.environment_tag, "Environment set location & lighting must be populated"
    assert (
        "stone" in gothic_tags.environment_tag.lower()
        or "castle" in gothic_tags.environment_tag.lower()
        or "candlelight" in gothic_tags.environment_tag.lower()
    )
    assert gothic_tags.camera_lighting_tag, "Camera motion, aspect ratio, & lighting must be populated"
    assert (
        "16:9" in gothic_tags.camera_lighting_tag
        or "widescreen" in gothic_tags.camera_lighting_tag
        or "tracking" in gothic_lighting_tag if (gothic_lighting_tag := gothic_tags.camera_lighting_tag.lower()) else True
    )
    assert gothic_tags.audio_beat, "Audio beat & soundscape must be populated"
    assert "bpm" in gothic_tags.audio_beat.lower()
    assert gothic_tags.vocal_delivery, "Vocal delivery must be populated"

    # 2. Trap / Rap Concept
    trap_tags = compiler.deconstruct_concept("Gordon Ramsay in a trap music video")
    assert trap_tags.characters, "Trap characters must be populated"
    for char in trap_tags.characters:
        assert char.aesthetic_tags, "Trap character wardrobe tags must be populated"
        assert char.voice_style, "Trap character voice style must be populated"
    assert trap_tags.aesthetic_tags, "Trap aesthetic tags must be populated"
    assert trap_tags.environment_tag, "Trap environment tag must be populated"
    assert trap_tags.camera_lighting_tag, "Trap camera/lighting tag must be populated"
    assert trap_tags.audio_beat, "Trap audio beat must be populated"
    assert trap_tags.vocal_delivery, "Trap vocal delivery must be populated"

    # 3. Generic Open-Ended Concept
    generic_tags = compiler.deconstruct_concept("A mysterious stranger walks into town")
    assert generic_tags.characters, "Generic characters must be populated"
    for char in generic_tags.characters:
        assert char.aesthetic_tags, "Generic character wardrobe tags must be populated"
        assert char.voice_style, "Generic character voice style must be populated"
    assert generic_tags.aesthetic_tags, "Generic aesthetic tags must be populated"
    assert generic_tags.environment_tag, "Generic environment tag must be populated"
    assert generic_tags.camera_lighting_tag, "Generic camera/lighting tag must be populated"
    assert generic_tags.audio_beat, "Generic audio beat must be populated"
    assert generic_tags.vocal_delivery, "Generic vocal delivery must be populated"


def test_compile_journey3_shot_prompt_formatting_title_cards_and_narrator():
    prompt = compile_journey3_shot_prompt(
        shot_number=1,
        action_directive="Dramatic camera slow push-in over ominous foggy skyline",
        title_card_text="IN A WORLD OF SHADOWS...",
        title_card_subtitle="AN ALL-NEW CINEMATIC EXPERIENCE",
        narrator_text="In a world where ancient magic meets high-tech cybernetics...",
        narrator_voice="Deep Cinematic Announcer",
        audio_stem="Deep cinematic trailer braam horn riser",
    )
    assert '- On-Screen Displayed Text / Title Card: "IN A WORLD OF SHADOWS..." (Subtitle: "AN ALL-NEW CINEMATIC EXPERIENCE")' in prompt
    assert '- Offscreen Narrator (Deep Cinematic Announcer): "In a world where ancient magic meets high-tech cybernetics..."' in prompt
    assert "- Visual Action: Dramatic camera slow push-in over ominous foggy skyline" in prompt
    assert "Audio: Deep cinematic trailer braam horn riser" in prompt


def test_gemini_omni_flash_instruction_constant_exists():
    from omnimash.prompts.compiler import GEMINI_OMNI_FLASH_INSTR

    assert isinstance(GEMINI_OMNI_FLASH_INSTR, str)
    assert "4-Block Meta-Prompt" in GEMINI_OMNI_FLASH_INSTR or "4-Block Anchor & Inject" in GEMINI_OMNI_FLASH_INSTR
    assert "### INPUT ROLES & REFERENCES" in GEMINI_OMNI_FLASH_INSTR
    assert "@Image1" in GEMINI_OMNI_FLASH_INSTR
    assert "@KeyframeSeed" in GEMINI_OMNI_FLASH_INSTR
    assert "- On-Screen Displayed Text / Title Card:" in GEMINI_OMNI_FLASH_INSTR

