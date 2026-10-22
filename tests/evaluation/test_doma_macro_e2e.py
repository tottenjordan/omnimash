from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from omnimash.api.app import create_app
from omnimash.evaluation.exemplar_bank import ExemplarBankManager
from omnimash.evaluation.models import (
    DefectCategory,
    UserFeedbackRecord,
)
from omnimash.evaluation.rule_inducer import DirectorialRuleInducer
from omnimash.evaluation.strategy_bank import StrategyBankManager
from omnimash.prompts.character_roles import CharacterRole
from omnimash.prompts.compiler import PromptCompiler, SceneDirective
from omnimash.prompts.preflight_linter import PreFlightGatekeeper
from omnimash.storage.gcs import GcsStorageManager


@pytest.fixture
def storage():
    return GcsStorageManager(mock_mode=True)


@pytest.fixture
def strategy_mgr(storage):
    return StrategyBankManager(storage=storage, mock_mode=True)


@pytest.fixture
def exemplar_mgr(storage):
    return ExemplarBankManager(storage=storage, mock_mode=True)


@pytest.fixture
def inducer(storage, strategy_mgr):
    return DirectorialRuleInducer(storage=storage, strategy_bank=strategy_mgr, mock_mode=True)


def test_doma_complete_closed_macro_loop(storage, strategy_mgr, exemplar_mgr, inducer):
    """Verifies the complete closed macro-loop:

    Defect Feedback -> Offline Rule Induction -> Strategy Bank Update ->
    Turn-0 Compilation -> Pre-Flight Gatekeeper Pass -> 5-Star Exemplar Ingestion ->
    Few-Shot Exemplar Block Injection into Future Compilations.
    """
    project_id = "proj_doma_e2e_macro"

    # Step 1: Accumulate historical defect triplets across director review sessions
    for i in range(3):
        storage.save_feedback(
            session_id=f"session_{i}",
            turn_id=f"turn_{i}",
            feedback=UserFeedbackRecord(
                session_id=f"session_{i}",
                turn_id=f"turn_{i}",
                rating=2,
                defects=[DefectCategory.TAG_COLLISION, DefectCategory.AUDIO_DROWNED],
                critique_text="Tags stacked inconsistently and audio bass drowned spoken lines.",
                project_id=project_id,
            ),
        )

    # Step 2: Macro-Loop Rule Inducer detects clusters, synthesizes invariant rules
    induced_rules = inducer.induce_rules_from_history(
        project_id=project_id,
        min_defect_count=2,
    )
    assert len(induced_rules) >= 2
    rule_categories = [r.category for r in induced_rules]
    assert DefectCategory.TAG_COLLISION in rule_categories or "TAG_INTEGRITY" in [
        str(c) for c in rule_categories
    ]

    # Verify rules are persisted in the Strategy Bank
    bank = strategy_mgr.get_strategy_bank(project_id=project_id)
    assert len(bank.rules) >= 2

    # Step 3: Pareto Pruning eliminates redundancy while retaining high-confidence rules
    pruned_bank = inducer.pareto_prune_rules(project_id=project_id, max_rules=5)
    assert len(pruned_bank.rules) <= 5

    # Step 4: Turn-0 Storyboard Compilation queries Strategy Bank & runs PreFlightGatekeeper
    compiler = PromptCompiler(
        mock_mode=True,
        strategy_bank=strategy_mgr,
        exemplar_bank=exemplar_mgr,
    )

    chars = [
        CharacterRole(
            role_id="Role A",
            name="Dumble Dior",
            description="Ancient wizard in haute couture streetwear",
            reference_url="gs://omnimash-vault/dumble_dior.png",
            voice_style="Booming bass wizard delivery",
        )
    ]
    scenes = [
        SceneDirective(
            scene_number=1,
            active_roles=["Role A"],
            action="Dumble Dior slams the ledger onto the counter with heavy bass resonance.",
            dialogue='Dumble Dior: "Where are the receipts for the velvet robes?"',
        )
    ]

    compiled_prompt = compiler.compile_turn0_prompt(
        concept="Trapwarts audit confrontation in a multi-character scene with spoken dialogue and background music",
        characters=chars,
        scenes=scenes,
        strategy_bank=strategy_mgr,
        project_id=project_id,
        enable_preflight=True,
    )

    # Verify invariant directives were injected and preflight sanitized
    assert "[Directorial Invariants]" in compiled_prompt
    assert "Where are the receipts" in compiled_prompt
    assert "Role A" in compiled_prompt

    # Gatekeeper verification
    lint_result = PreFlightGatekeeper.lint_and_repair(compiled_prompt)
    assert lint_result.passed is True

    # Step 5: Simulate 5-Star Render & Director Rating -> Ingest into 5-Star Exemplar Bank
    exemplar = exemplar_mgr.ingest_5star_prompt(
        session_id="session_e2e_5star",
        concept="Trapwarts Audit Confrontation",
        compiled_prompt=compiled_prompt,
        user_rating=5,
        style_preset="cinematic",
        project_id=project_id,
    )
    assert exemplar.exemplar_id.startswith("ex_")
    assert exemplar.user_rating == 5

    # Step 6: Few-Shot Exemplar Block Injection for subsequent generations
    retrieved_exemplars = exemplar_mgr.query_relevant_exemplars(
        concept="Trapwarts wizard audit high drama",
        style_preset="cinematic",
        project_id=project_id,
        limit=2,
    )
    assert len(retrieved_exemplars) >= 1
    assert retrieved_exemplars[0].exemplar_id == exemplar.exemplar_id

    few_shot_block = exemplar_mgr.format_exemplars_as_few_shot_block(retrieved_exemplars)
    assert "DIRECTORIAL FEW-SHOT EXEMPLARS" in few_shot_block
    assert exemplar.prompt in few_shot_block


def test_doma_macro_api_round_trip():
    """Verifies the complete DOMA Phase 3 & 4 HTTP API surface via FastAPI TestClient."""
    app = create_app(mock_mode=True)
    client = TestClient(app)
    project_id = "proj_api_macro_test"
    session_id = "sess_api_macro_test"

    # 1. Post defect feedback
    for i in range(2):
        fb_resp = client.post(
            "/api/feedback",
            json={
                "session_id": f"{session_id}_{i}",
                "turn_id": "turn_0",
                "rating": 1,
                "defects": ["LIKENESS_DRIFT", "WARDROBE_CONTRADICTION"],
                "critique_text": "Character face shifted and robe color changed mid-scene.",
                "project_id": project_id,
            },
        )
        assert fb_resp.status_code == 200

    # 2. Induce rules
    induce_resp = client.post(
        "/api/eval/induce-rules",
        json={"project_id": project_id, "min_defect_count": 2},
    )
    assert induce_resp.status_code == 200
    induce_data = induce_resp.json()
    assert induce_data["status"] == "success"
    assert induce_data["count"] >= 1

    # 3. Retrieve active rules
    rules_resp = client.get(f"/api/eval/rules?project_id={project_id}")
    assert rules_resp.status_code == 200
    rules_data = rules_resp.json()
    assert rules_data["status"] == "success"
    assert rules_data["total"] >= 1

    # 4. Prune rules
    prune_resp = client.post(
        "/api/eval/rules/prune",
        json={"project_id": project_id, "max_rules": 10},
    )
    assert prune_resp.status_code == 200
    prune_data = prune_resp.json()
    assert prune_data["status"] == "success"

    # 5. Ingest 5-star exemplar
    sample_prompt = (
        "[SCENE SETUP]\n"
        "Hyper-realistic 35mm film scene.\n\n"
        "[CHARACTER CONTINUITY]\n"
        "@Image1: Dumble Dior in street robes.\n\n"
        "[ACTION & CAMERA]\n"
        "Slow pan across the ledger table.\n\n"
        "[AUDIO & DIALOGUE]\n"
        "Dumble Dior (booming): 'Pay the vault toll.'"
    )
    exemplar_resp = client.post(
        "/api/eval/exemplars",
        json={
            "session_id": session_id,
            "concept": "Master Vault Toll Scene",
            "compiled_prompt": sample_prompt,
            "user_rating": 5,
            "style_preset": "cinematic",
            "project_id": project_id,
        },
    )
    assert exemplar_resp.status_code == 200
    exemplar_data = exemplar_resp.json()
    assert exemplar_data["exemplar_id"].startswith("ex_")
    assert exemplar_data["user_rating"] == 5

    # 6. List exemplars
    list_resp = client.get(f"/api/eval/exemplars?project_id={project_id}")
    assert list_resp.status_code == 200
    exemplars_list = list_resp.json()
    assert len(exemplars_list) >= 1
    assert any(ex["exemplar_id"] == exemplar_data["exemplar_id"] for ex in exemplars_list)
