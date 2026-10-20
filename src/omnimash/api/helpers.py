import os
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote_plus
from omnimash.agent.orchestrator import OmniMashAgent
from omnimash.api.models import CharacterRoleModel, GenerateShotRequest
from omnimash.prompts.compiler import CharacterRole, sanitize_real_names

_RE_ACTION = re.compile(r"-\s*Action\s*/\s*Subject:\s*(.*)", re.IGNORECASE)
_RE_DIALOGUE = re.compile(
    r"-\s*(?:Dialogue\s*/\s*Text\s*Overlay|Dialogue|Voiceover):\s*(.*)",
    re.IGNORECASE,
)
_RE_AUDIO = re.compile(r"-\s*Audio\s*Soundscape:\s*(.*)", re.IGNORECASE)
_RE_LOCATION = re.compile(r"-\s*Location:\s*(.*)", re.IGNORECASE)
_RE_STYLE = re.compile(r"-\s*Style\s*&\s*Lighting:\s*(.*)", re.IGNORECASE)
_RE_FRAMING = re.compile(r"-\s*Framing\s*&\s*Motion:\s*(.*)", re.IGNORECASE)


def clean_text(val: str | None, sanitize: bool = True) -> str:
    if not val:
        return ""
    return sanitize_real_names(val) if sanitize else val


def normalize_character_roles(
    characters: Sequence[CharacterRoleModel | dict[str, Any] | CharacterRole] | None,
    sanitize: bool = False,
    default_role_prefix: str = "",
) -> list[CharacterRole]:
    """Canonical normalization of mixed character inputs into CharacterRole objects."""
    if not characters:
        return []
    char_objs: list[CharacterRole] = []
    for i, c in enumerate(characters):
        fallback_role_id = f"{default_role_prefix}{i}" if default_role_prefix else ""
        if isinstance(c, CharacterRole):
            char_objs.append(c)
        elif isinstance(c, dict):
            voice_val = clean_text(c.get("voice_style") or c.get("voice_profile") or "", sanitize)
            char_objs.append(
                CharacterRole(
                    role_id=c.get("role_id", fallback_role_id),
                    name=clean_text(c.get("name", ""), sanitize),
                    description=clean_text(c.get("description", ""), sanitize),
                    reference_url=c.get("reference_url"),
                    aesthetic_tags=[clean_text(t, sanitize) for t in c.get("aesthetic_tags", [])],
                    voice_style=voice_val,
                    voice_profile=clean_text(
                        c.get("voice_profile") or c.get("voice_style") or "", sanitize
                    ),
                    wardrobe=clean_text(c.get("wardrobe", ""), sanitize),
                    image_role=c.get("image_role", "Character Reference"),
                    is_offscreen_narrator=c.get("is_offscreen_narrator", False),
                )
            )
        elif hasattr(c, "model_dump"):
            cd = c.model_dump()
            voice_val = clean_text(cd.get("voice_style") or cd.get("voice_profile") or "", sanitize)
            char_objs.append(
                CharacterRole(
                    role_id=cd.get("role_id", fallback_role_id),
                    name=clean_text(cd.get("name", ""), sanitize),
                    description=clean_text(cd.get("description", ""), sanitize),
                    reference_url=cd.get("reference_url"),
                    aesthetic_tags=[clean_text(t, sanitize) for t in cd.get("aesthetic_tags", [])],
                    voice_style=voice_val,
                    voice_profile=clean_text(
                        cd.get("voice_profile") or cd.get("voice_style") or "", sanitize
                    ),
                    wardrobe=clean_text(cd.get("wardrobe", ""), sanitize),
                    image_role=cd.get("image_role", "Character Reference"),
                    is_offscreen_narrator=cd.get("is_offscreen_narrator", False),
                )
            )
    return char_objs


def extract_reference_urls(
    characters: Sequence[CharacterRoleModel | dict[str, Any] | CharacterRole] | None,
) -> list[str]:
    """Extracts unique non-empty reference URLs from a list of character definitions."""
    if not characters:
        return []
    ref_urls: list[str] = []
    for c in characters:
        ref = c.get("reference_url") if isinstance(c, dict) else getattr(c, "reference_url", None)
        if ref and ref not in ref_urls:
            ref_urls.append(ref)
    return ref_urls


def parse_shot_directive_if_needed(
    req: GenerateShotRequest,
) -> tuple[str, str, str, str, str, str]:
    action = req.action or ""
    dialogue = req.dialogue or ""
    audio = req.audio or req.audio_stem or ""
    location = req.location or ""
    style_lighting = req.style_lighting or ""
    framing_motion = req.framing_motion or ""

    if req.shot_directive and req.shot_directive.strip():
        sd = req.shot_directive.strip()
        if not action:
            match_act = _RE_ACTION.search(sd)
            if match_act and match_act.group(1).strip():
                action = match_act.group(1).strip()
            elif not sd.startswith("[SHOT DIRECTIVE") and not sd.startswith("- "):
                action = sd
        if not dialogue:
            match_diag = _RE_DIALOGUE.search(sd)
            if match_diag and match_diag.group(1).strip():
                dialogue = match_diag.group(1).strip()
                if (dialogue.startswith('"') and dialogue.endswith('"')) or (
                    dialogue.startswith("'") and dialogue.endswith("'")
                ):
                    dialogue = dialogue[1:-1].strip()
        if not audio:
            match_aud = _RE_AUDIO.search(sd)
            if match_aud and match_aud.group(1).strip():
                audio = match_aud.group(1).strip()
        if not location:
            match_loc = _RE_LOCATION.search(sd)
            if match_loc and match_loc.group(1).strip():
                location = match_loc.group(1).strip()
        if not style_lighting:
            match_style = _RE_STYLE.search(sd)
            if match_style and match_style.group(1).strip():
                style_lighting = match_style.group(1).strip()
        if not framing_motion:
            match_frame = _RE_FRAMING.search(sd)
            if match_frame and match_frame.group(1).strip():
                framing_motion = match_frame.group(1).strip()

    if not action:
        action = f"Shot {req.shot_index} action"

    return action, dialogue, audio, location, style_lighting, framing_motion


def stitch_and_upload_master(
    agent: OmniMashAgent,
    shot_clips: list[str],
    title_cards: list[dict[str, Any]] | None = None,
    narrator_audio_paths: list[str] | None = None,
    background_music_path: str | None = None,
    session_id: str | None = None,
    aspect_ratio: str = "16:9",
) -> tuple[str, str]:
    """Stitches storyboard master video, uploads to GCS, and cleans up temporary /tmp/ files."""
    kwargs: dict[str, Any] = {
        "shot_clips": shot_clips,
        "title_cards": title_cards,
        "session_id": session_id,
        "aspect_ratio": aspect_ratio,
    }
    if narrator_audio_paths is not None:
        kwargs["narrator_audio_paths"] = narrator_audio_paths
    if background_music_path is not None:
        kwargs["background_music_path"] = background_music_path

    master_path = agent.stitcher.stitch_storyboard_master(**kwargs)
    local_master_path = master_path
    try:
        if os.path.exists(master_path):
            sess_name = session_id or "default"
            gcs_dest = f"sessions/{sess_name}/masters/{os.path.basename(master_path)}"
            gcs_uri = agent.storage.upload_file(master_path, gcs_dest)
            if gcs_uri:
                master_path = gcs_uri
                master_url = f"/api/media-proxy?uri={quote_plus(gcs_uri)}"
            else:
                master_url = f"/static/{os.path.basename(master_path)}"
        elif master_path.startswith("gs://"):
            master_url = f"/api/media-proxy?uri={quote_plus(master_path)}"
        else:
            master_url = master_path
    finally:
        if local_master_path.startswith("/tmp/") and os.path.exists(local_master_path):
            try:
                os.remove(local_master_path)
            except OSError:
                pass

    return master_path, master_url
