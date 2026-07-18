from dataclasses import dataclass

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


class OmniMashAgent:
    def __init__(self, mock_mode: bool = True):
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

        return AgentTurnResponse(
            success=True,
            status_event="COMPLETED",
            video_url=gen_res.video_url,
            turn_id=turn_node.turn_id,
        )
