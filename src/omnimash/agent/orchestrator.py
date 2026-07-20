from dataclasses import asdict, dataclass
from typing import Any

from google.adk.agents import Agent

from omnimash.engine.omni_client import OmniFlashClient
from omnimash.ingestion.media_extractor import MediaExtractor
from omnimash.prompts.compiler import CharacterRole, MetaPromptTags, SceneDirective
from omnimash.prompts.taxonomy import PromptTaxonomyEngine, StylePreset
from omnimash.security.guardrail import ModelArmorGuardrail
from omnimash.state.session_manager import SessionManager
from omnimash.storage.gcs import GcsStorageManager


@dataclass
class AgentTurnResponse:
    success: bool
    status_event: str
    video_url: str | None = None
    error_message: str | None = None
    generation_mode: str = "LIVE_OMNI_FLASH"
    turn_id: str | None = None
    depth: int = 0
    raw_compiled_prompt: str | None = None
    reference_analysis: dict | None = None


class OmniMashAgent:
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self.guardrail = ModelArmorGuardrail(mock_mode=mock_mode)
        self.session_manager = SessionManager()
        self.omni_client = OmniFlashClient(mock_mode=mock_mode)
        self.taxonomy = PromptTaxonomyEngine()
        self.media_extractor = MediaExtractor(mock_mode=mock_mode)
        self.storage = GcsStorageManager(mock_mode=mock_mode)

    def deconstruct_concept(self, concept: str) -> MetaPromptTags:
        return self.taxonomy.deconstruct_concept(concept)

    def process_user_turn(
        self,
        user_id: str,
        project_id: str,
        prompt: str = "",
        clip_index: int = 0,
        parent_turn_id: str | None = None,
        reference_url: str | None = None,
        audio_stem: str | None = None,
        voiceover: str | None = None,
        is_silent: bool = False,
        on_screen_text: str | None = None,
        compiled_override: str | None = None,
        session_name: str | None = None,
        concept: str | None = None,
        characters: list[Any] | None = None,
        scenes: list[dict] | None = None,
        aesthetic_tags: list[str] | None = None,
        environment_tag: str | None = None,
        vocal_delivery: str | None = None,
    ) -> AgentTurnResponse:
        session = self.session_manager.get_or_create_session(
            user_id, project_id, session_name=session_name
        )

        # Step 0: Process reference URL if provided
        reference_analysis = None
        if reference_url:
            self.media_extractor.process_youtube_url(
                reference_url, session_id=session.session_id
            )
            report = self.media_extractor.analyze_youtube_reference(
                reference_url, session_id=session.session_id
            )
            reference_analysis = asdict(report)

        # Step 1: Model Armor Gate
        input_prompt = prompt or concept or ""
        guard_res = self.guardrail.validate_prompt(input_prompt)
        if not guard_res.is_approved:
            return AgentTurnResponse(
                success=False,
                status_event="GUARDRAIL_BLOCKED",
                error_message=guard_res.rejection_reason,
            )

        # Step 2: Check if initial generation or conversational diff
        if parent_turn_id and parent_turn_id in session.turns:
            parent_turn = session.turns[parent_turn_id]
            delta_prompt = self.taxonomy.build_delta_prompt(
                parent_turn.prompt,
                guard_res.sanitized_prompt,
                override_prompt=compiled_override,
            )
            raw_compiled_prompt = delta_prompt
            self.storage.save_session_prompt(
                session.session_id, len(session.turns), delta_prompt
            )
            gen_res = self.omni_client.apply_interaction_diff(
                parent_turn.interaction_thread_id,
                delta_prompt,
                session_id=session.session_id,
                voiceover=voiceover,
                is_silent=is_silent,
                audio_stem=audio_stem,
            )
        else:
            if characters or scenes:
                char_objs: list[CharacterRole] = []
                if characters:
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
                                    voice_style=c.get("voice_style", ""),
                                )
                            )
                        elif hasattr(c, "model_dump"):
                            cd = c.model_dump()
                            char_objs.append(
                                CharacterRole(
                                    role_id=cd.get("role_id", ""),
                                    name=cd.get("name", ""),
                                    description=cd.get("description", ""),
                                    reference_url=cd.get("reference_url"),
                                    aesthetic_tags=cd.get("aesthetic_tags", []),
                                    voice_style=cd.get("voice_style", ""),
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
                                    voice_style=getattr(c, "voice_style", ""),
                                )
                            )
                scene_objs: list[SceneDirective] = []
                if scenes:
                    for s in scenes:
                        if isinstance(s, SceneDirective):
                            scene_objs.append(s)
                        elif isinstance(s, dict):
                            scene_objs.append(
                                SceneDirective(
                                    scene_number=s.get("scene_number", 0),
                                    active_roles=s.get("active_roles", []),
                                    action=s.get("action", ""),
                                    dialogue=s.get("dialogue", ""),
                                )
                            )
                storyboard_prompt = self.taxonomy.compiler.compile_storyboard(
                    concept=concept or guard_res.sanitized_prompt,
                    characters=char_objs,
                    scenes=scene_objs,
                    aesthetic_tags=aesthetic_tags,
                    environment_tag=environment_tag,
                    audio_beat=audio_stem,
                    vocal_delivery=vocal_delivery,
                )
                meta_prompt = (
                    compiled_override if compiled_override else storyboard_prompt
                )
            else:
                meta_prompt = self.taxonomy.build_initial_prompt(
                    base_character=guard_res.sanitized_prompt,
                    style_preset=StylePreset.NINETIES_RAP_VIDEO,
                    custom_instructions="parody skit",
                    audio_stem=audio_stem,
                    voiceover=voiceover,
                    is_silent=is_silent,
                    on_screen_text=on_screen_text,
                    override_prompt=compiled_override,
                )
            raw_compiled_prompt = meta_prompt
            self.storage.save_session_prompt(
                session.session_id, len(session.turns), meta_prompt
            )
            gen_res = self.omni_client.generate_clip(
                meta_prompt,
                session_id=session.session_id,
                voiceover=voiceover,
                is_silent=is_silent,
                audio_stem=audio_stem,
            )

        # Step 3: Persist Turn in Session Version Tree
        turn_node = self.session_manager.add_turn(
            session_id=session.session_id,
            clip_index=clip_index,
            prompt=guard_res.sanitized_prompt,
            interaction_thread_id=gen_res.interaction_thread_id,
            video_url=gen_res.video_url,
            parent_turn_id=parent_turn_id,
        )

        status_event = (
            "COMMIT_RECOMMENDED" if turn_node.edit_depth_in_thread >= 3 else "COMPLETED"
        )

        return AgentTurnResponse(
            success=True,
            status_event=status_event,
            video_url=gen_res.video_url,
            error_message=gen_res.error_message,
            generation_mode=gen_res.generation_mode,
            turn_id=turn_node.turn_id,
            depth=turn_node.edit_depth_in_thread,
            raw_compiled_prompt=raw_compiled_prompt,
            reference_analysis=reference_analysis,
        )

    def commit_and_branch(
        self,
        user_id: str,
        project_id: str,
        turn_id: str,
        prompt: str,
        session_name: str | None = None,
    ) -> AgentTurnResponse:
        guard_res = self.guardrail.validate_prompt(prompt)
        if not guard_res.is_approved:
            return AgentTurnResponse(
                success=False,
                status_event="GUARDRAIL_BLOCKED",
                error_message=guard_res.rejection_reason,
            )

        session = self.session_manager.get_or_create_session(
            user_id, project_id, session_name=session_name
        )
        if turn_id not in session.turns:
            return AgentTurnResponse(
                success=False,
                status_event="ERROR",
                error_message=f"Turn {turn_id} not found in session.",
            )

        committed_turn = self.session_manager.commit_turn(session.session_id, turn_id)
        gen_res = self.omni_client.start_thread_from_video(
            base_video_url=committed_turn.video_url,
            initial_prompt=guard_res.sanitized_prompt,
            session_id=session.session_id,
        )
        new_node = self.session_manager.add_turn(
            session_id=session.session_id,
            clip_index=committed_turn.clip_index,
            prompt=guard_res.sanitized_prompt,
            interaction_thread_id=gen_res.interaction_thread_id,
            video_url=gen_res.video_url,
            parent_turn_id=turn_id,
            is_checkpoint=True,
        )
        return AgentTurnResponse(
            success=True,
            status_event="REANCHORED",
            video_url=gen_res.video_url,
            error_message=gen_res.error_message,
            generation_mode=gen_res.generation_mode,
            turn_id=new_node.turn_id,
            depth=0,
        )

    def save_final_master(
        self,
        session_id: str | None,
        video_url: str,
        master_title: str,
    ) -> tuple[str, str]:
        return self.storage.save_final_master(
            session_id=session_id,
            source_rel_path=video_url,
            master_title=master_title,
        )

    def extend_scene(
        self,
        session_name: str | None = None,
        turn_id: str | None = None,
        next_scene_action: str = "",
        dialogue: str | None = None,
        active_roles: list[str] | None = None,
        user_id: str = "usr_default",
        project_id: str = "prj_default",
        vocal_delivery: str | None = None,
    ) -> AgentTurnResponse:
        prompt_parts = []
        if active_roles:
            roles_str = ", ".join(active_roles)
            prompt_parts.append(f"[{roles_str}]")
        if next_scene_action:
            prompt_parts.append(next_scene_action)
        if dialogue:
            prompt_parts.append(f'Dialogue: "{dialogue}"')

        combined_prompt = " ".join(prompt_parts) if prompt_parts else next_scene_action

        return self.process_user_turn(
            user_id=user_id,
            project_id=project_id,
            prompt=combined_prompt or next_scene_action,
            parent_turn_id=turn_id,
            session_name=session_name,
            voiceover=dialogue,
            vocal_delivery=vocal_delivery,
        )


def build_adk_agent(mock_mode: bool = True) -> Agent:
    """Builds and returns the official Google ADK Agent instance for OmniMash."""
    orchestrator = OmniMashAgent(mock_mode=mock_mode)

    def generate_parody_clip(
        user_id: str,
        project_id: str,
        prompt: str,
        clip_index: int = 0,
        parent_turn_id: str | None = None,
        reference_url: str | None = None,
    ) -> dict[str, str | bool | int | None]:
        """Generates a 720p parody video clip or conversational diff branch."""
        res = orchestrator.process_user_turn(
            user_id=user_id,
            project_id=project_id,
            prompt=prompt,
            clip_index=clip_index,
            parent_turn_id=parent_turn_id,
            reference_url=reference_url,
        )
        return {
            "success": res.success,
            "status": res.status_event,
            "video_url": res.video_url,
            "turn_id": res.turn_id,
            "depth": res.depth,
            "error": res.error_message,
        }

    instruction = (
        "You are the Prompt Compiler for OmniMash. Your job is to format user video concepts "
        "and conversational delta edits for the gemini-omni-flash-preview video model.\n\n"
        "Initial Video Turn Structure (6-Part Anchor & Inject):\n"
        "[SUBJECT ANCHOR] + [AESTHETIC INJECTION] + [ENVIRONMENT] + [CAMERA/LIGHTING] + [MOTION] + [AUDIO TRACK]\n\n"
        "Multi-Turn Conversational Delta Structure (Lock & Isolate):\n"
        "[PRESERVATION LOCK]: {maintain character face, likeness, expression, wardrobe baseline, environment, and audio stem rhythm} | "
        "[ISOLATED DIFF]: {alter only the single specified visual or acoustic variable}\n\n"
        "Rules:\n"
        "1. Prompt the video and audio layers simultaneously in the same payload so Omni Flash's joint latent space binds character kinematics to acoustic tempo.\n"
        "2. Never resubmit the massive full prompt on conversational delta edits to prevent facial shifting.\n"
        "3. Always acknowledge the lock first, then isolate the variable being altered."
    )

    return Agent(
        name="omnimash_orchestrator",
        model="gemini-omni-flash-preview",
        instruction=instruction,
        tools=[generate_parody_clip],
    )


root_agent = build_adk_agent(mock_mode=True)
