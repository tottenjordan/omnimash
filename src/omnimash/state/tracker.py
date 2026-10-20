"""State tracking for cumulative character and scene modifications across shot directives."""

from __future__ import annotations

import logging
import re
from typing import Any

from omnimash.prompts.journey3 import CumulativeShotState
from omnimash.state.session_manager import SessionManager

logger = logging.getLogger("omnimash.state.tracker")


class CumulativeStateTracker:
    """Tracks cumulative character and scene state modifications across shot directives."""

    def __init__(
        self,
        storage: Any | None = None,
        session_manager: SessionManager | None = None,
    ) -> None:
        self._session_states: dict[str, CumulativeShotState] = {}
        self.storage = storage
        self.session_manager = session_manager

    def _persist_state(
        self,
        session_id: str,
        state: CumulativeShotState,
        project_id: str | None = None,
    ) -> None:
        cumulative_dict = {
            "character_states": dict(state.character_states),
            "scene_states": list(state.scene_states),
        }
        if self.session_manager is not None:
            try:
                self.session_manager.update_cumulative_state(
                    session_id=session_id,
                    cumulative_state=cumulative_dict,
                    project_id=project_id,
                )
                return
            except Exception as exc:
                logger.warning(
                    "Failed to persist cumulative state via SessionManager for session %s: %s",
                    session_id,
                    exc,
                )

        if self.storage is not None and hasattr(self.storage, "save_session_manifest"):
            try:
                raw_manifest = (
                    self.storage.get_session_manifest(session_id, project_id=project_id)
                    if hasattr(self.storage, "get_session_manifest")
                    else None
                )
                manifest: dict[str, Any] = (
                    dict(raw_manifest)
                    if isinstance(raw_manifest, dict)
                    else {"session_id": session_id}
                )
                effective_project_id = project_id or manifest.get("project_id")
                if effective_project_id:
                    manifest["project_id"] = effective_project_id
                manifest["cumulative_state"] = cumulative_dict
                self.storage.save_session_manifest(
                    session_id=session_id,
                    manifest_data=manifest,
                    project_id=effective_project_id,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to persist cumulative state for session %s: %s", session_id, exc
                )

    def get_cumulative_state(
        self, session_id: str, project_id: str | None = None
    ) -> CumulativeShotState:
        if session_id not in self._session_states:
            hydrated_state = CumulativeShotState()
            cs: dict[str, Any] | None = None

            if self.session_manager is not None:
                try:
                    raw_cs = self.session_manager.get_cumulative_state(
                        session_id, project_id=project_id
                    )
                    if isinstance(raw_cs, dict) and raw_cs:
                        cs = raw_cs
                except Exception as exc:
                    logger.warning(
                        "Failed to get cumulative state from SessionManager for session %s: %s",
                        session_id,
                        exc,
                    )

            if (
                not cs
                and self.storage is not None
                and hasattr(self.storage, "get_session_manifest")
            ):
                try:
                    manifest = self.storage.get_session_manifest(session_id, project_id=project_id)
                    if isinstance(manifest, dict) and isinstance(
                        manifest.get("cumulative_state"), dict
                    ):
                        cs = manifest["cumulative_state"]
                except Exception as exc:
                    logger.warning(
                        "Failed to hydrate cumulative state for session %s: %s", session_id, exc
                    )

            if isinstance(cs, dict) and cs:
                if isinstance(cs.get("character_states"), dict):
                    for k, v in cs["character_states"].items():
                        if isinstance(v, list):
                            hydrated_state.character_states[str(k)] = [str(x) for x in v]
                if isinstance(cs.get("scene_states"), list):
                    hydrated_state.scene_states = [str(x) for x in cs["scene_states"]]

            self._session_states[session_id] = hydrated_state
        return self._session_states[session_id]

    def clear_session(self, session_id: str, project_id: str | None = None) -> None:
        if session_id in self._session_states:
            del self._session_states[session_id]
        self._persist_state(session_id, CumulativeShotState(), project_id=project_id)

    def record_shot_directive(
        self,
        session_id: str,
        shot_index: int,
        action_text: str,
        dialogue_text: str = "",
        known_characters: list[str] | None = None,
        project_id: str | None = None,
    ) -> None:
        state = self.get_cumulative_state(session_id, project_id=project_id)
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
            pattern = (
                r"\b" + re.escape(verb) + r"\s+(?:a|an|the|his|her|their)?\s*([a-zA-Z0-9_\s]+)"
            )
            for m in re.finditer(pattern, combined_text, re.IGNORECASE):
                raw_target = m.group(1).strip()
                target = (
                    re.split(
                        r"[,;.]|\b(?:while|as|and|then|in|on|at|under|into|through|across|towards|from|with|surrounded|steps|walks|moves|runs)\b",
                        raw_target,
                        flags=re.IGNORECASE,
                    )[0]
                    .strip()
                    .lower()
                )
                target_words = [
                    w
                    for w in re.split(r"\s+", target)
                    if w not in ("a", "an", "the", "and", "or", "to", "his", "her", "their")
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
            "Camera",
            "Wide",
            "Close",
            "Closeup",
            "Medium",
            "Low",
            "High",
            "Slow",
            "Fast",
            "Static",
            "Dynamic",
            "Tracking",
            "Dolly",
            "Pan",
            "Zoom",
            "Cut",
            "Scene",
            "Interior",
            "Exterior",
            "Establishing",
            "Dramatic",
            "Cinematic",
            "Glowing",
            "Dark",
            "Bright",
            "Neon",
            "Overhead",
            "Extreme",
            "Angle",
            "Frame",
            "Lighting",
        }
        char_name: str | None = None
        candidate_known = list(known_characters or []) + list(state.character_states.keys())
        for kc in candidate_known:
            kc_clean = str(kc).strip()
            if kc_clean and re.search(
                r"\b" + re.escape(kc_clean) + r"\b", combined_text, re.IGNORECASE
            ):
                char_name = kc_clean
                break

        if not char_name:
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
            pattern = (
                r"\b" + re.escape(verb) + r"\s+(?:a|an|the|his|her|their)?\s*([a-zA-Z0-9_\s]+)"
            )
            for m in re.finditer(pattern, combined_text, re.IGNORECASE):
                item_desc = m.group(1).strip()
                item_desc = re.split(
                    r"[,;.]|\b(?:while|as|and|then|in|on|at|under|into|through|across|towards|from|with|surrounded)\b",
                    item_desc,
                    flags=re.IGNORECASE,
                )[0].strip()
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

        self._persist_state(session_id, state, project_id=project_id)


# Backwards-compatibility alias for legacy code & tests
Journey3StateTracker = CumulativeStateTracker

__all__ = [
    "CumulativeShotState",
    "CumulativeStateTracker",
    "Journey3StateTracker",
]
