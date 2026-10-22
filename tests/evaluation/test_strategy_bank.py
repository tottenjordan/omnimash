from omnimash.evaluation.models import DefectCategory, DirectorialInvariantRule, StrategyBank
from omnimash.evaluation.strategy_bank import StrategyBankManager
from omnimash.storage.gcs import GcsStorageManager


def test_strategy_bank_initialization_and_seeding():
    storage = GcsStorageManager(mock_mode=True)
    manager = StrategyBankManager(storage=storage)
    bank = manager.get_strategy_bank()

    assert isinstance(bank, StrategyBank)
    assert len(bank.rules) >= 12
    rule_ids = {r.rule_id for r in bank.rules}
    assert "RULE-AUDIO-001" in rule_ids
    assert "RULE-WARDROBE-001" in rule_ids
    assert "RULE-KEYFRAME-001" in rule_ids
    assert "RULE-SPATIAL-001" in rule_ids


def test_strategy_bank_query_applicable_rules():
    storage = GcsStorageManager(mock_mode=True)
    manager = StrategyBankManager(storage=storage)

    # Query by defect category
    audio_rules = manager.query_applicable_rules(defect_categories=[DefectCategory.AUDIO_DROWNED])
    assert any(r.rule_id == "RULE-AUDIO-001" for r in audio_rules)

    # Query with keyframe flag
    keyframe_rules = manager.query_applicable_rules(has_keyframe=True)
    assert any(r.rule_id == "RULE-KEYFRAME-001" for r in keyframe_rules)

    # Query by keyword
    wardrobe_rules = manager.query_applicable_rules(
        concept="fashion runway with character reference image"
    )
    assert any(r.rule_id == "RULE-WARDROBE-001" for r in wardrobe_rules)


def test_strategy_bank_project_scoping():
    storage = GcsStorageManager(mock_mode=True)
    manager = StrategyBankManager(storage=storage)

    custom_rule = DirectorialInvariantRule(
        rule_id="RULE-PROJ-CYBER-001",
        category="STYLE",
        trigger_pattern="cyberpunk neon lighting",
        invariant_directive="Enforce cyan and magenta rim lighting at all times.",
        rationale="Client visual identity.",
        confidence_score=0.99,
    )
    manager.add_rule(custom_rule, project_id="proj_neon")

    # Global bank does not have project rule
    global_bank = manager.get_strategy_bank()
    assert not any(r.rule_id == "RULE-PROJ-CYBER-001" for r in global_bank.rules)

    # Project bank has both foundational and project rule
    project_bank = manager.get_strategy_bank(project_id="proj_neon")
    assert any(r.rule_id == "RULE-PROJ-CYBER-001" for r in project_bank.rules)
    assert any(r.rule_id == "RULE-AUDIO-001" for r in project_bank.rules)
