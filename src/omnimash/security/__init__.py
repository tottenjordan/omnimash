"""OmniMash security package.

Provides pre-generation Model Armor screening, jailbreak detection, and sensitive data
protection (SDP) for prompt inputs and agent turns.

Distinct from `omnimash.engine.guardrails`, which handles procedural character/trademark
abstraction and post-inference Gemini Omni Flash policy error parsing.
"""

from omnimash.security.adk_plugin import get_model_armor_adk_plugin
from omnimash.security.client import (
    close_model_armor_async_clients,
    close_model_armor_clients,
    get_model_armor_async_client,
    get_model_armor_client,
    is_model_armor_available,
    modelarmor_v1,
)
from omnimash.security.guardrail import ModelArmorGuardrail
from omnimash.security.heuristics import validate_prompt_heuristics
from omnimash.security.models import GuardrailResult

__all__ = [
    "GuardrailResult",
    "ModelArmorGuardrail",
    "close_model_armor_async_clients",
    "close_model_armor_clients",
    "get_model_armor_adk_plugin",
    "get_model_armor_async_client",
    "get_model_armor_client",
    "is_model_armor_available",
    "modelarmor_v1",
    "validate_prompt_heuristics",
]
