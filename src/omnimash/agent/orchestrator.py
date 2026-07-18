from dataclasses import dataclass

from google.adk.agents import Agent

from omnimash.engine.omni_client import OmniFlashClient
from omnimash.prompts.taxonomy import PromptTaxonomyEngine, StylePreset
from omnimash.security.guardrail import ModelArmorGuardrail
from omnimash.state.session_manager import SessionManager


@dataclass
class AgentTurnResponse:
    success: bool
    status_event: str
    video_url: str | None = None
    error_message: str | None = None
    turn_id: str | None = None
    depth: int = 0


class OmniMashAgent:
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self.guardrail = ModelArmorGuardrail(mock_mode=mock_mode)
        self.session_manager = SessionManager()
        self.omni_client = OmniFlashClient(mock_mode=mock_mode)
        self.taxonomy = PromptTaxonomyEngine()

    def process_user_turn(
        self,
        user_id: str,
        project_id: str,
        prompt: str,
        clip_index: int = 0,
        parent_turn_id: str | None = None,
    ) -> AgentTurnResponse:
        # Step 1: Model Armor Gate
        guard_res = self.guardrail.validate_prompt(prompt)
        if not guard_res.is_approved:
            return AgentTurnResponse(
                success=False,
                status_event="GUARDRAIL_BLOCKED",
                error_message=guard_res.rejection_reason,
            )

        # Step 2: Session Resolution
        session = self.session_manager.get_or_create_session(user_id, project_id)

        # Step 3: Check if initial generation or conversational diff
        if parent_turn_id and parent_turn_id in session.turns:
            parent_turn = session.turns[parent_turn_id]
            delta_prompt = self.taxonomy.build_delta_prompt(
                parent_turn.prompt, guard_res.sanitized_prompt
            )
            gen_res = self.omni_client.apply_interaction_diff(
                parent_turn.interaction_thread_id, delta_prompt
            )
        else:
            meta_prompt = self.taxonomy.build_initial_prompt(
                base_character=guard_res.sanitized_prompt,
                style_preset=StylePreset.NINETIES_RAP_VIDEO,
                custom_instructions="parody skit",
            )
            gen_res = self.omni_client.generate_clip(meta_prompt)

        # Step 4: Persist Turn in Session Version Tree
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
            turn_id=turn_node.turn_id,
            depth=turn_node.edit_depth_in_thread,
        )

    def commit_and_branch(
        self,
        user_id: str,
        project_id: str,
        turn_id: str,
        prompt: str,
    ) -> AgentTurnResponse:
        guard_res = self.guardrail.validate_prompt(prompt)
        if not guard_res.is_approved:
            return AgentTurnResponse(
                success=False,
                status_event="GUARDRAIL_BLOCKED",
                error_message=guard_res.rejection_reason,
            )

        session = self.session_manager.get_or_create_session(user_id, project_id)
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
            turn_id=new_node.turn_id,
            depth=0,
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
    ) -> dict[str, str | bool | int | None]:
        """Generates a 720p parody video clip or conversational diff branch."""
        res = orchestrator.process_user_turn(
            user_id=user_id,
            project_id=project_id,
            prompt=prompt,
            clip_index=clip_index,
            parent_turn_id=parent_turn_id,
        )
        return {
            "success": res.success,
            "status": res.status_event,
            "video_url": res.video_url,
            "turn_id": res.turn_id,
            "depth": res.depth,
            "error": res.error_message,
        }

    return Agent(
        name="omnimash_orchestrator",
        model="gemini-omni-flash-preview",
        instruction=(
            "You are OmniMash, an AI parody and mashup video creation agent. "
            "Use generate_parody_clip to validate prompts through Model Armor, "
            "structure style-blended prompts, and generate 720p clips."
        ),
        tools=[generate_parody_clip],
    )


root_agent = build_adk_agent(mock_mode=True)
