import re
import urllib.parse
from dataclasses import asdict, dataclass
from typing import Any

from google.adk.agents import Agent

from omnimash.engine.omni_client import OmniFlashClient
from omnimash.ingestion.media_extractor import MediaExtractor
from omnimash.prompts.compiler import CharacterRole, MetaPromptTags, SceneDirective
from omnimash.prompts.storyboard_agent import StoryboardAgent, StoryboardShot
from omnimash.prompts.taxonomy import PromptTaxonomyEngine, StylePreset
from omnimash.security.guardrail import ModelArmorGuardrail
from omnimash.state.session_manager import SessionManager
from omnimash.stitching.stitcher import VideoStitcher
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
        self.taxonomy = PromptTaxonomyEngine(mock_mode=mock_mode)
        self.media_extractor = MediaExtractor(mock_mode=mock_mode)
        self.storage = GcsStorageManager(mock_mode=mock_mode)
        self.stitcher = VideoStitcher(mock_mode=mock_mode)
        self.storyboard_agent = StoryboardAgent(mock_mode=mock_mode)

    def deconstruct_concept(self, concept: str) -> MetaPromptTags:
        return self.taxonomy.deconstruct_concept(concept)

    def expand_storyboard(
        self,
        concept: str,
        style_tone: str = "Cinematic Trap Parody",
        target_duration: float = 30.0,
    ) -> list[StoryboardShot]:
        return self.storyboard_agent.expand_vision(
            concept, style_tone=style_tone, target_duration=target_duration
        )

    def validate_conversational_edit(self, edit_prompt: str) -> tuple[bool, str]:
        """Validates that a conversational edit prompt contains only a single change.

        Enforces Google's Golden Rule for Gemini Omni Flash edits: One change per turn.
        """
        rejection_msg = (
            "Gemini Omni Flash performs best with one edit per turn to maintain scene coherence. "
            "Please split your request into single edits (e.g. first change the outfit, then adjust camera angle)."
        )

        if not edit_prompt or not edit_prompt.strip():
            return True, ""

        prompt_clean = edit_prompt.strip().lower()

        # Check for sequential/compound connectors
        connectors = [
            r"\bthen\b",
            r"\balso\b",
            r"\badditionally\b",
            r"\bplus\b",
            r"\bas well as\b",
            r"\balong with\b",
            r"\band also\b",
            r"\bafter that\b",
        ]
        for conn in connectors:
            if re.search(conn, prompt_clean):
                return False, rejection_msg

        # Match edit action verbs
        action_verbs = [
            "add",
            "adding",
            "change",
            "changing",
            "switch",
            "switching",
            "replace",
            "replacing",
            "remove",
            "removing",
            "make",
            "making",
            "adjust",
            "adjusting",
            "swap",
            "swapping",
            "turn",
            "turning",
            "alter",
            "altering",
            "modify",
            "modifying",
            "set",
            "setting",
            "zoom",
            "zooming",
            "pan",
            "panning",
            "rotate",
            "rotating",
            "shift",
            "shifting",
            "transform",
            "transforming",
            "update",
            "updating",
        ]
        verb_pattern = r"\b(" + "|".join(action_verbs) + r")\b"
        matched_verbs = re.findall(verb_pattern, prompt_clean)

        if len(matched_verbs) >= 2:
            return False, rejection_msg

        # Check for comma or semicolon separated clauses/actions
        comma_parts = [p.strip() for p in re.split(r"[,;]", prompt_clean) if p.strip()]
        if len(comma_parts) >= 2:
            if len(comma_parts) >= 3:
                return False, rejection_msg
            p2 = comma_parts[1]
            if (
                re.search(verb_pattern, p2)
                or re.search(r"\bto\b", p2)
                or re.search(r"\binto\b", p2)
                or p2.startswith("and ")
            ):
                return False, rejection_msg

        # Check for "and" joining two distinct edit clauses
        and_parts = [p.strip() for p in re.split(r"\band\b", prompt_clean) if p.strip()]
        if len(and_parts) >= 2:
            if re.search(r"\bto\b", and_parts[0]) and re.search(r"\bto\b", and_parts[1]):
                return False, rejection_msg
            if len(and_parts) >= 3:
                return False, rejection_msg

        return True, ""

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
        optimize_prompt: bool = False,
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

        turn_index = len(session.turns)
        if parent_turn_id and parent_turn_id in session.turns:
            is_valid, edit_err = self.validate_conversational_edit(
                guard_res.sanitized_prompt
            )
            if not is_valid:
                return AgentTurnResponse(
                    success=False,
                    status_event="MULTI_CHANGE_REJECTED",
                    error_message=edit_err,
                )
            parent_turn = session.turns[parent_turn_id]
            delta_prompt = self.taxonomy.build_delta_prompt(
                parent_turn.prompt,
                guard_res.sanitized_prompt,
                override_prompt=compiled_override,
            )
            raw_compiled_prompt = delta_prompt
            self.storage.save_session_prompt(
                session.session_id, turn_index, delta_prompt
            )
            gen_res = self._execute_turn_generation(
                session_id=session.session_id,
                turn_index=turn_index,
                prompt=delta_prompt,
                parent_thread_id=parent_turn.interaction_thread_id,
                voiceover=voiceover,
                is_silent=is_silent,
                audio_stem=audio_stem,
                characters=char_objs,
            )
        else:
            if characters or scenes:
                scene_objs: list[SceneDirective] = []
                if scenes:
                    for s in scenes:
                        if isinstance(s, SceneDirective):
                            scene_objs.append(s)
                        elif isinstance(s, dict):
                            sp_script = s.get("screenplay_text") or s.get("screenplay_script")
                            scene_objs.append(
                                SceneDirective(
                                    scene_number=s.get("scene_number", 0),
                                    active_roles=s.get("active_roles", []),
                                    action=s.get("action", ""),
                                    dialogue=s.get("dialogue", ""),
                                    screenplay_text=sp_script if isinstance(sp_script, str) else None,
                                    audio_cues=s.get("audio_cues", ""),
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
            if optimize_prompt:
                meta_prompt = self.taxonomy.compiler.optimize_prompt_for_omni_flash(
                    meta_prompt, use_llm=True
                )
            raw_compiled_prompt = meta_prompt
            self.storage.save_session_prompt(
                session.session_id, turn_index, meta_prompt
            )
            gen_res = self._execute_turn_generation(
                session_id=session.session_id,
                turn_index=turn_index,
                prompt=meta_prompt,
                parent_thread_id=None,
                voiceover=voiceover,
                is_silent=is_silent,
                audio_stem=audio_stem,
                characters=char_objs,
            )

        # Step 3: Persist Turn in Session Version Tree
        proxy_video_url = self._get_media_proxy_video_url(
            getattr(gen_res, "gcs_uri", None), gen_res.video_url
        )
        turn_node = self.session_manager.add_turn(
            session_id=session.session_id,
            clip_index=clip_index,
            prompt=guard_res.sanitized_prompt,
            interaction_thread_id=gen_res.interaction_thread_id,
            video_url=proxy_video_url,
            parent_turn_id=parent_turn_id,
        )

        status_event = (
            "COMMIT_RECOMMENDED" if turn_node.edit_depth_in_thread >= 3 else "COMPLETED"
        )

        return AgentTurnResponse(
            success=True,
            status_event=status_event,
            video_url=proxy_video_url,
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
        proxy_video_url = self._get_media_proxy_video_url(
            getattr(gen_res, "gcs_uri", None), gen_res.video_url
        )
        new_node = self.session_manager.add_turn(
            session_id=session.session_id,
            clip_index=committed_turn.clip_index,
            prompt=guard_res.sanitized_prompt,
            interaction_thread_id=gen_res.interaction_thread_id,
            video_url=proxy_video_url,
            parent_turn_id=turn_id,
            is_checkpoint=True,
        )
        return AgentTurnResponse(
            success=True,
            status_event="REANCHORED",
            video_url=proxy_video_url,
            error_message=gen_res.error_message,
            generation_mode=gen_res.generation_mode,
            turn_id=new_node.turn_id,
            depth=0,
        )

    def _get_media_proxy_video_url(self, gcs_uri: str | None, default_url: str) -> str:
        if gcs_uri and gcs_uri.startswith("gs://"):
            return f"/api/media-proxy?uri={urllib.parse.quote(gcs_uri, safe='')}"
        return default_url

    def _execute_turn_generation(
        self,
        session_id: str | None,
        turn_index: int,
        prompt: str,
        parent_thread_id: str | None = None,
        voiceover: str | None = None,
        is_silent: bool = False,
        audio_stem: str | None = None,
        characters: list[CharacterRole] | None = None,
    ) -> Any:
        if parent_thread_id:
            return self.omni_client.apply_interaction_diff(
                parent_thread_id,
                prompt,
                session_id=session_id,
                voiceover=voiceover,
                is_silent=is_silent,
                audio_stem=audio_stem,
                turn_index=turn_index,
                characters=characters,
            )
        return self.omni_client.generate_clip(
            prompt,
            session_id=session_id,
            voiceover=voiceover,
            is_silent=is_silent,
            audio_stem=audio_stem,
            turn_index=turn_index,
            characters=characters,
        )

    def _get_session(self, session_id: str | None) -> Any | None:
        if not session_id:
            return None
        if session_id in self.session_manager._sessions:
            return self.session_manager._sessions[session_id]
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id.strip())
        if sanitized in self.session_manager._sessions:
            return self.session_manager._sessions[sanitized]
        for session in self.session_manager._sessions.values():
            if session.session_id in (session_id, sanitized):
                return session
        return None

    def stitch_session_master(
        self,
        session_name: str | None,
        master_title: str,
        raw_compiled_prompt: str | None = None,
        master_audio_path: str | None = None,
    ) -> tuple[str, str]:
        session = self._get_session(session_name)
        clip_paths: list[str] = []
        if session and session.turns:
            clip_paths = [t.video_url for t in session.turns.values() if t.video_url]

        stitched_path = self.stitcher.concatenate_clips(
            clip_paths,
            session_id=session_name,
            master_audio_path=master_audio_path,
        )
        return self.storage.save_final_master(
            session_id=session_name,
            source_rel_path=stitched_path,
            master_title=master_title,
            prompt_data=raw_compiled_prompt,
        )

    def save_final_master(
        self,
        session_id: str | None = None,
        video_url: str = "",
        master_title: str = "",
        session_name: str | None = None,
        raw_compiled_prompt: str | None = None,
        master_audio_path: str | None = None,
    ) -> tuple[str, str]:
        s_id = session_id if session_id is not None else session_name
        session = self._get_session(s_id)
        if session:
            video_nodes = [t for t in session.turns.values() if t.video_url]
            if len(video_nodes) > 1:
                return self.stitch_session_master(
                    session_name=s_id,
                    master_title=master_title,
                    raw_compiled_prompt=raw_compiled_prompt,
                    master_audio_path=master_audio_path,
                )
        return self.storage.save_final_master(
            session_id=s_id,
            source_rel_path=video_url,
            master_title=master_title,
            prompt_data=raw_compiled_prompt,
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
