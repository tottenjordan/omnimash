"""Unit tests for ADK pipeline agents instantiation."""

from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from omnimash.agent.adk_pipeline import (
    build_production_orchestrator,
    create_final_cut_stitcher_agent,
    create_script_deconstructor_agent,
    create_shot_execution_worker,
    create_storyboard_compiler_agent,
)


def test_adk_deconstructor_and_storyboard_agents_instantiation():
    deconstructor = create_script_deconstructor_agent()
    storyboard_compiler = create_storyboard_compiler_agent()

    assert isinstance(deconstructor, Agent)
    assert deconstructor.name == "script_deconstructor"
    assert deconstructor.model == "gemini-omni-flash-preview"
    assert "Script Deconstructor Agent" in deconstructor.instruction

    assert isinstance(storyboard_compiler, Agent)
    assert storyboard_compiler.name == "storyboard_compiler"
    assert storyboard_compiler.model == "gemini-omni-flash-preview"
    assert "Storyboard Compiler Agent" in storyboard_compiler.instruction


def test_adk_shot_execution_and_stitcher_agents():
    shot_worker = create_shot_execution_worker(shot_idx=1)
    stitcher = create_final_cut_stitcher_agent()

    assert isinstance(shot_worker, Agent)
    assert shot_worker.name == "shot_execution_worker_1"
    assert shot_worker.model == "gemini-omni-flash-preview"
    assert "Shot Execution Worker Agent" in shot_worker.instruction
    assert "shot #1" in shot_worker.instruction

    assert isinstance(stitcher, Agent)
    assert stitcher.name == "final_cut_stitcher"
    assert stitcher.model == "gemini-omni-flash-preview"
    assert "Final Cut Stitcher Agent" in stitcher.instruction


def test_build_production_orchestrator():
    orchestrator = build_production_orchestrator(num_shots=3)

    assert isinstance(orchestrator, SequentialAgent)
    assert orchestrator.name == "root_production_orchestrator"
    assert len(orchestrator.sub_agents) == 4

    assert orchestrator.sub_agents[0].name == "script_deconstructor"
    assert orchestrator.sub_agents[1].name == "storyboard_compiler"

    shot_pipeline = orchestrator.sub_agents[2]
    assert isinstance(shot_pipeline, ParallelAgent)
    assert shot_pipeline.name == "shot_execution_pipeline"
    assert len(shot_pipeline.sub_agents) == 3
    assert [w.name for w in shot_pipeline.sub_agents] == [
        "shot_execution_worker_1",
        "shot_execution_worker_2",
        "shot_execution_worker_3",
    ]

    assert orchestrator.sub_agents[3].name == "final_cut_stitcher"


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


