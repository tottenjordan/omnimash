"""Unit tests for Model Armor Google ADK middleware plugin."""

from google.adk.integrations.model_armor import ModelArmorPlugin

from omnimash.security.adk_plugin import get_model_armor_adk_plugin


def test_get_model_armor_adk_plugin_default_config():
    """Verify get_model_armor_adk_plugin initializes a valid ModelArmorPlugin with default settings."""
    plugin = get_model_armor_adk_plugin()
    assert isinstance(plugin, ModelArmorPlugin)
    assert plugin.name == "model_armor_plugin"
    assert (
        plugin._config.prompt_template_name
        == "projects/hybrid-vertex/locations/us-central1/templates/omnimash-safety-filter"
    )
    assert plugin._config.block_on_screening_failure is False


def test_get_model_armor_adk_plugin_custom_templates():
    """Verify get_model_armor_adk_plugin respects custom prompt and response templates."""
    custom_prompt = "projects/my-proj/locations/us-central1/templates/input-filter"
    custom_resp = "projects/my-proj/locations/us-central1/templates/output-filter"

    plugin = get_model_armor_adk_plugin(
        prompt_template_name=custom_prompt,
        response_template_name=custom_resp,
        block_on_screening_failure=True,
    )
    assert plugin._config.prompt_template_name == custom_prompt
    assert plugin._config.response_template_name == custom_resp
    assert plugin._config.block_on_screening_failure is True
