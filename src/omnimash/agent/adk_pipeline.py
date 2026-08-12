"""ADK Multi-Agent Pipeline for OmniMash Scene Breakdown and Storyboard Compilation."""

from google.adk.agents import Agent, ParallelAgent, SequentialAgent

DECONSTRUCTOR_DEFAULT_INSTRUCTION = (
    "You are the Script Deconstructor Agent for OmniMash. "
    "Your responsibility is to analyze user screenplay scripts and concepts, "
    "deconstructing them into structured scenes, active character roles, actions, "
    "dialogue beats, and visual/audio cues."
)

STORYBOARD_COMPILER_DEFAULT_INSTRUCTION = (
    "You are the Storyboard Compiler Agent for OmniMash. "
    "Your responsibility is to take deconstructed scene directives, character specifications, "
    "and style presets to compile precise 6-part video generation prompts formatted as: "
    "[SUBJECT ANCHOR] + [AESTHETIC INJECTION] + [ENVIRONMENT] + [CAMERA/LIGHTING] + [MOTION] + [AUDIO TRACK] "
    "optimized for Gemini Omni Flash (gemini-omni-flash-preview)."
)


SHOT_EXECUTION_WORKER_DEFAULT_INSTRUCTION = (
    "You are the Shot Execution Worker Agent for OmniMash. "
    "Your responsibility is to execute video generation calls for shot #{shot_idx} "
    "using Gemini Omni Flash (gemini-omni-flash-preview) based on compiled 6-part prompt specifications."
)

FINAL_CUT_STITCHER_DEFAULT_INSTRUCTION = (
    "You are the Final Cut Stitcher Agent for OmniMash. "
    "Your responsibility is to concatenate, assemble, and stitch individual rendered shot MP4 clips "
    "and cross-fade audio tracks into final master video compositions."
)


def create_script_deconstructor_agent(
    name: str = "script_deconstructor",
    model: str = "gemini-omni-flash-preview",
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for script deconstruction."""
    effective_instruction = instruction or DECONSTRUCTOR_DEFAULT_INSTRUCTION
    return Agent(
        name=name,
        model=model,
        instruction=effective_instruction,
        tools=tools or [],
    )


def create_storyboard_compiler_agent(
    name: str = "storyboard_compiler",
    model: str = "gemini-omni-flash-preview",
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for storyboard prompt compilation."""
    effective_instruction = instruction or STORYBOARD_COMPILER_DEFAULT_INSTRUCTION
    return Agent(
        name=name,
        model=model,
        instruction=effective_instruction,
        tools=tools or [],
    )


def create_shot_execution_worker(
    shot_idx: int,
    name: str | None = None,
    model: str = "gemini-omni-flash-preview",
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for rendering a single video shot."""
    effective_name = name or f"shot_execution_worker_{shot_idx}"
    effective_instruction = (
        instruction
        or SHOT_EXECUTION_WORKER_DEFAULT_INSTRUCTION.format(shot_idx=shot_idx)
    )
    return Agent(
        name=effective_name,
        model=model,
        instruction=effective_instruction,
        tools=tools or [],
    )


def create_final_cut_stitcher_agent(
    name: str = "final_cut_stitcher",
    model: str = "gemini-omni-flash-preview",
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for stitching rendered shot MP4 clips into a final master video."""
    effective_instruction = instruction or FINAL_CUT_STITCHER_DEFAULT_INSTRUCTION
    return Agent(
        name=name,
        model=model,
        instruction=effective_instruction,
        tools=tools or [],
    )


def build_production_orchestrator(num_shots: int = 3) -> SequentialAgent:
    """Builds the multi-agent production pipeline orchestrator."""
    deconstructor = create_script_deconstructor_agent()
    storyboard_compiler = create_storyboard_compiler_agent()
    shot_workers = [
        create_shot_execution_worker(shot_idx=i) for i in range(1, num_shots + 1)
    ]
    parallel_shots = ParallelAgent(
        name="shot_execution_pipeline",
        sub_agents=shot_workers,
    )
    stitcher = create_final_cut_stitcher_agent()

    return SequentialAgent(
        name="root_production_orchestrator",
        sub_agents=[
            deconstructor,
            storyboard_compiler,
            parallel_shots,
            stitcher,
        ],
    )


__all__ = [
    "create_script_deconstructor_agent",
    "create_storyboard_compiler_agent",
    "create_shot_execution_worker",
    "create_final_cut_stitcher_agent",
    "build_production_orchestrator",
]
