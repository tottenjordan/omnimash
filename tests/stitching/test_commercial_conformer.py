"""Behavioral unit and FFmpeg integration tests for Mode 5 CommercialConformer."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from unittest.mock import patch
import zipfile

import pytest

from omnimash.prompts.soundstage_discovery import Palette603010, TerritoryAtmosphereSpec
from omnimash.stitching import (
    CANONICAL_SUBSHOT_IDS,
    CommercialConformer,
    ConformedDeliverables,
    SubShotTrimSpec,
    build_default_subshot_specs,
    normalize_subshot_specs,
)

HAS_FFMPEG = shutil.which("ffmpeg") is not None
HAS_FFPROBE = shutil.which("ffprobe") is not None


def _probe_streams(mp4_path: str) -> dict:
    """Inspects MP4 streams and format metadata via ffprobe when available."""
    assert os.path.isfile(mp4_path)
    assert os.path.getsize(mp4_path) > 512
    with open(mp4_path, "rb") as f:
        header = f.read(32)
    assert b"ftyp" in header

    if not HAS_FFPROBE:
        return {}

    res = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,codec_type,width,height,sample_rate,channels",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            mp4_path,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30.0,
    )
    return json.loads(res.stdout)


def _create_synthetic_mp4(path: str, color: str = "navy", with_audio: bool = True) -> str:
    """Generates a real 1.0-second 16:9 synthetic MP4 via lavfi for FFmpeg integration testing."""
    if with_audio:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=640x360:d=1.0",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=22050:duration=1.0",
            "-r",
            "24",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            path,
        ]
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=640x360:d=1.0",
            "-r",
            "24",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            path,
        ]
    subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30.0)
    return path


# ---------------------------------------------------------------------------
# 1. SubShotTrimSpec & Normalization
# ---------------------------------------------------------------------------


def test_build_default_subshot_specs_returns_nine_canonical_beats_summing_to_30s() -> None:
    specs = build_default_subshot_specs()
    assert tuple(s.shot_id for s in specs) == CANONICAL_SUBSHOT_IDS
    assert len(specs) == 9

    for act_idx in (0, 1, 2):
        act_specs = [s for s in specs if s.act_index == act_idx]
        assert [s.default_start_sec for s in act_specs] == [0.0, 3.3, 6.7]
        assert [s.default_duration_sec for s in act_specs] == [3.3, 3.4, 3.3]
        assert round(sum(s.effective_window(10.0)[1] for s in act_specs), 3) == 10.0

    total_30s = sum(s.effective_window(10.0)[1] for s in specs)
    assert round(total_30s, 3) == 30.0


def test_subshot_trim_spec_rejects_unknown_shot_id_and_mismatched_act_index() -> None:
    with pytest.raises(ValueError, match="shot_id"):
        SubShotTrimSpec(
            shot_id="4.1",
            act_index=0,
            default_start_sec=0.0,
            default_duration_sec=3.3,
        )

    with pytest.raises(ValueError, match="act_index"):
        SubShotTrimSpec(
            shot_id="2.1",
            act_index=0,
            default_start_sec=0.0,
            default_duration_sec=3.3,
        )

    with pytest.raises(ValueError, match="act_index"):
        SubShotTrimSpec(
            shot_id="2.1",
            act_index=True,  # type: ignore[arg-type]
            default_start_sec=0.0,
            default_duration_sec=3.3,
        )


def test_effective_window_clamps_minimum_duration_and_act_bounds() -> None:
    # Extreme positive trim_in pushing past end of 10s act clip -> clamps to (9.5, 0.5)
    spec_late = SubShotTrimSpec(shot_id="1.3", trim_in_sec=20.0)
    assert spec_late.effective_window(10.0) == (9.5, 0.5)

    # Extreme trim_out collapsing window below 0.5s -> clamps duration to 0.5s
    spec_collapsed = SubShotTrimSpec(shot_id="2.2", trim_in_sec=1.0, trim_out_sec=15.0)
    start, dur = spec_collapsed.effective_window(10.0)
    assert start == 4.3
    assert dur == 0.5

    # Negative trim_in before 0.0s and negative trim_out extending past 10.0s -> clamps to [0.0, 10.0]
    spec_overextended = SubShotTrimSpec(shot_id="1.1", trim_in_sec=-4.0, trim_out_sec=-25.0)
    assert spec_overextended.effective_window(10.0) == (0.0, 10.0)

    # Standard NLE +/- 0.25s step trim
    spec_step = SubShotTrimSpec(shot_id="2.1", trim_in_sec=0.25, trim_out_sec=0.25)
    assert spec_step.effective_window(10.0) == (0.25, 2.8)


def test_normalize_subshot_specs_merges_partial_patches_in_canonical_order() -> None:
    patched = normalize_subshot_specs(
        [
            {"shot_id": "3.2", "bypassed": True},
            {"shot_id": "1.2", "trim_in_sec": 0.25, "trim_out_sec": -0.25},
            SubShotTrimSpec(shot_id="2.3", trim_out_sec=0.5),
        ]
    )
    assert tuple(s.shot_id for s in patched) == CANONICAL_SUBSHOT_IDS

    by_id = {s.shot_id: s for s in patched}
    assert by_id["1.2"].trim_in_sec == 0.25
    assert by_id["1.2"].trim_out_sec == -0.25
    assert by_id["1.2"].default_start_sec == 3.3
    assert by_id["2.3"].trim_out_sec == 0.5
    assert by_id["3.2"].bypassed is True
    assert by_id["1.1"].bypassed is False

    with pytest.raises(ValueError, match="shot_id"):
        normalize_subshot_specs([{"shot_id": "9.9", "bypassed": True}])


# ---------------------------------------------------------------------------
# 2. Brand End-Card Rendering (Mock, Contrast Math, and Real Pillow + FFmpeg)
# ---------------------------------------------------------------------------


def test_render_brand_end_card_clip_mock_mode(tmp_path) -> None:
    conformer = CommercialConformer(mock_mode=True)
    with patch("subprocess.run") as mock_subproc:
        clip_path = conformer.render_brand_end_card_clip(
            display_subject="Maison Aura",
            display_tagline="Quiet Architecture in Motion",
            output_dir=str(tmp_path),
        )
    assert os.path.isfile(clip_path)
    assert clip_path.endswith(".mp4")
    mock_subproc.assert_not_called()


def test_render_brand_end_card_contrast_selection_dark_and_light_backgrounds() -> None:
    from omnimash.stitching.commercial_conformer import (
        _contrast_ratio,
        _parse_hex_rgb,
        _select_end_card_palette,
    )

    dark_palette = _select_end_card_palette(
        primary_hex="#E11D48",
        secondary_hex="#D4C5B0",
        neutral_hex="#111318",
    )
    # Dark obsidian background (#111318) selects ivory primary text (#F8F6F0)
    assert dark_palette["bg_rgb"] == (17, 19, 24)
    assert dark_palette["subject_rgb"] == (248, 246, 240)
    assert _contrast_ratio(dark_palette["subject_rgb"], dark_palette["bg_rgb"]) >= 12.0

    light_palette = _select_end_card_palette(
        primary_hex="#E11D48",
        secondary_hex="#D4C5B0",
        neutral_hex="#F5F5F0",
    )
    # Light alabaster background (#F5F5F0) selects obsidian primary text (#111318)
    assert light_palette["bg_rgb"] == (245, 245, 240)
    assert light_palette["subject_rgb"] == (17, 19, 24)
    assert _contrast_ratio(light_palette["subject_rgb"], light_palette["bg_rgb"]) >= 12.0
    assert _contrast_ratio(light_palette["tagline_rgb"], light_palette["bg_rgb"]) >= 4.5

    # Malformed hex falls back cleanly without raising
    assert _parse_hex_rgb("not-a-hex", (17, 19, 24)) == (17, 19, 24)


@pytest.mark.skipif(not HAS_FFMPEG, reason="FFmpeg binary not installed")
def test_render_brand_end_card_clip_real_ffmpeg_16x9_and_9x16_with_rgba_emblem(tmp_path) -> None:
    from PIL import Image, ImageDraw

    # Create a dark RGBA emblem PNG to exercise alpha compositing + contrast backing plate
    emblem_file = tmp_path / "brand_emblem.png"
    emblem = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    draw = ImageDraw.Draw(emblem)
    draw.ellipse((20, 20, 140, 140), fill=(20, 22, 28, 235))
    emblem.save(str(emblem_file))

    out_dir = tmp_path / "end_cards"
    conformer = CommercialConformer(mock_mode=False)

    clip_16x9 = conformer.render_brand_end_card_clip(
        display_subject="Maison Aura Atelier",
        display_tagline=(
            "Crafted for quiet metropolitan thresholds where precision stone meets warm evening light"
        ),
        primary_hex="#E11D48",
        secondary_hex="#D4C5B0",
        neutral_hex="#111318",
        emblem_path=str(emblem_file),
        duration_seconds=0.5,
        aspect_ratio="16:9",
        output_dir=str(out_dir),
    )
    info_16x9 = _probe_streams(clip_16x9)
    if info_16x9:
        v_stream = next(s for s in info_16x9["streams"] if s["codec_type"] == "video")
        a_stream = next(s for s in info_16x9["streams"] if s["codec_type"] == "audio")
        assert (v_stream["width"], v_stream["height"]) == (1280, 720)
        assert a_stream["codec_name"] == "aac"
        assert int(a_stream["channels"]) == 2

    clip_9x16 = conformer.render_brand_end_card_clip(
        display_subject="Atelier Solis",
        display_tagline="Precision daylight form and tactile poise.",
        primary_hex="#0F766E",
        secondary_hex="#475569",
        neutral_hex="#F5F5F0",
        emblem_path=str(emblem_file),
        duration_seconds=0.5,
        aspect_ratio="9:16",
        output_dir=str(out_dir),
    )
    info_9x16 = _probe_streams(clip_9x16)
    if info_9x16:
        v_stream = next(s for s in info_9x16["streams"] if s["codec_type"] == "video")
        assert (v_stream["width"], v_stream["height"]) == (720, 1280)

    # Temporary PNGs must be cleaned up inside output_dir
    leftover_pngs = [p.name for p in out_dir.iterdir() if p.suffix.lower() == ".png"]
    assert leftover_pngs == []


# ---------------------------------------------------------------------------
# 3. conform_all_formats (Mock Mode, -18dB Ducking, Real FFmpeg Audio & Silent)
# ---------------------------------------------------------------------------


def test_conform_all_formats_mock_mode_produces_all_deliverables_and_gcs_uris(tmp_path) -> None:
    conformer = CommercialConformer(mock_mode=True, bucket_name="test-soundstage-bucket")
    act_clips = [
        "gs://test-soundstage-bucket/sessions/s1/act1.mp4",
        "gs://test-soundstage-bucket/sessions/s1/act2.mp4",
        "gs://test-soundstage-bucket/sessions/s1/act3.mp4",
    ]

    with patch("subprocess.run") as mock_subproc:
        res = conformer.conform_all_formats(
            act_clips=act_clips,
            display_subject="Velour Espresso",
            display_tagline="Crema in Stillness",
            end_card_duration_sec=2.0,
            output_dir=str(tmp_path),
            session_id="soundstage_sess_1",
            project_id="proj_alpha",
        )

    mock_subproc.assert_not_called()
    assert isinstance(res, ConformedDeliverables)
    assert res.active_subshot_count == 9
    assert res.active_subshot_ids == list(CANONICAL_SUBSHOT_IDS)
    assert res.total_duration_sec == 32.0

    expected_keys = {
        "master_30s_16x9",
        "cutdown_15s_9x16",
        "bumper_6s_9x16",
        "end_card_16x9",
        "end_card_9x16",
    }
    assert set(res.local_paths.keys()) == expected_keys
    assert set(res.gcs_uris.keys()) == expected_keys

    for key in expected_keys:
        assert os.path.isfile(res.local_paths[key])
        assert res.gcs_uris[key].startswith(
            "gs://test-soundstage-bucket/projects/proj_alpha/sessions/soundstage_sess_1/final_masters/"
        )

    assert res.master_30s_16x9_url.startswith(
        "https://storage.googleapis.com/test-soundstage-bucket/"
    )
    assert res.cutdown_15s_9x16_url.startswith(
        "https://storage.googleapis.com/test-soundstage-bucket/"
    )
    assert res.bumper_6s_9x16_url.startswith(
        "https://storage.googleapis.com/test-soundstage-bucket/"
    )
    assert res.end_card_clip_url.startswith(
        "https://storage.googleapis.com/test-soundstage-bucket/"
    )
    assert res.end_card_9x16_url.startswith(
        "https://storage.googleapis.com/test-soundstage-bucket/"
    )


def test_conform_all_formats_applies_18db_sidechain_ducking_when_music_and_vo_provided(
    tmp_path,
) -> None:
    conformer = CommercialConformer(mock_mode=True)
    bgm = tmp_path / "score.mp3"
    bgm.write_bytes(b"mock bgm")
    vo = tmp_path / "narrator.mp3"
    vo.write_bytes(b"mock vo")

    with patch(
        "omnimash.stitching.commercial_conformer.apply_dialogue_audio_ducking",
        return_value=str(tmp_path / "ducked.aac"),
    ) as mock_duck:
        conformer.conform_all_formats(
            act_clips=["/tmp/act1.mp4", "/tmp/act2.mp4", "/tmp/act3.mp4"],
            display_subject="Aether Watch",
            background_music_path=str(bgm),
            narrator_audio_path=str(vo),
            output_dir=str(tmp_path),
        )

    mock_duck.assert_called_once()
    assert mock_duck.call_args.kwargs["ducking_db"] == -18.0


@pytest.mark.skipif(not HAS_FFMPEG, reason="FFmpeg binary not installed")
def test_conform_all_formats_real_ffmpeg_with_audio_clips(tmp_path) -> None:
    src_dir = tmp_path / "sources_audio"
    src_dir.mkdir()
    out_dir = tmp_path / "out_audio"
    act_clips = [
        _create_synthetic_mp4(str(src_dir / "act1.mp4"), color="navy", with_audio=True),
        _create_synthetic_mp4(str(src_dir / "act2.mp4"), color="darkred", with_audio=True),
        _create_synthetic_mp4(str(src_dir / "act3.mp4"), color="darkslategray", with_audio=True),
    ]

    conformer = CommercialConformer(mock_mode=False, bucket_name="test-bucket")
    with patch.object(
        conformer.storage,
        "upload_file",
        side_effect=lambda local_path, destination_blob_name=None, **kw: (
            f"https://storage.googleapis.com/test-bucket/{destination_blob_name}"
        ),
    ):
        deliverables = conformer.conform_all_formats(
            act_clips=act_clips,
            display_subject="Chronos Studio",
            display_tagline="Precision in Every Beat",
            end_card_duration_sec=0.5,
            output_dir=str(out_dir),
            session_id="live_audio_sess",
        )

    master_info = _probe_streams(deliverables.local_paths["master_30s_16x9"])
    cutdown_info = _probe_streams(deliverables.local_paths["cutdown_15s_9x16"])
    bumper_info = _probe_streams(deliverables.local_paths["bumper_6s_9x16"])

    if master_info:
        mv = next(s for s in master_info["streams"] if s["codec_type"] == "video")
        ma = next(s for s in master_info["streams"] if s["codec_type"] == "audio")
        assert (mv["width"], mv["height"]) == (1280, 720)
        assert ma["codec_name"] == "aac"
        assert int(ma["channels"]) == 2

    if cutdown_info and bumper_info:
        cv = next(s for s in cutdown_info["streams"] if s["codec_type"] == "video")
        bv = next(s for s in bumper_info["streams"] if s["codec_type"] == "video")
        assert (cv["width"], cv["height"]) == (720, 1280)
        assert (bv["width"], bv["height"]) == (720, 1280)
        assert float(bumper_info["format"]["duration"]) < float(cutdown_info["format"]["duration"])


@pytest.mark.skipif(not HAS_FFMPEG, reason="FFmpeg binary not installed")
def test_conform_all_formats_real_ffmpeg_with_silent_clips_without_audio_stream(tmp_path) -> None:
    """Proves silent video clips (-an) concatenate cleanly against stereo end-cards without stream mismatch."""
    src_dir = tmp_path / "sources_silent"
    src_dir.mkdir()
    out_dir = tmp_path / "out_silent"
    act_clips = [
        _create_synthetic_mp4(
            str(src_dir / "act1_silent.mp4"), color="midnightblue", with_audio=False
        ),
        _create_synthetic_mp4(str(src_dir / "act2_silent.mp4"), color="maroon", with_audio=False),
        _create_synthetic_mp4(str(src_dir / "act3_silent.mp4"), color="teal", with_audio=False),
    ]

    conformer = CommercialConformer(mock_mode=False, bucket_name="test-bucket")
    with patch.object(
        conformer.storage,
        "upload_file",
        side_effect=lambda local_path, destination_blob_name=None, **kw: (
            f"https://storage.googleapis.com/test-bucket/{destination_blob_name}"
        ),
    ):
        deliverables = conformer.conform_all_formats(
            act_clips=act_clips,
            display_subject="Silent Plinth",
            display_tagline="Pure Form",
            end_card_duration_sec=0.5,
            output_dir=str(out_dir),
            session_id="live_silent_sess",
        )

    for key, expected_dims in (
        ("master_30s_16x9", (1280, 720)),
        ("cutdown_15s_9x16", (720, 1280)),
        ("bumper_6s_9x16", (720, 1280)),
    ):
        info = _probe_streams(deliverables.local_paths[key])
        if info:
            v_stream = next(s for s in info["streams"] if s["codec_type"] == "video")
            a_stream = next(s for s in info["streams"] if s["codec_type"] == "audio")
            assert (v_stream["width"], v_stream["height"]) == expected_dims
            assert a_stream["codec_name"] == "aac"
            assert int(a_stream["channels"]) == 2


# ---------------------------------------------------------------------------
# 4. reconform_timeline NLE Operations & Guardrail Validations
# ---------------------------------------------------------------------------


def test_reconform_timeline_trims_and_bypasses_update_duration_and_counts_accurately(
    tmp_path,
) -> None:
    conformer = CommercialConformer(mock_mode=True)
    act_clips = ["/tmp/act1.mp4", "/tmp/act2.mp4", "/tmp/act3.mp4"]

    # Default is 30.0s across 9 shots + 2.0s end card = 32.0s.
    # Bypass 1.3 (-3.3s) and 3.2 (-3.4s) -> 23.3s across 7 shots.
    # Trim 1.1 in by +0.25s (-0.25s -> 3.05s) and extend 2.1 out by -0.5s (+0.5s -> 3.8s) -> 23.55s + 2.0s = 25.55s.
    res = conformer.reconform_timeline(
        act_clips=act_clips,
        subshot_specs=[
            {"shot_id": "1.1", "trim_in_sec": 0.25},
            {"shot_id": "1.3", "bypassed": True},
            {"shot_id": "2.1", "trim_out_sec": -0.5},
            {"shot_id": "3.2", "bypassed": True},
        ],
        display_subject="Maison Aura",
        display_tagline="Re-Timed Cut",
        end_card_duration_sec=2.0,
        output_dir=str(tmp_path),
        session_id="nle_sess_1",
    )

    assert res.active_subshot_count == 7
    assert res.active_subshot_ids == ["1.1", "1.2", "2.1", "2.2", "2.3", "3.1", "3.3"]
    assert res.total_duration_sec == 25.55


def test_reconform_timeline_fallback_when_all_preferred_bumper_and_cutdown_beats_bypassed(
    tmp_path,
) -> None:
    conformer = CommercialConformer(mock_mode=True)
    act_clips = ["/tmp/act1.mp4", "/tmp/act2.mp4", "/tmp/act3.mp4"]

    # Bypass all 5 preferred 15s cutdown beats (1.1, 2.1, 2.2, 2.3, 3.2) which includes both 6s bumper beats (2.2, 2.3)
    bypasses = [{"shot_id": sid, "bypassed": True} for sid in ("1.1", "2.1", "2.2", "2.3", "3.2")]
    res = conformer.reconform_timeline(
        act_clips=act_clips,
        subshot_specs=bypasses,
        display_subject="Fallback Brand",
        output_dir=str(tmp_path),
    )

    assert res.active_subshot_ids == ["1.2", "1.3", "3.1", "3.3"]
    assert res.active_subshot_count == 4
    assert os.path.isfile(res.local_paths["cutdown_15s_9x16"])
    assert os.path.isfile(res.local_paths["bumper_6s_9x16"])


def test_conform_rejects_empty_act_clips_all_bypassed_and_unsafe_identifiers(tmp_path) -> None:
    conformer = CommercialConformer(mock_mode=True)

    with pytest.raises(ValueError, match="act clip"):
        conformer.conform_all_formats(
            act_clips=[],
            display_subject="Empty Brand",
            output_dir=str(tmp_path),
        )

    all_bypassed = [{"shot_id": sid, "bypassed": True} for sid in CANONICAL_SUBSHOT_IDS]
    with pytest.raises(ValueError, match="active"):
        conformer.reconform_timeline(
            act_clips=["/tmp/act1.mp4", "/tmp/act2.mp4", "/tmp/act3.mp4"],
            subshot_specs=all_bypassed,
            display_subject="Bypassed Brand",
            output_dir=str(tmp_path),
        )

    with pytest.raises(ValueError, match="Invalid session_id"):
        conformer.conform_all_formats(
            act_clips=["/tmp/act1.mp4"],
            display_subject="Traversal Test",
            output_dir=str(tmp_path),
            session_id="../evil",
        )

    with pytest.raises(ValueError, match="Invalid project_id"):
        conformer.conform_all_formats(
            act_clips=["/tmp/act1.mp4"],
            display_subject="Traversal Test",
            output_dir=str(tmp_path),
            session_id="safe_session",
            project_id="../../evil_proj",
        )


# ---------------------------------------------------------------------------
# 5. build_campaign_package_zip
# ---------------------------------------------------------------------------


def test_build_campaign_package_zip_bundles_deliverables_storyboards_sanitized_refs_and_manifest(
    tmp_path,
) -> None:
    conformer = CommercialConformer(mock_mode=True, bucket_name="campaign-pkg-bucket")
    deliverables = conformer.conform_all_formats(
        act_clips=["/tmp/act1.mp4", "/tmp/act2.mp4", "/tmp/act3.mp4"],
        display_subject="Maison Aura",
        display_tagline="Quiet Architecture",
        output_dir=str(tmp_path),
        session_id="pkg_sess",
        project_id="pkg_proj",
    )

    sb_1 = tmp_path / "tile_1_1.png"
    sb_1.write_bytes(b"\x89PNG\r\n\x1a\nstoryboard_1_1")
    sb_2 = tmp_path / "tile_2_2.png"
    sb_2.write_bytes(b"\x89PNG\r\n\x1a\nstoryboard_2_2")

    ref_cast = tmp_path / "cast_sheet.png"
    ref_cast.write_bytes(b"\x89PNG\r\n\x1a\ncast_sheet")
    ref_prop = tmp_path / "packshot.png"
    ref_prop.write_bytes(b"\x89PNG\r\n\x1a\npackshot")

    palette = Palette603010(
        primary_hex="#E11D48",
        primary_name="Crimson Lacquer",
        secondary_hex="#D4C5B0",
        secondary_name="Warm Travertine",
        neutral_hex="#111318",
        neutral_name="Obsidian Slate",
    )
    territory = TerritoryAtmosphereSpec(
        place_name="Milan Brera District",
        temperature_c=18,
        condition="Crisp Twilight",
        lighting_directive="Warm tungsten architectural grazing light",
        cultural_pulse="Quiet evening aperitivo",
    )

    zip_path, gcs_uri = conformer.build_campaign_package_zip(
        deliverables=deliverables,
        display_subject="Maison Aura",
        display_offering="Signature Espresso Vessel",
        display_tagline="Quiet Architecture",
        palette_60_30_10=palette,
        territory=territory,
        executive_brief={"title": "Maison Aura Brera Spot", "objective": "Craft elevation"},
        timed_voiceover="[0:00] Stillness first.\n[0:10] One touch.\n[0:20] Quiet pulse.",
        storyboard_frames={"1.1": str(sb_1), "2.2": str(sb_2)},
        reference_kit={
            "lead_cast_sheet": str(ref_cast),
            "../../etc/evil_packshot": str(ref_prop),
        },
        social_copy={"headline": "Quiet Architecture by Maison Aura"},
        output_dir=str(tmp_path),
        session_id="pkg_sess",
        project_id="pkg_proj",
    )

    assert os.path.isfile(zip_path)
    assert os.path.basename(zip_path).startswith("campaign_package_maison_aura_")
    assert zip_path.endswith(".zip")
    assert gcs_uri.startswith(
        "gs://campaign-pkg-bucket/projects/pkg_proj/sessions/pkg_sess/final_masters/campaign_package_maison_aura_"
    )

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        assert "deliverables/30s_16x9_master.mp4" in names
        assert "deliverables/15s_9x16_cutdown.mp4" in names
        assert "deliverables/6s_9x16_bumper.mp4" in names
        assert "storyboards/shot_1.1.png" in names
        assert "storyboards/shot_2.2.png" in names
        assert "reference_kit/lead_cast_sheet.png" in names
        assert "campaign_manifest.json" in names

        # Verify Zip-Slip sanitization kept traversal key strictly confined inside reference_kit/
        ref_entries = [n for n in names if n.startswith("reference_kit/")]
        assert len(ref_entries) == 2
        for entry in names:
            assert ".." not in entry
            assert not entry.startswith("/")

        manifest = json.loads(zf.read("campaign_manifest.json").decode("utf-8"))
        assert manifest["display_subject"] == "Maison Aura"
        assert manifest["display_offering"] == "Signature Espresso Vessel"
        assert manifest["display_tagline"] == "Quiet Architecture"
        assert manifest["palette_60_30_10"]["primary_hex"] == "#E11D48"
        assert manifest["territory"]["place_name"] == "Milan Brera District"
        assert manifest["executive_brief"]["title"] == "Maison Aura Brera Spot"
        assert "[0:10] One touch." in manifest["timed_voiceover"]
        assert len(manifest["subshot_specs"]) == 9
        assert manifest["deliverables"]["active_subshot_count"] == 9
        assert manifest["social_copy"]["headline"] == "Quiet Architecture by Maison Aura"


def test_bumper_caps_each_subshot_to_2_4s_and_zip_integrates_with_soundstage_plan(tmp_path) -> None:
    from omnimash.prompts.commercial_planner import SoundstageThreeActPlanner

    planner = SoundstageThreeActPlanner(mock_mode=True)
    plan = planner.build_plan(
        subject="Atelier Vesper",
        offering="Obsidian Pour-Over Kettle",
        territory="Tokyo",
        tagline="Precision Pour at Dusk",
    )

    conformer_live = CommercialConformer(mock_mode=False, bucket_name="vesper-bucket")
    act_files = []
    for idx in range(3):
        p = tmp_path / f"act_{idx}.mp4"
        p.write_bytes(b"placeholder")
        act_files.append(str(p))

    extracted_calls: list[tuple[str, float, float]] = []

    def _fake_extract(
        source_clip: str,
        start_sec: float,
        duration_sec: float,
        aspect_ratio: str,
        has_audio: bool,
        output_path: str,
    ) -> str:
        extracted_calls.append((aspect_ratio, start_sec, duration_sec))
        with open(output_path, "wb") as f:
            f.write(b"fake segment")
        return output_path

    def _fake_concat(
        segment_paths: list[str],
        output_path: str,
        temp_dir: str,
        master_audio_path: str | None = None,
    ) -> str:
        with open(output_path, "wb") as f:
            f.write(b"fake Deliverable MP4")
        return output_path

    def _fake_end_card(*args, **kwargs) -> str:
        out_p = os.path.join(
            kwargs.get("output_dir", str(tmp_path)),
            f"fake_ec_{kwargs.get('aspect_ratio', '16:9').replace(':', 'x')}_{kwargs.get('duration_seconds')}.mp4",
        )
        with open(out_p, "wb") as f:
            f.write(b"fake EndCard MP4")
        return out_p

    with (
        patch.object(conformer_live, "_probe_clip_info", return_value=(True, 10.0)),
        patch.object(conformer_live, "_extract_subshot_segment", side_effect=_fake_extract),
        patch.object(conformer_live, "_concatenate_normalized_segments", side_effect=_fake_concat),
        patch.object(conformer_live, "render_brand_end_card_clip", side_effect=_fake_end_card),
        patch.object(
            conformer_live.storage,
            "upload_file",
            side_effect=lambda local_path, destination_blob_name=None, **kw: (
                f"https://storage.googleapis.com/vesper-bucket/{destination_blob_name}"
            ),
        ),
    ):
        deliverables = conformer_live.conform_all_formats(
            act_clips=act_files,
            display_subject=plan.identity.display_subject,
            display_tagline=plan.identity.display_tagline,
            primary_hex=plan.palette.primary_hex,
            secondary_hex=plan.palette.secondary_hex,
            neutral_hex=plan.palette.neutral_hex,
            output_dir=str(tmp_path),
            session_id="vesper_sess",
        )

    # Verify the two 6s bumper 9:16 extractions were capped at 2.4s (from 3.4s and 3.3s defaults)
    capped_9x16 = [c for c in extracted_calls if c[0] == "9:16" and c[2] == 2.4]
    assert len(capped_9x16) == 2

    # Package using `plan=` convenience integration
    conformer_mock = CommercialConformer(mock_mode=True, bucket_name="vesper-bucket")
    zip_path, _ = conformer_mock.build_campaign_package_zip(
        deliverables=deliverables,
        plan=plan,
        output_dir=str(tmp_path),
        session_id="vesper_sess",
    )
    with zipfile.ZipFile(zip_path, "r") as zf:
        manifest = json.loads(zf.read("campaign_manifest.json").decode("utf-8"))
        assert manifest["display_subject"] == "Atelier Vesper"
        assert manifest["display_offering"] == "Obsidian Pour-Over Kettle"
        assert manifest["palette_60_30_10"]["primary_hex"] == plan.palette.primary_hex


def test_conform_all_formats_bgm_without_narrator_vo_ducks_against_native_clip_audio_mock(
    tmp_path,
) -> None:
    conformer = CommercialConformer(mock_mode=True)
    bgm = tmp_path / "ambient_score.mp3"
    bgm.write_bytes(b"mock bgm bytes")
    act_clips = ["/tmp/act1.mp4", "/tmp/act2.mp4", "/tmp/act3.mp4"]

    with patch(
        "omnimash.stitching.commercial_conformer.apply_dialogue_audio_ducking",
        return_value=str(tmp_path / "ducked_native.aac"),
    ) as mock_duck:
        conformer.conform_all_formats(
            act_clips=act_clips,
            display_subject="Aura Soundstage",
            background_music_path=str(bgm),
            narrator_audio_path=None,
            output_dir=str(tmp_path),
        )

    mock_duck.assert_called_once()
    assert mock_duck.call_args.kwargs["music_path"] == str(bgm)
    assert mock_duck.call_args.kwargs["dialogue_path"] == act_clips[0]
    assert mock_duck.call_args.kwargs["ducking_db"] == -18.0


@pytest.mark.skipif(not HAS_FFMPEG, reason="FFmpeg binary not installed")
def test_conform_all_formats_real_ffmpeg_bgm_without_narrator_vo_preserves_and_ducks_native_audio(
    tmp_path,
) -> None:
    from omnimash.stitching.audio_overlay import apply_dialogue_audio_ducking as real_ducking

    src_dir = tmp_path / "native_vo_sources"
    src_dir.mkdir()
    out_dir = tmp_path / "native_vo_out"
    act_clips = [
        _create_synthetic_mp4(str(src_dir / "act1.mp4"), color="navy", with_audio=True),
        _create_synthetic_mp4(str(src_dir / "act2.mp4"), color="darkred", with_audio=True),
        _create_synthetic_mp4(str(src_dir / "act3.mp4"), color="teal", with_audio=True),
    ]
    bgm_path = str(src_dir / "bgm_bed.aac")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=220:sample_rate=44100:duration=8.0",
            "-c:a",
            "aac",
            bgm_path,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30.0,
    )

    conformer = CommercialConformer(mock_mode=False, bucket_name="test-bucket")
    with (
        patch(
            "omnimash.stitching.commercial_conformer.apply_dialogue_audio_ducking",
            wraps=real_ducking,
        ) as spy_duck,
        patch.object(
            conformer.storage,
            "upload_file",
            side_effect=lambda local_path, destination_blob_name=None, **kw: (
                f"https://storage.googleapis.com/test-bucket/{destination_blob_name}"
            ),
        ),
    ):
        deliverables = conformer.conform_all_formats(
            act_clips=act_clips,
            display_subject="Native Audio Brand",
            background_music_path=bgm_path,
            narrator_audio_path=None,
            end_card_duration_sec=0.5,
            output_dir=str(out_dir),
            session_id="native_duck_sess",
        )

    spy_duck.assert_called_once()
    assert spy_duck.call_args.kwargs["ducking_db"] == -18.0
    assert spy_duck.call_args.kwargs["dialogue_path"].endswith(".mp4")

    master_info = _probe_streams(deliverables.local_paths["master_30s_16x9"])
    if master_info:
        mv = next(s for s in master_info["streams"] if s["codec_type"] == "video")
        ma = next(s for s in master_info["streams"] if s["codec_type"] == "audio")
        assert (mv["width"], mv["height"]) == (1280, 720)
        assert ma["codec_name"] == "aac"
        assert int(ma["channels"]) == 2
        assert float(master_info["format"]["duration"]) >= 6.0


def test_build_campaign_package_zip_blocks_out_of_root_local_files_in_storyboards_and_refs(
    tmp_path,
) -> None:
    conformer = CommercialConformer(mock_mode=True, bucket_name="confinement-bucket")
    deliverables = conformer.conform_all_formats(
        act_clips=["/tmp/act1.mp4", "/tmp/act2.mp4", "/tmp/act3.mp4"],
        display_subject="Confined Brand",
        output_dir=str(tmp_path),
    )

    valid_sb = tmp_path / "valid_sb_1_1.png"
    valid_sb.write_bytes(b"\x89PNG\r\n\x1a\nvalid_sb")
    valid_ref = tmp_path / "valid_cast.png"
    valid_ref.write_bytes(b"\x89PNG\r\n\x1a\nvalid_cast")

    zip_path, _ = conformer.build_campaign_package_zip(
        deliverables=deliverables,
        display_subject="Confined Brand",
        storyboard_frames={
            "1.1": str(valid_sb),
            "1.2": "/etc/hosts",
        },
        reference_kit={
            "valid_cast": str(valid_ref),
            "repo_leak": "pyproject.toml",
            "proxy_leak": "/api/media-proxy?uri=/etc/hosts",
        },
        output_dir=str(tmp_path),
    )

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        assert "storyboards/shot_1.1.png" in names
        assert "reference_kit/valid_cast.png" in names
        assert "storyboards/shot_1.2.png" not in names
        assert "reference_kit/repo_leak.png" not in names
        assert "reference_kit/proxy_leak.png" not in names
