"""Data models for OmniMash security and Model Armor guardrails."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class GuardrailResult:
    """Represents the verdict and sanitized payload of a prompt or response security screening."""

    is_approved: bool
    sanitized_prompt: str
    rejection_reason: str | None = None
    filter_match_state: str | None = None
    triggers: list[str] = field(default_factory=list)
    filter_results: dict[str, Any] = field(default_factory=dict)
    deidentified: bool = False

    @property
    def is_blocked(self) -> bool:
        """Convenience property indicating whether the prompt was rejected by guardrails."""
        return not self.is_approved

    def to_dict(self) -> dict[str, Any]:
        """Serializes GuardrailResult into a plain dictionary."""
        return asdict(self)
