from omnimash.prompts.compiler import (
    CompiledDeltaPrompt,
    CompiledPromptParts,
    PromptCompiler,
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
