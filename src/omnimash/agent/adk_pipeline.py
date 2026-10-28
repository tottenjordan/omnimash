"""ADK Multi-Agent Pipeline for OmniMash Scene Breakdown and Storyboard Compilation."""

from typing import Any

from google.adk.agents import Agent
from google.adk.tools import AgentTool
from google.adk.workflow import START, JoinNode, Workflow

from omnimash.config import settings
from omnimash.prompts.compiler import CharacterRole, GEMINI_OMNI_FLASH_INSTR
from omnimash.prompts.preflight_linter import PreFlightGatekeeper
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
    "Enforce DOMA Phase 3 directorial invariants and pre-flight validation via PreFlightGatekeeper: "
    "1. Tag collision repair: clean stacked <IMAGE_REF_N> tags, eliminate duplicate @Image tokens, and strip unattached phantom tokens.\n"
    "2. Keyframe offset repair: auto-shift character reference tags from @Image1 to @Image2 (or @Image3 for dual-keyframe / seamless loop) when keyframe seed is provided.\n"
    "3. Zero Wardrobe Redundancy: scrub conflicting prose wardrobe descriptions for characters with reference sheets to lock visual appearance.\n"
    "4. Dual-layer audio ducking: enforce instrumental prefix on background score and inject canonical audio ducking clause under spoken dialogue.\n"
    "5. Spatial staging: enforce screen-left / screen-right staging for multi-character interaction scenes.\n\n"
    f"{GEMINI_OMNI_FLASH_INSTR}"
)


def preflight_lint_and_repair(
    prompt: str,
    keyframe_image_url: str | None = None,
    last_frame_image_url: str | None = None,
    is_seamless_loop: bool = False,
    has_dialogue: bool = False,
    offering_physics: dict[str, Any] | None = None,
    palette_60_30_10: dict[str, Any] | None = None,
    act_number: int | None = None,
) -> dict[str, Any]:
    """Validates and auto-repairs prompt against DOMA Phase 3 and Mode 5 Soundstage invariants using PreFlightGatekeeper.

    Enforces tag collision repair, keyframe offset adjustments, zero wardrobe redundancy,
    dual-layer audio ducking, spatial staging, 60/30/10 palette lock, and 3-act causality gates.
    """
    res = PreFlightGatekeeper.lint_and_repair(
        prompt_text=prompt,
        keyframe_image_url=keyframe_image_url,
        last_frame_image_url=last_frame_image_url,
        is_seamless_loop=is_seamless_loop,
        has_dialogue=has_dialogue,
        offering_physics=offering_physics,
        palette_60_30_10=palette_60_30_10,
        act_number=act_number,
    )
    return {
        "is_valid": res.is_valid,
        "repaired_prompt": res.repaired_prompt,
        "violations": [v.model_dump() for v in res.violations],
        "invariants_applied": res.invariants_applied,
    }


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
    """Creates a Google ADK Agent for storyboard prompt compilation and PreFlightGatekeeper invariant enforcement."""
    effective_instruction = instruction or STORYBOARD_COMPILER_DEFAULT_INSTRUCTION
    effective_tools = tools if tools is not None else [preflight_lint_and_repair]
    return Agent(
        name=name,
        model=model or getattr(settings, "flash_model_id", "gemini-3.8-flash"),
        instruction=effective_instruction,
        tools=effective_tools,
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


SOUNDSTAGE_PHYSICS_DEFAULT_INSTRUCTION = (
    "You are the Mode 5 Commercial Soundstage Offering Physics & Brand DNA Agent for OmniMash. "
    "Your responsibility is to deduce first-principles physical scale, human-offering ergonomic roles, "
    "surface branding constraints, thermal equilibrium states, 3-act temporal causality laws, "
    "60/30/10 architectural palette color locks, and Dual-Layer brand/cast trademark abstractions."
)

SOUNDSTAGE_PLANNER_DEFAULT_INSTRUCTION = (
    "You are the Mode 5 Commercial Soundstage Three-Act Planner Agent for OmniMash. "
    "Your responsibility is to architect a 30-second 3-act x 3-beat (9-tile) commercial spot plan "
    "and compile trademark-scrubbed 4-Block Meta-Prompt act directives "
    "(`### INPUT ROLES & REFERENCES`, `### CHARACTER PROFILES`, `### SCENE INSTRUCTIONS`, `### TIMELINE`) "
    f"for Gemini Omni Flash ({settings.omni_model_id}).\n\n"
    "Enforce strict 60/30/10 production design palette lock, 3-act temporal causality gates "
    "(Act 1 pre-interaction empty-handed anticipation, Act 2 tactile first contact + 100mm human-free "
    "craft macro + signature reaction, Act 3 post-experience payoff + motionless solo hero packshot), "
    "dual-keyframe slot offsets (@Image3/@Image4), and pre-flight validation via preflight_lint_and_repair.\n\n"
    f"{GEMINI_OMNI_FLASH_INSTR}"
)

KIT_AND_BOARDS_WORKER_DEFAULT_INSTRUCTION = (
    "You are the Mode 5 Reference Kit & 9-Tile Storyboard Worker Agent for OmniMash. "
    "Your responsibility is to synthesize stylized 2K multi-panel character turnaround reference sheets, "
    "abstract geometric emblem marks, 1:1 hero offering packshots, and all 9 dual-keyframe storyboard plates "
    "(`1.1` through `3.3`), strictly isolating human-free (`has_person=False`) plates (`1.3`, `2.2`, `3.3`) "
    "from cast reference bleed."
)

SOUNDSTAGE_ACT_WORKER_DEFAULT_INSTRUCTION = (
    "You are the Mode 5 Soundstage Act Execution Worker Agent for OmniMash. "
    "Your responsibility is to film continuous 10-second commercial Act #{act_idx} with native synchronized "
    "voiceover, foley, and ducked instrumental score using Gemini Omni Flash ({omni_model_id}) anchored by "
    "<FIRST_FRAME>, <LAST_FRAME>, and compiled 4-Block Meta-Prompt specifications."
)

COMMERCIAL_CONFORMER_DEFAULT_INSTRUCTION = (
    "You are the Mode 5 Commercial Conformer Agent for OmniMash. "
    "Your responsibility is to conform rendered 10-second continuous act clips with sub-shot NLE trims, "
    "-18dB dialogue audio ducking, and WCAG contrast-verified editorial brand lockup end-cards into "
    "30s 16:9 Master, 15s 9:16 Cutdown, and 6s 9:16 Bumper deliverables plus campaign archive packages."
)

DOMA_COMMERCIAL_CRITIC_DEFAULT_INSTRUCTION = (
    "You are the Mode 5 DOMA Commercial Critic Agent for OmniMash. "
    "Your responsibility is to evaluate conformed commercial Soundstage deliverables across 4 rubric "
    "dimensions: 3-act temporal causality & video-text adherence, cast/offering reference likeness, "
    "-18dB audio ducking harmony, and ordinal tag/index symmetry."
)


def create_soundstage_physics_agent(
    name: str = "soundstage_physics_and_dna",
    model: str | None = None,
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for Mode 5 offering physics deduction and brand DNA discovery."""
    effective_instruction = instruction or SOUNDSTAGE_PHYSICS_DEFAULT_INSTRUCTION
    return Agent(
        name=name,
        model=model or getattr(settings, "flash_model_id", "gemini-3.8-flash"),
        instruction=effective_instruction,
        tools=tools or [],
    )


def create_soundstage_planner_agent(
    name: str = "soundstage_three_act_planner",
    model: str | None = None,
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for Mode 5 3-act x 3-beat commercial planning and 4-Block compilation."""
    effective_instruction = instruction or SOUNDSTAGE_PLANNER_DEFAULT_INSTRUCTION
    effective_tools = tools if tools is not None else [preflight_lint_and_repair]
    return Agent(
        name=name,
        model=model or getattr(settings, "pro_model_id", "gemini-4-argon"),
        instruction=effective_instruction,
        tools=effective_tools,
    )


def create_kit_and_boards_worker_agent(
    name: str = "kit_and_boards_worker",
    model: str | None = None,
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for Mode 5 reference kit synthesis and 9-tile storyboard generation."""
    effective_instruction = instruction or KIT_AND_BOARDS_WORKER_DEFAULT_INSTRUCTION
    return Agent(
        name=name,
        model=model or getattr(settings, "flash_model_id", "gemini-3.8-flash"),
        instruction=effective_instruction,
        tools=tools or [],
    )


def create_soundstage_act_worker(
    act_idx: int,
    name: str | None = None,
    model: str | None = None,
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for filming a single 10-second continuous Mode 5 commercial act."""
    effective_name = name or f"soundstage_act_worker_{act_idx}"
    omni_id = getattr(settings, "omni_model_id", "gemini-omni-1.1-flash")
    effective_instruction = instruction or SOUNDSTAGE_ACT_WORKER_DEFAULT_INSTRUCTION.format(
        act_idx=act_idx,
        omni_model_id=omni_id,
    )
    return Agent(
        name=effective_name,
        model=model or getattr(settings, "flash_model_id", "gemini-3.8-flash"),
        instruction=effective_instruction,
        tools=tools or [],
    )


def create_commercial_conformer_agent(
    name: str = "commercial_conformer",
    model: str | None = None,
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for Mode 5 post-production conforming and multi-format deliverables."""
    effective_instruction = instruction or COMMERCIAL_CONFORMER_DEFAULT_INSTRUCTION
    return Agent(
        name=name,
        model=model or getattr(settings, "flash_model_id", "gemini-3.8-flash"),
        instruction=effective_instruction,
        tools=tools or [],
    )


def create_doma_commercial_critic_agent(
    name: str = "doma_commercial_critic",
    model: str | None = None,
    instruction: str | None = None,
    tools: list | None = None,
) -> Agent:
    """Creates a Google ADK Agent for Mode 5 DOMA commercial video evaluation."""
    effective_instruction = instruction or DOMA_COMMERCIAL_CRITIC_DEFAULT_INSTRUCTION
    return Agent(
        name=name,
        model=model or getattr(settings, "flash_model_id", "gemini-3.8-flash"),
        instruction=effective_instruction,
        tools=tools or [],
    )


def build_soundstage_commercial_workflow(num_acts: int = 3) -> Workflow:
    """Builds the Mode 5 Commercial Soundstage multi-agent DAG as an ADK 2.11+ Workflow.

    Architecture (DAG):
      START -> soundstage_physics_and_dna -> soundstage_three_act_planner -> kit_and_boards_worker
             -> [soundstage_act_worker_1 .. soundstage_act_worker_{num_acts} in parallel]
             -> JoinNode(name="acts_execution_join") -> commercial_conformer -> doma_commercial_critic
    """
    if isinstance(num_acts, bool) or not isinstance(num_acts, int) or num_acts < 1:
        raise ValueError(f"num_acts must be an integer >= 1, got {num_acts!r}.")

    physics_agent = create_soundstage_physics_agent()
    planner_agent = create_soundstage_planner_agent()
    kit_and_boards = create_kit_and_boards_worker_agent()
    act_workers = [create_soundstage_act_worker(act_idx=i) for i in range(1, num_acts + 1)]
    acts_join = JoinNode(name="acts_execution_join")
    conformer = create_commercial_conformer_agent()
    critic = create_doma_commercial_critic_agent()

    edges: list[tuple[Any, Any]] = [
        (START, physics_agent),
        (physics_agent, planner_agent),
        (planner_agent, kit_and_boards),
    ]
    for worker in act_workers:
        edges.append((kit_and_boards, worker))
    for worker in act_workers:
        edges.append((worker, acts_join))
    edges.append((acts_join, conformer))
    edges.append((conformer, critic))

    return Workflow(
        name="soundstage_commercial_orchestrator",
        edges=edges,
    )


__all__ = [
    "COMMERCIAL_CONFORMER_DEFAULT_INSTRUCTION",
    "DOMA_COMMERCIAL_CRITIC_DEFAULT_INSTRUCTION",
    "INTENT_CLARIFIER_DEFAULT_INSTRUCTION",
    "KIT_AND_BOARDS_WORKER_DEFAULT_INSTRUCTION",
    "SOUNDSTAGE_ACT_WORKER_DEFAULT_INSTRUCTION",
    "SOUNDSTAGE_PHYSICS_DEFAULT_INSTRUCTION",
    "SOUNDSTAGE_PLANNER_DEFAULT_INSTRUCTION",
    "STORYBOARD_COMPILER_DEFAULT_INSTRUCTION",
    "build_production_orchestrator",
    "build_soundstage_commercial_workflow",
    "create_adk_agent_tool_pipeline",
    "create_commercial_conformer_agent",
    "create_doma_commercial_critic_agent",
    "create_final_cut_stitcher_agent",
    "create_intent_clarifier_agent",
    "create_kit_and_boards_worker_agent",
    "create_script_deconstructor_agent",
    "create_shot_execution_worker",
    "create_soundstage_act_worker",
    "create_soundstage_physics_agent",
    "create_soundstage_planner_agent",
    "create_storyboard_compiler_agent",
    "deconstruct_screenplay_with_adk",
    "preflight_lint_and_repair",
]
