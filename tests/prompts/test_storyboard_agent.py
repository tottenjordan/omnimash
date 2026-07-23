from omnimash.prompts.compiler import CharacterRole
from omnimash.prompts.storyboard_agent import (
    StoryboardAgent,
    StoryboardShot,
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
    prompt = shot.to_omni_flash_prompt(
        role_mappings="[ROLE DEFINITIONS]\n- Role A (Snape)"
    )
    assert "[ROLE DEFINITIONS]" in prompt
    assert "Shot 1 (0-10s)" in prompt
    assert "- Action / Subject: Snape stirring a glowing purple potion carefully" in prompt
    assert (
        "- Location: A dimly lit stone dungeon classroom with bubbling cauldrons"
        in prompt
    )
    assert (
        "- Style & Lighting: Cinematic, realistic, lit by a warm off-screen fire with soft shadows"
        in prompt
    )
    assert "- Shot Framing & Motion: Static medium shot" in prompt
    assert (
        "- Audio Soundscape: Slow booming 808 trap beat with bubbling liquid sounds"
        in prompt
    )


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
    agent = StoryboardAgent(mock_mode=False)
    shots = agent.expand_vision(
        concept="30-second Dripwarts video",
        style_tone="Gritty 90s rap video",
        target_duration=30.0,
    )
    assert len(shots) >= 3
    assert all(s.duration_seconds <= 10.0 for s in shots)


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
    assert parsed[0] == (3.0, "Character A enters dungeon")
    assert parsed[1] == (3.0, "Character B turns up 808 trap beat")
    assert parsed[2] == (4.0, "Character A and Character B perform synchronized dance")
    assert parsed[3] == (5.5, "Half-time intro scene")
    assert parsed[4] == (3.0, "Plain numbers without s suffix")


def test_parse_timecoded_script_empty_or_invalid():
    assert parse_timecoded_script("") == []
    assert parse_timecoded_script("No timecodes here at all.") == []


def test_expand_vision_with_screenplay_script():
    agent = StoryboardAgent(mock_mode=True)
    script = (
        "[0-3s] Snape enters the potion room with dramatic flair.\n"
        "[3-7s] Dumbledore nods in approval while 808 sub-bass drops.\n"
        "[7-10s] Both wizards strike a final freeze-frame pose."
    )
    chars = [
        CharacterRole(role_id="Role A", name="Snape", description="Severe wizard"),
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
    assert "Role A (Snape)" in shots[0].action
    assert "Role B (Dumbledore)" in shots[1].action


def test_expand_vision_celebrity_sanitization():
    agent = StoryboardAgent(mock_mode=True)
    script = (
        "[0-4s] Gordon Ramsay yells at line cook in high energy kitchen.\n"
        "[4-10s] Drake drops a melodic verse while Jeezy counts cash."
    )
    shots = agent.expand_vision(
        concept="Celebrity kitchen rap battle",
        style_tone="Trap Parody",
        target_duration=10.0,
        screenplay_script=script,
    )
    assert len(shots) == 2
    assert "Gordon Ramsay" not in shots[0].action
    assert "Fiery Master Chef" in shots[0].action
    assert "Drake" not in shots[1].action
    assert "Melodic Rap Star" in shots[1].action
    assert "Jeezy" not in shots[1].action
    assert ("Atlanta Rap Artist" in shots[1].action or "Atlanta Rap Legend" in shots[1].action)


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


