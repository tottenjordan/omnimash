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
    """Verify LLM pass is invoked when requested and compiler client is available."""
    mock_compiler = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        "Refined qualitative directive [ROLE DEFINITIONS]: Role A is Severus Snape."
    )
    mock_compiler._flash_regional_client.models.generate_content.return_value = mock_response

    optimizer = PromptOptimizer(compiler=mock_compiler)
    result = optimizer.optimize(
        "[ROLE DEFINITIONS]: Role A is Snape. Audio: (ducked at 15% volume under dialogue)",
        use_llm=True,
    )
    assert result == "Refined qualitative directive [ROLE DEFINITIONS]: Role A is Severus Snape."
