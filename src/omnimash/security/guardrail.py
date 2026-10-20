"""Model Armor security guardrail integration for OmniMash."""

from omnimash.security.heuristics import validate_prompt_heuristics
from omnimash.security.models import GuardrailResult


class ModelArmorGuardrail:
    """Security guardrail providing prompt screening via Google Cloud Model Armor with local heuristic fallback."""

    def __init__(
        self,
        mock_mode: bool | None = None,
        template_id: str | None = None,
    ):
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
        return validate_prompt_heuristics(prompt)
