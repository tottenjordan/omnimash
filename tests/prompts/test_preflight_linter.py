from __future__ import annotations

from omnimash.prompts.character_roles import CharacterRole
from omnimash.prompts.models import PreFlightLintResult, PreFlightViolation
from omnimash.prompts.preflight_linter import PreFlightGatekeeper


def test_repair_tag_collisions_stacked_image_tags():
    """Stacked image reference tags (e.g. <IMAGE_REF_0> <IMAGE_REF_1>) should keep only canonical tag."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0> <IMAGE_REF_1>@Image1\n"
        "- Role A: gs://bucket/char.jpg (@Image1)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Detective.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic.\n"
        "Environment: Alley.\n"
        "Audio: instrumental ambient.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Walking."
    )
    repaired, violations = PreFlightGatekeeper.repair_tag_collisions(prompt)
    assert "<IMAGE_REF_0>@Image1" in repaired
    assert "<IMAGE_REF_1>" not in repaired
    assert len(violations) >= 1
    assert isinstance(violations[0], PreFlightViolation)
    assert violations[0].rule_id == "TAG_COLLISION"
    assert violations[0].category == "tagging"
    assert violations[0].repaired is True


def test_repair_tag_collisions_duplicate_image_tokens():
    """Duplicate @Image tokens on a single role should be collapsed to canonical tag."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0>@Image1\n"
        "- Role A: gs://bucket/char.jpg @Image1 @Image1\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (@Image1 @Image1): Detective.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic.\n"
        "Environment: Alley.\n"
        "Audio: instrumental ambient.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Detective (@Image1 @Image1) walks."
    )
    repaired, violations = PreFlightGatekeeper.repair_tag_collisions(prompt)
    assert "@Image1 @Image1" not in repaired
    assert "@Image1" in repaired
    assert len(violations) >= 1
    assert any(v.rule_id == "TAG_COLLISION" for v in violations)


def test_repair_tag_collisions_unattached_phantom_tokens():
    """Phantom tokens like 'KeyframeSeed' when not attached to <FIRST_FRAME> should be removed."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0>@Image1 KeyframeSeed\n"
        "- Role A: gs://bucket/char.jpg (@Image1)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Detective.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic.\n"
        "Environment: Alley.\n"
        "Audio: instrumental ambient.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Walking."
    )
    repaired, violations = PreFlightGatekeeper.repair_tag_collisions(prompt)
    assert "KeyframeSeed" not in repaired
    assert len(violations) >= 1
    assert any(v.rule_id == "TAG_COLLISION" for v in violations)


def test_repair_keyframe_offsets_single_keyframe():
    """When keyframe seed is provided, character references must start at @Image2."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "[# Sources <FIRST_FRAME>@KeyframeSeed]\n"
        "[# References <IMAGE_REF_0>@Image1]\n"
        "- Role A (Character Reference): gs://bucket/char.jpg (@Image1)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (Detective) (@Image1): Grim posture.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic.\n"
        "Environment: Alley.\n"
        "Audio: instrumental ambient.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Detective (@Image1) inspects clue."
    )
    repaired, violations = PreFlightGatekeeper.repair_keyframe_offsets(
        prompt, keyframe_image_url="https://storage.googleapis.com/b/seed.png"
    )
    assert "<FIRST_FRAME>@KeyframeSeed" in repaired
    assert "<IMAGE_REF_0>@Image2" in repaired
    assert "(@Image2)" in repaired
    assert "@Image1" not in repaired
    assert len(violations) >= 1
    assert violations[0].rule_id == "KEYFRAME_OFFSET"


def test_repair_keyframe_offsets_dual_keyframe_loop():
    """Dual-keyframe or seamless loop requires character references to start at @Image3."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "[# Sources <FIRST_FRAME>@Image1, <LAST_FRAME>@Image2]\n"
        "[# References <IMAGE_REF_0>@Image1, <IMAGE_REF_1>@Image2]\n"
        "- Role A: gs://bucket/a.jpg (@Image1)\n"
        "- Role B: gs://bucket/b.jpg (@Image2)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (@Image1): Lead.\n"
        "- Role B (@Image2): Rival.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic.\n"
        "Environment: Arena.\n"
        "Audio: instrumental ambient.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Role A (@Image1) confronts Role B (@Image2)."
    )
    repaired, violations = PreFlightGatekeeper.repair_keyframe_offsets(
        prompt, is_seamless_loop=True
    )
    assert "<FIRST_FRAME>@Image1" in repaired
    assert "<LAST_FRAME>@Image2" in repaired
    assert "<IMAGE_REF_0>@Image3" in repaired
    assert "<IMAGE_REF_1>@Image4" in repaired
    assert "Role A (@Image3)" in repaired
    assert "Role B (@Image4)" in repaired
    assert len(violations) >= 1


def test_repair_zero_wardrobe_redundancy_with_reference():
    """Characters with reference sheets must have conflicting clothing descriptions scrubbed."""
    characters = [
        CharacterRole(
            role_id="Role A",
            name="Detective",
            description="Severe expression, wearing a dark trenchcoat and wool sweater, sharp jawline.",
            reference_url="https://storage.googleapis.com/b/detective.jpg",
            voice_style="Gravelly whisper",
        )
    ]
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0>@Image2\n"
        "- Role A: gs://bucket/detective.jpg (@Image2)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (Detective) (@Image2): Severe expression, wearing a dark trenchcoat and wool sweater, sharp jawline. Voice: Gravelly whisper.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Noir shadows.\n"
        "Environment: Office.\n"
        "Audio: instrumental jazz.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Detective (@Image2) looks at map."
    )
    repaired, violations = PreFlightGatekeeper.repair_zero_wardrobe_redundancy(
        prompt, characters=characters
    )
    assert "wearing a dark trenchcoat and wool sweater" not in repaired
    assert (
        "Enforce Zero Wardrobe Redundancy: Visual appearance locked to reference sheet @Image2"
        in repaired
    )
    assert "Severe expression" in repaired
    assert "sharp jawline" in repaired
    assert "Gravelly whisper" in repaired
    assert len(violations) >= 1
    assert violations[0].rule_id == "ZERO_WARDROBE_REDUNDANCY"


def test_repair_zero_wardrobe_redundancy_without_reference():
    """Characters without reference sheets retain wardrobe prose without violation."""
    characters = [
        CharacterRole(
            role_id="Role A",
            name="Detective",
            description="Severe expression, wearing a dark trenchcoat and wool sweater.",
            reference_url=None,
        )
    ]
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "None.\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (Detective): Severe expression, wearing a dark trenchcoat and wool sweater.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Noir shadows.\n"
        "Environment: Office.\n"
        "Audio: instrumental jazz.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Detective sits."
    )
    repaired, violations = PreFlightGatekeeper.repair_zero_wardrobe_redundancy(
        prompt, characters=characters
    )
    assert "wearing a dark trenchcoat and wool sweater" in repaired
    assert len(violations) == 0


def test_repair_audio_ducking_with_dialogue():
    """Spoken dialogue triggers instrumental prefix check and canonical ducking clause injection."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "None.\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Speaker.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic.\n"
        "Environment: Studio.\n"
        "Audio: 140 BPM Trap.\n\n"
        "### TIMELINE\n"
        '[0-3s] Action: Speaker talks. Dialogue: Role A: "We need to act now."'
    )
    repaired, violations = PreFlightGatekeeper.repair_audio_ducking(prompt, has_dialogue=True)
    assert "instrumental 140 BPM Trap" in repaired
    assert (
        "Ensure the background music ducks under the spoken dialogue so the voice is clear, front-and-center, and intelligible."
        in repaired
    )
    assert len(violations) >= 1
    assert violations[0].rule_id == "AUDIO_DUCKING"


def test_repair_audio_ducking_already_compliant():
    """Already ducked and instrumental audio needs no modification."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "None.\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Speaker.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic.\n"
        "Environment: Studio.\n"
        "Audio: instrumental 140 BPM Trap. Ensure the background music ducks under the spoken dialogue so the voice is clear, front-and-center, and intelligible.\n\n"
        "### TIMELINE\n"
        '[0-3s] Action: Speaker talks. Dialogue: Role A: "We need to act now."'
    )
    repaired, violations = PreFlightGatekeeper.repair_audio_ducking(prompt, has_dialogue=True)
    assert repaired == prompt
    assert len(violations) == 0


def test_repair_spatial_staging_multiple_reference_characters():
    """2 or more characters with reference sheets must declare spatial staging in Block 3."""
    characters = [
        CharacterRole(
            role_id="Role A",
            name="Detective",
            description="Grim.",
            reference_url="https://storage.googleapis.com/b/det.jpg",
        ),
        CharacterRole(
            role_id="Role B",
            name="Suspect",
            description="Nervous.",
            reference_url="https://storage.googleapis.com/b/susp.jpg",
        ),
    ]
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0>@Image1\n"
        "<IMAGE_REF_1>@Image2\n"
        "- Role A: gs://b/det.jpg (@Image1)\n"
        "- Role B: gs://b/susp.jpg (@Image2)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Detective.\n"
        "- Role B: Suspect.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic.\n"
        "Environment: Interrogation room.\n"
        "Audio: instrumental ambient.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Both stare."
    )
    repaired, violations = PreFlightGatekeeper.repair_spatial_staging(prompt, characters=characters)
    assert (
        "Spatial staging: [Role A] positioned on screen-left, [Role B] positioned on screen-right to maintain clear identity separation."
        in repaired
    )
    assert len(violations) >= 1
    assert violations[0].rule_id == "SPATIAL_STAGING"


def test_repair_spatial_staging_already_staged():
    """If screen-left or screen-right is already present, no staging injection needed."""
    characters = [
        CharacterRole(
            role_id="Role A",
            name="Detective",
            description="Grim.",
            reference_url="https://storage.googleapis.com/b/det.jpg",
        ),
        CharacterRole(
            role_id="Role B",
            name="Suspect",
            description="Nervous.",
            reference_url="https://storage.googleapis.com/b/susp.jpg",
        ),
    ]
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0>@Image1\n"
        "<IMAGE_REF_1>@Image2\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Detective.\n"
        "- Role B: Suspect.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic. Spatial staging: [Role A] on screen-left, [Role B] on screen-right.\n"
        "Environment: Interrogation room.\n"
        "Audio: instrumental ambient.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Both stare."
    )
    repaired, violations = PreFlightGatekeeper.repair_spatial_staging(prompt, characters=characters)
    assert repaired == prompt
    assert len(violations) == 0


def test_lint_and_repair_clean_prompt():
    """A fully compliant prompt returns is_valid=True and 0 violations."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "[# Sources <FIRST_FRAME>@KeyframeSeed]\n"
        "[# References <IMAGE_REF_0>@Image2]\n"
        "- Role A (Character Reference): gs://bucket/det.jpg (@Image2)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (Detective) (@Image2): Severe expression. Enforce Zero Wardrobe Redundancy: Visual appearance locked to reference sheet @Image2. Voice: Gravelly whisper.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: In a single continuous shot. No scene cuts. Noir lighting.\n"
        "Environment: Dim office.\n"
        "Audio: instrumental slow jazz. Ensure the background music ducks under the spoken dialogue so the voice is clear, front-and-center, and intelligible.\n\n"
        "### TIMELINE\n"
        '[0-3s] Action: Detective (@Image2) examines notes. Dialogue: Role A: "Found it."\n'
        "[3-6s] Action: Detective (@Image2) looks up.\n"
        "[6-10s] Action: Door clicks open."
    )
    result = PreFlightGatekeeper.lint_and_repair(
        prompt_text=prompt,
        keyframe_image_url="https://storage.googleapis.com/b/seed.png",
        has_dialogue=True,
    )
    assert isinstance(result, PreFlightLintResult)
    assert result.is_valid is True
    assert len(result.violations) == 0
    assert result.repaired_prompt == prompt


def test_lint_and_repair_simultaneous_violations():
    """End-to-end linting test repairing multiple simultaneous violations across all categories."""
    characters = [
        CharacterRole(
            role_id="Role A",
            name="Detective",
            description="Grim look, wearing an oversized trenchcoat and wool scarf.",
            reference_url="https://storage.googleapis.com/b/det.jpg",
            voice_style="Gravelly",
        ),
        CharacterRole(
            role_id="Role B",
            name="Suspect",
            description="Nervous, dressed in a red hoodie and baggy jeans.",
            reference_url="https://storage.googleapis.com/b/susp.jpg",
            voice_style="Fast whisper",
        ),
    ]
    # Prompt with:
    # 1. Stacked tag (<IMAGE_REF_0> <IMAGE_REF_1>) & duplicate @Image token & phantom KeyframeSeed
    # 2. Keyframe offset error (starting at @Image1 despite keyframe seed)
    # 3. Wardrobe prose for reference characters
    # 4. Audio beat missing 'instrumental' and missing ducking clause when dialogue exists
    # 5. Missing spatial staging for 2 reference characters
    dirty_prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "[# Sources <FIRST_FRAME>@KeyframeSeed]\n"
        "<IMAGE_REF_0> <IMAGE_REF_1>@Image1 @Image1 KeyframeSeed\n"
        "<IMAGE_REF_1>@Image2\n"
        "- Role A: gs://b/det.jpg (@Image1)\n"
        "- Role B: gs://b/susp.jpg (@Image2)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (Detective) (@Image1): Grim look, wearing an oversized trenchcoat and wool scarf. Voice: Gravelly.\n"
        "- Role B (Suspect) (@Image2): Nervous, dressed in a red hoodie and baggy jeans. Voice: Fast whisper.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic.\n"
        "Environment: Interrogation room.\n"
        "Audio: 130 BPM Dark Synth.\n\n"
        "### TIMELINE\n"
        '[0-3s] Action: Detective (@Image1) looks at Suspect (@Image2). Dialogue: Role A: "Confess."\n'
        '[3-6s] Action: Suspect (@Image2) shakes head. Dialogue: Role B: "I was not there."\n'
        "[6-10s] Action: Tension rises."
    )

    result = PreFlightGatekeeper.lint_and_repair(
        prompt_text=dirty_prompt,
        characters=characters,
        keyframe_image_url="https://storage.googleapis.com/b/seed.png",
        has_dialogue=True,
    )

    assert result.is_valid is False
    assert len(result.violations) >= 4

    repaired = result.repaired_prompt

    # 1. Stacked tags and phantom tokens cleaned
    assert "<IMAGE_REF_0> <IMAGE_REF_1>" not in repaired
    assert "@Image1 @Image1" not in repaired
    assert "KeyframeSeed\n" not in repaired

    # 2. Character references shifted to @Image2 and @Image3
    assert "<IMAGE_REF_0>@Image2" in repaired
    assert "<IMAGE_REF_1>@Image3" in repaired
    assert "Detective (@Image2)" in repaired
    assert "Suspect (@Image3)" in repaired

    # 3. Wardrobe scrubbed
    assert "wearing an oversized trenchcoat" not in repaired
    assert "dressed in a red hoodie" not in repaired
    assert "Enforce Zero Wardrobe Redundancy" in repaired

    # 4. Audio ducking and instrumental
    assert "instrumental 130 BPM Dark Synth" in repaired
    assert "Ensure the background music ducks under the spoken dialogue" in repaired

    # 5. Spatial staging injected
    assert "screen-left" in repaired and "screen-right" in repaired
    assert "SPATIAL_STAGING" in result.invariants_applied or any(
        v.rule_id == "SPATIAL_STAGING" for v in result.violations
    )


def test_repair_tag_collisions_phantom_with_at_and_parens():
    """Unattached @KeyframeSeed and EndKeyframe with @ or parens must be removed."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "[# Sources <FIRST_FRAME>@KeyframeSeed]\n"
        "<IMAGE_REF_0>@Image1 @KeyframeSeed\n"
        "- Role A: gs://bucket/char.jpg (@KeyframeSeed) (@EndKeyframe)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (@KeyframeSeed): Detective.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic.\n"
        "Environment: Alley.\n"
        "Audio: instrumental ambient.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Detective walks."
    )
    repaired, violations = PreFlightGatekeeper.repair_tag_collisions(prompt)
    assert "<FIRST_FRAME>@KeyframeSeed" in repaired
    assert "@KeyframeSeed\n" not in repaired
    assert "(@KeyframeSeed)" not in repaired
    assert "(@EndKeyframe)" not in repaired
    assert len(violations) >= 1
    assert any(v.rule_id == "TAG_COLLISION" for v in violations)


def test_repair_tag_collisions_stacked_with_image_tags():
    """Stacked image reference tags with @Image attached (e.g. <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image1) keep canonical."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image1\n"
        "- Role A: gs://bucket/char.jpg (@Image1, @Image1)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Detective.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic.\n"
        "Environment: Alley.\n"
        "Audio: instrumental ambient.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Walking."
    )
    repaired, violations = PreFlightGatekeeper.repair_tag_collisions(prompt)
    assert "<IMAGE_REF_0>@Image1" in repaired
    assert "<IMAGE_REF_1>" not in repaired
    assert "(@Image1)" in repaired
    assert "(@Image1, @Image1)" not in repaired


def test_repair_keyframe_offsets_with_starting_frame_character_role():
    """Character role with image_role='Starting Frame' triggers keyframe offset shift to @Image2."""
    characters = [
        CharacterRole(
            role_id="First Frame",
            name="Opening Shot",
            description="Initial frame",
            image_role="Starting Frame",
        ),
        CharacterRole(
            role_id="Role A",
            name="Detective",
            description="Lead",
            reference_url="https://storage.googleapis.com/b/char.jpg",
        ),
    ]
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "- Role A: gs://bucket/char.jpg (@Image1)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (@Image1): Detective.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic.\n"
        "Environment: Alley.\n"
        "Audio: instrumental ambient.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Walking."
    )
    repaired, violations = PreFlightGatekeeper.repair_keyframe_offsets(
        prompt, characters=characters
    )
    assert "(@Image2)" in repaired
    assert "@Image1" not in repaired
    assert len(violations) >= 1


def test_repair_zero_wardrobe_redundancy_oxford_comma_and_preserves_posture_facial():
    """Comma-separated clothing list must be completely scrubbed while facial features and posture are preserved."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0>@Image1\n"
        "- Role A: gs://bucket/det.jpg (@Image1)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (Detective) (@Image1): Severe expression, wearing a dark trenchcoat, wool sweater, and leather gloves, sharp jawline. Voice: Gravelly whisper.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Noir.\n"
        "Environment: Office.\n"
        "Audio: instrumental jazz.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Sits."
    )
    repaired, violations = PreFlightGatekeeper.repair_zero_wardrobe_redundancy(prompt)
    assert "wearing a dark trenchcoat" not in repaired
    assert "wool sweater" not in repaired
    assert "leather gloves" not in repaired
    assert "Severe expression" in repaired
    assert "sharp jawline" in repaired
    assert "Gravelly whisper" in repaired
    assert (
        "Enforce Zero Wardrobe Redundancy: Visual appearance locked to reference sheet @Image1"
        in repaired
    )
    assert len(violations) >= 1


def test_repair_zero_wardrobe_redundancy_sentence_structure():
    """Sentence structures like 'He is wearing...' must not leave 'He is .' behind."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0>@Image1\n"
        "- Role A: gs://bucket/det.jpg (@Image1)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (Detective) (@Image1): Severe expression. He is wearing a dark trenchcoat and wool sweater. Voice: Gravelly whisper.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Noir.\n"
        "Environment: Office.\n"
        "Audio: instrumental jazz.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Sits."
    )
    repaired, violations = PreFlightGatekeeper.repair_zero_wardrobe_redundancy(prompt)
    assert "He is ." not in repaired
    assert "He is " not in repaired
    assert "wearing a dark trenchcoat" not in repaired
    assert "Severe expression" in repaired
    assert "Enforce Zero Wardrobe Redundancy" in repaired


def test_repair_zero_wardrobe_redundancy_colon_tag_with_commas():
    """'Wardrobe: item1, item2, item3.' must be completely scrubbed."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0>@Image1\n"
        "- Role A: gs://bucket/det.jpg (@Image1)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (Detective) (@Image1): Severe expression. Wardrobe: black hoodie, cargo pants, white sneakers. Voice: Gravelly.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Noir.\n"
        "Environment: Office.\n"
        "Audio: instrumental jazz.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Sits."
    )
    repaired, violations = PreFlightGatekeeper.repair_zero_wardrobe_redundancy(prompt)
    assert "cargo pants" not in repaired
    assert "white sneakers" not in repaired
    assert "black hoodie" not in repaired
    assert "Severe expression" in repaired
    assert "Enforce Zero Wardrobe Redundancy" in repaired


def test_repair_zero_wardrobe_redundancy_auto_detects_block1_without_characters_param():
    """When characters is None, reference character is detected from standard Block 1."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "[# References <IMAGE_REF_0>@Image1]\n"
        "- Role A: gs://bucket/char.jpg (@Image1)\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (Detective): Grim look, wearing an oversized trenchcoat. Voice: Gravelly.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Audio: instrumental jazz.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Walks.\n"
    )
    repaired, violations = PreFlightGatekeeper.repair_zero_wardrobe_redundancy(prompt)
    assert len(violations) >= 1
    assert "wearing an oversized trenchcoat" not in repaired
    assert (
        "Enforce Zero Wardrobe Redundancy: Visual appearance locked to reference sheet @Image1"
        in repaired
    )


def test_repair_audio_ducking_with_bullet_points():
    """Bulleted '- Audio:' and '- Sound design:' lines must be updated without adding duplicate directives."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "None.\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Speaker.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "- Camera & Lighting: Cinematic.\n"
        "- Audio: 140 BPM Trap.\n\n"
        "### TIMELINE\n"
        '[0-3s] Action: Talks. Dialogue: Role A: "Hello world."'
    )
    repaired, violations = PreFlightGatekeeper.repair_audio_ducking(prompt, has_dialogue=True)
    assert "- Audio: instrumental 140 BPM Trap." in repaired
    assert "Ensure the background music ducks under the spoken dialogue" in repaired
    assert repaired.count("Audio:") == 1
    assert len(violations) == 1


def test_repair_audio_ducking_ignores_title_card_quotes_outside_timeline():
    """Quotes in Block 3 (e.g. title cards) must not trigger audio ducking when no spoken dialogue is in timeline."""
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "None.\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Silent dancer.\n\n"
        "### SCENE INSTRUCTIONS\n"
        'On-Screen Displayed Text / Title Card: "SUMMER VIBES"\n'
        "Audio: upbeat electronic beat.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Dancing silently.\n"
        "[3-6s] Action: Continues dancing."
    )
    repaired, violations = PreFlightGatekeeper.repair_audio_ducking(prompt, has_dialogue=False)
    assert repaired == prompt
    assert len(violations) == 0


def test_repair_spatial_staging_with_bulleted_camera_line():
    """Spatial staging must be inserted after bulleted '- Camera & Lighting:' line."""
    characters = [
        CharacterRole(
            role_id="Role A",
            name="Detective",
            description="Grim.",
            reference_url="https://storage.googleapis.com/b/det.jpg",
        ),
        CharacterRole(
            role_id="Role B",
            name="Suspect",
            description="Nervous.",
            reference_url="https://storage.googleapis.com/b/susp.jpg",
        ),
    ]
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0>@Image1\n"
        "<IMAGE_REF_1>@Image2\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Detective.\n"
        "- Role B: Suspect.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "- Camera & Lighting: Cinematic wide angle.\n"
        "- Environment: Interrogation room.\n"
        "- Audio: instrumental ambient.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Both stare."
    )
    repaired, violations = PreFlightGatekeeper.repair_spatial_staging(prompt, characters=characters)
    assert (
        "- Camera & Lighting: Cinematic wide angle.\nSpatial staging: [Role A] positioned on screen-left, [Role B] positioned on screen-right"
        in repaired
    )
    assert len(violations) == 1


def test_repair_spatial_staging_not_suppressed_by_block2_facial_prose():
    """A facial description mentioning 'screen-left' in Block 2 must not suppress Block 3 staging."""
    characters = [
        CharacterRole(
            role_id="Role A",
            name="Detective",
            description="Scar on screen-left cheek.",
            reference_url="https://storage.googleapis.com/b/det.jpg",
        ),
        CharacterRole(
            role_id="Role B",
            name="Suspect",
            description="Nervous.",
            reference_url="https://storage.googleapis.com/b/susp.jpg",
        ),
    ]
    prompt = (
        "### INPUT ROLES & REFERENCES\n"
        "<IMAGE_REF_0>@Image1\n"
        "<IMAGE_REF_1>@Image2\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Detective with a scar on screen-left cheek.\n"
        "- Role B: Suspect.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: Cinematic.\n"
        "Environment: Interrogation room.\n"
        "Audio: instrumental ambient.\n\n"
        "### TIMELINE\n"
        "[0-3s] Action: Both stare."
    )
    repaired, violations = PreFlightGatekeeper.repair_spatial_staging(prompt, characters=characters)
    assert (
        "Spatial staging: [Role A] positioned on screen-left, [Role B] positioned on screen-right"
        in repaired
    )
    assert len(violations) == 1
