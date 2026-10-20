import time
import pytest

from omnimash.prompts.character_roles import CharacterRole
from omnimash.prompts.screenplay import (
    parse_directors_notes,
    parse_screenplay_script,
    parse_timecoded_script,
    validate_prompt_input_lengths,
)


def test_parse_directors_notes():
    script = (
        "[DIRECTOR'S NOTES]\n"
        "- Tone: High-energy 90s Rap Battle\n"
        "- Relational Dynamic: Intense rivalry\n\n"
        "[0-4s]\n"
        "ACTION: Dumble steps up.\n"
    )
    notes = parse_directors_notes(script)
    assert notes["tone"] == "High-energy 90s Rap Battle"
    assert notes["relational_dynamic"] == "Intense rivalry"


def test_parse_timecoded_script_unification_and_chunking():
    # CORR-01 & CORR-02: Scripts with blocks > 10.0s must be automatically split into <=10.0s chunks
    script = "[0-25s] Action: Long continuous wand duel between wizards.\nDialogue: Harry: 'Never surrender!'"
    chunks = parse_timecoded_script(script)
    assert len(chunks) == 3
    assert all(c["duration_seconds"] <= 10.0 for c in chunks)
    assert chunks[0]["start_seconds"] == 0.0
    assert chunks[0]["end_seconds"] == 10.0
    assert chunks[1]["start_seconds"] == 10.0
    assert chunks[1]["end_seconds"] == 20.0
    assert chunks[2]["start_seconds"] == 20.0
    assert chunks[2]["end_seconds"] == 25.0


def test_parse_screenplay_script_redos_immunity():
    # SEC-01: Adversarial malformed screenplay text with nested unclosed quotes/brackets
    adversarial = "Character " * 200 + ': ("' + " a " * 500 + "... " + "!" * 500
    t0 = time.perf_counter()
    res = parse_screenplay_script(adversarial)
    elapsed = time.perf_counter() - t0
    # Must finish in milliseconds without catastrophic backtracking
    assert elapsed < 0.2
    assert isinstance(res, dict)


def test_validate_prompt_input_lengths_rejects_huge_inputs():
    # SEC-02: Input length bounds
    with pytest.raises(ValueError, match="Screenplay script exceeds maximum allowed length"):
        validate_prompt_input_lengths(screenplay_script="a" * 20001)

    with pytest.raises(ValueError, match="Concept description exceeds maximum allowed length"):
        validate_prompt_input_lengths(concept="b" * 2001)

    # Valid lengths pass without error
    validate_prompt_input_lengths(concept="Normal concept", screenplay_script="Normal script")


def test_parse_screenplay_character_role_matching():
    characters = [
        CharacterRole(role_id="Role A", name="Harry Potter", description="Wizard"),
        CharacterRole(role_id="Role B", name="Severus Snape", description="Potion master"),
    ]
    script = '[0-4s] Snape: (Stepping forward. Low rumble.) "Silence!"\n[4-8s] Harry: "Yes sir."'
    blocks = parse_timecoded_script(script, characters=characters)
    assert len(blocks) == 2
    assert blocks[0]["active_roles"] == ["Role B"]
    assert blocks[1]["active_roles"] == ["Role A"]
