"""Unit tests for Mode 5: Commercial Soundstage ADK 2.11+ multi-agent pipeline and Workflow DAG."""

from __future__ import annotations

import pytest
from google.adk.agents import Agent
from google.adk.workflow import Workflow

import omnimash.agent.adk_pipeline as adk_pipeline
from omnimash.agent.adk_pipeline import (
    build_soundstage_commercial_workflow,
    create_commercial_conformer_agent,
    create_doma_commercial_critic_agent,
    create_kit_and_boards_worker_agent,
    create_soundstage_act_worker,
    create_soundstage_physics_agent,
    create_soundstage_planner_agent,
    preflight_lint_and_repair,
)
from omnimash.config import settings
from omnimash.prompts.compiler import GEMINI_OMNI_FLASH_INSTR


def test_soundstage_agent_factories_models_tools_and_instructions() -> None:
    """Verifies all 6 Mode 5 ADK agent factories use configured models, tools, and canonical instructions."""
    physics_agent = create_soundstage_physics_agent()
    planner_agent = create_soundstage_planner_agent()
    kit_boards_agent = create_kit_and_boards_worker_agent()
    act_worker_1 = create_soundstage_act_worker(act_idx=1)
    act_worker_2 = create_soundstage_act_worker(act_idx=2)
    act_worker_3 = create_soundstage_act_worker(act_idx=3)
    conformer_agent = create_commercial_conformer_agent()
    critic_agent = create_doma_commercial_critic_agent()

    assert isinstance(physics_agent, Agent)
    assert physics_agent.name == "soundstage_physics_and_dna"
    assert physics_agent.model == settings.flash_model_id

    assert isinstance(planner_agent, Agent)
    assert planner_agent.name == "soundstage_three_act_planner"
    assert planner_agent.model == settings.pro_model_id
    assert preflight_lint_and_repair in planner_agent.tools
    planner_instr = str(planner_agent.instruction)
    assert "4-Block Meta-Prompt" in planner_instr
    assert "60/30/10" in planner_instr
    assert "3-act" in planner_instr.lower()
    assert GEMINI_OMNI_FLASH_INSTR in planner_instr

    assert isinstance(kit_boards_agent, Agent)
    assert kit_boards_agent.name == "kit_and_boards_worker"
    assert kit_boards_agent.model == settings.flash_model_id

    for idx, worker in enumerate((act_worker_1, act_worker_2, act_worker_3), start=1):
        assert isinstance(worker, Agent)
        assert worker.name == f"soundstage_act_worker_{idx}"
        assert worker.model == settings.flash_model_id
        worker_instr = str(worker.instruction)
        assert settings.omni_model_id in worker_instr
        assert "4-Block Meta-Prompt" in worker_instr

    assert isinstance(conformer_agent, Agent)
    assert conformer_agent.name == "commercial_conformer"
    assert conformer_agent.model == settings.flash_model_id

    assert isinstance(critic_agent, Agent)
    assert critic_agent.name == "doma_commercial_critic"
    assert critic_agent.model == settings.flash_model_id


def test_soundstage_agent_factories_accept_custom_overrides() -> None:
    """Verifies custom name, model, instruction, and tools overrides on Mode 5 agent factories."""
    planner = create_soundstage_planner_agent(
        name="custom_planner",
        model="gemini-3.8-flash",
        instruction="Custom planner instruction",
        tools=[],
    )
    assert planner.name == "custom_planner"
    assert planner.model == "gemini-3.8-flash"
    assert str(planner.instruction) == "Custom planner instruction"
    assert planner.tools == []

    worker = create_soundstage_act_worker(
        act_idx=2,
        name="custom_act_2",
        model="gemini-3.8-flash",
        instruction="Custom act 2 worker",
    )
    assert worker.name == "custom_act_2"
    assert str(worker.instruction) == "Custom act 2 worker"


def test_build_soundstage_commercial_workflow_dag_topology() -> None:
    """Verifies exact DAG node names and directed edges for soundstage_commercial_orchestrator."""
    workflow = build_soundstage_commercial_workflow(num_acts=3)

    assert isinstance(workflow, Workflow)
    assert workflow.name == "soundstage_commercial_orchestrator"
    assert workflow.graph is not None

    node_names = [n.name for n in workflow.graph.nodes]
    expected_nodes = [
        "__START__",
        "soundstage_physics_and_dna",
        "soundstage_three_act_planner",
        "kit_and_boards_worker",
        "soundstage_act_worker_1",
        "soundstage_act_worker_2",
        "soundstage_act_worker_3",
        "acts_execution_join",
        "commercial_conformer",
        "doma_commercial_critic",
    ]
    for expected in expected_nodes:
        assert expected in node_names

    edge_pairs = [(e.from_node.name, e.to_node.name) for e in workflow.graph.edges]
    expected_edges = [
        ("__START__", "soundstage_physics_and_dna"),
        ("soundstage_physics_and_dna", "soundstage_three_act_planner"),
        ("soundstage_three_act_planner", "kit_and_boards_worker"),
        ("kit_and_boards_worker", "soundstage_act_worker_1"),
        ("kit_and_boards_worker", "soundstage_act_worker_2"),
        ("kit_and_boards_worker", "soundstage_act_worker_3"),
        ("soundstage_act_worker_1", "acts_execution_join"),
        ("soundstage_act_worker_2", "acts_execution_join"),
        ("soundstage_act_worker_3", "acts_execution_join"),
        ("acts_execution_join", "commercial_conformer"),
        ("commercial_conformer", "doma_commercial_critic"),
    ]
    assert edge_pairs == expected_edges


@pytest.mark.parametrize("invalid_num_acts", [0, -1, -3, True, False])
def test_build_soundstage_commercial_workflow_rejects_invalid_num_acts(
    invalid_num_acts: int | bool,
) -> None:
    """Verifies num_acts < 1 or boolean values raise ValueError."""
    with pytest.raises(ValueError, match="num_acts"):
        build_soundstage_commercial_workflow(num_acts=invalid_num_acts)  # type: ignore[arg-type]


def test_soundstage_exports_present_in_adk_pipeline_all() -> None:
    """Verifies all Mode 5 factories and workflow builder are exported in adk_pipeline.__all__."""
    expected_exports = {
        "build_soundstage_commercial_workflow",
        "create_commercial_conformer_agent",
        "create_doma_commercial_critic_agent",
        "create_kit_and_boards_worker_agent",
        "create_soundstage_act_worker",
        "create_soundstage_physics_agent",
        "create_soundstage_planner_agent",
    }
    assert expected_exports.issubset(set(adk_pipeline.__all__))
