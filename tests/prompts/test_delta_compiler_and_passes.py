from __future__ import annotations

from omnimash.prompts.delta_compiler import (
    I2VDeltaPromptSpec,
    KeyframeModularPromptSpec,
    calculate_shot_word_budget,
    convert_legacy_tags_to_omni_1_2_natural_language,
    format_unquoted_video_dialogue,
)
from omnimash.prompts.preflight_linter import PreFlightGatekeeper
from omnimash.prompts.shot_pair_planner import (
    TwoShotHardCutPlan,
    build_two_shot_hard_cut_plan,
)


def test_format_unquoted_video_dialogue_strips_quotes_and_timecodes():
    """Spoken video dialogue must strip timecode brackets and quotation marks while preserving contractions."""
    formatted = format_unquoted_video_dialogue(
        speaker_descriptor="the tattooed man in the blue aviator sunglasses",
        voice_style="Cold, unhurried, deadpan Glasgow Scottish accent",
        dialogue_text='[0-3s] "Never got caught slippin\', ken... kept the "drip" and control."',
    )
    assert "[0-3s]" not in formatted
    assert '"' not in formatted
    assert "“" not in formatted
    assert "”" not in formatted
    assert (
        formatted
        == "In a cold, unhurried, deadpan Glasgow Scottish accent, the tattooed man in the blue aviator sunglasses says: Never got caught slippin', ken... kept the drip and control."
    )


def test_calculate_shot_word_budget_enforces_cut_buffer_and_3_5_wps_cap():
    """Word budget subtracts 0.7s cut buffer and enforces both WPM and 3.5 WPS caps."""
    assert calculate_shot_word_budget(7.0, wpm=130) == 13
    # High WPM must still be capped at floor((10.0 - 0.7) * 3.5) = 32
    assert calculate_shot_word_budget(10.0, wpm=300) == 32
    assert calculate_shot_word_budget(0.5, wpm=130) == 0


def test_i2v_delta_prompt_spec_compiles_untimed_motion_dialogue_sound_whitelist_and_starting_frame_binding():
    """I2VDeltaPromptSpec compiles an untimed single-paragraph delta prompt with sound whitelist and starting frame binding."""
    spec = I2VDeltaPromptSpec(
        camera_motion="[0-3s] Locked-off camera with a very slow push in",
        subject_action="[3-6s] He completes his last step, stops, and lifts his chin",
        speaker_descriptor="the tattooed man in the blue aviator sunglasses",
        voice_style="cold, unhurried, deadpan Glasgow Scottish accent",
        spoken_dialogue='"Never got caught slippin, ken."',
        post_dialogue_hold="After the line he holds still with a faint smirk",
        environmental_motion="Rain falls steadily through the cool backlight behind him",
        ambient_noise="steady rain on stone and distant wind",
        explicit_sound_whitelist=["his voice", "the rain", "the wind"],
    )
    compiled = spec.compile()
    assert "[0-3s]" not in compiled
    assert "[3-6s]" not in compiled
    assert '"' not in compiled
    assert "says: Never got caught slippin, ken." in compiled
    assert "After the line he holds still with a faint smirk." in compiled
    assert "Ambient noise: steady rain on stone and distant wind." in compiled
    assert "The only sounds are his voice, the rain, and the wind." in compiled
    assert compiled.endswith("Use this image as the starting frame.")

    spec_no_binding = spec.model_copy(update={"include_starting_frame_binding": False})
    compiled_no_binding = spec_no_binding.compile()
    assert compiled_no_binding.endswith("The only sounds are his voice, the rain, and the wind.")
    assert "Use this image as the starting frame." not in compiled_no_binding


def test_build_two_shot_hard_cut_plan_pairs_28mm_wide_and_85mm_mcu_with_shared_location():
    """Two-shot hard-cut planner pairs a 28mm wide establishing shot with an 85mm MCU sharing verbatim location."""
    shared_loc = (
        "Rain-slicked black basalt Gothic courtyard archway with pointed vaults and iron lanterns"
    )
    plan = build_two_shot_hard_cut_plan(
        scene_id="scene_01",
        character_name="the tattooed wizard",
        speaker_descriptor="the tattooed man in the blue aviator sunglasses",
        voice_style="cold, unhurried, deadpan Glasgow Scottish accent",
        fixed_character_block="Tattooed man with blue aviator sunglasses and dark tailored overcoat",
        wetness_lighting_block="Damp hair strands, wet specular skin sheen, cool cyan-indigo storm backlight",
        matched_location_block=shared_loc,
        wide_action_summary="steps forward out of the shadowed threshold",
        mcu_spoken_line="Never got caught slippin, ken.",
        narrator_text="Back from the fortress.",
    )
    assert isinstance(plan, TwoShotHardCutPlan)
    assert isinstance(plan.shot_a_keyframe_spec, KeyframeModularPromptSpec)
    assert isinstance(plan.shot_b_keyframe_spec, KeyframeModularPromptSpec)
    assert plan.hard_cut_timestamp_sec == 4.5
    assert plan.shot_a_render_duration_sec == 5
    assert plan.shot_b_render_duration_sec == 7

    kf_a = plan.shot_a_keyframe_spec.compile()
    kf_b = plan.shot_b_keyframe_spec.compile()
    assert "28mm" in kf_a
    assert "85mm" in kf_b
    assert shared_loc in kf_a
    assert shared_loc in kf_b

    i2v_a = plan.shot_a_i2v_spec.compile()
    i2v_b = plan.shot_b_i2v_spec.compile()
    assert "says:" not in i2v_a
    assert "says: Never got caught slippin, ken." in i2v_b
    assert i2v_a.endswith("Use this image as the starting frame.")
    assert i2v_b.endswith("Use this image as the starting frame.")


def test_convert_legacy_tags_to_omni_1_2_natural_language():
    """Legacy bracket/tag syntax converts cleanly into natural-language positional references."""
    legacy = (
        "[# Sources <FIRST_FRAME>@KeyframeSeed]\n"
        "[# References <IMAGE_REF_0>@Image2]\n"
        "Role A (<IMAGE_REF_0>@Image2) walks from <FIRST_FRAME>@KeyframeSeed."
    )
    converted = convert_legacy_tags_to_omni_1_2_natural_language(legacy)
    assert "<FIRST_FRAME>" not in converted
    assert "<IMAGE_REF_0>" not in converted
    assert "[# Sources" not in converted
    assert "[# References" not in converted
    assert "@Image2" not in converted
    assert "reference image 2" in converted.lower() or "image 2" in converted.lower()
    assert "first image" in converted.lower() or "starting frame" in converted.lower()


def test_pass7_negative_physical_clauses_parameterized_by_style_preset():
    """Pass 7 rewrites general negations to domain-neutral positive descriptions and restricts gothic basalt rewrites to gothic_trailer."""
    raw = (
        "Wide shot in modern neon loft, no background music, no subtitles, "
        "zero water on face, no harsh white searchlight, zero fire embers, "
        "no wooden watchtowers."
    )
    repaired_default, v_default = PreFlightGatekeeper.repair_negative_physical_clauses(raw)
    assert len(v_default) >= 5
    assert all(v.rule_id == "NEGATIVE_PHYSICAL_CLAUSE" for v in v_default)
    assert "no background music" not in repaired_default.lower()
    assert "no subtitles" not in repaired_default.lower()
    assert "zero water on face" not in repaired_default.lower()
    assert "no harsh white searchlight" not in repaired_default.lower()
    assert "zero fire embers" not in repaired_default.lower()
    # Non-gothic default MUST NOT inject gothic basalt gargoyles
    assert "basalt gargoyles" not in repaired_default.lower()
    assert "gargoyles" not in repaired_default.lower()

    repaired_gothic, v_gothic = PreFlightGatekeeper.repair_negative_physical_clauses(
        "Castle gate with no wooden watchtowers and no harsh white searchlight.",
        style_preset="gothic_trailer",
    )
    assert len(v_gothic) >= 2
    assert "basalt" in repaired_gothic.lower()
    assert "gargoyles" in repaired_gothic.lower()

    # Silent video directive must remain untouched
    silent_prompt = "Audio: Silent video. No background music, no audio."
    repaired_silent, v_silent = PreFlightGatekeeper.repair_negative_physical_clauses(silent_prompt)
    assert repaired_silent == silent_prompt
    assert v_silent == []


def test_pass8_bilateral_prop_locks_works_with_1_or_2_args_and_various_props():
    """Pass 8 triggers on persistent held props + handoff verbs with neutral/character-aware phrasing and thin-prop separation."""
    from types import SimpleNamespace

    # 1-arg call with leather briefcase + reaches out + wand thin prop
    raw_1arg = (
        "Role A carries a leather briefcase and reaches out to pick up a silver wand "
        "above a bright marble counter."
    )
    repaired_1arg, v_1arg = PreFlightGatekeeper.repair_bilateral_prop_locks(raw_1arg)
    rule_ids_1 = {v.rule_id for v in v_1arg}
    assert "BILATERAL_PROP_LOCK" in rule_ids_1
    assert "PROP_FIGURE_GROUND_LOCK" in rule_ids_1
    assert "leather briefcase" in repaired_1arg.lower()
    assert "he holds the cup" not in repaired_1arg.lower()
    assert "left hand" in repaired_1arg.lower()
    assert "right hand" in repaired_1arg.lower()
    assert "silhouetted cleanly against" in repaired_1arg.lower()

    # Test all required persistent prop keywords
    for prop in (
        "styrofoam cup",
        "double cup",
        "chalice",
        "coffee cup",
        "phone",
        "handbag",
    ):
        txt = f"Subject holds a {prop} and takes the envelope."
        rep, viols = PreFlightGatekeeper.repair_bilateral_prop_locks(txt)
        assert any(v.rule_id == "BILATERAL_PROP_LOCK" for v in viols), f"Failed for {prop}"
        assert prop in rep.lower()

    # 2-arg call with character.signature_prop and Wardrobe prop
    char_with_sig = SimpleNamespace(
        role_id="Role A",
        name="Elena",
        description="Courier",
        signature_prop="brass lantern",
        wardrobe="",
    )
    repaired_2arg, v_2arg = PreFlightGatekeeper.repair_bilateral_prop_locks(
        "Elena grabs the parcel from the shelf.",
        characters=[char_with_sig],
    )
    assert any(v.rule_id == "BILATERAL_PROP_LOCK" for v in v_2arg)
    assert "Elena" in repaired_2arg
    assert "brass lantern" in repaired_2arg.lower()

    # Wardrobe prop in prompt text
    wardrobe_prompt = (
        "- Role A (Character Reference): Courier [Wardrobe: dark coat, leather satchel]\n"
        "Courier picks up the key."
    )
    repaired_w, v_w = PreFlightGatekeeper.repair_bilateral_prop_locks(wardrobe_prompt)
    assert any(v.rule_id == "BILATERAL_PROP_LOCK" for v in v_w)
    assert "leather satchel" in repaired_w.lower()


def test_pass9_dialogue_quotes_narrator_strip_and_word_budget():
    """Pass 9 strips spoken dialogue quotes, optionally strips Offscreen Narrator lines, and flags WORD_BUDGET_EXCEEDED."""
    prompt = (
        "### SCENE INSTRUCTIONS\n"
        'On-Screen Displayed Text / Title Card: "CHAPTER ONE"\n'
        "Audio: instrumental 140 BPM Trap.\n\n"
        "### TIMELINE\n"
        '- Offscreen Narrator (Deep Cinematic Voice): "In a shadowed world." (off-screen)\n'
        '- Spoken Dialogue (Role A): "One two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen."\n'
        'Role A says: "Keep the title card intact."'
    )
    repaired, violations = PreFlightGatekeeper.repair_dialogue_quotes_and_word_budget(
        prompt,
        shot_seconds=5.0,
        strip_offscreen_narrator=True,
    )
    rule_ids = {v.rule_id for v in violations}
    assert "DIALOGUE_QUOTES" in rule_ids
    assert "OFFSCREEN_NARRATOR_STRIPPED" in rule_ids
    assert "WORD_BUDGET_EXCEEDED" in rule_ids

    # Title card quotes must remain intact; spoken quotes must be stripped
    assert '"CHAPTER ONE"' in repaired
    assert "Offscreen Narrator" not in repaired
    assert (
        "- Spoken Dialogue (Role A): One two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen."
        in repaired
    )
    assert "Role A says: Keep the title card intact." in repaired

    budget_violation = next(v for v in violations if v.rule_id == "WORD_BUDGET_EXCEEDED")
    assert budget_violation.repaired is False


def test_lint_and_repair_integrates_passes_7_to_9_and_pass4_detects_unquoted_says():
    """PreFlightGatekeeper.lint_and_repair applies Passes 7-9 and Pass 4 detects unquoted 'says: line' dialogue."""
    prompt = (
        "### INPUT ROLES & REFERENCES\nNone.\n\n"
        "### CHARACTER PROFILES\n- Role A: Courier.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Environment: Studio with no harsh white searchlight.\n"
        "Audio: 120 BPM Synth.\n\n"
        "### TIMELINE\n"
        'Role A holds a coffee cup and reaches out for the pass. Role A says: "We move now."'
    )
    result = PreFlightGatekeeper.lint_and_repair(
        prompt_text=prompt,
        shot_seconds=5.0,
    )
    assert "no harsh white searchlight" not in result.repaired_prompt.lower()
    assert "basalt gargoyles" not in result.repaired_prompt.lower()
    assert "left hand" in result.repaired_prompt.lower()
    assert "says: We move now." in result.repaired_prompt
    assert 'says: "We move now."' not in result.repaired_prompt
    assert "instrumental 120 BPM Synth" in result.repaired_prompt
    assert PreFlightGatekeeper.CANONICAL_DUCKING_CLAUSE in result.repaired_prompt


def test_compilers_emit_unquoted_dialogue_and_skip_forced_timecodes_for_single_keyframe_i2v():
    """journey3 & PromptCompiler emit unquoted spoken dialogue and skip forced [0-3s]/[3-6s]/[6-10s] slicing for single-keyframe I2V."""
    from omnimash.prompts.character_roles import CharacterRole
    from omnimash.prompts.compiler import PromptCompiler, SceneDirective
    from omnimash.prompts.journey3 import compile_journey3_shot_prompt

    chars = [
        CharacterRole(
            role_id="Role A",
            name="Courier",
            description="Tattooed courier in dark coat",
            voice_style="Deadpan Scottish accent",
        )
    ]

    j3_i2v = compile_journey3_shot_prompt(
        shot_number=1,
        action_directive="Slow push in as he lifts his chin",
        characters=chars,
        timeline_dialogue='Courier: "Never got caught slippin."',
        keyframe_image_url="https://example.com/kf.png",
        compilation_mode="i2v_delta_only",
    )
    assert "[0-3s]" not in j3_i2v
    assert "[3-6s]" not in j3_i2v
    assert "[6-10s]" not in j3_i2v
    assert '"' not in j3_i2v
    assert "says: Never got caught slippin." in j3_i2v
    assert j3_i2v.endswith("Use this image as the starting frame.")

    compiler = PromptCompiler(mock_mode=True)
    sb_i2v = compiler.compile_storyboard(
        concept="Courier arrival",
        characters=chars,
        scenes=[
            SceneDirective(
                scene_number=1,
                active_roles=["Role A"],
                action="Steps forward into threshold",
                dialogue='Courier: "Keep moving."',
            )
        ],
        has_keyframe_seed=True,
        keyframe_image_url="https://example.com/kf.png",
        compilation_mode="i2v_delta_only",
    )
    assert "[0-3s]" not in sb_i2v
    assert "[3-6s]" not in sb_i2v
    assert "[6-10s]" not in sb_i2v
    assert '"' not in sb_i2v
    assert "says: Keep moving." in sb_i2v
    assert sb_i2v.endswith("Use this image as the starting frame.")
