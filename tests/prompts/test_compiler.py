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
    assert "10-second" in parts.motion or "nodding" in parts.motion

    full_prompt = parts.to_full_prompt()
    assert "[SUBJECT ANCHOR]:" in full_prompt
    assert "[AESTHETIC INJECTION]:" in full_prompt


def test_prompt_compiler_lock_and_isolate_delta():
    compiler = PromptCompiler()
    delta = compiler.compile_delta(delta_instruction="make his chain bigger")
    assert isinstance(delta, CompiledDeltaPrompt)
    assert "[PRESERVATION LOCK]:" in delta.to_delta_prompt()
    assert "Maintain exact subject face" in delta.preservation_lock
    assert "[ISOLATED DIFF]:" in delta.to_delta_prompt()
    assert "make his chain bigger" in delta.isolated_diff
