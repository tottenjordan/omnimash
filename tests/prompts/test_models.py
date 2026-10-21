from __future__ import annotations

from omnimash.prompts.compiler import (
    CompiledDeltaPrompt as CompilerDeltaPrompt,
    CompiledPromptParts as CompilerPromptParts,
    DeconstructedCharacterSchema as CompilerCharSchema,
    DeconstructedConceptSchema as CompilerConceptSchema,
    MetaPromptTags as CompilerMetaTags,
    SceneDirective as CompilerSceneDirective,
)
from omnimash.prompts.models import (
    CompiledDeltaPrompt,
    CompiledPromptParts,
    DeconstructedCharacterSchema,
    DeconstructedConceptSchema,
    MetaPromptTags,
    SceneDirective,
)


def test_prompt_models_exports_and_parity():
    """Verify models are accessible and identical across prompts.models and prompts.compiler."""
    assert CompiledPromptParts is CompilerPromptParts
    assert CompiledDeltaPrompt is CompilerDeltaPrompt
    assert SceneDirective is CompilerSceneDirective
    assert MetaPromptTags is CompilerMetaTags
    assert DeconstructedCharacterSchema is CompilerCharSchema
    assert DeconstructedConceptSchema is CompilerConceptSchema


def test_compiled_prompt_parts_generation():
    """Verify CompiledPromptParts formats blocks correctly."""
    parts = CompiledPromptParts(
        subject_anchor="A cybernetic detective",
        aesthetic_injection="Neon cyberpunk rain",
        environment="Rainy dark alley",
        camera_lighting="Anamorphic widescreen lens",
        motion="Slow motion walking forward",
        audio_track="120 BPM dark synthwave",
        voiceover="The city never sleeps.",
    )
    full = parts.to_full_prompt()
    assert "### INPUT ROLES & REFERENCES" in full
    assert "### CHARACTER PROFILES" in full
    assert "### SCENE INSTRUCTIONS" in full
    assert "### TIMELINE" in full
    assert "A cybernetic detective" in full
    assert "The city never sleeps" in full


def test_compiled_delta_prompt_formatting():
    """Verify CompiledDeltaPrompt formats preservation lock and isolated diff."""
    delta = CompiledDeltaPrompt(
        preservation_lock="Maintain character face, wardrobe baseline, and environment",
        isolated_diff="Add glowing red cybernetic eye implant",
    )
    res = delta.to_delta_prompt()
    assert "[PRESERVATION LOCK]:" in res
    assert "[ISOLATED DIFF]:" in res
    assert "Add glowing red cybernetic eye implant" in res


def test_deconstructed_schemas():
    """Verify Pydantic schemas validate correctly."""
    char = DeconstructedCharacterSchema(
        role_id="Role A",
        name="Severus Snape",
        description="Severe cynical expression, black hair",
        aesthetic_tags=["dark robe", "gothic"],
        voice_style="Dry, slow, menacing",
    )
    assert char.name == "Severus Snape"

    concept = DeconstructedConceptSchema(
        characters=[char],
        aesthetic_tags=["cyberpunk"],
        environment_tag="neon neon",
        camera_lighting_tag="anamorphic",
        audio_beat="120 bpm",
        vocal_delivery="menacing",
    )
    assert len(concept.characters) == 1
    assert concept.characters[0].role_id == "Role A"


def test_compiled_prompt_parts_acoustic_progression():
    """Verify CompiledPromptParts formats seamless acoustic progression without instrumental or Sound design prefixes."""
    parts = CompiledPromptParts(
        subject_anchor="Hero in desert",
        aesthetic_injection="Cinematic lighting",
        environment="Dune ridge",
        camera_lighting="Widescreen tracking shot",
        motion="Walking slowly forward",
        audio_track="Seamless acoustic progression from prior ambient audio",
    )
    full = parts.to_full_prompt()
    assert "Audio: Seamless acoustic progression from prior ambient audio." in full
    assert "instrumental" not in full
    assert "Sound design:" not in full

