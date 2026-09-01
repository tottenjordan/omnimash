"""ADK Multi-Agent Pipeline for OmniMash Scene Breakdown and Storyboard Compilation."""

from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.tools import AgentTool

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
    "and style presets to compile precise 6-part video generation prompts formatted as: "
    "[SUBJECT ANCHOR] + [AESTHETIC INJECTION] + [ENVIRONMENT] + [CAMERA/LIGHTING] + [MOTION] + [AUDIO TRACK] "
    "optimized for Gemini Omni Flash (gemini-omni-flash-preview).\n\n"
    f"{GEMINI_OMNI_FLASH_INSTR}"
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
) -> list[StoryboardShot]:
    """Deconstructs screenplay scripts and concepts into storyboard shots using Google ADK ScriptDeconstructorAgent and StoryboardCompilerAgent."""
    deconstructor = create_script_deconstructor_agent()
    compiler = create_storyboard_compiler_agent()

    from omnimash.prompts.storyboard_agent import StoryboardAgent

    sb_agent = StoryboardAgent()

    char_objs: list[CharacterRole] | None = None
    if characters:
        char_objs = []
        for c in characters:
            if isinstance(c, CharacterRole):
                char_objs.append(c)
            elif isinstance(c, dict):
                char_objs.append(
                    CharacterRole(
                        role_id=c.get("role_id", ""),
                        name=c.get("name", ""),
                        description=c.get("description", ""),
                        reference_url=c.get("reference_url"),
                        aesthetic_tags=c.get("aesthetic_tags", []),
                        voice_style=c.get("voice_style") or c.get("voice_profile") or "",
                        voice_profile=c.get("voice_style") or c.get("voice_profile") or "",
                        wardrobe=c.get("wardrobe", ""),
                        image_role=c.get("image_role", "Character Reference"),
                        is_offscreen_narrator=c.get("is_offscreen_narrator", False),
                    )
                )
            elif hasattr(c, "role_id"):
                char_objs.append(
                    CharacterRole(
                        role_id=getattr(c, "role_id", ""),
                        name=getattr(c, "name", ""),
                        description=getattr(c, "description", ""),
                        reference_url=getattr(c, "reference_url", None),
                        aesthetic_tags=getattr(c, "aesthetic_tags", []),
                        voice_style=getattr(c, "voice_style", "") or getattr(c, "voice_profile", ""),
                        voice_profile=getattr(c, "voice_style", "") or getattr(c, "voice_profile", ""),
                        wardrobe=getattr(c, "wardrobe", ""),
                        image_role=getattr(c, "image_role", "Character Reference"),
                        is_offscreen_narrator=getattr(c, "is_offscreen_narrator", False),
                    )
                )

    shots = sb_agent.expand_vision(
        concept=concept,
        style_tone=style_tone,
        target_duration=target_duration,
        characters=char_objs,
        screenplay_script=screenplay_script,
    )
    return shots


__all__ = [
    "create_script_deconstructor_agent",
    "create_storyboard_compiler_agent",
    "create_shot_execution_worker",
    "create_final_cut_stitcher_agent",
    "build_production_orchestrator",
    "create_adk_agent_tool_pipeline",
    "deconstruct_screenplay_with_adk",
]


