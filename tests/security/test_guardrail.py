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


def test_guardrail_stays_relaxed_for_edgy_free_text():
    # Regression guard: guardrails are permissive by design. Edgy-but-legal
    # creative content must pass — only explicit policy triggers block.
    guardrail = ModelArmorGuardrail(mock_mode=True)
    spicy = (
        "Snape brutally roasts Draco in a savage explicit diss track: profanity, "
        "gory neon violence, dark drug-den imagery, and raunchy adult humor."
    )
    result = guardrail.validate_prompt(spicy)
    assert result.is_approved is True
    assert result.sanitized_prompt == spicy.strip()
