"""ADK Multi-Agent Pipeline for OmniMash Scene Breakdown and Storyboard Compilation."""

from typing import Any

from google.adk.agents import Agent
from google.adk.tools import AgentTool
from google.adk.workflow import START, JoinNode, Workflow

from omnimash.config import settings
from omnimash.prompts.compiler import CharacterRole, GEMINI_OMNI_FLASH_INSTR
from omnimash.prompts.storyboard_agent import StoryboardShot

DECONSTRUCTOR_DEFAULT_INSTRUCTION = (
    "You are the Script Deconstructor Agent for OmniMash. "
    "Your responsibility is to analyze user screenplay scripts and concepts, "
    "deconstructing them into structured scenes, active character roles, actions, "
    "dialogue beats, and visual/audio cues."
)

STORYBOARD_COMPILER_DEFAULT_INSTRUCTION = (
    "You are the Storyboard Compiler Agent for OmniMash. "
    "Your responsibility is to take deconstructed scene directives, character specifications, "
    "and style presets to compile precise 4-Block Meta-Prompt video generation prompts "
    "(`### INPUT ROLES & REFERENCES`, `### CHARACTER PROFILES`, `### SCENE INSTRUCTIONS`, `### TIMELINE`) "
    f"optimized for Gemini Omni Flash 1.1 ({settings.omni_model_id}).\n\n"
    f"{GEMINI_OMNI_FLASH_INSTR}"
)


SHOT_EXECUTION_WORKER_DEFAULT_INSTRUCTION = (
    "You are the Shot Execution Worker Agent for OmniMash. "
    "Your responsibility is to execute video generation calls for shot #{shot_idx} "
    f"using Gemini Omni Flash 1.1 ({settings.omni_model_id}) based on compiled 4-Block Meta-Prompt specifications."
)

FINAL_CUT_STITCHER_DEFAULT_INSTRUCTION = (
    "You are the Final Cut Stitcher Agent for OmniMash. "
    "Your responsibility is to concatenate, assemble, and stitch individual rendered shot MP4 clips "
    "and cross-fade audio tracks into final master video compositions."
)

INTENT_CLARIFIER_DEFAULT_INSTRUCTION = (
    "You are the Director's Assistant & Intent Clarifier Agent for OmniMash. "
    "Your responsibility is to take ambiguous, open-ended user intents and optional constraints, "
    "identify missing directorial slots (characters, setting, soundscape, sound effects, dialogue), "
    "generate clear 1-click multiple choice questions, and synthesize high-synergy 4-block "
    "production plans optimized for Gemini Omni Flash 1.1."
)


def create_intent_clarifier_agent(
    name: str = "intent_clarifier",
    model: str | None = None,
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for intent clarification and plan synthesis."""
    effective_instruction = instruction or INTENT_CLARIFIER_DEFAULT_INSTRUCTION
    return Agent(
        name=name,
        model=model or getattr(settings, "flash_model_id", "gemini-3.8-flash"),
        instruction=effective_instruction,
        tools=tools or [],
    )


def create_script_deconstructor_agent(
    name: str = "script_deconstructor",
    model: str | None = None,
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for script deconstruction."""
    effective_instruction = instruction or DECONSTRUCTOR_DEFAULT_INSTRUCTION
    return Agent(
        name=name,
        model=model or getattr(settings, "flash_model_id", "gemini-3.8-flash"),
        instruction=effective_instruction,
        tools=tools or [],
    )


def create_storyboard_compiler_agent(
    name: str = "storyboard_compiler",
    model: str | None = None,
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for storyboard prompt compilation."""
    effective_instruction = instruction or STORYBOARD_COMPILER_DEFAULT_INSTRUCTION
    return Agent(
        name=name,
        model=model or getattr(settings, "flash_model_id", "gemini-3.8-flash"),
        instruction=effective_instruction,
        tools=tools or [],
    )


def create_shot_execution_worker(
    shot_idx: int,
    name: str | None = None,
    model: str | None = None,
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for rendering a single video shot."""
    effective_name = name or f"shot_execution_worker_{shot_idx}"
    effective_instruction = instruction or SHOT_EXECUTION_WORKER_DEFAULT_INSTRUCTION.format(
        shot_idx=shot_idx
    )
    return Agent(
        name=effective_name,
        model=model or getattr(settings, "flash_model_id", "gemini-3.8-flash"),
        instruction=effective_instruction,
        tools=tools or [],
    )


def create_final_cut_stitcher_agent(
    name: str = "final_cut_stitcher",
    model: str | None = None,
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for stitching rendered shot MP4 clips into a final master video."""
    effective_instruction = instruction or FINAL_CUT_STITCHER_DEFAULT_INSTRUCTION
    return Agent(
        name=name,
        model=model or getattr(settings, "flash_model_id", "gemini-3.8-flash"),
        instruction=effective_instruction,
        tools=tools or [],
    )


def build_production_orchestrator(num_shots: int = 3) -> Workflow:
    """Builds the multi-agent production pipeline orchestrator as an ADK graph Workflow.

    Architecture (DAG):
      START -> script_deconstructor -> storyboard_compiler
             -> [shot_execution_worker_1 .. N in parallel]
             -> shot_join_node -> final_cut_stitcher
    """
    deconstructor = create_script_deconstructor_agent()
    storyboard_compiler = create_storyboard_compiler_agent()
    shot_workers = [create_shot_execution_worker(shot_idx=i) for i in range(1, num_shots + 1)]
    join_node = JoinNode(name="shot_join_node")
    stitcher = create_final_cut_stitcher_agent()

    edges: list[tuple[Any, Any]] = [
        (START, deconstructor),
        (deconstructor, storyboard_compiler),
    ]
    for worker in shot_workers:
        edges.append((storyboard_compiler, worker))
        edges.append((worker, join_node))
    edges.append((join_node, stitcher))

    return Workflow(
        name="root_production_orchestrator",
        edges=edges,
    )


def create_adk_agent_tool_pipeline() -> list[AgentTool]:
    """Creates ADK AgentTool wrappers for script_deconstructor and storyboard_compiler agents."""
    deconstructor = create_script_deconstructor_agent()
    storyboard_compiler = create_storyboard_compiler_agent()
    return [
        AgentTool(agent=deconstructor),
        AgentTool(agent=storyboard_compiler),
    ]


def deconstruct_screenplay_with_adk(
    concept: str,
    style_tone: str = "Cinematic Trap Parody",
    target_duration: float = 30.0,
    characters: list[CharacterRole] | list[dict] | None = None,
    screenplay_script: str = "",
    mock_mode: bool | None = None,
    camera_lighting: str | None = None,
    aesthetic_tags: list[str] | None = None,
    audio_beat: str | None = None,
    vocal_delivery: str | None = None,
    environment: str | None = None,
) -> list[StoryboardShot]:
    """Deconstructs screenplay scripts and concepts into storyboard shots using Google ADK ScriptDeconstructorAgent and StoryboardCompilerAgent."""
    from omnimash.prompts.character_roles import normalize_character_role
    from omnimash.prompts.storyboard_agent import StoryboardAgent

    sb_agent = StoryboardAgent(mock_mode=mock_mode)
    deconstructor_agent = create_script_deconstructor_agent(tools=[sb_agent.expand_vision])
    assert deconstructor_agent.name == "script_deconstructor"

    char_objs: list[CharacterRole] | None = None
    if characters:
        char_objs = [normalize_character_role(c) for c in characters]

    shots = sb_agent.expand_vision(
        concept=concept,
        style_tone=style_tone,
        target_duration=target_duration,
        characters=char_objs,
        screenplay_script=screenplay_script,
        camera_lighting=camera_lighting,
        aesthetic_tags=aesthetic_tags,
        audio_beat=audio_beat,
        vocal_delivery=vocal_delivery,
        environment=environment,
    )
    return shots


__all__ = [
    "INTENT_CLARIFIER_DEFAULT_INSTRUCTION",
    "create_script_deconstructor_agent",
    "create_storyboard_compiler_agent",
    "create_shot_execution_worker",
    "create_final_cut_stitcher_agent",
    "create_intent_clarifier_agent",
    "build_production_orchestrator",
    "create_adk_agent_tool_pipeline",
    "deconstruct_screenplay_with_adk",
]
