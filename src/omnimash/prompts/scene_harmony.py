"""Scene Harmony Producer for unifying cast, continuity bridges, and acoustic lock across 3 saved scenes."""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from omnimash.prompts.character_roles import CharacterRole, normalize_character_role
from omnimash.prompts.compiler import (
    PromptCompiler,
    SceneDirective,
    validate_and_repair_role_bindings,
)

logger = logging.getLogger(__name__)


class SavedSceneSpec(BaseModel):
    """Represents a user-finalized scene stored in the Saved Scenes Vault."""

    scene_id: str = Field(default_factory=lambda: f"scn_{uuid.uuid4().hex[:10]}")
    title: str = "Saved Scene"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    project_id: str = "prj_default"
    session_id: str = "default_session"
    prompt: str = ""
    action: str = ""
    dialogue: str = ""
    dialogue_direction: str = ""
    screenplay_script: str = ""
    environment: str = ""
    style_tone: str = "90s_rap_video"
    audio_beat: str = "140 BPM Heavy 808 Trap"
    vocal_delivery: str = ""
    characters: list[CharacterRole] = Field(default_factory=list)
    keyframe_image_url: str | None = None
    video_url: str | None = None
    gcs_uri: str | None = None
    aspect_ratio: str = "16:9"
    is_locked_video: bool = True


class HarmonizedScenePlan(BaseModel):
    """Output of SceneHarmonyProducer.harmonize_three_scenes."""

    unified_characters: list[CharacterRole] = Field(default_factory=list)
    harmonized_scenes: list[dict[str, Any]] = Field(default_factory=list)
    compiled_prompts: list[str] = Field(default_factory=list)
    audio_beat: str = "140 BPM Heavy 808 Trap"
    style_tone: str = "90s_rap_video"
    environment: str = ""
    harmony_notes: list[str] = Field(default_factory=list)


class SceneHarmonyProducer:
    """Harmonizes 3 finalized scenes into a cohesive 3-Act narrative while preserving scene likeness."""

    def __init__(self, mock_mode: bool = False, compiler: PromptCompiler | None = None) -> None:
        self.mock_mode = mock_mode
        self.compiler = compiler or PromptCompiler(mock_mode=mock_mode)

    @staticmethod
    def unify_cast_across_scenes(
        scenes: list[SavedSceneSpec],
    ) -> tuple[list[CharacterRole], dict[str, str]]:
        """Deduplicates characters across scenes by normalized name or reference_url and assigns canonical Role A, Role B, Role C...

        Returns:
            (unified_characters, alias_to_canonical_role_id)
        """
        canonical_chars: list[CharacterRole] = []
        seen_keys: dict[str, int] = {}
        alias_map: dict[str, str] = {}

        for scene in scenes:
            for raw_char in scene.characters:
                c = (
                    raw_char
                    if isinstance(raw_char, CharacterRole)
                    else normalize_character_role(raw_char)
                )
                norm_name = (c.name or "").strip().lower()
                norm_ref = (c.reference_url or "").strip().lower()
                old_role = (c.role_id or "").strip()

                match_idx: int | None = None
                if norm_name and f"name:{norm_name}" in seen_keys:
                    match_idx = seen_keys[f"name:{norm_name}"]
                elif norm_ref and f"ref:{norm_ref}" in seen_keys:
                    match_idx = seen_keys[f"ref:{norm_ref}"]
                elif (
                    not norm_name
                    and not norm_ref
                    and old_role
                    and f"role:{old_role.lower()}" in seen_keys
                ):
                    match_idx = seen_keys[f"role:{old_role.lower()}"]

                if match_idx is not None:
                    existing = canonical_chars[match_idx]
                    if not existing.reference_url and c.reference_url:
                        existing.reference_url = c.reference_url
                    if not existing.description and c.description:
                        existing.description = c.description
                    if not existing.voice_style and c.voice_style:
                        existing.voice_style = c.voice_style
                    if not existing.aesthetic_tags and c.aesthetic_tags:
                        existing.aesthetic_tags = list(c.aesthetic_tags)
                    if old_role:
                        alias_map[old_role] = existing.role_id
                    if c.name:
                        alias_map[c.name] = existing.role_id
                else:
                    new_idx = len(canonical_chars)
                    canonical_role_id = f"Role {chr(65 + new_idx)}"
                    unified_c = CharacterRole(
                        role_id=canonical_role_id,
                        name=c.name or canonical_role_id,
                        description=c.description or "A distinct cinematic character",
                        reference_url=c.reference_url,
                        aesthetic_tags=list(c.aesthetic_tags or []),
                        voice_style=c.voice_style,
                        voice_profile=c.voice_profile,
                        wardrobe=getattr(c, "wardrobe", ""),
                        image_role=getattr(c, "image_role", "Character Reference"),
                        is_offscreen_narrator=getattr(c, "is_offscreen_narrator", False),
                    )
                    canonical_chars.append(unified_c)
                    if norm_name:
                        seen_keys[f"name:{norm_name}"] = new_idx
                    if norm_ref:
                        seen_keys[f"ref:{norm_ref}"] = new_idx
                    if old_role:
                        seen_keys[f"role:{old_role.lower()}"] = new_idx
                        alias_map[old_role] = canonical_role_id
                    if c.name:
                        alias_map[c.name] = canonical_role_id

        if not canonical_chars:
            default_char = CharacterRole(
                role_id="Role A",
                name="Lead Subject",
                description="A distinct cinematic character with expressive features",
            )
            canonical_chars.append(default_char)
            alias_map["Role A"] = "Role A"

        return canonical_chars, alias_map

    @staticmethod
    def _remap_text_to_unified_cast(
        text: str,
        scene_chars: list[CharacterRole],
        unified_chars: list[CharacterRole],
    ) -> str:
        """Remaps scene-local Role IDs and character names to canonical unified Role IDs."""
        if not text:
            return ""
        name_to_canonical: dict[str, str] = {}
        ref_to_canonical: dict[str, str] = {}
        for uc in unified_chars:
            if uc.name:
                name_to_canonical[uc.name.strip().lower()] = uc.role_id
            if uc.reference_url:
                ref_to_canonical[uc.reference_url.strip().lower()] = uc.role_id

        local_role_to_canonical: dict[str, str] = {}
        for sc in scene_chars:
            c = sc if isinstance(sc, CharacterRole) else normalize_character_role(sc)
            c_name = (c.name or "").strip().lower()
            c_ref = (c.reference_url or "").strip().lower()
            target_role = name_to_canonical.get(c_name) or ref_to_canonical.get(c_ref) or c.role_id
            if c.role_id and target_role:
                local_role_to_canonical[c.role_id.strip()] = target_role

        # Use placeholders to avoid chained replacements (e.g. Role C -> Role B -> Role A)
        result = text
        placeholders: dict[str, str] = {}
        for idx, (local_role, canonical_role) in enumerate(local_role_to_canonical.items()):
            ph = f"__UNIFIED_ROLE_PH_{idx}__"
            placeholders[ph] = canonical_role
            result = re.sub(rf"\b{re.escape(local_role)}\b", ph, result)

        for ph, canonical_role in placeholders.items():
            result = result.replace(ph, canonical_role)

        return result

    def harmonize_three_scenes(
        self,
        scenes: Sequence[SavedSceneSpec | dict[str, Any]],
        bridging_direction: str = "",
    ) -> HarmonizedScenePlan:
        """Harmonizes up to 3 saved scenes into a unified cast, continuity-bridged 3-Act plan."""
        parsed_scenes: list[SavedSceneSpec] = [
            s if isinstance(s, SavedSceneSpec) else SavedSceneSpec.model_validate(s) for s in scenes
        ]
        if not parsed_scenes:
            return HarmonizedScenePlan()

        unified_chars, _ = self.unify_cast_across_scenes(parsed_scenes)

        # Resolve shared acoustic stem, environment, and style tone across the 3 scenes
        primary_audio = next(
            (s.audio_beat.strip() for s in parsed_scenes if s.audio_beat and s.audio_beat.strip()),
            "140 BPM Heavy 808 Trap",
        )
        primary_style = next(
            (s.style_tone.strip() for s in parsed_scenes if s.style_tone and s.style_tone.strip()),
            "90s_rap_video",
        )
        primary_env = next(
            (
                s.environment.strip()
                for s in parsed_scenes
                if s.environment and s.environment.strip()
            ),
            "Atmospheric cinematic studio set with dramatic directional lighting",
        )

        harmony_notes: list[str] = [
            f"Unified Cast Roster: Locked {len(unified_chars)} character(s) ({', '.join(f'{c.role_id}: {c.name}' for c in unified_chars)}) with consistent <IMAGE_REF_N> anchors across all {len(parsed_scenes)} scenes.",
            f"Acoustic & Tempo Lock: Synchronized continuous audio stem ({primary_audio}) with vocal ducking across all {len(parsed_scenes)} scenes.",
        ]
        if bridging_direction and bridging_direction.strip():
            harmony_notes.append(f"Director Bridging Note Applied: {bridging_direction.strip()}")

        harmonized_scenes_list: list[dict[str, Any]] = []
        compiled_prompts: list[str] = []
        all_role_ids = [c.role_id for c in unified_chars]

        total = len(parsed_scenes)
        for idx, scene in enumerate(parsed_scenes):
            act_num = idx + 1
            remapped_action = self._remap_text_to_unified_cast(
                scene.action or scene.prompt,
                scene.characters,
                unified_chars,
            ).strip()
            remapped_dialogue = self._remap_text_to_unified_cast(
                scene.dialogue,
                scene.characters,
                unified_chars,
            ).strip()
            remapped_script = self._remap_text_to_unified_cast(
                scene.screenplay_script,
                scene.characters,
                unified_chars,
            ).strip()

            # Build smooth visual/narrative entry & exit bridges while preserving 100% of user's core action
            prev_title = parsed_scenes[idx - 1].title if idx > 0 else None
            next_title = parsed_scenes[idx + 1].title if idx + 1 < total else None

            bridge_prefix = ""
            bridge_suffix = ""
            if prev_title:
                bridge_prefix = f"[Continuity Bridge from Scene {idx} ({prev_title}): Maintain lighting, spatial axis, and character momentum] "
            if next_title:
                bridge_suffix = f" [Exit Bridge into Scene {idx + 2} ({next_title}): Hold final eyeline and motion vector for seamless cut]"

            bridged_action = PromptCompiler._ensure_temporal_micro_beats(
                f"{bridge_prefix}{remapped_action}{bridge_suffix}".strip(),
                char_label=unified_chars[0].role_id,
                env_tag=scene.environment or primary_env,
            )

            harmony_notes.append(
                f"Scene {act_num} ({scene.title}): Preserved finalized action & dialogue likeness; bound to {', '.join(all_role_ids)}."
            )

            scene_directive = SceneDirective(
                scene_number=1,
                active_roles=all_role_ids,
                action=bridged_action,
                dialogue=remapped_dialogue,
                screenplay_text=remapped_script if remapped_script else None,
                audio_cues=primary_audio,
                timecode="0-10s",
                duration_seconds=10.0,
            )

            concept_parts = [
                scene.prompt or scene.title or f"Act {act_num} cohesive scene",
            ]
            if bridging_direction and bridging_direction.strip():
                concept_parts.append(f"Continuity Direction: {bridging_direction.strip()}")
            if scene.dialogue_direction and scene.dialogue_direction.strip():
                concept_parts.append(f"Dialogue Direction: {scene.dialogue_direction.strip()}")
            scene_concept = " | ".join(concept_parts)

            compiled = self.compiler.compile_storyboard(
                concept=scene_concept,
                characters=unified_chars,
                scenes=[scene_directive],
                environment_tag=scene.environment or primary_env,
                audio_beat=primary_audio,
                vocal_delivery=scene.vocal_delivery or scene.dialogue_direction or None,
                keyframe_image_url=scene.keyframe_image_url,
                has_keyframe_seed=bool(scene.keyframe_image_url),
                enable_sanitization=False,
                aspect_ratio=scene.aspect_ratio or "16:9",
            )
            compiled = validate_and_repair_role_bindings(compiled, unified_chars)
            compiled_prompts.append(compiled)

            harmonized_scenes_list.append(
                {
                    "scene_index": idx,
                    "scene_number": act_num,
                    "scene_id": scene.scene_id,
                    "title": scene.title,
                    "action": bridged_action,
                    "dialogue": remapped_dialogue,
                    "dialogue_direction": scene.dialogue_direction,
                    "environment": scene.environment or primary_env,
                    "audio_beat": primary_audio,
                    "keyframe_image_url": scene.keyframe_image_url,
                    "video_url": scene.video_url,
                    "is_locked_video": scene.is_locked_video,
                    "active_roles": all_role_ids,
                    "compiled_prompt": compiled,
                }
            )

        return HarmonizedScenePlan(
            unified_characters=unified_chars,
            harmonized_scenes=harmonized_scenes_list,
            compiled_prompts=compiled_prompts,
            audio_beat=primary_audio,
            style_tone=primary_style,
            environment=primary_env,
            harmony_notes=harmony_notes,
        )
