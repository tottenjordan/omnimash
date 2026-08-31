import math
import re
import urllib.parse
from dataclasses import asdict, dataclass
from typing import Any

from omnimash.config import settings
from google.adk.agents import Agent

from omnimash.engine.omni_client import OmniFlashClient
from omnimash.ingestion.media_extractor import MediaExtractor
from omnimash.prompts.compiler import (
    CharacterRole,
    CumulativeShotState,
    MetaPromptTags,
    SceneDirective,
    sanitize_real_names,
)
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


class Journey3StateTracker:
    """Tracks cumulative character and scene state modifications across shot directives for Journey 3."""

    def __init__(self) -> None:
        self._session_states: dict[str, CumulativeShotState] = {}

    def get_cumulative_state(self, session_id: str) -> CumulativeShotState:
        if session_id not in self._session_states:
            self._session_states[session_id] = CumulativeShotState()
        return self._session_states[session_id]

    def clear_session(self, session_id: str) -> None:
        if session_id in self._session_states:
            del self._session_states[session_id]

    def record_shot_directive(
        self,
        session_id: str,
        shot_index: int,
        action_text: str,
        dialogue_text: str = "",
    ) -> None:
        state = self.get_cumulative_state(session_id)
        combined_text = f"{action_text or ''} {dialogue_text or ''}".strip()
        if not combined_text:
            return

        removal_verbs = [
            "removes",
            "remove",
            "takes off",
            "take off",
            "taking off",
            "drops",
            "drop",
            "unsets",
            "unset",
            "loses",
            "lose",
            "takes away",
        ]

        # 1. Removal / un-setting
        for verb in removal_verbs:
            pattern = r"\b" + re.escape(verb) + r"\s+(?:a|an|the|his|her|their)?\s*([a-zA-Z0-9_\s]+)"
            for m in re.finditer(pattern, combined_text, re.IGNORECASE):
                target = m.group(1).strip().lower()
                target_words = [
                    w for w in re.split(r"\s+", target) if w not in ("a", "an", "the", "and", "or")
                ]
                if not target_words:
                    continue
                for char in list(state.character_states.keys()):
                    for st_desc in list(state.character_states[char]):
                        st_lower = st_desc.lower()
                        if any(tw in st_lower for tw in target_words):
                            state.remove_character_state(char, st_desc)
                for sc_desc in list(state.scene_states):
                    sc_lower = sc_desc.lower()
                    if any(tw in sc_lower for tw in target_words):
                        if sc_desc in state.scene_states:
                            state.scene_states.remove(sc_desc)

        # 2. Addition / setting keywords & character state extraction
        tracked_keywords = [
            "blindfold",
            "handcuffed",
            "magic aura",
            "golden cup",
            "holding",
            "wearing",
            "neon candles",
        ]

        stop_words = {
            "Yo",
            "The",
            "A",
            "An",
            "In",
            "On",
            "At",
            "With",
            "After",
            "Before",
            "Suddenly",
            "As",
            "Shot",
            "And",
            "Or",
        }
        char_name: str | None = None
        for w in combined_text.split():
            clean_w = re.sub(r"[^\w]", "", w)
            if clean_w and clean_w[0].isupper() and clean_w not in stop_words:
                char_name = clean_w
                break

        addition_verbs = [
            "puts on",
            "wears",
            "wearing",
            "holding",
            "holds",
            "picks up",
            "has",
            "equipped with",
        ]
        for verb in addition_verbs:
            pattern = r"\b" + re.escape(verb) + r"\s+(?:a|an|the|his|her|their)?\s*([a-zA-Z0-9_\s]+)"
            for m in re.finditer(pattern, combined_text, re.IGNORECASE):
                item_desc = m.group(1).strip()
                item_desc = re.split(r"[,;.]", item_desc)[0].strip()
                if item_desc:
                    full_desc = (
                        f"{verb} {item_desc}" if verb in ("wearing", "holding") else item_desc
                    )
                    if char_name:
                        state.add_character_state(char_name, full_desc)
                    else:
                        state.add_scene_state(full_desc)

        for kw in tracked_keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", combined_text, re.IGNORECASE):
                is_removed = any(
                    re.search(
                        r"\b" + re.escape(rv) + r"\s+.*" + re.escape(kw),
                        combined_text,
                        re.IGNORECASE,
                    )
                    for rv in removal_verbs
                )
                if not is_removed:
                    existing = state.format_cumulative_state_block().lower()
                    if kw not in existing:
                        if kw in ("neon candles", "magic aura") and not char_name:
                            state.add_scene_state(f"with {kw}")
                        elif char_name:
                            state.add_character_state(char_name, kw)
                        else:
                            state.add_scene_state(kw)


class OmniMashAgent:
    def __init__(self, mock_mode: bool | None = None):
        self.mock_mode = mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
        self.guardrail = ModelArmorGuardrail(mock_mode=mock_mode)
        self.session_manager = SessionManager()
        self.omni_client = OmniFlashClient(mock_mode=mock_mode)
        self.taxonomy = PromptTaxonomyEngine(mock_mode=mock_mode)
        self.media_extractor = MediaExtractor(mock_mode=mock_mode)
        self.storage = GcsStorageManager(mock_mode=mock_mode)
        self.stitcher = VideoStitcher(mock_mode=mock_mode)
        self.storyboard_agent = StoryboardAgent(mock_mode=mock_mode)
        self.journey3_tracker = Journey3StateTracker()

    def deconstruct_concept(self, concept: str) -> MetaPromptTags:
        return self.taxonomy.deconstruct_concept(concept)

    def expand_storyboard(
        self,
        concept: str,
        style_tone: str = "Cinematic Trap Parody",
        target_duration: float = 30.0,
        characters: list[CharacterRole] | None = None,
        screenplay_script: str = "",
    ) -> list[StoryboardShot]:
        return self.storyboard_agent.expand_vision(
            concept,
            style_tone=style_tone,
            target_duration=target_duration,
            characters=characters,
            screenplay_script=screenplay_script,
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
        duration_seconds: float = 10.0,
        is_conversational_edit: bool = False,
        reference_url: str | None = None,
        audio_stem: str | None = None,
        voiceover: str | None = None,
        is_silent: bool = False,
        on_screen_text: str | None = None,
        compiled_override: str | None = None,
        session_name: str | None = None,
        concept: str | None = None,
        characters: list[Any] | None = None,
        scenes: list[Any] | None = None,
        aesthetic_tags: list[str] | None = None,
        environment_tag: str | None = None,
        vocal_delivery: str | None = None,
        optimize_prompt: bool = False,
        keyframe_image_url: str | None = None,
        enable_sanitization: bool = True,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
    ) -> AgentTurnResponse:
        session = self.session_manager.get_or_create_session(
            user_id, project_id, session_name=session_name
        )

        def _clean(val: str | None) -> str:
            if not val:
                return ""
            return sanitize_real_names(val) if enable_sanitization else val

        num_chunks = max(1, int(math.ceil(duration_seconds / 10.0)))
        if num_chunks > 1:
            chunk_urls: list[str] = []
            curr_parent_turn_id = parent_turn_id
            last_resp: AgentTurnResponse | None = None

            for c_idx in range(num_chunks):
                c_prompt = prompt if num_chunks == 1 else f"{prompt} (Part {c_idx + 1}/{num_chunks})"
                turn_resp = self.process_user_turn(
                    user_id=user_id,
                    project_id=project_id,
                    prompt=c_prompt,
                    clip_index=clip_index,
                    parent_turn_id=curr_parent_turn_id,
                    duration_seconds=10.0,
                    reference_url=reference_url,
                    audio_stem=audio_stem,
                    voiceover=voiceover,
                    is_silent=is_silent,
                    on_screen_text=on_screen_text,
                    compiled_override=compiled_override,
                    session_name=session_name,
                    concept=concept,
                    characters=characters,
                    scenes=scenes,
                    aesthetic_tags=aesthetic_tags,
                    environment_tag=environment_tag,
                    vocal_delivery=vocal_delivery,
                    optimize_prompt=optimize_prompt,
                    enable_sanitization=enable_sanitization,
                    aspect_ratio=aspect_ratio,
                )
                if not turn_resp.success:
                    return turn_resp
                curr_parent_turn_id = turn_resp.turn_id
                if turn_resp.video_url:
                    chunk_urls.append(turn_resp.video_url)
                last_resp = turn_resp

            if len(chunk_urls) > 1:
                stitched_path = self.stitcher.concatenate_clips(
                    chunk_urls, session_id=session.session_id
                )
                _pub_url, gcs_uri = self.storage.save_final_master(
                    session_id=session.session_id,
                    source_rel_path=stitched_path,
                    master_title=f"shot_{clip_index}_{int(duration_seconds)}s",
                )
                proxy_url = self._get_media_proxy_video_url(gcs_uri, _pub_url)
                return AgentTurnResponse(
                    success=True,
                    status_event="COMPLETED",
                    video_url=proxy_url,
                    turn_id=last_resp.turn_id if last_resp else None,
                    generation_mode=last_resp.generation_mode if last_resp else "LIVE_OMNI_FLASH",
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
                    char_objs.append(
                        CharacterRole(
                            role_id=c.role_id,
                            name=_clean(c.name),
                            description=_clean(c.description),
                            reference_url=c.reference_url,
                            aesthetic_tags=[_clean(t) for t in (c.aesthetic_tags or [])],
                            voice_style=_clean(c.voice_style or ""),
                            voice_profile=_clean(c.voice_profile or ""),
                            image_role=getattr(c, "image_role", "Character Reference"),
                            is_offscreen_narrator=getattr(c, "is_offscreen_narrator", False),
                        )
                    )
                elif isinstance(c, dict):
                    char_objs.append(
                        CharacterRole(
                            role_id=c.get("role_id", ""),
                            name=_clean(c.get("name", "")),
                            description=_clean(c.get("description", "")),
                            reference_url=c.get("reference_url"),
                            aesthetic_tags=[_clean(t) for t in c.get("aesthetic_tags", [])],
                            voice_style=_clean(c.get("voice_style", "")),
                            voice_profile=_clean(c.get("voice_profile", "")),
                            image_role=c.get("image_role", "Character Reference"),
                            is_offscreen_narrator=c.get("is_offscreen_narrator", False),
                        )
                    )
                elif hasattr(c, "model_dump"):
                    cd = c.model_dump()
                    char_objs.append(
                        CharacterRole(
                            role_id=cd.get("role_id", ""),
                            name=_clean(cd.get("name", "")),
                            description=_clean(cd.get("description", "")),
                            reference_url=cd.get("reference_url"),
                            aesthetic_tags=[_clean(t) for t in cd.get("aesthetic_tags", [])],
                            voice_style=_clean(cd.get("voice_style", "")),
                            voice_profile=_clean(cd.get("voice_profile", "")),
                            image_role=cd.get("image_role", "Character Reference"),
                            is_offscreen_narrator=cd.get("is_offscreen_narrator", False),
                        )
                    )
                elif hasattr(c, "role_id"):
                    char_objs.append(
                        CharacterRole(
                            role_id=getattr(c, "role_id", ""),
                            name=_clean(getattr(c, "name", "")),
                            description=_clean(getattr(c, "description", "")),
                            reference_url=getattr(c, "reference_url", None),
                            aesthetic_tags=[_clean(t) for t in getattr(c, "aesthetic_tags", [])],
                            voice_style=_clean(getattr(c, "voice_style", "")),
                            voice_profile=_clean(getattr(c, "voice_profile", "")),
                            image_role=getattr(c, "image_role", "Character Reference"),
                            is_offscreen_narrator=getattr(c, "is_offscreen_narrator", False),
                        )
                    )

        turn_index = len(session.turns)
        parent_turn = session.turns.get(parent_turn_id) if parent_turn_id else None
        parent_thread_id = parent_turn.interaction_thread_id if parent_turn else parent_turn_id

        if is_conversational_edit and (parent_turn or parent_thread_id):
            is_valid, edit_err = self.validate_conversational_edit(
                guard_res.sanitized_prompt
            )
            if not is_valid:
                return AgentTurnResponse(
                    success=False,
                    status_event="MULTI_CHANGE_REJECTED",
                    error_message=edit_err,
                )
            delta_prompt = self.taxonomy.build_delta_prompt(
                parent_turn.prompt if parent_turn else "",
                guard_res.sanitized_prompt,
                override_prompt=compiled_override,
            )
            raw_compiled_prompt = delta_prompt
            self.storage.save_session_prompt(
                session.session_id, turn_index, delta_prompt
            )
            effective_keyframe = keyframe_image_url or (
                getattr(parent_turn, "video_url", None) if parent_turn else None
            )
            gen_res = self._execute_turn_generation(
                session_id=session.session_id,
                turn_index=turn_index,
                prompt=delta_prompt,
                parent_thread_id=parent_thread_id,
                voiceover=voiceover,
                is_silent=is_silent,
                audio_stem=audio_stem,
                characters=char_objs,
                keyframe_image_url=effective_keyframe,
                enable_sanitization=enable_sanitization,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
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
                                    title_card_text=s.get("title_card_text"),
                                    title_card_subtitle=s.get("title_card_subtitle"),
                                    narrator_text=s.get("narrator_text"),
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
                    edit_instruction=prompt if (is_conversational_edit and parent_turn) else None,
                    enable_sanitization=enable_sanitization,
                    aspect_ratio=aspect_ratio,
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
            if enable_sanitization:
                meta_prompt = sanitize_real_names(meta_prompt)
            raw_compiled_prompt = meta_prompt
            self.storage.save_session_prompt(
                session.session_id, turn_index, meta_prompt
            )
            effective_thread_id = parent_thread_id if is_conversational_edit else None
            gen_res = self._execute_turn_generation(
                session_id=session.session_id,
                turn_index=turn_index,
                prompt=meta_prompt,
                parent_thread_id=effective_thread_id,
                voiceover=voiceover,
                is_silent=is_silent,
                audio_stem=audio_stem,
                characters=char_objs,
                keyframe_image_url=keyframe_image_url,
                enable_sanitization=enable_sanitization,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
            )

        if gen_res.error_message and not gen_res.video_url:
            return AgentTurnResponse(
                success=False,
                status_event="GENERATION_FAILED",
                error_message=gen_res.error_message,
                generation_mode=gen_res.generation_mode,
                raw_compiled_prompt=raw_compiled_prompt,
                reference_analysis=reference_analysis,
            )
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
        keyframe_image_url: str | None = None,
        enable_sanitization: bool = True,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
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
                keyframe_image_url=keyframe_image_url,
                enable_safety_sanitization=enable_sanitization,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
            )
        return self.omni_client.generate_clip(
            prompt,
            session_id=session_id,
            voiceover=voiceover,
            is_silent=is_silent,
            audio_stem=audio_stem,
            turn_index=turn_index,
            characters=characters,
            keyframe_image_url=keyframe_image_url,
            enable_safety_sanitization=enable_sanitization,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
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
        resolution: str = "720p",
    ) -> AgentTurnResponse:
        session = self._get_session(session_name)
        turn = session.turns.get(turn_id) if (session and turn_id) else None
        prev_inter_id = turn.interaction_thread_id if turn else turn_id

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
            is_conversational_edit=True if prev_inter_id else False,
            aspect_ratio="16:9",
            resolution=resolution,
        )


def build_adk_agent(mock_mode: bool | None = None) -> Agent:
    """Builds and returns the official Google ADK Agent instance for OmniMash."""
    is_mock = mock_mode if mock_mode is not None else getattr(settings, "mock_mode", False)
    orchestrator = OmniMashAgent(mock_mode=is_mock)

    def generate_parody_clip(
        user_id: str,
        project_id: str,
        prompt: str,
        clip_index: int = 0,
        parent_turn_id: str | None = None,
        reference_url: str | None = None,
    ) -> dict[str, str | bool | int | None]:
        """Generates a parody video clip or conversational diff branch using Gemini Omni 1.1 Flash."""
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
        "You are the Prompt Compiler for OmniMash, powered by Gemini Omni 1.1 Flash. "
        "Your job is to format user video concepts, dual-keyframe transitions (<FIRST_FRAME> and <LAST_FRAME>), "
        "360p draft previews / 4K master exports, stateful scene extensions with up to 10s prior context analysis "
        "(max 40s total continuation via previous_interaction_id), and conversational delta edits.\n\n"
        "Initial Video Turn Structure (4-Block Anchor & Inject):\n"
        "Block 1: ### INPUT ROLES & REFERENCES (<FIRST_FRAME>@Image1, <LAST_FRAME>@Image2, <IMAGE_REF_0>@Image3)\n"
        "Block 2: ### CHARACTER PROFILES\n"
        "Block 3: ### SCENE INSTRUCTIONS\n"
        "Block 4: ### TIMELINE ([0-3s], [3-6s], [6-10s])\n\n"
        "Multi-Turn Conversational Delta Structure (Lock & Isolate):\n"
        "[PRESERVATION LOCK]: {maintain character face, likeness, expression, wardrobe baseline, environment, and audio stem rhythm} | "
        "[ISOLATED DIFF]: {alter only the single specified visual or acoustic variable}\n\n"
        "Rules:\n"
        "1. Prompt the video and audio layers simultaneously in the same payload so Omni Flash 1.1's joint latent space binds character kinematics to acoustic tempo.\n"
        "2. Leverage stateful extension (previous_interaction_id) to analyze 10s of prior context (up to 40s max cumulative extension).\n"
        "3. Pair <LAST_FRAME> anchors strictly with <FIRST_FRAME> anchors when specifying dual-keyframe interpolated transitions.\n"
        "4. Support fast 360p draft rendering for rapid feedback before exporting 4K masters."
    )

    model_id = getattr(settings, "omni_model_id", "gemini-omni-1.1-flash-preview")

    return Agent(
        name="omnimash_orchestrator",
        model=model_id,
        instruction=instruction,
        tools=[generate_parody_clip],
    )


root_agent = build_adk_agent(mock_mode=getattr(settings, "mock_mode", False))
