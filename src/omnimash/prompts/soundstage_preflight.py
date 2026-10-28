"""Mode 5 Commercial Soundstage PreFlight Gatekeeper Pass 6 repairs.

Enforces:
- Clean-frame typography prohibition ("No text, no subtitles on screen.")
- 60/30/10 Production Design Color-Lock with hex verification (`PALETTE_60_30_10_LOCK`)
- Act-specific 3-Act Temporal Causality Gates (`TEMPORAL_CAUSALITY_GATE`)
- Thermal equilibrium physics across `ambient`, `chilled`, and `hot` offerings (`OFFERING_THERMAL_PHYSICS`)
"""

from __future__ import annotations

import re
from typing import Any

from omnimash.prompts.models import PreFlightViolation

_SKIP_GUARDRAIL_CUES: tuple[str, ...] = (
    "causality gate",
    "never add",
    "never render",
    "zero condensation",
    "without condensation",
    "no condensation",
    "zero rising vapor",
)

_AMBIENT_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\bcovered in\s+ice-cold condensation\s+and\s+frosty droplets\b",
            re.IGNORECASE,
        ),
        "with a clean dry ambient surface finish",
    ),
    (re.compile(r"\bice-cold condensation\b", re.IGNORECASE), "clean dry ambient surface finish"),
    (
        re.compile(r"\b(?:icy|cold|chilled)\s+condensation(?:\s+droplets)?\b", re.IGNORECASE),
        "clean dry ambient finish",
    ),
    (re.compile(r"\bbeads of condensation\b", re.IGNORECASE), "crisp ambient specular highlights"),
    (re.compile(r"\bcondensation droplets\b", re.IGNORECASE), "crisp ambient specular highlights"),
    (re.compile(r"\bfrosty droplets\b", re.IGNORECASE), "crisp ambient specular highlights"),
    (re.compile(r"\bfrost-covered\b", re.IGNORECASE), "dry matte ambient"),
    (re.compile(r"\bwhile steaming hot\b", re.IGNORECASE), "at dry room-temperature equilibrium"),
    (re.compile(r"\bsteaming hot\b", re.IGNORECASE), "dry room-temperature ambient"),
    (re.compile(r"\bbillowing steam\b", re.IGNORECASE), "clean still studio air"),
    (re.compile(r"\bsteam rising\b", re.IGNORECASE), "clean still ambient air"),
    (
        re.compile(r"\b(?:piping hot|rising|wisps of(?:\s+hot)?)\s+steam\b", re.IGNORECASE),
        "clean still ambient air",
    ),
    (re.compile(r"\bboiling hot\b", re.IGNORECASE), "room-temperature ambient"),
)

_CHILLED_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bwhile steaming hot\b", re.IGNORECASE), "at crisp chilled temperature"),
    (re.compile(r"\bsteaming hot\b", re.IGNORECASE), "frost-cooled chilled"),
    (re.compile(r"\bbillowing steam\b", re.IGNORECASE), "fine chilled micro-condensation sheen"),
    (re.compile(r"\bsteam rising\b", re.IGNORECASE), "crisp chilled surface sheen"),
    (
        re.compile(r"\b(?:piping hot|rising|wisps of(?:\s+hot)?)\s+steam\b", re.IGNORECASE),
        "fine chilled micro-condensation",
    ),
    (re.compile(r"\bboiling hot\b", re.IGNORECASE), "crisp chilled"),
)

_HOT_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\bcovered in\s+ice-cold condensation\s+and\s+frosty droplets\b",
            re.IGNORECASE,
        ),
        "cradling delicate warm aromatic vapor wisps",
    ),
    (re.compile(r"\bice-cold condensation\b", re.IGNORECASE), "delicate warm thermal vapor wisps"),
    (
        re.compile(r"\b(?:icy|cold|chilled)\s+condensation(?:\s+droplets)?\b", re.IGNORECASE),
        "warm freshly prepared surface sheen",
    ),
    (re.compile(r"\bbeads of condensation\b", re.IGNORECASE), "warm ceramic specular highlights"),
    (re.compile(r"\bcondensation droplets\b", re.IGNORECASE), "warm specular highlights"),
    (re.compile(r"\bfrosty droplets\b", re.IGNORECASE), "delicate warm vapor wisps"),
    (re.compile(r"\bfrost-covered\b", re.IGNORECASE), "warm freshly prepared"),
)

_THERMAL_RULES_MAP: dict[str, tuple[tuple[tuple[re.Pattern[str], str], ...], str]] = {
    "ambient": (
        _AMBIENT_REPLACEMENTS,
        "Scrubbed thermal condensation/steam contradiction from dry ambient offering prompt.",
    ),
    "chilled": (
        _CHILLED_REPLACEMENTS,
        "Scrubbed hot steam/vapor contradiction from chilled offering prompt.",
    ),
    "hot": (
        _HOT_REPLACEMENTS,
        "Scrubbed frost/cold-condensation contradiction from hot offering prompt.",
    ),
}


def append_to_scene_instructions(prompt_text: str, directive_line: str) -> str:
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
    return prompt_text[: scene_match.start(2)] + updated_body + prompt_text[scene_match.end(2) :]


def _extract_palette_directive_and_hexes(palette_60_30_10: Any) -> tuple[str, list[str]]:
    """Extracts formatted 60/30/10 directive and expected #RRGGBB hex codes from model or dict."""
    hex_60: str | None = None
    hex_30: str | None = None
    hex_10: str | None = None
    directive = ""

    if isinstance(palette_60_30_10, dict):
        directive = str(palette_60_30_10.get("production_design_directive", "") or "").strip()
        hex_60 = palette_60_30_10.get("primary_hex") or palette_60_30_10.get("neutral_hex_60")
        hex_30 = palette_60_30_10.get("secondary_hex") or palette_60_30_10.get("secondary_hex_30")
        hex_10 = palette_60_30_10.get("neutral_hex") or palette_60_30_10.get("primary_hex_10")
    else:
        directive = str(getattr(palette_60_30_10, "production_design_directive", "") or "").strip()
        hex_60 = getattr(palette_60_30_10, "primary_hex", None)
        hex_30 = getattr(palette_60_30_10, "secondary_hex", None)
        hex_10 = getattr(palette_60_30_10, "neutral_hex", None)

    expected_hexes = [
        str(h).strip().upper()
        for h in (hex_60, hex_30, hex_10)
        if h and str(h).strip().startswith("#")
    ]

    if not directive or any(h.lower() not in directive.lower() for h in expected_hexes):
        c60 = str(hex_60 or "#1F242D").strip().upper()
        c30 = str(hex_30 or "#C47D4E").strip().upper()
        c10 = str(hex_10 or "#F2EFE9").strip().upper()
        directive = (
            f"60% ({c60}) architectural & set surfaces / "
            f"30% ({c30}) wardrobe & practical props / "
            f"10% ({c10}) foundational hero surface"
        )

    return directive, expected_hexes


def repair_soundstage_physics_and_causality(
    prompt_text: str,
    offering_physics: Any | None = None,
    palette_60_30_10: Any | None = None,
    act_number: int | None = None,
) -> tuple[str, list[PreFlightViolation]]:
    """Enforces Mode 5 clean-frame no-text, 60/30/10 hex lock, 3-act causality gates, and thermal physics."""
    if not prompt_text or (
        offering_physics is None and palette_60_30_10 is None and act_number is None
    ):
        return prompt_text, []

    violations: list[PreFlightViolation] = []
    repaired = prompt_text

    # 1. Clean Frame No-Text Lock whenever any Mode 5 context argument is provided
    if "no text, no subtitles on screen" not in repaired.lower():
        clean_frame_line = "- Clean Frame Directive: No text, no subtitles on screen."
        repaired = append_to_scene_instructions(repaired, clean_frame_line)
        violations.append(
            PreFlightViolation(
                rule_id="CLEAN_FRAME_NO_TEXT",
                category="typography",
                description=(
                    "Injected clean-frame 'No text, no subtitles on screen.' directive into "
                    "Block 3 scene instructions."
                ),
                repaired=True,
                original_snippet="",
                repaired_snippet=clean_frame_line,
            )
        )

    # 2. 60/30/10 Production Design Color-Lock (verifies both 60%/30%/10% ratios and actual hex codes)
    if palette_60_30_10 is not None:
        palette_directive, expected_hexes = _extract_palette_directive_and_hexes(palette_60_30_10)
        if palette_directive:
            scene_match = re.search(
                r"### SCENE INSTRUCTIONS[^\n]*\n(.*?)(?=\n### |\Z)",
                repaired,
                flags=re.DOTALL,
            )
            scene_body = scene_match.group(1) if scene_match else ""
            scene_lower = scene_body.lower()
            has_ratio_lock = "60%" in scene_body and "30%" in scene_body and "10%" in scene_body
            has_all_hexes = all(h.lower() in scene_lower for h in expected_hexes)
            if not (has_ratio_lock and has_all_hexes):
                palette_line = (
                    f"- Production Design Palette (60/30/10 Color Lock): {palette_directive}"
                )
                repaired = append_to_scene_instructions(repaired, palette_line)
                violations.append(
                    PreFlightViolation(
                        rule_id="PALETTE_60_30_10_LOCK",
                        category="production_design",
                        description=(
                            "Injected 60/30/10 production design hex color-lock directive into "
                            "Block 3 scene instructions."
                        ),
                        repaired=True,
                        original_snippet="",
                        repaired_snippet=palette_line,
                    )
                )

    # 3. Act-Specific Temporal Causality Gate & Thermal Physics (`ambient`, `chilled`, `hot`)
    if offering_physics is not None:
        laws = getattr(offering_physics, "act_causality_laws", None)
        if laws is None and isinstance(offering_physics, dict):
            laws = offering_physics.get("act_causality_laws")

        if act_number is not None and isinstance(laws, dict):
            act_law = str(laws.get(act_number) or laws.get(str(act_number)) or "").strip()
            gate_header = f"Causality Gate (Act {act_number}):"
            if act_law and act_law not in repaired and gate_header not in repaired:
                causality_line = f"- {gate_header} {act_law}"
                repaired = append_to_scene_instructions(repaired, causality_line)
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

        thermal_key = str(thermal_state or "").strip().lower()
        if thermal_key in _THERMAL_RULES_MAP:
            replacements, violation_desc = _THERMAL_RULES_MAP[thermal_key]
            updated_lines: list[str] = []
            for line in repaired.splitlines():
                lower_line = line.lower()
                if any(cue in lower_line for cue in _SKIP_GUARDRAIL_CUES):
                    updated_lines.append(line)
                    continue

                working_line = line
                for pattern, replacement in replacements:
                    match = pattern.search(working_line)
                    if match:
                        orig_snippet = match.group(0)
                        working_line = pattern.sub(replacement, working_line)
                        violations.append(
                            PreFlightViolation(
                                rule_id="OFFERING_THERMAL_PHYSICS",
                                category="physics",
                                description=violation_desc,
                                repaired=True,
                                original_snippet=orig_snippet,
                                repaired_snippet=replacement,
                            )
                        )
                updated_lines.append(working_line)
            repaired = "\n".join(updated_lines)

    return repaired, violations


__all__ = ["append_to_scene_instructions", "repair_soundstage_physics_and_causality"]
