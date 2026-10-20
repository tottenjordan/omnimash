"""Unit tests for ADK pipeline agents instantiation."""

from google.adk.agents import Agent
from google.adk.workflow import Workflow
from omnimash.agent.adk_pipeline import (
    build_production_orchestrator,
    create_final_cut_stitcher_agent,
    create_script_deconstructor_agent,
    create_shot_execution_worker,
    create_storyboard_compiler_agent,
)


def test_adk_deconstructor_and_storyboard_agents_instantiation():
    from omnimash.config import settings

    deconstructor = create_script_deconstructor_agent()
    storyboard_compiler = create_storyboard_compiler_agent()

    assert isinstance(deconstructor, Agent)
    assert deconstructor.name == "script_deconstructor"
    assert deconstructor.model == settings.flash_model_id
    assert "Script Deconstructor Agent" in str(deconstructor.instruction)

    assert isinstance(storyboard_compiler, Agent)
    assert storyboard_compiler.name == "storyboard_compiler"
    assert storyboard_compiler.model == settings.flash_model_id
    assert "Storyboard Compiler Agent" in str(storyboard_compiler.instruction)


def test_adk_shot_execution_and_stitcher_agents():
    from omnimash.config import settings

    shot_worker = create_shot_execution_worker(shot_idx=1)
    stitcher = create_final_cut_stitcher_agent()

    assert isinstance(shot_worker, Agent)
    assert shot_worker.name == "shot_execution_worker_1"
    assert shot_worker.model == settings.flash_model_id
    assert "Shot Execution Worker Agent" in str(shot_worker.instruction)
    assert "shot #1" in str(shot_worker.instruction)

    assert isinstance(stitcher, Agent)
    assert stitcher.name == "final_cut_stitcher"
    assert stitcher.model == settings.flash_model_id
    assert "Final Cut Stitcher Agent" in str(stitcher.instruction)


def test_build_production_orchestrator():
    orchestrator = build_production_orchestrator(num_shots=3)

    assert isinstance(orchestrator, Workflow)
    assert orchestrator.name == "root_production_orchestrator"
    assert orchestrator.graph is not None

    node_names = [n.name for n in orchestrator.graph.nodes]
    assert "__START__" in node_names
    assert "script_deconstructor" in node_names
    assert "storyboard_compiler" in node_names
    assert "shot_execution_worker_1" in node_names
    assert "shot_execution_worker_2" in node_names
    assert "shot_execution_worker_3" in node_names
    assert "shot_join_node" in node_names
    assert "final_cut_stitcher" in node_names

    # Check DAG edge topology
    edge_pairs = [(e.from_node.name, e.to_node.name) for e in orchestrator.graph.edges]
    assert ("__START__", "script_deconstructor") in edge_pairs
    assert ("script_deconstructor", "storyboard_compiler") in edge_pairs
    assert ("storyboard_compiler", "shot_execution_worker_1") in edge_pairs
    assert ("storyboard_compiler", "shot_execution_worker_2") in edge_pairs
    assert ("storyboard_compiler", "shot_execution_worker_3") in edge_pairs
    assert ("shot_execution_worker_1", "shot_join_node") in edge_pairs
    assert ("shot_execution_worker_2", "shot_join_node") in edge_pairs
    assert ("shot_execution_worker_3", "shot_join_node") in edge_pairs
    assert ("shot_join_node", "final_cut_stitcher") in edge_pairs


def test_adk_pipeline_instructions_include_omni_flash_guidance_and_agent_tools():
    from google.adk.tools import AgentTool
    from omnimash.agent.adk_pipeline import (
        STORYBOARD_COMPILER_DEFAULT_INSTRUCTION,
        create_adk_agent_tool_pipeline,
    )
    from omnimash.prompts.compiler import GEMINI_OMNI_FLASH_INSTR

    assert GEMINI_OMNI_FLASH_INSTR in STORYBOARD_COMPILER_DEFAULT_INSTRUCTION
    tools = create_adk_agent_tool_pipeline()
    assert isinstance(tools, list)
    assert len(tools) >= 2
    assert all(isinstance(t, AgentTool) for t in tools)


def test_adk_agents_use_configured_models_and_4_block_instructions():
    from omnimash.agent.adk_pipeline import (
        SHOT_EXECUTION_WORKER_DEFAULT_INSTRUCTION,
        STORYBOARD_COMPILER_DEFAULT_INSTRUCTION,
    )
    from omnimash.config import settings

    assert "[SUBJECT ANCHOR]" not in STORYBOARD_COMPILER_DEFAULT_INSTRUCTION
    assert "4-Block Meta-Prompt" in STORYBOARD_COMPILER_DEFAULT_INSTRUCTION
    assert "4-Block Meta-Prompt" in SHOT_EXECUTION_WORKER_DEFAULT_INSTRUCTION
    assert settings.omni_model_id == "gemini-omni-1.1-flash-preview"


def test_adk_script_deconstructor_expands_storyboard():
    from unittest.mock import patch
    from omnimash.agent import adk_pipeline
    from omnimash.prompts.storyboard_agent import StoryboardShot

    with patch(
        "omnimash.agent.adk_pipeline.create_script_deconstructor_agent",
        wraps=adk_pipeline.create_script_deconstructor_agent,
    ) as spy_deconstructor:
        shots = adk_pipeline.deconstruct_screenplay_with_adk(
            concept="Cyberpunk battle",
            style_tone="Cinematic Trap Parody",
            target_duration=30.0,
            screenplay_script="[00:00-00:05] Intro shot: Neon street\n[00:05-00:10] Action: Duel begins",
            mock_mode=True,
        )
        assert spy_deconstructor.call_count == 1
    assert isinstance(shots, list)
    assert len(shots) == 2
    assert isinstance(shots[0], StoryboardShot)
    assert shots[0].shot_index == 1
    assert shots[0].duration_seconds == 5.0
    assert "Neon street" in shots[0].summary or "Neon street" in shots[0].action
