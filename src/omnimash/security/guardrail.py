from dataclasses import dataclass


@dataclass
class GuardrailResult:
    is_approved: bool
    sanitized_prompt: str
    rejection_reason: str | None = None


class ModelArmorGuardrail:
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode

    def validate_prompt(self, prompt: str) -> GuardrailResult:
        lowered = prompt.lower()
        if "illegal" in lowered or "hate speech" in lowered:
            return GuardrailResult(
                is_approved=False,
                sanitized_prompt="",
                rejection_reason="Policy violation: Prompt flagged by Model Armor for harmful content.",
            )
        return GuardrailResult(is_approved=True, sanitized_prompt=prompt.strip())
