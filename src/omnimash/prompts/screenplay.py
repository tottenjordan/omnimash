"""Screenplay and timecoded script parsing engine for OmniMash prompt engineering.

Parses line-by-line screenplay text, directors' notes, parenthetical audio cues,
and timecode blocks with automatic <=10s shot splitting and ReDoS protection.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Any

from omnimash.prompts.image_tags import get_character_identifier

if TYPE_CHECKING:
    from omnimash.prompts.character_roles import CharacterRole

MAX_SCREENPLAY_CHARS: int = 20_000
MAX_CONCEPT_CHARS: int = 2_000


def validate_prompt_input_lengths(
    concept: str | None = None,
    screenplay_script: str | None = None,
    raw_prompt: str | None = None,
) -> None:
    """Validates user text inputs against excessive string lengths to protect against memory/token exhaustion."""
    if screenplay_script and len(screenplay_script) > MAX_SCREENPLAY_CHARS:
        raise ValueError(
            f"Screenplay script exceeds maximum allowed length ({len(screenplay_script)} > {MAX_SCREENPLAY_CHARS} chars)"
        )
    if concept and len(concept) > MAX_CONCEPT_CHARS:
        raise ValueError(
            f"Concept description exceeds maximum allowed length ({len(concept)} > {MAX_CONCEPT_CHARS} chars)"
        )
    if raw_prompt and len(raw_prompt) > MAX_CONCEPT_CHARS:
        raise ValueError(
            f"Raw prompt exceeds maximum allowed length ({len(raw_prompt)} > {MAX_CONCEPT_CHARS} chars)"
        )


def parse_directors_notes(script_text: str) -> dict[str, str]:
    """Parses [DIRECTOR'S NOTES] block from screenplay text."""
    if not script_text or "[DIRECTOR'S NOTES]" not in script_text.upper():
        return {}

    notes: dict[str, str] = {}
    notes_match = re.search(
        r"\[\s*DIRECTOR['’]?S\s+NOTES\s*\]([\s\S]*?)(?=\[\s*\d|\Z)",
        script_text,
        re.IGNORECASE,
    )
    if not notes_match:
        return notes

    block = notes_match.group(1).strip()
    for line in block.splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if not line:
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key_clean = key.strip().lower().replace(" ", "_")
            notes[key_clean] = val.strip()

    notes["raw_notes"] = block
    return notes


SCREENPLAY_AUDIO_KEYWORDS: frozenset[str] = frozenset(
    {
        "audio",
        "sound",
        "music",
        "beat",
        "bgm",
        "sfx",
        "thunder",
        "bass",
        "boom",
        "track",
        "rumble",
        "rumbles",
        "reverb",
        "echo",
        "hiss",
        "synth",
        "drums",
        "screech",
        "whisper",
        "noise",
        "loud",
        "cue",
        "playing",
        "rhythm",
        "melody",
        "vocals",
        "singing",
        "rap",
        "808",
        "drone",
    }
)

_RESERVED_KEYWORD_SET: frozenset[str] = frozenset(
    {
        "ACTION",
        "DIALOGUE",
        "AUDIO",
        "SOUND",
        "MUSIC",
        "SOUND DESIGN",
        "BACKGROUND AUDIO",
        "AUDIO CUES",
        "CAMERA",
        "LOCATION",
        "LIGHTING",
        "STYLE",
        "NOTE",
        "NOTES",
        "DIRECTOR'S NOTES",
        "DIRECTORS NOTES",
        "VISUAL",
        "SHOT",
    }
)


def _slice_lines(lines: list[str], chunk_idx: int, num_chunks: int) -> list[str]:
    """Helper to slice or distribute lines across sequential shot chunks."""
    if not lines:
        return []
    if len(lines) <= num_chunks:
        if chunk_idx < len(lines):
            return [lines[chunk_idx]]
        return [lines[-1]]
    chunk_size = math.ceil(len(lines) / num_chunks)
    start = chunk_idx * chunk_size
    if start >= len(lines):
        return [lines[-1]]
    end = min(len(lines), start + chunk_size)
    return lines[start:end]


def _extract_character_dialogue(text: str) -> tuple[str, str | None, str | None]:
    """Linear, non-backtracking extraction of character dialogue and parenthetical cues from a single line.

    Replaces nested regex lookbehinds with deterministic token splitting (SEC-01 ReDoS immunity).
    Returns:
        (action_text, dialogue_text, audio_text)
    """
    if not text or not text.strip():
        return text.strip(), None, None

    stripped = text.strip()

    # Strip leading ACTION: or DIALOGUE: prefix if present
    clean_text = re.sub(r"^(?:ACTION|DIALOGUE)\s*:\s*", "", stripped, flags=re.IGNORECASE).strip()

    # Find the dialogue separator (colon or says:) outside quotes and parentheses
    colon_idx = -1
    in_paren = 0
    in_quote = False
    quote_char = ""

    for i, ch in enumerate(clean_text):
        if ch in ('"', "'", "“", "”"):
            if not in_quote:
                in_quote = True
                quote_char = ch
            elif ch == quote_char or (quote_char == "“" and ch == "”"):
                in_quote = False
        elif ch in ("(", "["):
            if not in_quote:
                in_paren += 1
        elif ch in (")", "]"):
            if not in_quote and in_paren > 0:
                in_paren -= 1
        elif ch == ":" and not in_quote and in_paren == 0:
            colon_idx = i
            break

    separator_start = colon_idx
    separator_end = colon_idx + 1 if colon_idx != -1 else -1

    if separator_start == -1:
        says_match = re.search(r"\bsays:?\s*", clean_text, flags=re.IGNORECASE)
        if says_match:
            separator_start = says_match.start()
            separator_end = says_match.end()

    if separator_start == -1:
        return clean_text, None, None

    prefix = clean_text[:separator_start].strip()
    remainder = clean_text[separator_end:].strip()

    # Scan backwards to separate preceding action from speaker name
    # e.g., "Establishing shot of Hogwarts courtyard. Yo Totti" -> action: "Establishing shot...", speaker: "Yo Totti"
    action_before = ""
    speaker_candidate = prefix

    delim_idx = -1
    p_level = 0
    for i in range(len(prefix) - 1, -1, -1):
        c = prefix[i]
        if c in (")", "]"):
            p_level += 1
        elif c in ("(", "["):
            p_level = max(0, p_level - 1)
        elif p_level == 0 and c in (".", "!", "?", ";", "\n", "–", "—"):
            delim_idx = i
            break

    if delim_idx != -1:
        action_before = prefix[: delim_idx + 1].strip()
        speaker_candidate = prefix[delim_idx + 1 :].strip()

    speaker_candidate = speaker_candidate.strip("-*• ").strip()

    if (
        not speaker_candidate
        or speaker_candidate.upper() in _RESERVED_KEYWORD_SET
        or len(speaker_candidate) > 60
    ):
        return clean_text, None, None

    paren_match = re.match(r"^\(([^)]+)\)\s*(.*)$", remainder, flags=re.DOTALL)
    audio_part: str | None = None
    paren_action: str = ""

    if paren_match:
        paren_content = paren_match.group(1).strip()
        raw_speech = paren_match.group(2).strip()

        audio_match = re.search(
            r"\b(?:AUDIO|SOUND|SOUND EFFECT|SFX|MUSIC|SOUND DESIGN|BACKGROUND AUDIO|AUDIO CUES):\s*(.*)",
            paren_content,
            re.IGNORECASE,
        )
        if audio_match:
            audio_part = audio_match.group(1).strip()
            paren_action = paren_content[: audio_match.start()].strip().rstrip(".;,")
        else:
            paren_action = paren_content

        spoken_dialogue = raw_speech.strip().strip('"').strip("'").strip("“").strip("”")
    else:
        spoken_dialogue = remainder.strip().strip('"').strip("'").strip("“").strip("”")

    actions = [a for a in [action_before, paren_action] if a]
    action_result = " ".join(actions).strip()

    dialogue_part = f'{speaker_candidate}: "{spoken_dialogue}"' if spoken_dialogue else None

    return action_result, dialogue_part, audio_part


def parse_screenplay_script(
    script_text: str,
    characters: list[CharacterRole] | None = None,
    char_tag_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Parses line-by-line screenplay text into structured components.

    Format: `CharacterName: (Action description. Audio cue.) "Spoken dialogue."`
    Returns a dictionary with keys: active_roles, action, audio_cues, dialogue.
    """
    if not script_text or not script_text.strip():
        return {
            "active_roles": [],
            "action": "",
            "audio_cues": "",
            "dialogue": "",
        }

    validate_prompt_input_lengths(screenplay_script=script_text)

    active_roles: list[str] = []
    action_parts: list[str] = []
    audio_cue_parts: list[str] = []
    dialogue_parts: list[str] = []
    seen_actions: set[str] = set()
    seen_audio: set[str] = set()

    lines = [line.strip() for line in script_text.splitlines() if line.strip()]

    for line in lines:
        line = re.sub(
            r"^\[\s*\d+[:\.\d]*\s*[sS]?\s*(?:-\s*\d+[:\.\d]*\s*[sS]?)?\s*\]\s*",
            "",
            line,
        ).strip()
        if not line:
            continue

        kw_pattern = r"(?i)\b(Action|Audio|Sound|Dialogue)\s*:"
        line_no_parens = re.sub(r"\([^)]*\)", "", line)
        line_no_quotes = re.sub(r'["“][^"”]*["”]', "", line_no_parens)
        if list(re.finditer(kw_pattern, line_no_quotes)):
            kw_matches = list(re.finditer(kw_pattern, line))
            for i, match in enumerate(kw_matches):
                kw_name = match.group(1).lower()
                start_idx = match.end()
                end_idx = kw_matches[i + 1].start() if i + 1 < len(kw_matches) else len(line)
                val = line[start_idx:end_idx].strip()
                if not val:
                    continue

                if kw_name == "action":
                    val_clean = val.rstrip(".").strip()
                    if val_clean and val_clean not in seen_actions:
                        seen_actions.add(val_clean)
                        action_parts.append(val_clean)
                elif kw_name in ("audio", "sound"):
                    val_clean = val.rstrip(".").strip()
                    if val_clean and val_clean not in seen_audio:
                        seen_audio.add(val_clean)
                        audio_cue_parts.append(val_clean)
                elif kw_name == "dialogue":
                    speaker_raw: str | None = None
                    colon_idx = val.find(":")
                    quote_idx = min(
                        [idx for idx in [val.find('"'), val.find("“")] if idx != -1],
                        default=-1,
                    )
                    if colon_idx != -1 and (quote_idx == -1 or colon_idx < quote_idx):
                        paren_idx = val.find("(")
                        end_spk = min(idx for idx in [colon_idx, paren_idx] if idx != -1)
                        candidate_clean = re.sub(
                            r"^[\[\(\s]+|[\]\)\:\s]+$", "", val[:end_spk]
                        ).strip()
                        if candidate_clean:
                            speaker_raw = candidate_clean
                        remainder = val[colon_idx + 1 :].strip()
                    else:
                        remainder = val.strip()

                    matched_role_id: str | None = None
                    matched_role_name: str | None = None
                    if speaker_raw:
                        spk_lower = speaker_raw.lower()
                        if characters:
                            for char in characters:
                                char_role = char.role_id.strip().lower()
                                char_name = char.name.strip().lower()
                                if spk_lower in (char_role, char_name):
                                    matched_role_id = char.role_id
                                    matched_role_name = char.name
                                    break
                                if spk_lower in char_name or char_name in spk_lower:
                                    matched_role_id = char.role_id
                                    matched_role_name = char.name
                                    break
                                if char_role in spk_lower:
                                    matched_role_id = char.role_id
                                    matched_role_name = char.name
                                    break

                        role_to_add = matched_role_id if matched_role_id else speaker_raw
                        if role_to_add not in active_roles:
                            active_roles.append(role_to_add)

                    quotes = re.findall(r'["“]([^"”]+)["”]', remainder)
                    if quotes:
                        spoken_text = " ".join(q.strip() for q in quotes if q.strip())
                    else:
                        spoken_text = remainder.strip()

                    if spoken_text:
                        matched_char = None
                        if matched_role_id and characters:
                            for c in characters:
                                if getattr(c, "role_id", "") == matched_role_id:
                                    matched_char = c
                                    break
                        if matched_char:
                            speaker_display = get_character_identifier(matched_char)
                        elif matched_role_id and matched_role_name:
                            speaker_display = f"{matched_role_id} - {matched_role_name}"
                        else:
                            speaker_display = speaker_raw if speaker_raw else "Speaker"

                        if char_tag_map and char_tag_map.get(speaker_display):
                            tag = char_tag_map[speaker_display]
                            if tag not in speaker_display:
                                speaker_display = f"{speaker_display} {tag}"

                        dialogue_parts.append(f'{speaker_display}: "{spoken_text}"')
            continue

        speaker_raw: str | None = None
        colon_idx = line.find(":")
        paren_idx = line.find("(")
        quote_idx = line.find('"')
        smart_quote_idx = line.find("“")

        delim_indices = [
            idx for idx in [colon_idx, paren_idx, quote_idx, smart_quote_idx] if idx != -1
        ]
        if delim_indices:
            first_idx = min(delim_indices)
            candidate = line[:first_idx].strip()
            candidate_clean = re.sub(r"^[\[\(\s]+|[\]\)\:\s]+$", "", candidate).strip()
            if candidate_clean:
                speaker_raw = candidate_clean

        matched_role_id: str | None = None
        matched_role_name: str | None = None
        if speaker_raw:
            spk_lower = speaker_raw.lower()
            if characters:
                for char in characters:
                    char_role = char.role_id.strip().lower()
                    char_name = char.name.strip().lower()
                    if spk_lower in (char_role, char_name):
                        matched_role_id = char.role_id
                        matched_role_name = char.name
                        break
                    if spk_lower in char_name or char_name in spk_lower:
                        matched_role_id = char.role_id
                        matched_role_name = char.name
                        break
                    if char_role in spk_lower:
                        matched_role_id = char.role_id
                        matched_role_name = char.name
                        break

            role_to_add = matched_role_id if matched_role_id else speaker_raw
            if role_to_add not in active_roles:
                active_roles.append(role_to_add)

        # Parenthetical extraction
        parentheticals = re.findall(r"\((.*?)\)", line)
        for ptext in parentheticals:
            ptext_clean = ptext.strip()
            if not ptext_clean:
                continue
            segments = [s.strip() for s in re.split(r"[.;]", ptext_clean) if s.strip()]
            for seg in segments:
                seg_lower = seg.lower()
                has_audio_kw = any(kw in seg_lower for kw in SCREENPLAY_AUDIO_KEYWORDS)
                is_pure_audio = seg_lower.startswith(
                    ("audio:", "sound:", "bgm:", "sfx:", "cue:")
                ) or (
                    has_audio_kw
                    and not any(
                        w in seg_lower
                        for w in [
                            "standing",
                            "bopping",
                            "walking",
                            "looking",
                            "stepping",
                            "sitting",
                            "gesturing",
                            "head",
                            "wand",
                            "hand",
                            "eye",
                            "face",
                            "wearing",
                            "facing",
                            "running",
                            "moving",
                            "turning",
                        ]
                    )
                )
                if not is_pure_audio:
                    if seg not in seen_actions:
                        seen_actions.add(seg)
                        action_parts.append(seg)
                if has_audio_kw:
                    seg_clean = re.sub(
                        r"^(?:audio|sound|bgm|sfx|cue)\s*:\s*",
                        "",
                        seg,
                        flags=re.IGNORECASE,
                    ).strip()
                    if seg_clean and seg_clean not in seen_audio:
                        seen_audio.add(seg_clean)
                        audio_cue_parts.append(seg_clean)

        # Quoted text extraction
        quotes = re.findall(r'["“]([^"”]+)["”]', line)
        if quotes:
            spoken_text = " ".join(q.strip() for q in quotes if q.strip())
            if spoken_text:
                matched_char = None
                if matched_role_id and characters:
                    for c in characters:
                        if getattr(c, "role_id", "") == matched_role_id:
                            matched_char = c
                            break
                if matched_char:
                    speaker_display = get_character_identifier(matched_char)
                elif matched_role_id and matched_role_name:
                    speaker_display = f"{matched_role_id} - {matched_role_name}"
                else:
                    speaker_display = speaker_raw if speaker_raw else "Speaker"

                if char_tag_map and char_tag_map.get(speaker_display):
                    tag = char_tag_map[speaker_display]
                    if tag not in speaker_display:
                        speaker_display = f"{speaker_display} {tag}"

                dialogue_parts.append(f'{speaker_display}: "{spoken_text}"')

    action_str = ". ".join(action_parts).strip()
    if action_str and not action_str.endswith("."):
        action_str += "."

    audio_cues_str = ". ".join(audio_cue_parts).strip()
    if audio_cues_str and not audio_cues_str.endswith("."):
        audio_cues_str += "."

    dialogue_str = " / ".join(dialogue_parts).strip()

    return {
        "active_roles": active_roles,
        "action": action_str,
        "audio_cues": audio_cues_str,
        "dialogue": dialogue_str,
    }


def parse_timecoded_script(
    script_text: str,
    characters: list[CharacterRole] | None = None,
    char_tag_map: dict[str, str] | None = None,
    default_duration: float = 30.0,
) -> list[dict[str, Any]]:
    """Canonical screenplay and timecoded script parser for OmniMash.

    Unifies timecode extraction, parenthetical audio/action parsing, role injection,
    and automatic <=10.0s shot interval splitting (CORR-01 and CORR-02).
    """
    if not script_text or not script_text.strip():
        return []

    validate_prompt_input_lengths(screenplay_script=script_text)

    def _parse_tc_sec(val_str: str) -> float:
        val_str = val_str.strip()
        if ":" in val_str:
            parts = val_str.split(":")
            return float(parts[0]) * 60.0 + float(parts[1])
        return float(val_str)

    pattern = r"\[\s*((?:\d+:)?\d+(?:\.\d+)?)\s*s?\s*-\s*((?:\d+:)?\d+(?:\.\d+)?)\s*s?\s*\]"
    matches = list(re.finditer(pattern, script_text))

    raw_blocks: list[dict[str, Any]] = []

    if matches:
        for i, m in enumerate(matches):
            start_t = _parse_tc_sec(m.group(1))
            end_t = _parse_tc_sec(m.group(2))
            text_start = m.end()
            text_end = matches[i + 1].start() if i + 1 < len(matches) else len(script_text)
            block = script_text[text_start:text_end].strip()
            raw_blocks.append(
                {
                    "start_t": start_t,
                    "end_t": end_t,
                    "block": block,
                }
            )
    else:
        clean_text = re.sub(
            r"\[\s*DIRECTOR['’]?S\s+NOTES\s*\][\s\S]*?(?=\[\s*\d|\Z)",
            "",
            script_text,
            flags=re.IGNORECASE,
        ).strip()
        if clean_text:
            raw_blocks.append(
                {
                    "start_t": 0.0,
                    "end_t": float(default_duration),
                    "block": clean_text,
                }
            )

    if not raw_blocks:
        return []

    results: list[dict[str, Any]] = []

    def _resolve_roles(diag_text: str, default_roles: list[str]) -> list[str]:
        if default_roles:
            return list(default_roles)
        if ":" not in diag_text:
            return []
        spk = diag_text.split(":", 1)[0].strip()
        if not spk:
            return []
        if characters:
            spk_lower = spk.lower()
            for char in characters:
                c_role = char.role_id.strip().lower()
                c_name = char.name.strip().lower()
                if spk_lower in (c_role, c_name) or c_role in spk_lower or spk_lower in c_name:
                    return [char.role_id]
                c_id = get_character_identifier(char).strip().lower()
                if spk_lower in c_id or c_id in spk_lower:
                    return [char.role_id]
        return [spk]

    for raw in raw_blocks:
        start_t = raw["start_t"]
        end_t = raw["end_t"]
        block = raw["block"]
        total_duration = max(0.0, round(end_t - start_t, 2))

        parsed_roles: list[str] = []
        # Check for structured multi-line block syntax
        if any(k in block.upper() for k in ("ACTION:", "DIALOGUE:", "AUDIO:")):
            action_match = re.search(
                r"ACTION:\s*(.*?)(?=\n(?:DIALOGUE|AUDIO|ACTION):|$)",
                block,
                re.IGNORECASE | re.DOTALL,
            )
            dialogue_match = re.search(
                r"DIALOGUE:\s*(.*?)(?=\n(?:DIALOGUE|AUDIO|ACTION):|$)",
                block,
                re.IGNORECASE | re.DOTALL,
            )
            audio_match = re.search(
                r"AUDIO(?:_CUES)?:\s*(.*?)(?=\n(?:DIALOGUE|AUDIO|ACTION):|$)",
                block,
                re.IGNORECASE | re.DOTALL,
            )

            raw_act = action_match.group(1).strip().replace("\n", " ") if action_match else ""
            raw_diag = dialogue_match.group(1).strip().replace("\n", " ") if dialogue_match else ""
            raw_aud = audio_match.group(1).strip().replace("\n", " ") if audio_match else ""

            # Check if action or dialogue contains character dialogue
            sub_act, sub_diag, sub_aud = _extract_character_dialogue(raw_act)
            if sub_diag and not raw_diag:
                raw_diag = sub_diag
                raw_act = sub_act
            if sub_aud and not raw_aud:
                raw_aud = sub_aud

            action_lines = [raw_act] if raw_act else []
            dialogue_lines = [raw_diag] if raw_diag else []
            audio_lines = [raw_aud] if raw_aud else []
        else:
            parsed = parse_screenplay_script(
                block, characters=characters, char_tag_map=char_tag_map
            )
            action_lines = [parsed["action"]] if parsed.get("action") else []
            dialogue_lines = [parsed["dialogue"]] if parsed.get("dialogue") else []
            audio_lines = [parsed["audio_cues"]] if parsed.get("audio_cues") else []
            parsed_roles = parsed.get("active_roles", [])

        if total_duration > 10.0:
            num_chunks = int(math.ceil(total_duration / 10.0))
            for k in range(num_chunks):
                chunk_start = round(start_t + k * 10.0, 2)
                chunk_end = round(min(end_t, chunk_start + 10.0), 2)
                chunk_dur = max(0.0, round(chunk_end - chunk_start, 2))
                start_str = f"{int(chunk_start) if chunk_start.is_integer() else chunk_start}"
                end_str = f"{int(chunk_end) if chunk_end.is_integer() else chunk_end}"
                tc_label = f"[{start_str}-{end_str}s]"

                chunk_action_lines = _slice_lines(action_lines, k, num_chunks)
                chunk_dialogue_lines = _slice_lines(dialogue_lines, k, num_chunks)
                chunk_audio_lines = _slice_lines(audio_lines, k, num_chunks)

                action_text = (
                    "\n".join(chunk_action_lines).strip()
                    if chunk_action_lines
                    else (block if not dialogue_lines and not audio_lines else "")
                )
                dialogue_text = "\n".join(chunk_dialogue_lines).strip()
                audio_text = "\n".join(chunk_audio_lines).strip()
                summary_text = (
                    chunk_action_lines[0]
                    if chunk_action_lines
                    else (
                        chunk_dialogue_lines[0]
                        if chunk_dialogue_lines
                        else (action_lines[0] if action_lines else f"Shot {len(results) + 1}")
                    )
                )

                roles = _resolve_roles(dialogue_text, parsed_roles)
                results.append(
                    {
                        "timecode": tc_label,
                        "start_seconds": chunk_start,
                        "end_seconds": chunk_end,
                        "duration_seconds": chunk_dur,
                        "active_roles": roles,
                        "action": action_text,
                        "dialogue": dialogue_text,
                        "audio": audio_text,
                        "audio_cues": audio_text,
                        "summary": summary_text,
                        "raw_text": block,
                    }
                )
        else:
            start_str = f"{int(start_t) if start_t.is_integer() else start_t}"
            end_str = f"{int(end_t) if end_t.is_integer() else end_t}"
            tc_label = f"[{start_str}-{end_str}s]"

            action_text = (
                "\n".join(action_lines).strip()
                if action_lines
                else (block if not dialogue_lines and not audio_lines else "")
            )
            dialogue_text = "\n".join(dialogue_lines).strip()
            audio_text = "\n".join(audio_lines).strip()
            summary_text = (
                action_lines[0]
                if action_lines
                else (
                    dialogue_lines[0]
                    if dialogue_lines
                    else (block.splitlines()[0] if block else f"Shot {len(results) + 1}")
                )
            )

            roles = _resolve_roles(dialogue_text, parsed_roles)
            results.append(
                {
                    "timecode": tc_label,
                    "start_seconds": start_t,
                    "end_seconds": end_t,
                    "duration_seconds": total_duration,
                    "active_roles": roles,
                    "action": action_text,
                    "dialogue": dialogue_text,
                    "audio": audio_text,
                    "audio_cues": audio_text,
                    "summary": summary_text,
                    "raw_text": block,
                }
            )

    return results


__all__ = [
    "MAX_CONCEPT_CHARS",
    "MAX_SCREENPLAY_CHARS",
    "SCREENPLAY_AUDIO_KEYWORDS",
    "parse_directors_notes",
    "parse_screenplay_script",
    "parse_timecoded_script",
    "validate_prompt_input_lengths",
]
