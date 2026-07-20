from omnimash.prompts.compiler import (
    CharacterRole,
    CompiledDeltaPrompt,
    CompiledPromptParts,
    PromptCompiler,
    SceneDirective,
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
        "- Role A (Harry): Wizard with round glasses [Style: Red Gucci Tracksuit, Cartier Glasses] (Ref: gs://bucket/harry.jpg)"
        in prompt
    )


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
        "Background Beat: 140 BPM Heavy 808 Trap (ducked at 15% volume under dialogue)"
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
