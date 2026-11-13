"""Two-Shot Hard-Cut Pair Planner (Wide Establishing Shot A + Hard Cut on Action + MCU Shot B)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from omnimash.prompts.delta_compiler import I2VDeltaPromptSpec, KeyframeModularPromptSpec


class TwoShotHardCutPlan(BaseModel):
    """Specification for a 2-shot hard-cut scene (Wide Establishing Shot A + MCU Shot B)."""

    scene_id: str
    total_edit_duration_sec: float = 11.5
    hard_cut_timestamp_sec: float = 4.5
    shot_a_render_duration_sec: int = Field(default=5, ge=3, le=15)
    shot_b_render_duration_sec: int = Field(default=7, ge=3, le=15)
    shot_a_keyframe_spec: KeyframeModularPromptSpec
    shot_b_keyframe_spec: KeyframeModularPromptSpec
    shot_a_i2v_spec: I2VDeltaPromptSpec
    shot_b_i2v_spec: I2VDeltaPromptSpec
    narrator_text: str = ""
    narrator_start_sec: float = 0.30
    guillotine_start_sec: float = 5.50
    punchline_808_sec: float = 9.78
    root_note_808: str = "D1"


def build_two_shot_hard_cut_plan(
    *,
    scene_id: str,
    character_name: str,
    speaker_descriptor: str,
    voice_style: str,
    fixed_character_block: str,
    wetness_lighting_block: str,
    matched_location_block: str,
    wide_action_summary: str,
    mcu_spoken_line: str,
    narrator_text: str = "",
    ambient_noise: str = "steady rain on stone and distant wind",
    root_note_808: str = "D1",
) -> TwoShotHardCutPlan:
    """Constructs a canonical Shot A (Wide 28mm) + Shot B (MCU 85mm) hard-cut scene plan."""
    shot_a_kf = KeyframeModularPromptSpec(
        camera_block=(
            "Wide three-quarter angle establishing shot from about 25 to 30 meters outside the threshold, "
            "28mm lens at f/2.8. The camera stands well to the left of the centerline looking diagonally across "
            "an empty approach road in the foreground so the threshold sits on the right third of the frame. "
            f"{character_name} is small in the distance—occupying 15% to 20% of the vertical frame height—"
            f"deep inside the shadowed archway threshold, {wide_action_summary}"
        ),
        fixed_character_block=fixed_character_block,
        wetness_lighting_block=wetness_lighting_block,
        matched_location_block=matched_location_block,
    )
    shot_b_kf = KeyframeModularPromptSpec(
        camera_block=(
            "Medium close-up shot (chest-up, eye level), 85mm lens at f/2.0 with shallow depth of field. "
            f"{character_name} stands directly inside the threshold filling the center of the frame from the chest up"
        ),
        fixed_character_block=fixed_character_block,
        wetness_lighting_block=wetness_lighting_block,
        matched_location_block=matched_location_block,
    )
    shot_a_i2v = I2VDeltaPromptSpec(
        camera_motion=(
            "Slow, steady camera push-in toward the threshold with real 3D parallax as foreground "
            "elements shift against the receding architecture"
        ),
        subject_action=f"He walks forward in a slow, unbothered stride ({wide_action_summary})",
        spoken_dialogue="",
        environmental_motion="Atmospheric particles move steadily through the backlight",
        ambient_noise=ambient_noise,
        explicit_sound_whitelist=["the rain", "the wind", "distant thunder"],
    )
    shot_b_i2v = I2VDeltaPromptSpec(
        camera_motion="Locked-off camera with a very slow push in",
        subject_action="He completes his last step, stops, lifts his chin slightly, and speaks to the lens",
        speaker_descriptor=speaker_descriptor,
        voice_style=voice_style,
        spoken_dialogue=mcu_spoken_line,
        post_dialogue_hold="After the line he holds still with a faint smirk",
        environmental_motion="Rain falls steadily through the cool backlight behind him",
        ambient_noise=ambient_noise,
        explicit_sound_whitelist=["his voice", "the rain", "the wind"],
    )
    return TwoShotHardCutPlan(
        scene_id=scene_id,
        shot_a_keyframe_spec=shot_a_kf,
        shot_b_keyframe_spec=shot_b_kf,
        shot_a_i2v_spec=shot_a_i2v,
        shot_b_i2v_spec=shot_b_i2v,
        narrator_text=narrator_text,
        root_note_808=root_note_808,
    )


__all__ = [
    "TwoShotHardCutPlan",
    "build_two_shot_hard_cut_plan",
]
