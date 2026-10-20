"""Model Armor security guardrail integration for OmniMash.

Provides the primary security gateway for screening raw user inputs, prompt directives,
and agent turns against Google Cloud Model Armor. Detects adversarial prompt injections,
jailbreak attempts, and sensitive data (PII) before prompts reach models.

Note on Architecture:
    Pre-generation prompt screening is owned by this module (`omnimash.security`).
    This is distinct from `omnimash.engine.guardrails`, which handles procedural
    character likeness abstraction (e.g. pop-culture names/trademarks) and post-inference
    Gemini Omni Flash 400 error guidance parsing. Decoupling pre-generation Model Armor
    screening from video generation avoids the google-genai constraint where model_armor_config
    and relaxed safety_settings are mutually exclusive in GenerateContentConfig.
"""

import logging
from typing import Any

from omnimash.security.client import (
    get_model_armor_async_client,
    get_model_armor_client,
    is_model_armor_available,
    modelarmor_v1,
)
from omnimash.security.heuristics import validate_prompt_heuristics
from omnimash.security.models import GuardrailResult

logger = logging.getLogger("omnimash.security.guardrail")


class ModelArmorGuardrail:
    """Security guardrail providing prompt screening via Google Cloud Model Armor with local heuristic fallback."""

    def __init__(
        self,
        mock_mode: bool | None = None,
        template_id: str | None = None,
        location: str | None = None,
        project_id: str | None = None,
        fail_closed: bool | None = None,
        timeout: float | None = None,
        client: Any | None = None,
        async_client: Any | None = None,
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
        self.location = (
            location
            if location is not None
            else getattr(settings, "model_armor_location", "us-central1")
        )
        self.project_id = (
            project_id
            if project_id is not None
            else getattr(settings, "google_cloud_project", "hybrid-vertex")
        )
        self.fail_closed = (
            fail_closed
            if fail_closed is not None
            else getattr(settings, "model_armor_fail_closed", False)
        )
        self.timeout = (
            timeout if timeout is not None else getattr(settings, "model_armor_timeout", 5.0)
        )
        self._client = client
        self._async_client = async_client

    @property
    def template_name(self) -> str:
        """Returns the fully-qualified resource name of the Model Armor template."""
        if self.template_id.startswith("projects/"):
            return self.template_id
        return f"projects/{self.project_id}/locations/{self.location}/templates/{self.template_id}"

    def validate_prompt(self, prompt: str) -> GuardrailResult:
        """Synchronously validates prompt against Model Armor security guardrails.

        Falls back to local heuristic validation in mock mode or when the remote service is unavailable.
        """
        # Short-circuit empty or whitespace-only prompts without remote RPC calls
        if not prompt or not prompt.strip():
            return GuardrailResult(
                is_approved=True,
                sanitized_prompt="",
                filter_match_state="NO_MATCH_FOUND",
            )

        if self.mock_mode or not is_model_armor_available() or modelarmor_v1 is None:
            return validate_prompt_heuristics(prompt)

        try:
            client = self._client or get_model_armor_client(location=self.location)
            request = modelarmor_v1.SanitizeUserPromptRequest(
                name=self.template_name,
                user_prompt_data=modelarmor_v1.DataItem(text=prompt),
            )
            response = client.sanitize_user_prompt(request=request, timeout=self.timeout)
            return self._process_sanitization_result(response, prompt)
        except Exception as err:
            logger.warning(
                "Model Armor sanitization call failed (%s). Fallback triggered.",
                err,
            )
            if self.fail_closed:
                return GuardrailResult(
                    is_approved=False,
                    sanitized_prompt="",
                    rejection_reason=f"Model Armor service unavailable: {err}",
                    filter_match_state="EXECUTION_ERROR",
                )
            return validate_prompt_heuristics(prompt)

    async def validate_prompt_async(self, prompt: str) -> GuardrailResult:
        """Asynchronously validates prompt against Model Armor security guardrails.

        Falls back to local heuristic validation in mock mode or when the remote service is unavailable.
        """
        # Short-circuit empty or whitespace-only prompts without remote RPC calls
        if not prompt or not prompt.strip():
            return GuardrailResult(
                is_approved=True,
                sanitized_prompt="",
                filter_match_state="NO_MATCH_FOUND",
            )

        if self.mock_mode or not is_model_armor_available() or modelarmor_v1 is None:
            return validate_prompt_heuristics(prompt)

        try:
            client = self._async_client or get_model_armor_async_client(location=self.location)
            request = modelarmor_v1.SanitizeUserPromptRequest(
                name=self.template_name,
                user_prompt_data=modelarmor_v1.DataItem(text=prompt),
            )
            response = await client.sanitize_user_prompt(request=request, timeout=self.timeout)
            return self._process_sanitization_result(response, prompt)
        except Exception as err:
            logger.warning(
                "Model Armor async sanitization call failed (%s). Fallback triggered.",
                err,
            )
            if self.fail_closed:
                return GuardrailResult(
                    is_approved=False,
                    sanitized_prompt="",
                    rejection_reason=f"Model Armor service unavailable: {err}",
                    filter_match_state="EXECUTION_ERROR",
                )
            return validate_prompt_heuristics(prompt)

    def _process_sanitization_result(
        self,
        response: Any,
        original_prompt: str,
    ) -> GuardrailResult:
        """Parses SanitizeUserPromptResponse into a structured GuardrailResult."""
        if not hasattr(response, "sanitization_result"):
            return validate_prompt_heuristics(original_prompt)

        result = response.sanitization_result
        match_state = getattr(result, "filter_match_state", None)
        inv_result = getattr(result, "invocation_result", None)

        # Check for detector execution failure or backend error
        is_failure = False
        if modelarmor_v1 and hasattr(modelarmor_v1, "InvocationResult"):
            is_failure = inv_result in (
                modelarmor_v1.InvocationResult.FAILURE,
                getattr(modelarmor_v1.InvocationResult, "PARTIAL", None),
            )
        else:
            is_failure = str(inv_result) in ("FAILURE", "PARTIAL", "3", "2")

        is_exec_error = (
            str(match_state) in ("EXECUTION_ERROR", "FILTER_MATCH_STATE_UNSPECIFIED", "0")
            and is_failure
        ) or str(match_state) == "EXECUTION_ERROR"

        if is_failure or is_exec_error:
            logger.warning(
                "Model Armor screening encountered backend execution error (invocation_result=%s, match_state=%s).",
                inv_result,
                match_state,
            )
            if self.fail_closed:
                return GuardrailResult(
                    is_approved=False,
                    sanitized_prompt="",
                    rejection_reason="Model Armor screening service encountered an execution failure.",
                    filter_match_state="EXECUTION_ERROR",
                )
            return validate_prompt_heuristics(original_prompt)

        # Check MATCH_FOUND
        is_match = False
        if modelarmor_v1 and hasattr(modelarmor_v1, "FilterMatchState"):
            is_match = match_state == modelarmor_v1.FilterMatchState.MATCH_FOUND
        else:
            is_match = str(match_state) in ("MATCH_FOUND", "2")

        triggers: list[str] = []
        filter_results_dict: dict[str, Any] = {}

        if hasattr(result, "filter_results"):
            for k, v in result.filter_results.items():
                filter_results_dict[k] = str(v)
                triggers.append(k)

        if is_match:
            rejection_msg = "Policy violation: Prompt flagged by Model Armor for harmful content."
            return GuardrailResult(
                is_approved=False,
                sanitized_prompt="",
                rejection_reason=rejection_msg,
                filter_match_state="MATCH_FOUND",
                triggers=triggers,
                filter_results=filter_results_dict,
            )

        # Check for SDP de-identification
        sanitized_text = original_prompt.strip()
        deidentified = False
        sdp_res = getattr(result, "filter_results", {}).get("sdp")
        if sdp_res and hasattr(sdp_res, "sdp_filter_result"):
            sub_sdp = sdp_res.sdp_filter_result
            if hasattr(sub_sdp, "deidentify_result") and hasattr(sub_sdp.deidentify_result, "data"):
                deid_text = getattr(sub_sdp.deidentify_result.data, "text", None)
                if deid_text and deid_text != original_prompt:
                    sanitized_text = deid_text
                    deidentified = True

        return GuardrailResult(
            is_approved=True,
            sanitized_prompt=sanitized_text,
            filter_match_state="NO_MATCH_FOUND",
            triggers=triggers,
            filter_results=filter_results_dict,
            deidentified=deidentified,
        )
