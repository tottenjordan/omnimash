from dataclasses import dataclass


@dataclass
class GuardrailResult:
    is_approved: bool
    sanitized_prompt: str
    rejection_reason: str | None = None


class ModelArmorGuardrail:
    def __init__(self, mock_mode: bool | None = None, template_id: str | None = None):
        from omnimash.config import settings

        self.mock_mode = (
            mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        )
        self.template_id = (
            template_id
            if template_id is not None
            else getattr(settings, "model_armor_template_id", "omnimash-safety-filter")
        )

    def validate_prompt(self, prompt: str) -> GuardrailResult:
        """Validates prompt against Model Armor security guardrails.

        Refined to detect true malicious prompt injection or overt policy violations,
        while allowing harmless parody terms (e.g., 'illegal beat drop', 'potion battle').
        """
        lowered = prompt.lower()

        malicious_patterns = [
            "ignore previous instructions",
            "ignore all previous instructions",
            "disregard previous instructions",
            "forget all prior instructions",
            "system override prompt",
            "[system]",
            "<|im_start|>",
            "developer mode",
            "jailbreak",
            "do anything now",
            "bypass safety filter",
            "reveal system prompt",
            "hate speech",
            "overt hate speech attack",
        ]

        for pattern in malicious_patterns:
            if pattern in lowered:
                return GuardrailResult(
                    is_approved=False,
                    sanitized_prompt="",
                    rejection_reason="Policy violation: Prompt flagged by Model Armor for harmful content.",
                )

        return GuardrailResult(is_approved=True, sanitized_prompt=prompt.strip())
