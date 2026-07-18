from omnimash.security.guardrail import ModelArmorGuardrail


def test_guardrail_pass():
    guardrail = ModelArmorGuardrail(mock_mode=True)
    result = guardrail.validate_prompt(
        "Make Snape look like he is in a 90s rap video wearing a bomber jacket."
    )
    assert result.is_approved is True
    assert result.sanitized_prompt != ""


def test_guardrail_block_policy_violation():
    guardrail = ModelArmorGuardrail(mock_mode=True)
    result = guardrail.validate_prompt(
        "Generate illegal content with severe hate speech violation."
    )
    assert result.is_approved is False
    assert "Policy violation" in (result.rejection_reason or "")
