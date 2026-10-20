"""Google ADK middleware plugin integration for Model Armor."""

import logging
from typing import Any

logger = logging.getLogger("omnimash.security.adk_plugin")


def get_model_armor_adk_plugin(
    prompt_template_name: str | None = None,
    response_template_name: str | None = None,
    block_on_screening_failure: bool = False,
    credentials: Any | None = None,
) -> Any:
    """Creates a configured ModelArmorPlugin for Google ADK Runner execution.

    Args:
        prompt_template_name: Fully-qualified Model Armor template resource name for input screening.
            Defaults to settings.model_armor_template_name.
        response_template_name: Fully-qualified Model Armor template resource name for output screening.
        block_on_screening_failure: Whether to block turns when Model Armor API calls fail.
        credentials: Optional Google credentials object.

    Returns:
        google.adk.integrations.model_armor.ModelArmorPlugin instance.
    """
    from omnimash.config import settings

    try:
        from google.adk.integrations.model_armor import ModelArmorConfig, ModelArmorPlugin
    except ImportError as err:
        logger.warning("Google ADK Model Armor integration not available: %s", err)
        raise

    effective_prompt_template = prompt_template_name or getattr(
        settings, "model_armor_template_name", None
    )

    config = ModelArmorConfig(
        prompt_template_name=effective_prompt_template,
        response_template_name=response_template_name,
        block_on_screening_failure=block_on_screening_failure,
    )

    return ModelArmorPlugin(
        config=config,
        credentials=credentials,
    )
