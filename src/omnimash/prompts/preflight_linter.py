"""Pre-flight Gatekeeper and Linter for OmniMash Gemini Omni Flash prompts.

Implements Track 1 of DOMA Phase 3:
1. Tag collision repair: cleans stacked <IMAGE_REF_N> tags, duplicate @Image tokens,
   and unattached phantom tokens (e.g. 'KeyframeSeed', 'EndKeyframe').
2. Keyframe offset repair: auto-shifts character reference indices from @Image1 to @Image2
   (or @Image3 for dual-keyframe / seamless loop) when keyframe seed is provided.
3. Zero Wardrobe Redundancy: scrubs conflicting clothing prose for characters with attached
   reference sheets and enforces reference sheet appearance lock while preserving
   personality, posture, and voice styling.
4. Dual-layer audio ducking: ensures instrumental prefix on background music and injects
   canonical audio ducking clause under spoken dialogue.
5. Spatial staging: enforces screen-left / screen-right staging when 2 or more reference
   characters appear in scene.
"""

from __future__ import annotations

import re
from typing import Any

from omnimash.prompts.character_roles import normalize_character_role
from omnimash.prompts.models import PreFlightLintResult, PreFlightViolation


class PreFlightGatekeeper:
    """Pre-flight linter and invariant gatekeeper enforcing DOMA Phase 3 prompt standards."""

    CANONICAL_DUCKING_CLAUSE: str = (
        "Ensure the background music ducks under the spoken dialogue so the voice is clear, "
        "front-and-center, and intelligible."
    )

    @classmethod
    def repair_tag_collisions(
        cls,
        prompt_text: str,
        characters: list[Any] | None = None,
    ) -> tuple[str, list[PreFlightViolation]]:
        """Detects stacked image tags (e.g., <IMAGE_REF_0> <IMAGE_REF_1> or duplicate @Image tokens on a single role).

        Keeps only the canonical tag, strips redundant/colliding tags, and cleans phantom tokens like
        'KeyframeSeed' when unattached.
        """
        if not prompt_text:
            return prompt_text, []

        violations: list[PreFlightViolation] = []
        repaired = prompt_text

        # 1. Stacked image tags: e.g. <IMAGE_REF_0> <IMAGE_REF_1>, <IMAGE_REF_0>@Image1 <IMAGE_REF_1>,
        # or <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image1
        stacked_tag_pattern = re.compile(
            r"(<IMAGE_REF_\d+>(?:@Image\d+)?)(?:\s*<IMAGE_REF_\d+>(?:@Image\d+)?)+",
            re.IGNORECASE,
        )

        def _replace_stacked_tags(match: re.Match[str]) -> str:
            full = match.group(0)

            # Check if match is inside [# References ...] or [# Sources ...]
            preceding = prompt_text[: match.start()]
            following = prompt_text[match.end() :]
            last_open = preceding.rfind("[")
            last_close = preceding.rfind("]")
            if last_open > last_close:
                next_close = following.find("]")
                if next_close != -1:
                    bracket_content = prompt_text[last_open : match.end() + next_close + 1]
                    if re.match(
                        r"^\[#\s*(?:References|Sources)\b",
                        bracket_content,
                        flags=re.IGNORECASE,
                    ):
                        parsed_tags = re.findall(
                            r"<IMAGE_REF_(\d+)>(?:@Image(\d+))?",
                            full,
                            flags=re.IGNORECASE,
                        )
                        ref_ids = [t[0] for t in parsed_tags]
                        img_ids = [t[1] for t in parsed_tags if t[1]]
                        if (
                            len(parsed_tags) > 1
                            and len(ref_ids) == len(set(ref_ids))
                            and len(img_ids) == len(parsed_tags)
                            and len(img_ids) == len(set(img_ids))
                        ):
                            return full

            canonical = match.group(1)
            # If canonical lacked @Image but a colliding tag had it, preserve the @Image attachment
            if "@Image" not in canonical:
                img_m = re.search(r"@Image\d+", full, flags=re.IGNORECASE)
                if img_m:
                    canonical = f"{canonical}{img_m.group(0)}"
            violations.append(
                PreFlightViolation(
                    rule_id="TAG_COLLISION",
                    category="tagging",
                    description=(
                        f"Stacked image reference tags detected ('{full}'). "
                        f"Kept canonical tag '{canonical}' and stripped colliding tags."
                    ),
                    repaired=True,
                    original_snippet=full,
                    repaired_snippet=canonical,
                )
            )
            return canonical

        repaired = stacked_tag_pattern.sub(_replace_stacked_tags, repaired)

        # 2. Duplicate @Image tokens on a single role or mention (e.g. @Image1 @Image1, @Image1, @Image1, (@Image1) (@Image1))
        # Handle parenthesized duplicates first: (@Image1) (@Image1) or (@Image1, @Image1)
        dup_parens_pattern = re.compile(
            r"(\(@Image\d+\))(?:\s*,\s*|\s+)(\(@Image\d+\))+",
            re.IGNORECASE,
        )

        def _replace_dup_parens(match: re.Match[str]) -> str:
            canonical = match.group(1)
            violations.append(
                PreFlightViolation(
                    rule_id="TAG_COLLISION",
                    category="tagging",
                    description=(
                        f"Duplicate parenthesized image tokens detected ('{match.group(0)}'). "
                        f"Kept canonical '{canonical}'."
                    ),
                    repaired=True,
                    original_snippet=match.group(0),
                    repaired_snippet=canonical,
                )
            )
            return canonical

        repaired = dup_parens_pattern.sub(_replace_dup_parens, repaired)

        # Handle duplicates inside single parens: (@Image1, @Image1) or (@Image1 @Image1)
        dup_inside_parens_pattern = re.compile(
            r"\((@Image\d+)(?:[,\s]+@Image\d+)+\)",
            re.IGNORECASE,
        )

        def _replace_dup_inside_parens(match: re.Match[str]) -> str:
            canonical = f"({match.group(1)})"
            violations.append(
                PreFlightViolation(
                    rule_id="TAG_COLLISION",
                    category="tagging",
                    description=(
                        f"Duplicate image tokens inside parentheses detected ('{match.group(0)}'). "
                        f"Kept canonical '{canonical}'."
                    ),
                    repaired=True,
                    original_snippet=match.group(0),
                    repaired_snippet=canonical,
                )
            )
            return canonical

        repaired = dup_inside_parens_pattern.sub(_replace_dup_inside_parens, repaired)

        # Handle unparenthesized duplicate @Image tokens: @Image1 @Image1, @Image1, @Image1
        dup_img_pattern = re.compile(
            r"(@Image\d+)(?:[,\s]+@Image\d+)+",
            re.IGNORECASE,
        )

        def _replace_dup_images(match: re.Match[str]) -> str:
            canonical = match.group(1)
            violations.append(
                PreFlightViolation(
                    rule_id="TAG_COLLISION",
                    category="tagging",
                    description=(
                        f"Duplicate @Image tokens detected ('{match.group(0)}'). "
                        f"Kept canonical token '{canonical}'."
                    ),
                    repaired=True,
                    original_snippet=match.group(0),
                    repaired_snippet=canonical,
                )
            )
            return canonical

        repaired = dup_img_pattern.sub(_replace_dup_images, repaired)

        # 3. Phantom unattached tokens like 'KeyframeSeed' and 'EndKeyframe'
        # KeyframeSeed is canonical ONLY when attached to <FIRST_FRAME> (e.g. <FIRST_FRAME>@KeyframeSeed)
        # EndKeyframe is canonical ONLY when attached to <LAST_FRAME> (e.g. <LAST_FRAME>@EndKeyframe)
        # Any occurrence unattached to its canonical anchor is a phantom token to be removed.
        def _clean_phantom_tokens(text: str) -> str:
            protected_canonical: dict[str, str] = {}
            p_counter = 0

            def _protect(m: re.Match[str]) -> str:
                nonlocal p_counter
                ph = f"__CANONICAL_ANCHOR_{p_counter}__"
                protected_canonical[ph] = m.group(0)
                p_counter += 1
                return ph

            # Protect canonical keyframe attachments
            text = re.sub(
                r"<FIRST_FRAME>\s*@?(?:KeyframeSeed\b|Image\d+)",
                _protect,
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(
                r"<LAST_FRAME>\s*@?(?:EndKeyframe\b|KeyframeSeed\b|Image\d+)",
                _protect,
                text,
                flags=re.IGNORECASE,
            )

            # Match any unattached KeyframeSeed or EndKeyframe (with optional @, parens, and leading whitespace)
            phantom_re = re.compile(
                r"(?:\s*\(?@?(?:KeyframeSeed|EndKeyframe)\)?|\b@?(?:KeyframeSeed|EndKeyframe)\b)",
                flags=re.IGNORECASE,
            )

            matches = list(phantom_re.finditer(text))
            if matches:
                for m in reversed(matches):
                    snippet = m.group(0)
                    if not snippet.strip():
                        continue
                    violations.append(
                        PreFlightViolation(
                            rule_id="TAG_COLLISION",
                            category="tagging",
                            description=f"Removed unattached phantom token '{snippet.strip()}'.",
                            repaired=True,
                            original_snippet=snippet,
                            repaired_snippet="",
                        )
                    )
                    text = text[: m.start()] + text[m.end() :]

            # Restore canonical anchors
            for ph, orig in protected_canonical.items():
                text = text.replace(ph, orig)

            return text

        repaired = _clean_phantom_tokens(repaired)
        return repaired, violations

    @classmethod
    def repair_keyframe_offsets(
        cls,
        prompt_text: str,
        keyframe_image_url: str | None = None,
        characters: list[Any] | None = None,
        is_seamless_loop: bool = False,
        last_frame_image_url: str | None = None,
    ) -> tuple[str, list[PreFlightViolation]]:
        """When a keyframe seed is provided, character references MUST start at @Image2 (or @Image3 if dual-keyframe / loop).

        Auto-shifts character reference indices and adjusts mentions throughout prompt text.
        """
        if not prompt_text:
            return prompt_text, []

        violations: list[PreFlightViolation] = []

        # Normalize character models if provided
        norm_chars = [normalize_character_role(c) for c in (characters or [])]

        has_first_frame = bool(
            (keyframe_image_url and str(keyframe_image_url).strip())
            or "<FIRST_FRAME>" in prompt_text
            or any(
                c.image_role in ("Starting Frame", "Keyframe Seed Anchor", "First Frame")
                for c in norm_chars
            )
        )
        has_last_frame = bool(
            is_seamless_loop
            or (last_frame_image_url and str(last_frame_image_url).strip())
            or "<LAST_FRAME>" in prompt_text
            or any(
                c.image_role in ("Ending Frame", "Keyframe Last Anchor", "Last Frame")
                for c in norm_chars
            )
        )

        if not has_first_frame and not has_last_frame:
            return prompt_text, []

        target_start_index = 3 if has_last_frame else 2

        # Step 1: Temporarily protect keyframe tag indices from shifting
        preserved_map: dict[str, str] = {}
        counter = 0

        def _preserve(match: re.Match[str]) -> str:
            nonlocal counter
            placeholder = f"__PRESERVED_KEYFRAME_{counter}__"
            preserved_map[placeholder] = match.group(0)
            counter += 1
            return placeholder

        protected_text = re.sub(
            r"<FIRST_FRAME>\s*@?(?:KeyframeSeed|Image\d+)",
            _preserve,
            prompt_text,
            flags=re.IGNORECASE,
        )
        protected_text = re.sub(
            r"<LAST_FRAME>\s*@?(?:EndKeyframe|KeyframeSeed|Image\d+)",
            _preserve,
            protected_text,
            flags=re.IGNORECASE,
        )

        # Step 2: Determine current character image starting index from remaining @Image tokens
        char_image_matches = list(re.finditer(r"@Image(\d+)", protected_text))
        if not char_image_matches:
            return prompt_text, []

        min_char_index = min(int(m.group(1)) for m in char_image_matches)

        if min_char_index >= target_start_index:
            # Indices already properly offset
            return prompt_text, []

        shift = target_start_index - min_char_index

        # Step 3: Shift all character @Image tokens by `shift`
        def _shift_image(match: re.Match[str]) -> str:
            current_idx = int(match.group(1))
            new_idx = current_idx + shift
            return f"@Image{new_idx}"

        shifted_text = re.sub(r"@Image(\d+)", _shift_image, protected_text)

        # Step 4: Restore preserved keyframe tokens
        for placeholder, original in preserved_map.items():
            shifted_text = shifted_text.replace(placeholder, original)

        violations.append(
            PreFlightViolation(
                rule_id="KEYFRAME_OFFSET",
                category="keyframe",
                description=(
                    f"Character reference indices auto-shifted from @Image{min_char_index} to "
                    f"@Image{target_start_index} (+{shift}) due to keyframe presence."
                ),
                repaired=True,
                original_snippet=f"@Image{min_char_index}",
                repaired_snippet=f"@Image{target_start_index}",
            )
        )

        return shifted_text, violations

    @classmethod
    def repair_zero_wardrobe_redundancy(
        cls,
        prompt_text: str,
        characters: list[Any] | None = None,
    ) -> tuple[str, list[PreFlightViolation]]:
        """If a character has an attached image reference sheet, checks ### CHARACTER PROFILES.

        Scrubs conflicting wardrobe prose from their profile description and locks appearance
        to the reference sheet ("Enforce Zero Wardrobe Redundancy: Visual appearance locked to reference sheet @ImageN").
        """
        if not prompt_text:
            return prompt_text, []

        violations: list[PreFlightViolation] = []

        # Find character profiles section
        section_match = re.search(
            r"(### CHARACTER PROFILES[^\n]*\n)(.*?)(?=\n### |\Z)",
            prompt_text,
            flags=re.DOTALL,
        )
        if not section_match:
            return prompt_text, []

        profiles_body = section_match.group(2)

        # Build mapping of character identifiers to image reference tags
        ref_roles: dict[
            str, str
        ] = {}  # normalized role/name identifier -> image tag (e.g. '@Image2')
        if characters:
            for char in characters:
                norm = normalize_character_role(char)
                if norm.reference_url and str(norm.reference_url).strip():
                    r_id = norm.role_id.strip()
                    if r_id:
                        ref_roles[r_id.lower()] = ""
                    name = norm.name.strip()
                    if name:
                        ref_roles[name.lower()] = ""

        # Inspect prompt's ### INPUT ROLES & REFERENCES for reference sheet bindings
        input_match = re.search(
            r"### INPUT ROLES & REFERENCES[^\n]*\n(.*?)(?=\n### |\Z)",
            prompt_text,
            flags=re.DOTALL,
        )
        if input_match:
            input_body = input_match.group(1)
            # Find any references declared in Block 1
            has_image_refs_in_block1 = bool(re.search(r"<IMAGE_REF_\d+>", input_body))
            for line in input_body.splitlines():
                line_s = line.strip()
                if not line_s or line_s.startswith("[# Sources"):
                    continue

                # Check if this line binds a role
                role_match = re.search(
                    r"-\s*(Role\s+[A-Z0-9]+|[A-Za-z0-9_\s]+?)(?:\s*\([^)]*\))?\s*:",
                    line_s,
                    flags=re.IGNORECASE,
                )
                img_match = re.search(r"@Image(\d+)", line_s)
                tag = f"@Image{img_match.group(1)}" if img_match else ""

                if role_match:
                    role_name = role_match.group(1).strip().lower()
                    if tag or has_image_refs_in_block1 or "gs://" in line_s or "http" in line_s:
                        ref_roles[role_name] = tag

        lines = profiles_body.splitlines()
        repaired_lines: list[str] = []

        # Regex patterns for wardrobe scrubbing
        p_wardrobe_bracket = re.compile(r"\[Wardrobe:[^\]]*\]", re.IGNORECASE)
        p_wardrobe_colon = re.compile(
            r"Wardrobe:\s*.*?(?=(?:\.\s+[A-Z]|Voice:|\[Voice|\Z|\n))(?:\.)?",
            re.IGNORECASE,
        )
        p_sentence_clothing = re.compile(
            r"(?:(?:he|she|they)\s+(?:is|are|was|were)\s+)"
            r"(?:wearing|dressed in|attired in|clad in|sporting|outfitted in)\s+"
            r".*?(?=(?:\.\s+[A-Z]|Voice:|\[Voice|\Z|\n))(?:\.)?",
            re.IGNORECASE,
        )
        p_clause_clothing = re.compile(
            r",?\s*(?:wearing|dressed in|attired in|clad in|sporting|outfitted in)\s+"
            r"[^.,;\n]+?"
            r"(?:(?:,\s*[^.,;\n]+?)*\s*(?:,\s*and|\s+and|\s+with)\s+[^.,;\n]+|(?=[.,;\n]))(?:\.)?",
            re.IGNORECASE,
        )

        for line in lines:
            line_str = line.strip()
            if not line_str.startswith(("-", "*", "[")) and "Role" not in line_str:
                repaired_lines.append(line)
                continue

            # Check if this character has an attached reference sheet
            has_ref = False
            line_lower = line_str.lower()
            tag_for_char = "@Image1"

            img_on_line = re.search(r"@Image(\d+)", line_str)
            if img_on_line:
                tag_for_char = f"@Image{img_on_line.group(1)}"
                has_ref = True
            elif "<IMAGE_REF_" in line_str:
                has_ref = True

            for r_key, bound_tag in ref_roles.items():
                if r_key in line_lower:
                    has_ref = True
                    if bound_tag:
                        tag_for_char = bound_tag
                    break

            if not has_ref:
                repaired_lines.append(line)
                continue

            # Check for wardrobe indicators
            has_clothing_prose = bool(
                p_wardrobe_bracket.search(line_str)
                or p_wardrobe_colon.search(line_str)
                or p_sentence_clothing.search(line_str)
                or p_clause_clothing.search(line_str)
            )

            if not has_clothing_prose:
                repaired_lines.append(line)
                continue

            original_line = line
            cleaned = line
            cleaned = p_wardrobe_bracket.sub("", cleaned)
            cleaned = p_wardrobe_colon.sub("", cleaned)
            cleaned = p_sentence_clothing.sub("", cleaned)
            cleaned = p_clause_clothing.sub("", cleaned)

            # Clean up residual punctuation and spacing
            cleaned = re.sub(r",\s*,", ", ", cleaned)
            cleaned = re.sub(r",\s*\.", ".", cleaned)
            cleaned = re.sub(r":\s*,", ":", cleaned)
            cleaned = re.sub(r"\.\s*\.", ".", cleaned)
            cleaned = re.sub(r":\s*\.", ":", cleaned)
            cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

            # Insert zero wardrobe lock clause
            lock_clause = (
                f"Enforce Zero Wardrobe Redundancy: Visual appearance locked to reference sheet "
                f"{tag_for_char}"
            )
            if "Enforce Zero Wardrobe Redundancy" not in cleaned:
                voice_match = re.search(r"(Voice(?:\s*style)?\s*:|\[Voice)", cleaned, re.IGNORECASE)
                if voice_match:
                    v_start = voice_match.start()
                    prefix = cleaned[:v_start].rstrip()
                    if prefix.endswith(":"):
                        cleaned = f"{prefix} {lock_clause}. {cleaned[v_start:]}"
                    else:
                        if not prefix.endswith((".", ";")):
                            prefix += "."
                        cleaned = f"{prefix} {lock_clause}. {cleaned[v_start:]}"
                else:
                    if cleaned.endswith(":"):
                        cleaned = f"{cleaned} {lock_clause}."
                    else:
                        end_clean = cleaned.rstrip(". ")
                        cleaned = f"{end_clean}. {lock_clause}." if end_clean else f"{lock_clause}."

            violations.append(
                PreFlightViolation(
                    rule_id="ZERO_WARDROBE_REDUNDANCY",
                    category="wardrobe",
                    description=(
                        f"Scrubbed conflicting wardrobe prose and locked visual appearance "
                        f"to reference sheet {tag_for_char}."
                    ),
                    repaired=True,
                    original_snippet=original_line.strip(),
                    repaired_snippet=cleaned.strip(),
                )
            )
            repaired_lines.append(cleaned)

        if not violations:
            return prompt_text, []

        new_profiles_body = "\n".join(repaired_lines)
        repaired_prompt = (
            prompt_text[: section_match.start(2)]
            + new_profiles_body
            + prompt_text[section_match.end(2) :]
        )
        return repaired_prompt, violations

    @classmethod
    def repair_audio_ducking(
        cls,
        prompt_text: str,
        has_dialogue: bool = False,
    ) -> tuple[str, list[PreFlightViolation]]:
        """If dialogue is present, ensures 'instrumental' is prefixed to background beat and appends canonical ducking clause in Block 3."""
        if not prompt_text:
            return prompt_text, []

        violations: list[PreFlightViolation] = []

        # Find TIMELINE section to isolate timeline dialogue and quotes
        timeline_match = re.search(
            r"### TIMELINE[^\n]*\n(.*?)(?=\n### |\Z)",
            prompt_text,
            flags=re.DOTALL,
        )
        timeline_body = timeline_match.group(1) if timeline_match else ""

        # Detect dialogue presence:
        # 1. has_dialogue flag
        # 2. 'Dialogue:' or 'Dialogue between subjects:' directive in prompt
        # 3. Quotes or spoken verbs inside ### TIMELINE
        # (avoid matching non-dialogue quotes like title cards in Block 3)
        dialogue_detected = bool(
            has_dialogue
            or re.search(r"Dialogue(?:\s*between\s*subjects)?\s*:", prompt_text, re.IGNORECASE)
            or re.search(
                r'\b(?:says|speaks|whispers|shouts|yells):\s*["\']|["\'][^"\']{2,}["\']',
                timeline_body,
                flags=re.IGNORECASE,
            )
        )

        if not dialogue_detected:
            return prompt_text, []

        # Locate ### SCENE INSTRUCTIONS
        scene_match = re.search(
            r"(### SCENE INSTRUCTIONS[^\n]*\n)(.*?)(?=\n### |\Z)",
            prompt_text,
            flags=re.DOTALL,
        )
        if not scene_match:
            # Inject ### SCENE INSTRUCTIONS if missing
            ducking_clause = cls.CANONICAL_DUCKING_CLAUSE
            injected = (
                f"\n\n### SCENE INSTRUCTIONS\nAudio: instrumental ambient track. {ducking_clause}"
            )
            violations.append(
                PreFlightViolation(
                    rule_id="AUDIO_DUCKING",
                    category="audio",
                    description="Injected missing Block 3 scene instructions with canonical dialogue ducking clause.",
                    repaired=True,
                    original_snippet="",
                    repaired_snippet=injected.strip(),
                )
            )
            return f"{prompt_text}{injected}", violations

        scene_body = scene_match.group(2)
        lines = scene_body.splitlines()
        repaired_lines: list[str] = []
        audio_found = False

        ducking_clause = cls.CANONICAL_DUCKING_CLAUSE
        audio_line_re = re.compile(
            r"^(\s*(?:[-*]\s*)?(?:Audio|Sound design|Audio Soundscape):\s*)(.*)$",
            re.IGNORECASE,
        )

        for line in lines:
            m = audio_line_re.match(line)
            if m:
                audio_found = True
                orig_audio = line
                prefix = m.group(1)
                rest = m.group(2).strip()

                # Check if audio is explicitly silent/muted or seamless acoustic progression
                if any(
                    k in rest.lower()
                    for k in (
                        "silent video",
                        "no background music",
                        "mute",
                        "silent.",
                        "seamless acoustic progression",
                    )
                ):
                    repaired_lines.append(line)
                    continue

                # 1. Prefix 'instrumental' if not already present
                if not rest.lower().startswith("instrumental"):
                    rest = f"instrumental {rest}"

                # 2. Append canonical ducking clause if not already present
                if ducking_clause not in rest:
                    clean_core = rest.rstrip(". ")
                    rest = f"{clean_core}. {ducking_clause}"

                updated_audio = f"{prefix}{rest}"
                if updated_audio != orig_audio:
                    violations.append(
                        PreFlightViolation(
                            rule_id="AUDIO_DUCKING",
                            category="audio",
                            description=(
                                "Enforced instrumental background beat prefix and injected "
                                "canonical dialogue audio ducking clause into Block 3."
                            ),
                            repaired=True,
                            original_snippet=orig_audio.strip(),
                            repaired_snippet=updated_audio.strip(),
                        )
                    )
                repaired_lines.append(updated_audio)
            else:
                repaired_lines.append(line)

        if not audio_found:
            injected_line = f"Audio: instrumental ambient track. {ducking_clause}"
            repaired_lines.append(injected_line)
            violations.append(
                PreFlightViolation(
                    rule_id="AUDIO_DUCKING",
                    category="audio",
                    description="Injected missing audio directive with canonical dialogue ducking clause into Block 3.",
                    repaired=True,
                    original_snippet="",
                    repaired_snippet=injected_line,
                )
            )

        if not violations:
            return prompt_text, []

        new_scene_body = "\n".join(repaired_lines)
        repaired_prompt = (
            prompt_text[: scene_match.start(2)] + new_scene_body + prompt_text[scene_match.end(2) :]
        )
        return repaired_prompt, violations

    @classmethod
    def repair_spatial_staging(
        cls,
        prompt_text: str,
        characters: list[Any] | None = None,
    ) -> tuple[str, list[PreFlightViolation]]:
        """If 2 or more characters with reference sheets appear in scene and spatial staging is undeclared, injects staging into Block 3."""
        if not prompt_text:
            return prompt_text, []

        violations: list[PreFlightViolation] = []

        # Count reference characters
        ref_role_ids: list[str] = []
        if characters:
            for char in characters:
                norm = normalize_character_role(char)
                if norm.reference_url and str(norm.reference_url).strip():
                    r_id = norm.role_id or norm.name or "Role"
                    if r_id not in ref_role_ids:
                        ref_role_ids.append(r_id)

        # Also inspect prompt's ### INPUT ROLES & REFERENCES for reference sheet characters
        if len(ref_role_ids) < 2:
            input_match = re.search(
                r"### INPUT ROLES & REFERENCES[^\n]*\n(.*?)(?=\n### |\Z)",
                prompt_text,
                flags=re.DOTALL,
            )
            if input_match:
                input_body = input_match.group(1)
                for line in input_body.splitlines():
                    m = re.search(
                        r"-\s*(Role\s+[A-Z0-9]+|[A-Za-z0-9_\s]+?)(?:\s*\([^)]*\))?\s*:",
                        line,
                        flags=re.IGNORECASE,
                    )
                    if m:
                        r_name = m.group(1).strip()
                        if (
                            "@Image" in line
                            or "<IMAGE_REF_" in line
                            or "gs://" in line
                            or "http" in line
                        ) and r_name not in ref_role_ids:
                            ref_role_ids.append(r_name)

        # Fallback check if prompt text has >= 2 image reference tags
        if len(ref_role_ids) < 2:
            img_refs = list(re.finditer(r"<IMAGE_REF_(\d+)>", prompt_text))
            if len(img_refs) >= 2:
                for idx in range(len(img_refs)):
                    role_label = f"Role {chr(ord('A') + idx)}"
                    if role_label not in ref_role_ids:
                        ref_role_ids.append(role_label)

        if len(ref_role_ids) < 2:
            return prompt_text, []

        # Check if spatial staging is already declared in ### SCENE INSTRUCTIONS or ### TIMELINE
        staging_context = ""
        scene_match = re.search(
            r"### SCENE INSTRUCTIONS[^\n]*\n(.*?)(?=\n### |\Z)",
            prompt_text,
            flags=re.DOTALL,
        )
        if scene_match:
            staging_context += scene_match.group(1) + "\n"

        timeline_match = re.search(
            r"### TIMELINE[^\n]*\n(.*?)(?=\n### |\Z)",
            prompt_text,
            flags=re.DOTALL,
        )
        if timeline_match:
            staging_context += timeline_match.group(1)

        lower_staging = staging_context.lower()
        if (
            "screen-left" in lower_staging
            or "screen-right" in lower_staging
            or "screen left" in lower_staging
            or "screen right" in lower_staging
        ):
            return prompt_text, []

        role_a = ref_role_ids[0] if len(ref_role_ids) > 0 else "Role A"
        role_b = ref_role_ids[1] if len(ref_role_ids) > 1 else "Role B"

        staging_clause = (
            f"Spatial staging: [{role_a}] positioned on screen-left, "
            f"[{role_b}] positioned on screen-right to maintain clear identity separation."
        )

        full_scene_match = re.search(
            r"(### SCENE INSTRUCTIONS[^\n]*\n)(.*?)(?=\n### |\Z)",
            prompt_text,
            flags=re.DOTALL,
        )
        if full_scene_match:
            body = full_scene_match.group(2)
            lines = body.splitlines()

            cam_idx = -1
            for idx, l_text in enumerate(lines):
                cleaned_l = l_text.strip().lstrip("-* ").lower()
                if cleaned_l.startswith("camera & lighting:"):
                    cam_idx = idx
                    break

            if cam_idx != -1:
                lines.insert(cam_idx + 1, staging_clause)
            else:
                lines.insert(0, staging_clause)

            new_body = "\n".join(lines)
            repaired_prompt = (
                prompt_text[: full_scene_match.start(2)]
                + new_body
                + prompt_text[full_scene_match.end(2) :]
            )
        else:
            repaired_prompt = f"{prompt_text}\n\n### SCENE INSTRUCTIONS\n{staging_clause}"

        violations.append(
            PreFlightViolation(
                rule_id="SPATIAL_STAGING",
                category="staging",
                description="Injected spatial staging to maintain clear identity separation between reference sheet characters.",
                repaired=True,
                original_snippet="",
                repaired_snippet=staging_clause,
            )
        )

        return repaired_prompt, violations

    @staticmethod
    def _append_to_scene_instructions(prompt_text: str, directive_line: str) -> str:
        """Appends a directive line cleanly to ### SCENE INSTRUCTIONS (or creates Block 3 if absent)."""
        scene_match = re.search(
            r"(### SCENE INSTRUCTIONS[^\n]*\n)(.*?)(?=\n### |\Z)",
            prompt_text,
            flags=re.DOTALL,
        )
        if not scene_match:
            return f"{prompt_text}\n\n### SCENE INSTRUCTIONS\n{directive_line}"

        existing_body = scene_match.group(2).rstrip("\n")
        trailing = "\n" if scene_match.group(2).endswith("\n") else ""
        updated_body = (
            f"{existing_body}\n{directive_line}{trailing}"
            if existing_body
            else f"{directive_line}{trailing}"
        )
        return (
            prompt_text[: scene_match.start(2)] + updated_body + prompt_text[scene_match.end(2) :]
        )

    @classmethod
    def repair_offering_physics_and_causality(
        cls,
        prompt_text: str,
        offering_physics: Any | None = None,
        palette_60_30_10: Any | None = None,
        act_number: int | None = None,
    ) -> tuple[str, list[PreFlightViolation]]:
        """Enforces Mode 5 60/30/10 palette lock, 3-act temporal causality gates, and ambient thermal physics."""
        if not prompt_text or (offering_physics is None and palette_60_30_10 is None):
            return prompt_text, []

        violations: list[PreFlightViolation] = []
        repaired = prompt_text

        # 1. 60/30/10 Production Design Color-Lock
        if palette_60_30_10 is not None:
            if hasattr(palette_60_30_10, "production_design_directive"):
                palette_directive = str(palette_60_30_10.production_design_directive).strip()
            elif isinstance(palette_60_30_10, dict):
                palette_directive = str(
                    palette_60_30_10.get("production_design_directive", "")
                ).strip()
                if not palette_directive:
                    p_hex = palette_60_30_10.get("primary_hex", "#1F242D")
                    s_hex = palette_60_30_10.get("secondary_hex", "#C47D4E")
                    n_hex = palette_60_30_10.get("neutral_hex", "#F2EFE9")
                    palette_directive = (
                        f"60% ({p_hex}) architectural set surfaces / "
                        f"30% ({s_hex}) wardrobe & practical props / "
                        f"10% ({n_hex}) foundational hero surface"
                    )
            else:
                palette_directive = ""

            if palette_directive:
                scene_match = re.search(
                    r"### SCENE INSTRUCTIONS[^\n]*\n(.*?)(?=\n### |\Z)",
                    repaired,
                    flags=re.DOTALL,
                )
                scene_body = scene_match.group(1) if scene_match else ""
                has_ratio_lock = "60%" in scene_body and "30%" in scene_body and "10%" in scene_body
                if not has_ratio_lock:
                    palette_line = (
                        f"- Production Design Palette (60/30/10 Color Lock): {palette_directive}"
                    )
                    repaired = cls._append_to_scene_instructions(repaired, palette_line)
                    violations.append(
                        PreFlightViolation(
                            rule_id="PALETTE_60_30_10_LOCK",
                            category="production_design",
                            description=(
                                "Injected 60/30/10 production design color-lock directive into "
                                "Block 3 scene instructions."
                            ),
                            repaired=True,
                            original_snippet="",
                            repaired_snippet=palette_line,
                        )
                    )

        # 2. Act-Specific Temporal Causality Gate & Ambient Thermal Physics
        if offering_physics is not None:
            laws = getattr(offering_physics, "act_causality_laws", None)
            if laws is None and isinstance(offering_physics, dict):
                laws = offering_physics.get("act_causality_laws")

            if act_number is not None and isinstance(laws, dict):
                act_law = str(laws.get(act_number) or laws.get(str(act_number)) or "").strip()
                gate_header = f"Causality Gate (Act {act_number}):"
                if act_law and act_law not in repaired and gate_header not in repaired:
                    causality_line = f"- {gate_header} {act_law}"
                    repaired = cls._append_to_scene_instructions(repaired, causality_line)
                    violations.append(
                        PreFlightViolation(
                            rule_id="TEMPORAL_CAUSALITY_GATE",
                            category="causality",
                            description=(
                                f"Injected Act {act_number} temporal causality guardrail into "
                                "Block 3 scene instructions."
                            ),
                            repaired=True,
                            original_snippet="",
                            repaired_snippet=causality_line,
                        )
                    )

            thermal_state = getattr(offering_physics, "thermal_state", None)
            if thermal_state is None and isinstance(offering_physics, dict):
                thermal_state = offering_physics.get("thermal_state")

            if str(thermal_state or "").strip().lower() == "ambient":
                ambient_replacements: tuple[tuple[re.Pattern[str], str], ...] = (
                    (
                        re.compile(
                            r"\bcovered in\s+ice-cold condensation\s+and\s+frosty droplets\b",
                            re.IGNORECASE,
                        ),
                        "with a clean dry ambient surface finish",
                    ),
                    (
                        re.compile(r"\bice-cold condensation\b", re.IGNORECASE),
                        "clean dry ambient surface finish",
                    ),
                    (
                        re.compile(
                            r"\b(?:icy|cold)\s+condensation(?:\s+droplets)?\b",
                            re.IGNORECASE,
                        ),
                        "clean dry ambient finish",
                    ),
                    (
                        re.compile(r"\bbeads of condensation\b", re.IGNORECASE),
                        "crisp ambient specular highlights",
                    ),
                    (
                        re.compile(r"\bcondensation droplets\b", re.IGNORECASE),
                        "crisp ambient specular highlights",
                    ),
                    (
                        re.compile(r"\bfrosty droplets\b", re.IGNORECASE),
                        "crisp ambient specular highlights",
                    ),
                    (
                        re.compile(r"\bfrost-covered\b", re.IGNORECASE),
                        "dry matte ambient",
                    ),
                    (
                        re.compile(r"\bwhile steaming hot\b", re.IGNORECASE),
                        "at dry room-temperature equilibrium",
                    ),
                    (
                        re.compile(r"\bsteaming hot\b", re.IGNORECASE),
                        "dry room-temperature ambient",
                    ),
                    (
                        re.compile(r"\bbillowing steam\b", re.IGNORECASE),
                        "clean still studio air",
                    ),
                    (
                        re.compile(
                            r"\b(?:piping hot|rising|wisps of(?:\s+hot)?)\s+steam\b",
                            re.IGNORECASE,
                        ),
                        "clean still ambient air",
                    ),
                )

                updated_lines: list[str] = []
                for line in repaired.splitlines():
                    lower_line = line.lower()
                    if any(
                        skip_cue in lower_line
                        for skip_cue in (
                            "causality gate",
                            "never add",
                            "zero condensation",
                            "without condensation",
                            "no condensation",
                        )
                    ):
                        updated_lines.append(line)
                        continue

                    working_line = line
                    for pattern, replacement in ambient_replacements:
                        match = pattern.search(working_line)
                        if match:
                            orig_snippet = match.group(0)
                            working_line = pattern.sub(replacement, working_line)
                            violations.append(
                                PreFlightViolation(
                                    rule_id="OFFERING_THERMAL_PHYSICS",
                                    category="physics",
                                    description=(
                                        "Scrubbed thermal condensation/steam contradiction from "
                                        "dry ambient offering prompt."
                                    ),
                                    repaired=True,
                                    original_snippet=orig_snippet,
                                    repaired_snippet=replacement,
                                )
                            )
                    updated_lines.append(working_line)

                repaired = "\n".join(updated_lines)

        return repaired, violations

    @classmethod
    def lint_and_repair(
        cls,
        prompt_text: str,
        characters: list[Any] | None = None,
        keyframe_image_url: str | None = None,
        last_frame_image_url: str | None = None,
        is_seamless_loop: bool = False,
        has_dialogue: bool = False,
        offering_physics: Any | None = None,
        palette_60_30_10: Any | None = None,
        act_number: int | None = None,
    ) -> PreFlightLintResult:
        """Main entry point for Pre-Flight Gatekeeper.

        Sequentially applies all 6 invariant repair passes:
        1. Tag collisions (stacked tags, duplicate @Image, phantom tokens)
        2. Keyframe offsets (auto-shifting character @Image indices)
        3. Zero Wardrobe Redundancy (scrubbing conflicting clothing prose)
        4. Audio ducking (instrumental prefix + canonical ducking clause)
        5. Spatial staging (screen-left / screen-right separation for multiple characters)
        6. Offering physics, 60/30/10 palette lock & 3-act temporal causality gates
        """
        all_violations: list[PreFlightViolation] = []
        current_text = prompt_text

        # Pass 1: Tag Collisions
        current_text, v1 = cls.repair_tag_collisions(current_text, characters=characters)
        all_violations.extend(v1)

        # Pass 2: Keyframe Offsets
        current_text, v2 = cls.repair_keyframe_offsets(
            current_text,
            keyframe_image_url=keyframe_image_url,
            characters=characters,
            is_seamless_loop=is_seamless_loop,
            last_frame_image_url=last_frame_image_url,
        )
        all_violations.extend(v2)

        # Pass 3: Zero Wardrobe Redundancy
        current_text, v3 = cls.repair_zero_wardrobe_redundancy(current_text, characters=characters)
        all_violations.extend(v3)

        # Pass 4: Audio Ducking
        current_text, v4 = cls.repair_audio_ducking(current_text, has_dialogue=has_dialogue)
        all_violations.extend(v4)

        # Pass 5: Spatial Staging
        current_text, v5 = cls.repair_spatial_staging(current_text, characters=characters)
        all_violations.extend(v5)

        # Pass 6: Offering Physics, 60/30/10 Palette Lock & Temporal Causality
        current_text, v6 = cls.repair_offering_physics_and_causality(
            current_text,
            offering_physics=offering_physics,
            palette_60_30_10=palette_60_30_10,
            act_number=act_number,
        )
        all_violations.extend(v6)

        invariants_applied = list(dict.fromkeys(v.rule_id for v in all_violations))
        is_valid = len(all_violations) == 0

        return PreFlightLintResult(
            is_valid=is_valid,
            repaired_prompt=current_text,
            violations=all_violations,
            invariants_applied=invariants_applied,
        )


__all__ = ["PreFlightGatekeeper"]
