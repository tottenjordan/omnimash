from __future__ import annotations

from unittest.mock import MagicMock

from omnimash.prompts.compiler import PromptOptimizer as CompilerOptimizer
from omnimash.prompts.optimizer import PromptOptimizer


def test_prompt_optimizer_exports_and_parity():
    """Verify PromptOptimizer is exported and identical across compiler and optimizer modules."""
    assert PromptOptimizer is CompilerOptimizer


def test_prompt_optimizer_tier1_qualitative_ducking():
    """Verify quantitative audio ducking terms are converted to qualitative descriptors."""
    optimizer = PromptOptimizer()
    prompt = (
        "### SCENE INSTRUCTIONS\n"
        "Audio: Sound design: 120 BPM beat (ducked at 15% volume under dialogue).\n"
        "Audio: Sound design: Background beat is quietly ducked at 15% volume in the background."
    )
    result = optimizer.optimize(prompt, use_llm=False)
    assert "(subtly ducked in the background beneath dialogue)" in result
    assert "ducked at 15% volume" not in result


def test_prompt_optimizer_empty_prompt():
    """Verify empty or whitespace-only prompt returns unchanged."""
    optimizer = PromptOptimizer()
    assert optimizer.optimize("") == ""
    assert optimizer.optimize("   ") == "   "


def test_prompt_optimizer_tier2_mock_llm():
    """Verify LLM pass is invoked and validates canonical 4-Block headers."""
    mock_compiler = MagicMock()
    mock_response = MagicMock()
    canonical_llm_out = (
        "### INPUT ROLES & REFERENCES\n"
        "[# References <IMAGE_REF_0>@Image1]\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A (Severus Snape) <IMAGE_REF_0>@Image1: Gothic Potion Master.\n\n"
        "### SCENE INSTRUCTIONS\n"
        "Camera & Lighting: In a single continuous shot. No scene cuts.\n"
        "Audio: Sound design: Foreground spoken voiceover/dialogue is dominant, crystal-clear, and front-of-mix. "
        "Background beat (instrumental 120 BPM beat) is subtly ducked in the background beneath dialogue.\n\n"
        "### TIMELINE\n"
        "- [0-3s] Role A steps into frame. [3-6s] Role A stirs cauldron. [6-10s] Role A glares at camera."
    )
    mock_response.text = canonical_llm_out
    mock_compiler._flash_regional_client.models.generate_content.return_value = mock_response

    optimizer = PromptOptimizer(compiler=mock_compiler)
    result = optimizer.optimize(
        "### INPUT ROLES & REFERENCES\nNone.\n\n"
        "### CHARACTER PROFILES\n- Role A: Snape.\n\n"
        "### SCENE INSTRUCTIONS\nAudio: (ducked at 15% volume under dialogue)\n\n"
        "### TIMELINE\n- [0-10s] Scene 1 [Role A]: Action.",
        use_llm=True,
    )
    assert result == canonical_llm_out


def test_prompt_optimizer_tier2_rejects_legacy_role_definitions_without_4_blocks():
    """Verify LLM output with legacy [ROLE DEFINITIONS] instead of canonical 4-Block headers falls back to Tier 1."""
    mock_compiler = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Refined directive [ROLE DEFINITIONS]: Role A is Severus Snape."
    mock_compiler._flash_regional_client.models.generate_content.return_value = mock_response

    optimizer = PromptOptimizer(compiler=mock_compiler)
    tier1_input = (
        "### INPUT ROLES & REFERENCES\nNone.\n\n"
        "### CHARACTER PROFILES\n- Role A: Snape.\n\n"
        "### SCENE INSTRUCTIONS\nAudio: (ducked at 15% volume under dialogue)\n\n"
        "### TIMELINE\n- [0-10s] Scene 1 [Role A]: Action."
    )
    result = optimizer.optimize(tier1_input, use_llm=True)
    assert "### INPUT ROLES & REFERENCES" in result
    assert "(subtly ducked in the background beneath dialogue)" in result
    assert "[ROLE DEFINITIONS]" not in result


def test_prompt_optimizer_tier2_rejects_llm_output_that_strips_temporal_beats():
    """Verify LLM output that keeps 4-Block headers but strips [0-3s]/[3-6s]/[6-10s] beats falls back to Tier 1."""
    mock_compiler = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        "### INPUT ROLES & REFERENCES\nNone.\n\n"
        "### CHARACTER PROFILES\n- Role A: Snape.\n\n"
        "### SCENE INSTRUCTIONS\nCamera & Lighting: Continuous shot.\n\n"
        "### TIMELINE\n- [0-10s] Role A stirs potion in one smooth motion."
    )
    mock_compiler._flash_regional_client.models.generate_content.return_value = mock_response

    optimizer = PromptOptimizer(compiler=mock_compiler)
    tier1_input = (
        "### INPUT ROLES & REFERENCES\nNone.\n\n"
        "### CHARACTER PROFILES\n- Role A: Snape.\n\n"
        "### SCENE INSTRUCTIONS\nAudio: (ducked at 15% volume under dialogue)\n\n"
        "### TIMELINE\n- [0-10s] Scene 1 [Role A]: [0-3s] Enters. [3-6s] Stirs. [6-10s] Glares."
    )
    result = optimizer.optimize(tier1_input, use_llm=True)
    assert "[0-3s]" in result
    assert "[3-6s]" in result
    assert "[6-10s]" in result
    assert "(subtly ducked in the background beneath dialogue)" in result
