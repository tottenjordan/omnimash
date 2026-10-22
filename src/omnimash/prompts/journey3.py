"""Journey 3 multi-shot compilation engine for OmniMash prompt engineering."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from omnimash.prompts.image_tags import (
    get_character_identifier,
    replace_character_in_text_image_tags,
)
from omnimash.prompts.parody import sanitize_real_names
from omnimash.prompts.preflight_linter import PreFlightGatekeeper
from omnimash.prompts.voice import (
    apply_conversational_voice_edits,
    ensure_character_voice_style,
)


@dataclass
class CumulativeShotState:
    character_states: dict[str, list[str]] = field(default_factory=dict)
    scene_states: list[str] = field(default_factory=list)

    def add_character_state(self, character: str, state_desc: str) -> None:
        if character not in self.character_states:
            self.character_states[character] = []
        if state_desc not in self.character_states[character]:
            self.character_states[character].append(state_desc)

    def remove_character_state(self, character: str, state_desc: str) -> None:
        if character in self.character_states:
            if state_desc in self.character_states[character]:
                self.character_states[character].remove(state_desc)
            if not self.character_states[character]:
                del self.character_states[character]

    def add_scene_state(self, state_desc: str) -> None:
        if state_desc not in self.scene_states:
            self.scene_states.append(state_desc)

    def format_cumulative_state_block(self) -> str:
        lines: list[str] = []
        if self.character_states:
            lines.append("Character States:")
            for char, states in self.character_states.items():
                for st in states:
                    lines.append(f"- {char}: {st}")
        if self.scene_states:
            lines.append("Scene States:")
            for sc in self.scene_states:
                lines.append(f"- {sc}")
        return "\n".join(lines) if lines else "None."


def validate_compiled_prompt(prompt_text: str) -> None:
    """Validates that prompt text payload adheres to Gemini Omni Flash anchor rules."""
    if "<LAST_FRAME>" in prompt_text and "<FIRST_FRAME>" not in prompt_text:
        raise ValueError(
            "<LAST_FRAME> anchor requires a corresponding <FIRST_FRAME> anchor in prompt payload."
        )


def compile_journey3_shot_prompt(
    shot_number: int,
    action_directive: str,
    cumulative_state: CumulativeShotState | None = None,
    aspect_ratio: str = "16:9",
    character_roster: str = "",
    timeline_dialogue: str = "",
    enable_sanitization: bool = True,
    characters: list[Any] | None = None,
    audio_mode: str = "global",
    audio_stem: str | None = None,
    global_audio_beat: str | None = None,
    audio_track: str | None = None,
    soundscape: str | None = None,
    is_silent: bool = False,
    title_card_text: str | None = None,
    title_card_subtitle: str | None = None,
    narrator_text: str | None = None,
    narrator_voice: str | None = None,
    style_preset: str | None = None,
    last_frame_image_url: str | None = None,
    keyframe_image_url: str | None = None,
    is_seamless_loop: bool = False,
    enable_preflight: bool = False,
) -> str:
    """Compiles 4-block prompt for Journey 3 shot generation adhering to GEMINI_OMNI_FLASH_INSTR.

    Blocks:
    1. ### INPUT ROLES & REFERENCES
    2. ### CHARACTER PROFILES
    3. ### SCENE INSTRUCTIONS
    4. ### TIMELINE
    """
    if is_seamless_loop and keyframe_image_url and keyframe_image_url.strip():
        last_frame_image_url = keyframe_image_url.strip()

    char_list: list[Any] = list(characters) if characters is not None else []
    if last_frame_image_url and last_frame_image_url.strip():
        has_last = any(
            (getattr(c, "image_role", "") if not isinstance(c, dict) else c.get("image_role", ""))
            in ("Ending Frame", "Keyframe Last Anchor")
            for c in char_list
        )
        if not has_last:
            char_list.append(
                {
                    "name": "Ending Frame Anchor",
                    "role_id": "Ending Frame",
                    "image_role": "Ending Frame",
                    "reference_url": last_frame_image_url.strip(),
                }
            )
        characters = char_list

    sources_meta: list[str] = []
    references_meta: list[str] = []
    if is_seamless_loop and keyframe_image_url and keyframe_image_url.strip():
        sources_meta.extend(["<FIRST_FRAME>@KeyframeSeed", "<LAST_FRAME>@KeyframeSeed"])
    elif keyframe_image_url and keyframe_image_url.strip():
        sources_meta.append("<FIRST_FRAME>@KeyframeSeed")

    block1_role_lines: list[str] = []
    char_lines: list[str] = []
    if characters:
        apply_conversational_voice_edits(action_directive, characters)
        ref_idx = 1
        for char in characters:
            char_id = get_character_identifier(
                char, enable_sanitization=enable_sanitization, use_role_id=True
            )
            ref_url = (
                getattr(char, "reference_url", None)
                if not isinstance(char, dict)
                else char.get("reference_url")
            )
            wardrobe = (
                getattr(char, "wardrobe", None)
                if not isinstance(char, dict)
                else char.get("wardrobe")
            )
            aesthetic_tags = (
                getattr(char, "aesthetic_tags", None)
                if not isinstance(char, dict)
                else char.get("aesthetic_tags")
            )
            voice_style = ensure_character_voice_style(char, concept=action_directive)

            wardrobe_str = (
                f" [Wardrobe: {str(wardrobe).strip()}]"
                if wardrobe and str(wardrobe).strip()
                else ""
            )

            style_val = ""
            if aesthetic_tags:
                if isinstance(aesthetic_tags, list):
                    style_val = ", ".join(str(t).strip() for t in aesthetic_tags if str(t).strip())
                else:
                    style_val = str(aesthetic_tags).strip()
            style_str = f" [Style: {style_val}]" if style_val else ""

            img_role = (
                getattr(char, "image_role", "Character Reference")
                if not isinstance(char, dict)
                else char.get("image_role", "Character Reference")
            ) or "Character Reference"

            if img_role in ("Starting Frame", "Keyframe Seed Anchor"):
                ref_desc = f"<FIRST_FRAME>@Image{ref_idx}"
            elif img_role in ("Ending Frame", "Keyframe Last Anchor"):
                ref_desc = f"<LAST_FRAME>@Image{ref_idx}"
            else:
                ref_desc = f"Reference Image: @Image{ref_idx}"

            voice_str = f" [Voice Style: {str(voice_style).strip()}]"

            if ref_url and isinstance(ref_url, str) and ref_url.strip():
                if img_role in ("Starting Frame", "Keyframe Seed Anchor"):
                    sources_meta.append(f"<FIRST_FRAME>@Image{ref_idx}")
                elif img_role in ("Ending Frame", "Keyframe Last Anchor"):
                    sources_meta.append(f"<LAST_FRAME>@Image{ref_idx}")
                else:
                    references_meta.append(f"<IMAGE_REF_{len(references_meta)}>@Image{ref_idx}")
                block1_role_lines.append(
                    f"- {char_id} ({img_role}): {ref_url.strip()} (@Image{ref_idx}){wardrobe_str}{style_str}"
                )
                # Zero Wardrobe Redundancy Rule in Block 2: omit redundant physical/wardrobe/style text when reference_url is set
                char_lines.append(
                    f"- {char_id}: ({ref_desc} - extract character facial likeness and wardrobe, ignore old background environment){voice_str}"
                )
                ref_idx += 1
            else:
                desc = (
                    getattr(char, "description", "")
                    if not isinstance(char, dict)
                    else char.get("description", "")
                ) or ""
                if enable_sanitization and desc:
                    desc = sanitize_real_names(desc)
                block1_role_lines.append(
                    f"- {char_id} (Text Role): Unanchored text role{wardrobe_str}"
                )
                line_content = f"{desc}{wardrobe_str}{style_str}{voice_str}".strip()
                char_lines.append(f"- {char_id}: {line_content}")
        if not character_roster and char_lines:
            character_roster = "\n".join(char_lines)

    block1_meta_lines: list[str] = []
    if sources_meta:
        block1_meta_lines.append(f"[# Sources {' '.join(sources_meta)}]")
    if references_meta:
        block1_meta_lines.append(f"[# References {', '.join(references_meta)}]")

    base_roster_str = character_roster.strip() if character_roster else "None."
    if enable_sanitization and base_roster_str != "None.":
        base_roster_str = sanitize_real_names(base_roster_str)

    block1_roles_body = (
        "\n".join(block1_role_lines).strip() if block1_role_lines else base_roster_str
    )
    if enable_sanitization and block1_roles_body != "None.":
        block1_roles_body = sanitize_real_names(block1_roles_body)

    block1_parts = list(block1_meta_lines)
    if block1_roles_body != "None." or not block1_parts:
        block1_parts.append(block1_roles_body)
    block1_roster_str = "\n".join(block1_parts).strip()
    roster_str = base_roster_str

    action_str = action_directive.strip()
    if enable_sanitization and action_str:
        action_str = sanitize_real_names(action_str)

    name_to_tag: dict[str, str] = {}
    if characters:
        img_idx = 1
        for char in characters:
            ref_url = (
                getattr(char, "reference_url", None)
                if not isinstance(char, dict)
                else char.get("reference_url")
            )
            if ref_url and isinstance(ref_url, str) and ref_url.strip():
                tag = f"@Image{img_idx}"
                img_idx += 1
                char_id = get_character_identifier(
                    char, enable_sanitization=enable_sanitization, use_role_id=True
                )
                role_id = str(
                    getattr(char, "role_id", "")
                    if not isinstance(char, dict)
                    else char.get("role_id", "") or ""
                ).strip()
                name = str(
                    getattr(char, "name", "")
                    if not isinstance(char, dict)
                    else char.get("name", "") or ""
                ).strip()

                name_clean = (
                    (sanitize_real_names(name) if name else "") if enable_sanitization else name
                )
                base_name = re.sub(r"\s*\(.*?\)", "", name).strip() if name else ""
                base_name_clean = (
                    (sanitize_real_names(base_name) if base_name else "")
                    if enable_sanitization
                    else base_name
                )

                for k in (char_id, role_id, name, name_clean, base_name, base_name_clean):
                    if k and k.strip():
                        name_to_tag[k.strip()] = tag

    if roster_str != "None.":
        for line in roster_str.splitlines():
            m = re.search(r"-\s*([^:\n]+):\s*\(Reference Image:\s*(@Image\d+)", line)
            if m:
                c_name = m.group(1).strip()
                c_tag = m.group(2).strip()
                name_to_tag[c_name] = c_tag
                b_name = re.sub(r"\s*\(.*?\)", "", c_name).strip()
                if b_name:
                    name_to_tag[b_name] = c_tag

    if name_to_tag and action_str:
        action_str = replace_character_in_text_image_tags(action_str, name_to_tag)

    custom_stem = audio_stem or soundscape
    global_beat = global_audio_beat or audio_track

    if audio_mode == "silent" or is_silent:
        resolved_audio = "Silent video. No background music, no audio."
    elif audio_mode == "custom" and custom_stem:
        resolved_audio = custom_stem.strip()
    elif global_beat:
        resolved_audio = global_beat.strip()
    elif custom_stem:
        resolved_audio = custom_stem.strip()
    else:
        resolved_audio = ""

    if enable_sanitization and resolved_audio:
        resolved_audio = sanitize_real_names(resolved_audio)

    dialogue_str = timeline_dialogue.strip() if timeline_dialogue else ""

    timeline_items: list[str] = []
    if title_card_text and title_card_text.strip():
        tc_val = title_card_text.strip()
        if enable_sanitization:
            tc_val = sanitize_real_names(tc_val)
        sub_str = (
            f' (Subtitle: "{sanitize_real_names(title_card_subtitle.strip()) if enable_sanitization else title_card_subtitle.strip()}")'
            if title_card_subtitle and title_card_subtitle.strip()
            else ""
        )
        timeline_items.append(f'- On-Screen Displayed Text / Title Card: "{tc_val}"{sub_str}')

    if narrator_text and narrator_text.strip():
        n_val = narrator_text.strip()
        v_val = (
            narrator_voice.strip()
            if narrator_voice and narrator_voice.strip()
            else "Deep Cinematic Voice"
        )
        if enable_sanitization:
            n_val = sanitize_real_names(n_val)
            v_val = sanitize_real_names(v_val)
        timeline_items.append(
            f'- Offscreen Narrator ({v_val}): "{n_val}" (off-screen) — Do not show a narrator speaking on camera.'
        )

    if action_str:
        timeline_items.append(f"- Visual Action: {action_str}")

    if dialogue_str:
        diag_chunks = [c.strip() for c in re.split(r"[\n/|]", dialogue_str) if c.strip()]
        for chunk in diag_chunks:
            sd_match = re.match(r"^-\s*Spoken Dialogue\s*\((.*?)\):\s*[\"“]?(.*?)[\"”]?$", chunk)
            if sd_match:
                spk = sd_match.group(1).strip()
                txt = sd_match.group(2).strip()
                txt_clean = txt.strip('"').strip("'").strip("“").strip("”")
                matched_spk: str | None = None
                matched_char_obj = None
                if characters:
                    spk_lower = spk.lower()
                    for c in characters:
                        c_name = str(
                            getattr(c, "name", "")
                            if not isinstance(c, dict)
                            else c.get("name", "") or ""
                        ).strip()
                        c_role = str(
                            getattr(c, "role_id", "")
                            if not isinstance(c, dict)
                            else c.get("role_id", "") or ""
                        ).strip()
                        if (
                            spk_lower in (c_name.lower(), c_role.lower())
                            or (c_name and c_name.lower() in spk_lower)
                            or (c_role and c_role.lower() in spk_lower)
                        ):
                            matched_spk = get_character_identifier(
                                c, enable_sanitization=enable_sanitization, use_role_id=True
                            )
                            matched_char_obj = c
                            break
                if not matched_spk:
                    matched_spk = sanitize_real_names(spk) if enable_sanitization else spk
                if enable_sanitization and txt_clean:
                    txt_clean = sanitize_real_names(txt_clean)

                voice_tag = ""
                if matched_char_obj:
                    v_style = ensure_character_voice_style(
                        matched_char_obj, concept=action_directive
                    )
                    v_clean = sanitize_real_names(v_style) if enable_sanitization else v_style
                    voice_tag = f" [Voice Style: {v_clean}]"

                timeline_items.append(
                    f'- Spoken Dialogue ({matched_spk}){voice_tag}: "{txt_clean}"'
                )
                continue

            match = re.match(r"^(?:-\s*)?([^:]+):\s*[\"“]?(.*?)[\"”]?$", chunk)
            if match:
                spk = match.group(1).strip()
                txt = match.group(2).strip()
                spk = re.sub(r"\s+says$", "", spk, flags=re.IGNORECASE).strip()
                txt_clean = txt.strip('"').strip("'").strip("“").strip("”")

                matched_char_id: str | None = None
                matched_char_obj = None
                if characters:
                    spk_lower = spk.lower()
                    for c in characters:
                        c_name = str(
                            getattr(c, "name", "")
                            if not isinstance(c, dict)
                            else c.get("name", "") or ""
                        ).strip()
                        c_role = str(
                            getattr(c, "role_id", "")
                            if not isinstance(c, dict)
                            else c.get("role_id", "") or ""
                        ).strip()
                        if (
                            spk_lower in (c_name.lower(), c_role.lower())
                            or (c_name and c_name.lower() in spk_lower)
                            or (c_role and c_role.lower() in spk_lower)
                        ):
                            matched_char_id = get_character_identifier(
                                c, enable_sanitization=enable_sanitization, use_role_id=True
                            )
                            matched_char_obj = c
                            break

                if not matched_char_id:
                    matched_char_id = sanitize_real_names(spk) if enable_sanitization else spk

                if enable_sanitization and txt_clean:
                    txt_clean = sanitize_real_names(txt_clean)

                voice_tag = ""
                if matched_char_obj:
                    v_style = ensure_character_voice_style(
                        matched_char_obj, concept=action_directive
                    )
                    v_clean = sanitize_real_names(v_style) if enable_sanitization else v_style
                    voice_tag = f" [Voice Style: {v_clean}]"

                timeline_items.append(
                    f'- Spoken Dialogue ({matched_char_id}){voice_tag}: "{txt_clean}"'
                )
            else:
                txt_clean = chunk.strip('"').strip("'").strip("“").strip("”")
                if characters and len(characters) == 1:
                    spk_id = get_character_identifier(
                        characters[0], enable_sanitization=enable_sanitization
                    )
                    v_style = ensure_character_voice_style(characters[0], concept=action_directive)
                    v_clean = sanitize_real_names(v_style) if enable_sanitization else v_style
                    voice_tag = f" [Voice Style: {v_clean}]"
                else:
                    spk_id = "Speaker"
                    voice_tag = ""
                if enable_sanitization and txt_clean:
                    txt_clean = sanitize_real_names(txt_clean)
                timeline_items.append(f'- Spoken Dialogue ({spk_id}){voice_tag}: "{txt_clean}"')

    has_spoken_audio = bool(
        (dialogue_str and dialogue_str.strip()) or (narrator_text and narrator_text.strip())
    )
    is_silent_audio = bool(
        audio_mode == "silent"
        or is_silent
        or (resolved_audio and resolved_audio.startswith("Silent video"))
    )

    if resolved_audio:
        if is_silent_audio:
            timeline_items.append(
                resolved_audio
                if resolved_audio.startswith("Audio:")
                else f"Audio: {resolved_audio}"
            )
        else:
            raw_audio_body = re.sub(r"^Audio:\s*", "", resolved_audio, flags=re.IGNORECASE).strip()
            instr_audio = (
                raw_audio_body
                if raw_audio_body.lower().startswith("instrumental")
                else f"instrumental {raw_audio_body}"
            )
            base_audio_line = (
                resolved_audio
                if resolved_audio.startswith("Audio:")
                else f"Audio: {resolved_audio}"
            )
            if has_spoken_audio:
                timeline_items.append(
                    f"{base_audio_line} ({instr_audio} — Ensure the background music ducks under the spoken dialogue so the voice is clear, front-and-center, and intelligible.)"
                )
            else:
                timeline_items.append(f"{base_audio_line} ({instr_audio})")

    if timeline_items:
        timeline_content = "\n".join(timeline_items)
    else:
        timeline_content = "None."

    scene_inst_items = [
        f"- Shot Number: {shot_number}",
        f"- Action Directive: {action_str}",
        f"- Aspect Ratio: {aspect_ratio}",
    ]
    if style_preset and style_preset.strip():
        sp_clean = style_preset.strip()
        if enable_sanitization:
            sp_clean = sanitize_real_names(sp_clean)
        scene_inst_items.append(
            f"- Medium & Aesthetic Style: Shot strictly in the exact artistic medium of Attached Image #1 (<FIRST_FRAME>@KeyframeSeed): {sp_clean}. Maintain 100% visual texture and animation medium continuity with <FIRST_FRAME>@KeyframeSeed, rendering all movement, characters, and environment strictly in {sp_clean} with zero photorealistic texture bleeding."
        )

    if characters:
        for c in characters:
            v_style = ensure_character_voice_style(c, concept=action_directive)
            c_id = get_character_identifier(
                c, enable_sanitization=enable_sanitization, use_role_id=True
            )
            v_clean = sanitize_real_names(v_style) if enable_sanitization else v_style
            scene_inst_items.append(f"- Voice Style ({c_id}): {v_clean}")

    if resolved_audio and not is_silent_audio:
        raw_audio_body = re.sub(r"^Audio:\s*", "", resolved_audio, flags=re.IGNORECASE).strip()
        instr_audio = (
            raw_audio_body
            if raw_audio_body.lower().startswith("instrumental")
            else f"instrumental {raw_audio_body}"
        )
        if has_spoken_audio:
            scene_inst_items.append(
                f"- Audio Beat & Ducking: {instr_audio}. Ensure the background music ducks under the spoken dialogue so the voice is clear, front-and-center, and intelligible."
            )
        else:
            scene_inst_items.append(f"- Audio Beat: {instr_audio}")

    if is_seamless_loop:
        scene_inst_items.append(
            "- Seamless Infinite Loop Mode: Seamless continuous infinite loop directive. Mirror start frame <FIRST_FRAME>@KeyframeSeed and end frame <LAST_FRAME>@KeyframeSeed so the final frame smoothly, imperceptibly loops back to the beginning with identical character posture, camera position, and ambient lighting."
        )

    if cumulative_state:
        st_block = cumulative_state.format_cumulative_state_block().strip()
        if st_block and st_block != "None.":
            scene_inst_items.append(f"Cumulative Shot State:\n{st_block}")
    scene_inst_str = "\n".join(scene_inst_items)

    block1 = f"### INPUT ROLES & REFERENCES\n{block1_roster_str}"
    block2 = f"### CHARACTER PROFILES\n{roster_str}"
    block3 = f"### SCENE INSTRUCTIONS\n{scene_inst_str}"
    block4 = f"### TIMELINE\n{timeline_content}"

    res = f"{block1}\n\n{block2}\n\n{block3}\n\n{block4}"
    if enable_preflight:
        lint_res = PreFlightGatekeeper.lint_and_repair(
            res,
            characters=char_list,
            keyframe_image_url=keyframe_image_url,
            last_frame_image_url=last_frame_image_url,
            is_seamless_loop=is_seamless_loop,
            has_dialogue=bool(timeline_dialogue and timeline_dialogue.strip()),
        )
        validate_compiled_prompt(lint_res.repaired_prompt)
        return lint_res.repaired_prompt

    validate_compiled_prompt(res)
    return res


__all__ = [
    "CumulativeShotState",
    "compile_journey3_shot_prompt",
    "validate_compiled_prompt",
]
