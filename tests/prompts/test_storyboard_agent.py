from omnimash.prompts.compiler import CharacterRole
from omnimash.prompts.storyboard_agent import (
    StoryboardAgent,
    StoryboardShot,
    parse_directors_notes,
    parse_timecoded_script,
)


def test_storyboard_shot_5_part_structure():
    shot = StoryboardShot(
        shot_index=1,
        duration_seconds=9.5,
        action="Snape stirring a glowing purple potion carefully",
        location="A dimly lit stone dungeon classroom with bubbling cauldrons",
        style_lighting="Cinematic, realistic, lit by a warm off-screen fire with soft shadows",
        framing_motion="Static medium shot",
        audio="Slow booming 808 trap beat with bubbling liquid sounds",
    )
    prompt = shot.to_omni_flash_prompt(role_mappings="[ROLE DEFINITIONS]\n- Role A (Snape)")
    assert "[ROLE DEFINITIONS]" in prompt
    assert "Shot 1 (0-10s)" in prompt
    assert "- Action / Subject: Snape stirring a glowing purple potion carefully" in prompt
    assert "- Location: A dimly lit stone dungeon classroom with bubbling cauldrons" in prompt
    assert (
        "- Style & Lighting: Cinematic, realistic, lit by a warm off-screen fire with soft shadows"
        in prompt
    )
    assert "- Shot Framing & Motion: Static medium shot" in prompt
    assert "- Audio Soundscape: Slow booming 808 trap beat with bubbling liquid sounds" in prompt


def test_storyboard_shot_to_omni_flash_prompt_without_role_mappings():
    shot = StoryboardShot(
        shot_index=2,
        duration_seconds=10.0,
        action="Harry Potter drawing his wand quickly",
        location="Gothic hallway with lit sconces",
        style_lighting="High contrast neon rim lighting",
        framing_motion="Dolly zoom in",
        audio="Trap hi-hat trill with dramatic synth drone",
    )
    prompt = shot.to_omni_flash_prompt()
    assert "[SHOT DIRECTIVE: Shot 2 (0-10s)]" in prompt
    assert "[ROLE DEFINITIONS]" not in prompt
    assert "- Action / Subject: Harry Potter drawing his wand quickly" in prompt
    assert "- Location: Gothic hallway with lit sconces" in prompt
    assert "- Style & Lighting: High contrast neon rim lighting" in prompt
    assert "- Shot Framing & Motion: Dolly zoom in" in prompt
    assert "- Audio Soundscape: Trap hi-hat trill with dramatic synth drone" in prompt


def test_expand_vision_into_storyboard_mock():
    agent = StoryboardAgent(mock_mode=True)
    shots = agent.expand_vision(
        concept="30-second Dripwarts video. Snape brews potion, drinks it, becomes Snape Dogg.",
        style_tone="Gritty 90s rap video",
        target_duration=30.0,
    )
    assert len(shots) == 3
    assert all(isinstance(s, StoryboardShot) for s in shots)
    assert all(s.duration_seconds <= 10.0 for s in shots)
    assert shots[0].shot_index == 1
    assert shots[1].shot_index == 2
    assert shots[2].shot_index == 3
    assert shots[0].framing_motion != ""
    assert shots[0].action != ""
    assert shots[0].location != ""
    assert shots[0].style_lighting != ""
    assert shots[0].audio != ""


def test_expand_vision_custom_duration():
    agent = StoryboardAgent(mock_mode=True)
    shots_60s = agent.expand_vision(
        concept="60-second epic Hogwarts rap battle",
        style_tone="Cinematic Trap Parody",
        target_duration=60.0,
    )
    assert len(shots_60s) == 6
    assert all(s.duration_seconds <= 10.0 for s in shots_60s)
    assert [s.shot_index for s in shots_60s] == [1, 2, 3, 4, 5, 6]

    shots_40s = agent.expand_vision(
        concept="40-second spell duel",
        style_tone="Cyberpunk Drift",
        target_duration=40.0,
    )
    assert len(shots_40s) == 4
    assert all(s.duration_seconds <= 10.0 for s in shots_40s)


def test_expand_vision_live_fallback():
    from unittest.mock import MagicMock

    agent = StoryboardAgent(mock_mode=False)
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Simulated live API failure")
    agent._genai_client = mock_client

    shots = agent.expand_vision(
        concept="30-second Dripwarts video",
        style_tone="Gritty 90s rap video",
        target_duration=30.0,
    )
    assert len(shots) >= 3
    assert all(s.duration_seconds <= 10.0 for s in shots)
    assert mock_client.models.generate_content.called
    for call in mock_client.models.generate_content.call_args_list:
        assert call.kwargs.get("model") == "gemini-3.8-flash"
        if call.kwargs.get("config") is not None:
            assert getattr(call.kwargs["config"], "temperature", None) is None


def test_parse_timecoded_script():
    script_text = (
        "[0-3s] Character A enters dungeon\n"
        "[3-6s] Character B turns up 808 trap beat\n"
        "[6-10s] Character A and Character B perform synchronized dance\n"
        "[0-5.5s] Half-time intro scene\n"
        "[0-3] Plain numbers without s suffix"
    )
    parsed = parse_timecoded_script(script_text)
    assert len(parsed) == 5
    assert parsed[0]["duration_seconds"] == 3.0
    assert parsed[0]["action"] == "Character A enters dungeon"
    assert parsed[1]["duration_seconds"] == 3.0
    assert parsed[1]["action"] == "Character B turns up 808 trap beat"
    assert parsed[2]["duration_seconds"] == 4.0
    assert parsed[3]["duration_seconds"] == 5.5
    assert parsed[4]["duration_seconds"] == 3.0


def test_parse_directors_notes_and_dialogue():
    script = (
        "[DIRECTOR'S NOTES]\n"
        "- Tone: High-energy 90s Cel-Shaded Anime Rap Battle\n"
        "- Relational Dynamic: Fierce rivalry between Dumble Dior and Snape Dawg\n\n"
        "[0-4s]\n"
        "ACTION: Dumble Dior steps up to the mic under glowing neon lights.\n"
        'DIALOGUE: Dumble Dior: "Welcome to Dripwarts, turn the beat up!"\n'
    )
    notes = parse_directors_notes(script)
    assert notes["tone"] == "High-energy 90s Cel-Shaded Anime Rap Battle"
    assert notes["relational_dynamic"] == "Fierce rivalry between Dumble Dior and Snape Dawg"

    parsed = parse_timecoded_script(script)
    assert len(parsed) == 1
    assert parsed[0]["duration_seconds"] == 4.0
    assert parsed[0]["action"] == "Dumble Dior steps up to the mic under glowing neon lights."
    assert parsed[0]["dialogue"] == 'Dumble Dior: "Welcome to Dripwarts, turn the beat up!"'


def test_expand_vision_with_screenplay_script():
    agent = StoryboardAgent(mock_mode=True)
    script = (
        "[0-3s] Severus Snape enters the potion room with dramatic flair.\n"
        "[3-7s] Dumbledore nods in approval while 808 sub-bass drops.\n"
        "[7-10s] Both wizards strike a final freeze-frame pose."
    )
    chars = [
        CharacterRole(role_id="Role A", name="Severus Snape", description="Severe wizard"),
        CharacterRole(role_id="Role B", name="Dumbledore", description="Elderly headmaster"),
    ]
    shots = agent.expand_vision(
        concept="Wizard rap duel",
        style_tone="Cinematic Trap Parody",
        target_duration=10.0,
        characters=chars,
        screenplay_script=script,
    )
    assert len(shots) == 3
    assert shots[0].duration_seconds == 3.0
    assert shots[1].duration_seconds == 4.0
    assert shots[2].duration_seconds == 3.0
    assert shots[0].shot_index == 1
    assert shots[1].shot_index == 2
    assert shots[2].shot_index == 3
    assert "Role A (Gothic Potion Master Fam)" in shots[0].action
    assert "Role B (Venerable High Wizard Bruv)" in shots[1].action


def test_expand_vision_celebrity_sanitization():
    agent = StoryboardAgent(mock_mode=True)
    script = (
        "[0-4s] Gordon Ramsay yells at line cook in high energy kitchen.\n"
        "[4-10s] Drake drops a melodic verse while Young Jeezy counts cash."
    )
    shots = agent.expand_vision(
        concept="Celebrity kitchen rap battle",
        style_tone="Trap Parody",
        target_duration=10.0,
        screenplay_script=script,
    )
    assert len(shots) == 2
    assert "Gordon Ramsay" not in shots[0].action
    assert "Fiery Chef Blood" in shots[0].action
    assert "Drake" not in shots[1].action
    assert "Drizzy Bruv" in shots[1].action
    assert "Young Jeezy" not in shots[1].action
    assert "Trap Legend Fam" in shots[1].action


def test_expand_vision_location_directives_formatting_and_sanitization():
    agent = StoryboardAgent(mock_mode=True)
    chars = [
        CharacterRole(role_id="Role A", name="Snape", description="Severe wizard"),
    ]
    shots = agent.expand_vision(
        concept="Gordon Ramsay in Snape's dungeon",
        style_tone="Parody",
        target_duration=10.0,
        characters=chars,
    )
    assert len(shots) >= 1
    for s in shots:
        assert "Gordon Ramsay" not in s.location
        assert "Gordon Ramsay" not in s.action
        assert "Gordon Ramsay" not in s.summary


def test_storyboard_shot_narrative_continuity():
    shot = StoryboardShot(
        shot_index=2,
        duration_seconds=10.0,
        action="Retainer Grainger reacts to the glowing spell",
        location="Gothic potions classroom",
        style_lighting="High contrast neon rim lights",
        framing_motion="Dolly zoom in",
        audio="Trap beat drop with sub-bass",
        narrative_stage="Rising Action",
        preceding_context="Retainer Grainger raised her glowing wand",
        camera_transition="Continuous match cut",
        character_continuity="Maintain red tracksuit and gold glasses",
    )
    prompt = shot.to_omni_flash_prompt()
    assert "[SCENE CONTINUATION & VISUAL FLOW]" in prompt
    assert "- Story Arc Phase: Rising Action" in prompt
    assert "- Preceding Shot Context: Retainer Grainger raised her glowing wand" in prompt
    assert "- Camera & Scene Transition: Continuous match cut" in prompt
    assert "- Character Continuity: Maintain red tracksuit and gold glasses" in prompt


def test_optimize_shot_prompt_mock_mode():
    agent = StoryboardAgent(mock_mode=True)
    raw_directive = "Snape brews a glowing potion carefully"
    optimized = agent.optimize_shot_prompt(raw_directive, style_tone="Cinematic Trap Parody")

    assert "Cinematic Trap Parody" in optimized
    assert "brews a glowing potion carefully" in optimized
    assert "anamorphic lens flare" in optimized.lower()
    assert "cinematic" in optimized.lower()


def test_optimize_shot_prompt_custom_style_tone():
    agent = StoryboardAgent(mock_mode=True)
    raw_directive = "Hero character steps into neon lighting"
    optimized = agent.optimize_shot_prompt(raw_directive, style_tone="Cyberpunk Synthwave")

    assert "Cyberpunk Synthwave" in optimized
    assert "Hero character steps into neon lighting" in optimized


def test_optimize_shot_prompt_empty_directive():
    agent = StoryboardAgent(mock_mode=True)
    assert agent.optimize_shot_prompt("") == ""
    assert agent.optimize_shot_prompt("   ") == "   "


def test_optimize_shot_prompt_celebrity_sanitization():
    agent = StoryboardAgent(mock_mode=True)
    raw_directive = "Gordon Ramsay yells in the kitchen while Drake counts cash"
    optimized = agent.optimize_shot_prompt(raw_directive)

    assert "Gordon Ramsay" not in optimized
    assert "Drake" not in optimized
    assert "Fiery Chef Blood" in optimized
    assert "Drizzy Bruv" in optimized


def test_optimize_shot_prompt_live_mocked_genai(monkeypatch):
    agent = StoryboardAgent(mock_mode=False)

    class MockResponse:
        text = '"Low-angle cinematic tracking shot of Severus Snape in atmospheric green lighting with anamorphic lens flares."'

    class MockModels:
        def generate_content(self, model, contents, config=None):
            assert model == "gemini-3.8-flash"
            if config is not None:
                assert getattr(config, "temperature", None) is None
            assert "Hollywood cinematographer" in contents
            assert "Dark Fantasy" in contents
            assert "Severus Snape enters the potion room" in contents
            return MockResponse()

    class MockGenaiClient:
        models = MockModels()

    agent._genai_client = MockGenaiClient()

    optimized = agent.optimize_shot_prompt(
        "Severus Snape enters the potion room", style_tone="Dark Fantasy"
    )
    assert (
        optimized
        == "Low-angle cinematic tracking shot of Gothic Potion Master Fam in atmospheric green lighting with anamorphic lens flares."
    )


def test_expand_vision_passes_through_optimize_shot_prompt():
    agent = StoryboardAgent(mock_mode=True)
    shots = agent.expand_vision("Wizard rap battle", style_tone="Gritty Noir")
    assert len(shots) > 0
    for shot in shots:
        assert "Gritty Noir" in shot.action
        assert "anamorphic lens flare" in shot.action.lower()


def test_parse_timecoded_script_omni_flash_blocks():
    script_text = (
        "[0-3s]\n"
        "ACTION: Snape stirring a glowing purple potion in a stone dungeon.\n"
        'DIALOGUE: Snape: "Observe the subtle art."\n'
        "AUDIO: Slow heavy 808 trap beat with bubbling liquid sound.\n\n"
        "[3-6s]\n"
        "ACTION: Dumbledore steps forward under glowing sconces.\n"
        'DIALOGUE: Dumbledore: "Turn the beat up!"\n'
        "AUDIO: Trap beat drop with crisp snare trills.\n\n"
        "[6-10s]\n"
        "ACTION: Both wizards perform a synchronized pose.\n"
        "AUDIO: Booming sub-bass with reverb tail.\n"
    )
    parsed = parse_timecoded_script(script_text)
    assert len(parsed) == 3
    assert parsed[0]["duration_seconds"] == 3.0
    assert parsed[0]["timecode"] == "[0-3s]"
    assert parsed[0]["action"] == "Snape stirring a glowing purple potion in a stone dungeon."
    assert parsed[0]["dialogue"] == 'Snape: "Observe the subtle art."'
    assert parsed[0]["audio"] == "Slow heavy 808 trap beat with bubbling liquid sound."

    assert parsed[1]["duration_seconds"] == 3.0
    assert parsed[1]["timecode"] == "[3-6s]"
    assert parsed[1]["action"] == "Dumbledore steps forward under glowing sconces."
    assert parsed[1]["dialogue"] == 'Dumbledore: "Turn the beat up!"'
    assert parsed[1]["audio"] == "Trap beat drop with crisp snare trills."

    assert parsed[2]["duration_seconds"] == 4.0
    assert parsed[2]["timecode"] == "[6-10s]"
    assert parsed[2]["action"] == "Both wizards perform a synchronized pose."
    assert parsed[2]["dialogue"] == ""
    assert parsed[2]["audio"] == "Booming sub-bass with reverb tail."

    agent = StoryboardAgent(mock_mode=True)
    shots = agent.expand_vision(
        concept="Wizard rap duel",
        style_tone="Cinematic Trap Parody",
        target_duration=10.0,
        screenplay_script=script_text,
    )
    assert len(shots) == 3
    assert shots[0].duration_seconds == 3.0
    assert shots[1].duration_seconds == 3.0
    assert shots[2].duration_seconds == 4.0
    assert "in a single continuous shot. no scene cuts." in shots[0].framing_motion.lower()
    assert shots[0].audio != ""
    assert "808" in shots[0].audio or "trap" in shots[0].audio.lower()


def test_expand_vision_splits_long_script_into_10s_shots():
    agent = StoryboardAgent(mock_mode=True)

    # Test 30s script without per-shot breaks
    script_30s = (
        "[DIRECTOR'S NOTES]\n"
        "- Tone: High-energy 90s Rap Battle\n\n"
        "ACTION: Snape enters dungeon and brews glowing potion while trap beat drops.\n"
        'DIALOGUE: Snape: "Observe the subtle art of the 808 beat."\n'
        "ACTION: Dumbledore steps forward and drops heavy bassline.\n"
        "ACTION: Snape transforms into Snape Dogg and performs synchronized pose."
    )

    shots_30s = agent.expand_vision(
        concept="30s wizard rap battle",
        style_tone="Cinematic Trap Parody",
        target_duration=30.0,
        screenplay_script=script_30s,
    )

    assert len(shots_30s) == 3
    assert all(s.duration_seconds <= 10.0 for s in shots_30s)
    assert shots_30s[0].start_seconds == 0.0
    assert shots_30s[0].end_seconds == 10.0
    assert shots_30s[1].start_seconds == 10.0
    assert shots_30s[1].end_seconds == 20.0
    assert shots_30s[2].start_seconds == 20.0
    assert shots_30s[2].end_seconds == 30.0

    for i, shot in enumerate(shots_30s):
        assert shot.shot_index == i + 1
        assert "continuous shot" in shot.framing_motion.lower()
        assert "match cut" in shot.camera_transition.lower()
        assert (
            "maintain" in shot.character_continuity.lower()
            or "character" in shot.character_continuity.lower()
        )

    prompt_shot2 = shots_30s[1].to_omni_flash_prompt()
    assert "[SHOT DIRECTIVE: Shot 2 (10-20s)]" in prompt_shot2
    assert "Continuous match cut" in prompt_shot2

    # Test 45s script with explicit single timecode block [0-45s]
    script_45s = (
        "[0-45s]\n"
        "ACTION: Epic 45-second spell duel between wizards with intense lighting and explosions."
    )

    shots_45s = agent.expand_vision(
        concept="45s spell duel",
        style_tone="Cinematic Fantasy",
        target_duration=45.0,
        screenplay_script=script_45s,
    )

    assert len(shots_45s) == 5
    assert all(s.duration_seconds <= 10.0 for s in shots_45s)
    assert shots_45s[0].start_seconds == 0.0
    assert shots_45s[0].end_seconds == 10.0
    assert shots_45s[3].start_seconds == 30.0
    assert shots_45s[3].end_seconds == 40.0
    assert shots_45s[4].start_seconds == 40.0
    assert shots_45s[4].end_seconds == 45.0


def test_parse_timecoded_script_character_dialogue_extraction():
    script_text = (
        '[0-5s] Action: Establishing shot of Hogwarts courtyard. Yo Totti: "It\'s time to go wholesale from sorcerer stones to sorcerer BRICKS."\n'
        '[5-10s] Action: Swagrid heaves black duffel bag. Swagrid: "Your cut from before. What\'s the first move?"'
    )
    parsed = parse_timecoded_script(script_text)
    assert len(parsed) == 2
    assert parsed[0]["duration_seconds"] == 5.0
    assert (
        parsed[0]["dialogue"]
        == 'Yo Totti: "It\'s time to go wholesale from sorcerer stones to sorcerer BRICKS."'
    )
    assert parsed[0]["action"] == "Establishing shot of Hogwarts courtyard."
    assert "Yo Totti:" not in parsed[0]["action"]
    assert "sorcerer BRICKS" not in parsed[0]["action"]

    assert parsed[1]["duration_seconds"] == 5.0
    assert parsed[1]["dialogue"] == 'Swagrid: "Your cut from before. What\'s the first move?"'
    assert parsed[1]["action"] == "Swagrid heaves black duffel bag."
    assert "What's the first move" not in parsed[1]["action"]


def test_parse_timecoded_script_extracts_dialogue_into_shot_field():
    script_text = (
        '[0-5s] Action: Dumble Dior steps up to the mic. Dumble Dior: "Welcome to Dripwarts!"'
    )
    parsed = parse_timecoded_script(script_text)
    assert len(parsed) == 1
    assert parsed[0]["dialogue"] == 'Dumble Dior: "Welcome to Dripwarts!"'
    assert parsed[0]["action"] == "Dumble Dior steps up to the mic."


def test_storyboard_shot_to_from_dict():
    shot = StoryboardShot(
        shot_index=1,
        duration_seconds=5.0,
        action="Wizard brewing potion",
        location="Dungeon",
        style_lighting="Neon",
        framing_motion="Medium tracking shot",
        audio="Trap beat",
        audio_mode="custom",
        soundscape="Custom bubbling soundscape",
    )
    data = shot.to_dict()
    assert data["audio_mode"] == "custom"
    assert data["soundscape"] == "Custom bubbling soundscape"
    assert data["shot_index"] == 1

    restored = StoryboardShot.from_dict(data)
    assert restored.audio_mode == "custom"
    assert restored.soundscape == "Custom bubbling soundscape"
    assert restored.action == "Wizard brewing potion"


def test_expand_vision_live_uses_response_schema_and_system_instruction():
    from unittest.mock import MagicMock

    from omnimash.prompts.storyboard_agent import (
        StoryboardAgent,
        StoryboardShotSchema,
    )

    agent = StoryboardAgent(mock_mode=True)
    mock_client = MagicMock()
    agent._genai_client = mock_client
    agent.mock_mode = False

    expand_resp = MagicMock()
    expand_resp.parsed = [
        StoryboardShotSchema(
            shot_index=1,
            start_seconds=0.0,
            end_seconds=10.0,
            duration_seconds=10.0,
            summary="Opening dungeon shot",
            action="Severus Snape stirs cauldron",
            location="Stone dungeon",
            style_lighting="Moody green neon",
            framing_motion="In a single continuous shot. No scene cuts. Medium tracking shot",
            audio="140 BPM 808 trap beat",
            narrative_stage="Setup",
            preceding_context="",
            camera_transition="Continuous match cut",
            character_continuity="Maintain dark robes",
        )
    ]
    expand_resp.text = ""

    opt_resp = MagicMock()
    opt_resp.text = "Low-angle tracking shot of Potion Master stirring cauldron under green neon."

    mock_client.models.generate_content.side_effect = [expand_resp, opt_resp]

    shots = agent.expand_vision(
        concept="Snape in dungeon",
        style_tone="Trap Parody",
        target_duration=10.0,
    )
    assert len(shots) == 1
    assert shots[0].shot_index == 1
    assert "Potion Master" in shots[0].action

    first_call_kwargs = mock_client.models.generate_content.call_args_list[0].kwargs
    first_config = first_call_kwargs.get("config")
    assert first_config is not None
    assert first_config.response_mime_type == "application/json"
    assert first_config.response_schema == list[StoryboardShotSchema]
    assert first_config.system_instruction is not None

    second_call_kwargs = mock_client.models.generate_content.call_args_list[1].kwargs
    second_config = second_call_kwargs.get("config")
    assert second_config is not None
    assert second_config.system_instruction is not None
    assert "Hollywood cinematographer" in second_config.system_instruction
    assert "[0-3s]" in shots[0].action
    assert "[3-6s]" in shots[0].action
    assert "[6-10s]" in shots[0].action


def test_storyboard_agent_preserves_temporal_beats_and_forwards_compiler_mock_mode():
    from unittest.mock import MagicMock, patch

    from omnimash.prompts.compiler import PromptCompiler

    agent = StoryboardAgent(mock_mode=True)
    shots = agent.expand_vision("Cyberpunk ramen duel", style_tone="Neon Synthwave")
    for s in shots:
        assert "[0-3s]" in s.action
        assert "[3-6s]" in s.action
        assert "[6-10s]" in s.action

    # Verify live optimize_shot_prompt preserves [0-3s]/[3-6s]/[6-10s] even if LLM omits timecodes
    live_agent = StoryboardAgent(mock_mode=True)
    live_agent.mock_mode = False
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Wide anamorphic shot with dramatic volumetric lighting and lens flares."
    mock_client.models.generate_content.return_value = mock_resp
    live_agent._genai_client = mock_client

    raw_timed = "[0-3s] Chef enters. [3-6s] Chef flips wok. [6-10s] Chef plates neon ramen."
    optimized = live_agent.optimize_shot_prompt(raw_timed, style_tone="Cyberpunk")
    assert "[0-3s]" in optimized
    assert "[3-6s]" in optimized
    assert "[6-10s]" in optimized
    assert "Wide anamorphic shot" in optimized

    # Verify expand_vision with screenplay_script passes self.mock_mode to PromptCompiler
    captured_mock_modes: list[bool | None] = []
    orig_init = PromptCompiler.__init__

    def _spy_init(self, mock_mode: bool | None = None) -> None:
        captured_mock_modes.append(mock_mode)
        orig_init(self, mock_mode=True)

    with patch.object(PromptCompiler, "__init__", _spy_init):
        live_agent.expand_vision(
            concept="Wizard duel",
            screenplay_script="[0-5s] Action: Wizard raises staff.",
        )
    assert False in captured_mock_modes


def test_expand_vision_applies_forwarded_camera_aesthetic_audio_vocal_and_environment():
    agent = StoryboardAgent(mock_mode=True)
    shots = agent.expand_vision(
        concept="Samurai showdown",
        style_tone="Cyberpunk Drift",
        target_duration=30.0,
        camera_lighting="Low-angle anamorphic crane tracking shot",
        aesthetic_tags=["Chrome Armor", "Laser Fog"],
        audio_beat="135 BPM Industrial Techno",
        vocal_delivery="Resonant stoic baritone",
        environment="Floating neon pagoda in digital rain",
    )
    assert len(shots) == 3
    for s in shots:
        assert "Floating neon pagoda in digital rain" in s.location
        assert "Low-angle anamorphic crane tracking shot" in s.framing_motion
        assert "Chrome Armor" in s.style_lighting
        assert "135 BPM Industrial Techno" in s.audio
        assert "Resonant stoic baritone" in s.audio


def test_optimize_shot_prompt_partial_llm_timecode_preserves_all_input_beats():
    from unittest.mock import MagicMock

    live_agent = StoryboardAgent(mock_mode=True)
    live_agent.mock_mode = False
    mock_client = MagicMock()
    mock_resp = MagicMock()
    # LLM keeps [0-3s] but drops [3-6s] and [6-10s]
    mock_resp.text = "[0-3s] Wide anamorphic tracking shot as chef enters the neon kitchen."
    mock_client.models.generate_content.return_value = mock_resp
    live_agent._genai_client = mock_client

    raw_timed = "[0-3s] Chef enters. [3-6s] Chef flips wok. [6-10s] Chef plates neon ramen."
    optimized = live_agent.optimize_shot_prompt(raw_timed, style_tone="Cyberpunk")
    assert "[0-3s]" in optimized
    assert "[3-6s]" in optimized
    assert "[6-10s]" in optimized

    # Verify _ensure_shot_temporal_beats does not duplicate partial timecodes
    partial = "[0-3s] Enters arena. [3-6s] Draws blade."
    beat_fixed = live_agent._ensure_shot_temporal_beats(partial)
    assert beat_fixed.count("[0-3s]") == 1
    assert beat_fixed.count("[3-6s]") == 1
    assert beat_fixed.count("[6-10s]") == 1


def test_expand_vision_with_screenplay_script_preserves_aesthetic_tags_in_style_lighting():
    agent = StoryboardAgent(mock_mode=True)
    shots = agent.expand_vision(
        concept="Samurai duel",
        style_tone="Cyberpunk Drift",
        aesthetic_tags=["Chrome Armor", "Laser Fog"],
        screenplay_script="[0-5s]\nACTION: Samurai draws blade.\n[5-10s]\nACTION: Samurai strikes.",
    )
    assert len(shots) == 2
    for s in shots:
        assert "Cyberpunk Drift" in s.style_lighting
        assert "Chrome Armor" in s.style_lighting
        assert "Laser Fog" in s.style_lighting
