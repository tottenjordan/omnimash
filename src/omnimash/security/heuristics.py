"""Local heuristic guardrail engine for prompt injection and policy violation screening.

Provides fast, deterministic, zero-ReDoS local screening for mock testing and
resilience fallback when remote Model Armor API services are unavailable.
"""

import re
from typing import Final

from omnimash.security.models import GuardrailResult

# Curated high-precision malicious patterns for local heuristic screening.
# Uses word boundaries or exact structural markers to avoid false positives on parody text.
_MALICIOUS_PROMPT_PATTERNS: Final[tuple[str, ...]] = (
    r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions",
    r"disregard\s+(?:all\s+)?(?:previous|prior)\s+instructions",
    r"forget\s+all\s+prior\s+instructions",
    r"system\s+override\s+prompt",
    r"system\s*:\s*ignore\s+previous",
    r"\[system\]",
    r"<\|im_start\|>",
    r"\bdeveloper\s+mode\b",
    r"\bjailbreak\b",
    r"\bdo\s+anything\s+now\b",
    r"\bbypass\s+safety\s+filter\b",
    r"\breveal\s+system\s+prompt\b",
    r"\bovert\s+hate\s+speech\b",
    r"\bhate\s+speech\b",
)

_MALICIOUS_PROMPT_RE: Final[re.Pattern[str]] = re.compile(
    "|".join(_MALICIOUS_PROMPT_PATTERNS),
    re.IGNORECASE,
)


def validate_prompt_heuristics(prompt: str) -> GuardrailResult:
    """Validates prompt text using high-speed local heuristic patterns.

    Detects malicious prompt injections, jailbreak attempts, and overt policy violations
    while allowing safe parody and creative terms (e.g., 'illegal beat drop', 'potion battle').

    Args:
        prompt: Raw prompt string to validate.

    Returns:
        GuardrailResult indicating whether the prompt is approved and sanitization state.
    """
    match = _MALICIOUS_PROMPT_RE.search(prompt)
    if match:
        trigger = match.group(0).strip().lower()
        return GuardrailResult(
            is_approved=False,
            sanitized_prompt="",
            rejection_reason="Policy violation: Prompt flagged by Model Armor for harmful content.",
            filter_match_state="MATCH_FOUND",
            triggers=[trigger],
            filter_results={"pi_and_jailbreak": {"matched": True, "trigger": trigger}},
        )

    return GuardrailResult(
        is_approved=True,
        sanitized_prompt=prompt.strip(),
        filter_match_state="NO_MATCH_FOUND",
    )
