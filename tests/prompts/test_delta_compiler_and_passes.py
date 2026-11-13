from __future__ import annotations

from omnimash.prompts.delta_compiler import (
    I2VDeltaPromptSpec,
    KeyframeModularPromptSpec,
    calculate_shot_word_budget,
    convert_legacy_tags_to_omni_1_2_natural_language,
    format_unquoted_video_dialogue,
)
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
