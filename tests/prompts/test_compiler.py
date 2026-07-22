from omnimash.prompts.compiler import (
    CHARACTER_LORE,
    CHARACTER_LORE_ANCHORS,
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
    assert "puffer jacket" in parts.aesthetic_injection or "Cuban link" in parts.aesthetic_injection
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
    assert "Voiceover: Gaunt wizard speaking with a deep sarcastic British drawl." in full_vo

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
    parts = compiler.compile("Snape rap", voiceover="Gaunt wizard speaking: Potter explain")
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
    scenes = [SceneDirective(scene_number=1, active_roles=["Role A"], action="Cooking potions")]
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
    assert "Voice Style (Role A): Fast-paced confident Atlanta rap flow with autotune" in compiled
    assert (
        "Voice Style (Role B): Pompous, cynical British drawl with aggressive cadence" in compiled
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

    tags_mock = compiler_mock.deconstruct_concept("Harry Potter vs Draco Malfoy rap battle")
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
        mock_pro_client.models.generate_content.side_effect = RuntimeError("Quota exceeded on Pro")

        mock_flash_response = MagicMock()
        mock_flash_response.text = json_payload.replace("Hogwarts dungeon", "Flash regional stage")
        mock_flash_client.models.generate_content.return_value = mock_flash_response

        tags_t2 = compiler.deconstruct_concept("Harry Potter in trap video")
        assert tags_t2.environment_tag == "Flash regional stage"
        mock_flash_client.models.generate_content.assert_called_once()

        # 5. Test Tier 1 failure & Tier 2 failure -> Tier 3 fallback
        mock_pro_client.models.generate_content.side_effect = RuntimeError("Pro error")
        mock_flash_client.models.generate_content.side_effect = RuntimeError("Flash error")

        tags_t3 = compiler.deconstruct_concept("Harry Potter vs Draco Malfoy rap battle")
        assert isinstance(tags_t3, MetaPromptTags)
        assert len(tags_t3.characters) >= 2


def test_parse_screenplay_script():
    characters = [
        CharacterRole(role_id="Role A", name="Severus Snape", description="Gaunt wizard"),
        CharacterRole(role_id="Role B", name="Harry Potter", description="Young wizard"),
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
    assert "thunder" in result["audio_cues"].lower() or "beat" in result["audio_cues"].lower()

    # Spoken dialogue extraction and formatting
    assert 'Snape: "Silence, Potter!"' in result["dialogue"]
    assert 'Harry: "It was the beat, professor!"' in result["dialogue"]


def test_compile_prompt_with_screenplay_text():
    compiler = PromptCompiler()
    characters = [CharacterRole(role_id="Role A", name="Severus Snape", description="Gaunt wizard")]
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
    assert '  Snape: (Standing in the dungeon. Low bass rumble.) "Silence, Potter!"' in prompt
    assert '  Harry: (Bopping head to 120 BPM beat.) "No!"' in prompt
    assert "Scene 1 Audio Cues:" in prompt


def test_character_lore_anchors_derive_from_single_source():
    # CHARACTER_LORE is the sole lore source; the anchor lookup must be a pure
    # projection of it so the two never drift apart.
    derived = {key: desc for key, (_name, desc) in CHARACTER_LORE.items()}
    assert derived == CHARACTER_LORE_ANCHORS


def test_fallback_deconstruct_uses_shared_lore():
    # The offline fallback deconstructor must resolve character descriptions
    # from the same CHARACTER_LORE map that feeds subject-anchor resolution.
    compiler = PromptCompiler()
    tags = compiler._deconstruct_fallback("Harry Potter versus Draco Malfoy in a rap battle")
    by_name = {c.name: c.description for c in tags.characters}
    assert by_name["Harry"] == CHARACTER_LORE["harry"][1]
    assert by_name["Draco"] == CHARACTER_LORE["draco"][1]


# --- Golden characterization tests for _deconstruct_fallback -----------------
# These lock the exact heuristic output for four representative concepts, one
# per style category (trap / cyber / anime / cinematic) and covering the lore
# multi-character path, the chef environment variant, the single "Lead Subject"
# fallback, and the "X vs Y" split. They must stay green through the
# table-driven refactor (Task 5.3) — any diff is a behavior change, not a
# refactor.


def _tags_as_dict(tags) -> dict:
    return {
        "characters": [
            {
                "role_id": c.role_id,
                "name": c.name,
                "description": c.description,
                "aesthetic_tags": c.aesthetic_tags,
                "voice_style": c.voice_style,
            }
            for c in tags.characters
        ],
        "aesthetic_tags": tags.aesthetic_tags,
        "environment_tag": tags.environment_tag,
        "camera_lighting_tag": tags.camera_lighting_tag,
        "audio_beat": tags.audio_beat,
        "vocal_delivery": tags.vocal_delivery,
    }


def test_fallback_golden_trap_multichar():
    compiler = PromptCompiler()
    result = _tags_as_dict(compiler._deconstruct_fallback("harry vs draco trap rap battle"))
    assert result == {
        "characters": [
            {
                "role_id": "Role A",
                "name": "Harry",
                "description": CHARACTER_LORE["harry"][1],
                "aesthetic_tags": ["Red Gucci Tracksuit", "Cartier Glasses"],
                "voice_style": "Fast-paced confident Atlanta rap flow with autotune",
            },
            {
                "role_id": "Role B",
                "name": "Draco",
                "description": CHARACTER_LORE["draco"][1],
                "aesthetic_tags": ["Platinum Slicked Hair", "Diamond Iced-Out Chain"],
                "voice_style": "Pompous, cynical British drawl with aggressive rap cadence",
            },
        ],
        "aesthetic_tags": [
            "2000s Atlanta Trap Disstrack",
            "Diamond Lightning Bolt Chain",
            "Vintage Streetwear",
            "Heavy 808 Bass Lighting",
        ],
        "environment_tag": "Gothic Hogwarts courtyard lit by neon stage lights and smoky haze",
        "camera_lighting_tag": (
            "Low-angle 90s fisheye tracking shot with high-contrast green and purple neon rim lights"
        ),
        "audio_beat": "140 BPM Heavy 808 Trap",
        "vocal_delivery": (
            "High-energy back-and-forth rap battle delivery with synchronized "
            "lip-sync and punchy cadence"
        ),
    }


def test_fallback_golden_cyber_chef_variant():
    compiler = PromptCompiler()
    result = _tags_as_dict(
        compiler._deconstruct_fallback("ramsay vs julia cyberpunk iron chef showdown")
    )
    assert result == {
        "characters": [
            {
                "role_id": "Role A",
                "name": "Gordon Ramsay",
                "description": CHARACTER_LORE["ramsay"][1],
                "aesthetic_tags": ["Holographic Chef Jacket", "Laser Thermal Blade"],
                "voice_style": "High-intensity barking commands with sharp electronic vocoding",
            },
            {
                "role_id": "Role B",
                "name": "Julia Child",
                "description": CHARACTER_LORE["julia"][1],
                "aesthetic_tags": ["Cybernetic Apron", "Holographic Visor"],
                "voice_style": "Warm vintage tone with cheerful cybernetic filter",
            },
        ],
        "aesthetic_tags": [
            "Cyberpunk Glow",
            "Neon Cyan & Purple Color Grading",
            "Futuristic Techwear",
            "Anamorphic Lens Flare",
        ],
        "environment_tag": ("Futuristic neon kitchen colosseum with holographic spectator screens"),
        "camera_lighting_tag": (
            "Anamorphic widescreen tracking shot with high-gloss neon reflections "
            "and holographic bloom"
        ),
        "audio_beat": "110 BPM Cyberpunk Synthwave Groove",
        "vocal_delivery": (
            "Futuristic vocoded dialogue with sharp synthesized delivery and spatial reverb"
        ),
    }


def test_fallback_golden_anime_lead_subject():
    compiler = PromptCompiler()
    result = _tags_as_dict(
        compiler._deconstruct_fallback("a mysterious hero in an anime vhs showdown")
    )
    assert result == {
        "characters": [
            {
                "role_id": "Role A",
                "name": "Lead Subject",
                "description": (
                    "A distinct cinematic character with expressive facial features "
                    "and stylized attire"
                ),
                "aesthetic_tags": ["Cel-Shaded Styling", "Retro Headband"],
                "voice_style": "Expressive retro anime dub voice with dramatic flair",
            },
        ],
        "aesthetic_tags": [
            "Retro VHS Anime Lo-Fi",
            "Analog Scanlines",
            "Warm Nostalgic Bloom",
            "Cel-Shaded Styling",
        ],
        "environment_tag": "Retro 80s anime cityscape bathed in sunset pastel lighting",
        "camera_lighting_tag": (
            "Retro 4:3 VHS tape framing with chromatic aberration and warm bloom"
        ),
        "audio_beat": "85 BPM VHS Lo-Fi City Pop",
        "vocal_delivery": (
            "Expressive 80s anime dub voiceover with dramatic dynamic range and emotional emphasis"
        ),
    }


def test_fallback_golden_cinematic_vs_split():
    compiler = PromptCompiler()
    result = _tags_as_dict(compiler._deconstruct_fallback("Godzilla vs Kong epic battle"))
    assert result == {
        "characters": [
            {
                "role_id": "Role A",
                "name": "Godzilla",
                "description": (
                    "Godzilla, a distinct cinematic character with sharp expressive features"
                ),
                "aesthetic_tags": ["Stylized Wardrobe", "Cinematic Attire"],
                "voice_style": "Cinematic theatrical voice with distinct expressive delivery",
            },
            {
                "role_id": "Role B",
                "name": "Kong Epic Battle",
                "description": (
                    "Kong Epic Battle, a compelling rival character with bold visual presence"
                ),
                "aesthetic_tags": ["Stylized Wardrobe", "Cinematic Attire"],
                "voice_style": "Cinematic theatrical voice with distinct expressive delivery",
            },
        ],
        "aesthetic_tags": [
            "High-Contrast Cinematic Parody",
            "Stylized Wardrobe",
            "Dramatic Lighting",
        ],
        "environment_tag": (
            "Atmospheric stage set with dramatic directional lighting and smoke effects"
        ),
        "camera_lighting_tag": (
            "Cinematic 16:9 tracking shot with balanced ambient lighting and crisp depth of field"
        ),
        "audio_beat": "120 BPM Cinematic Beat",
        "vocal_delivery": (
            "Crisp cinematic dialogue with natural conversational timing and clear studio projection"
        ),
    }
