"""Behavioral unit and FFmpeg integration tests for Mode 5 end-card rendering, media confinement, and campaign ZIPs."""

from __future__ import annotations

from datetime import date
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch
import zipfile

import pytest

from omnimash.prompts.soundstage_discovery import Palette603010, TerritoryAtmosphereSpec
from omnimash.stitching import CommercialConformer, ConformedDeliverables
from omnimash.stitching import end_card_renderer

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


# ---------------------------------------------------------------------------
# 1. Shared Media Source Confinement (resolve_confined_media_source)
# ---------------------------------------------------------------------------


def test_resolve_confined_media_source_blocks_out_of_root_and_unwraps_three_hop_proxy(
    tmp_path,
) -> None:
    resolve_fn = getattr(end_card_renderer, "resolve_confined_media_source")

    safe_file = tmp_path / "safe_emblem.png"
    safe_file.write_bytes(b"\x89PNG\r\n\x1a\nsafe")
    temp_dir = tmp_path / "work_tmp"
    temp_dir.mkdir()

    # Valid direct path in allowed output_dir / /tmp
    assert resolve_fn(
        str(safe_file), temp_dir=str(temp_dir), output_dir=str(tmp_path)
    ) == os.path.realpath(str(safe_file))

    # Valid 3-hop /api/media-proxy unwrapping to confined file
    hop1 = f"/api/media-proxy?uri={safe_file}"
    hop2 = f"/api/media-proxy?uri={hop1.replace('?', '%3F').replace('=', '%3D')}"
    hop3 = f"/api/media-proxy?uri={hop2.replace('?', '%3F').replace('=', '%3D')}"
    assert resolve_fn(hop3, temp_dir=str(temp_dir), output_dir=str(tmp_path)) == os.path.realpath(
        str(safe_file)
    )

    # 4-hop proxy wrapper is rejected
    hop4 = f"/api/media-proxy?uri={hop3.replace('?', '%3F').replace('=', '%3D')}"
    assert resolve_fn(hop4, temp_dir=str(temp_dir), output_dir=str(tmp_path)) is None

    # Out-of-root local paths and proxied out-of-root paths are rejected in both live and mock modes
    for forbidden in ("pyproject.toml", "/etc/hosts", "/api/media-proxy?uri=/etc/hosts"):
        assert (
            resolve_fn(forbidden, temp_dir=str(temp_dir), output_dir=str(tmp_path), mock_mode=False)
            is None
        )
        assert (
            resolve_fn(forbidden, temp_dir=str(temp_dir), output_dir=str(tmp_path), mock_mode=True)
            is None
        )

    # Non-existent /tmp fixture path is allowed ONLY when mock_mode=True
    assert (
        resolve_fn(
            "/tmp/nonexistent_fixture_clip.mp4",
            temp_dir=str(temp_dir),
            output_dir=str(tmp_path),
            mock_mode=True,
        )
        == "/tmp/nonexistent_fixture_clip.mp4"
    )
    assert (
        resolve_fn(
            "/tmp/nonexistent_fixture_clip.mp4",
            temp_dir=str(temp_dir),
            output_dir=str(tmp_path),
            mock_mode=False,
        )
        is None
    )


# ---------------------------------------------------------------------------
# 2. Brand End-Card Rendering, Contrast Math, Emblem Confinement & Validation
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
    assert dark_palette["bg_rgb"] == (17, 19, 24)
    assert dark_palette["subject_rgb"] == (248, 246, 240)
    assert _contrast_ratio(dark_palette["subject_rgb"], dark_palette["bg_rgb"]) >= 12.0

    light_palette = _select_end_card_palette(
        primary_hex="#E11D48",
        secondary_hex="#D4C5B0",
        neutral_hex="#F5F5F0",
    )
    assert light_palette["bg_rgb"] == (245, 245, 240)
    assert light_palette["subject_rgb"] == (17, 19, 24)
    assert _contrast_ratio(light_palette["subject_rgb"], light_palette["bg_rgb"]) >= 12.0
    assert _contrast_ratio(light_palette["tagline_rgb"], light_palette["bg_rgb"]) >= 4.5
    assert _parse_hex_rgb("not-a-hex", (17, 19, 24)) == (17, 19, 24)


def test_render_brand_end_card_rejects_non_finite_or_non_positive_duration(tmp_path) -> None:
    conformer = CommercialConformer(mock_mode=True)
    for bad_dur in (math.nan, math.inf, -math.inf, 0.0, -1.5, True):
        with pytest.raises(ValueError, match="duration_seconds"):
            conformer.render_brand_end_card_clip(
                display_subject="Maison Aura",
                duration_seconds=bad_dur,  # type: ignore[arg-type]
                output_dir=str(tmp_path),
            )


def test_render_brand_end_card_ignores_out_of_root_emblem_paths(tmp_path) -> None:
    conformer = CommercialConformer(mock_mode=False)
    for bad_emblem in ("pyproject.toml", "/etc/hosts", "/api/media-proxy?uri=/etc/hosts"):
        with (
            patch.object(end_card_renderer.Image, "open") as mock_img_open,
            patch(
                "omnimash.stitching.end_card_renderer.subprocess.run",
                return_value=subprocess.CompletedProcess(args=["ffmpeg"], returncode=0),
            ),
        ):
            conformer.render_brand_end_card_clip(
                display_subject="Confined Emblem Brand",
                emblem_path=bad_emblem,
                duration_seconds=0.5,
                output_dir=str(tmp_path),
            )
            mock_img_open.assert_not_called()


@pytest.mark.skipif(not HAS_FFMPEG, reason="FFmpeg binary not installed")
def test_render_brand_end_card_clip_real_ffmpeg_16x9_and_9x16_with_rgba_emblem(tmp_path) -> None:
    from PIL import Image, ImageDraw

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

    leftover_pngs = [p.name for p in out_dir.iterdir() if p.suffix.lower() == ".png"]
    assert leftover_pngs == []


def test_concatenate_normalized_av_segments_cleans_up_concat_manifest_and_downloaded_audio(
    tmp_path,
) -> None:
    temp_dir = tmp_path / "concat_tmp"
    temp_dir.mkdir()
    seg = tmp_path / "seg1.mp4"
    seg.write_bytes(b"fake mp4 segment")
    out_mp4 = tmp_path / "out.mp4"

    downloaded_audio = temp_dir / "clip_dl1234.mp4"
    downloaded_audio.write_bytes(b"downloaded real audio bytes" * 8)

    with (
        patch(
            "omnimash.stitching.end_card_renderer.resolve_media_source_to_local_path",
            return_value=str(downloaded_audio),
        ),
        patch(
            "omnimash.stitching.end_card_renderer.subprocess.run",
            return_value=subprocess.CompletedProcess(args=["ffmpeg"], returncode=1, stderr="boom"),
        ),
    ):
        with pytest.raises(RuntimeError, match="concatenation failed"):
            end_card_renderer.concatenate_normalized_av_segments(
                segment_paths=[str(seg)],
                output_path=str(out_mp4),
                temp_dir=str(temp_dir),
                master_audio_path="gs://soundstage-bucket/bgm.mp3",
            )

    # Both concat_*.txt and temporary downloaded audio in temp_dir must be unlinked in finally:
    assert list(temp_dir.iterdir()) == []


# ---------------------------------------------------------------------------
# 3. build_campaign_package_zip, Deduplication, Manifest & Cleanup
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


def test_build_campaign_package_zip_while_loop_deduplicates_colliding_keys_and_tracks_written_deliverables(
    tmp_path,
) -> None:
    conformer = CommercialConformer(mock_mode=False, bucket_name="dedup-bucket")
    master_mp4 = tmp_path / "master_real.mp4"
    master_mp4.write_bytes(b"real master bytes")

    # cutdown and bumper point to disallowed / missing paths so only master_30s_16x9 is written
    deliverables = ConformedDeliverables(
        master_30s_16x9_url="",
        cutdown_15s_9x16_url="",
        bumper_6s_9x16_url="",
        end_card_clip_url="",
        end_card_9x16_url="",
        local_paths={
            "master_30s_16x9": str(master_mp4),
            "cutdown_15s_9x16": "/etc/hosts",
            "bumper_6s_9x16": "",
        },
        gcs_uris={},
        active_subshot_ids=["1.1"],
        active_subshot_count=1,
        total_duration_sec=5.3,
        subshot_specs=[],
    )

    p1 = tmp_path / "img1.png"
    p2 = tmp_path / "img2.png"
    p3 = tmp_path / "img3.png"
    for p in (p1, p2, p3):
        p.write_bytes(b"\x89PNG\r\n\x1a\nimg")

    palette = Palette603010(
        primary_hex="#E11D48",
        primary_name="Crimson",
        secondary_hex="#D4C5B0",
        secondary_name="Stone",
        neutral_hex="#111318",
        neutral_name="Obsidian",
    )

    with patch.object(
        conformer.storage,
        "upload_file",
        return_value="https://storage.googleapis.com/dedup-bucket/pkg.zip",
    ):
        zip_path, _ = conformer.build_campaign_package_zip(
            deliverables=deliverables,
            display_subject="Dedup Atelier",
            storyboard_frames={
                "custom": str(p1),
                "custom_2": str(p2),
                "custom.png": str(p3),
            },
            reference_kit={
                "hero": str(p1),
                "hero_2": str(p2),
                "hero.png": str(p3),
            },
            timed_voiceover=[palette, ("act_2", Path("/tmp/vo_note.txt"))],
            social_copy={
                "tags": ("atelier", "soundstage"),
                "release_date": date(2026, 10, 28),
                "nested_palette": palette,
                "optional_cta": None,
            },
            output_dir=str(tmp_path),
        )

    with zipfile.ZipFile(zip_path, "r") as zf:
        name_list = zf.namelist()
        # Zero duplicate member entries in the ZIP central directory
        assert len(name_list) == len(set(name_list))
        assert {
            "reference_kit/hero.png",
            "reference_kit/hero_2.png",
            "reference_kit/hero_3.png",
        }.issubset(set(name_list))
        assert {
            "storyboards/shot_custom.png",
            "storyboards/shot_custom_2.png",
            "storyboards/shot_custom_3.png",
        }.issubset(set(name_list))

        manifest = json.loads(zf.read("campaign_manifest.json").decode("utf-8"))
        # Only master_30s_16x9 was actually written to the archive
        assert manifest["deliverables"]["archive_entries"] == {
            "master_30s_16x9": "deliverables/30s_16x9_master.mp4"
        }
        assert manifest["social_copy"]["tags"] == ["atelier", "soundstage"]
        assert manifest["social_copy"]["release_date"] == "2026-10-28"
        assert manifest["social_copy"]["nested_palette"]["primary_hex"] == "#E11D48"
        assert manifest["social_copy"]["optional_cta"] is None
        assert manifest["timed_voiceover"][0]["primary_hex"] == "#E11D48"
        assert manifest["timed_voiceover"][1] == ["act_2", "/tmp/vo_note.txt"]


def test_build_campaign_package_zip_unlinks_partial_zip_on_upload_exception(tmp_path) -> None:
    conformer = CommercialConformer(mock_mode=True, bucket_name="fail-bucket")
    deliverables = conformer.conform_all_formats(
        act_clips=["/tmp/act1.mp4", "/tmp/act2.mp4", "/tmp/act3.mp4"],
        display_subject="Rollback Brand",
        output_dir=str(tmp_path),
    )

    out_zip_dir = tmp_path / "zip_out"
    out_zip_dir.mkdir()
    with patch.object(
        conformer.storage,
        "upload_file",
        side_effect=RuntimeError("simulated GCS upload outage"),
    ):
        with pytest.raises(RuntimeError, match="simulated GCS upload outage"):
            conformer.build_campaign_package_zip(
                deliverables=deliverables,
                display_subject="Rollback Brand",
                output_dir=str(out_zip_dir),
            )

    assert [p for p in out_zip_dir.iterdir() if p.suffix == ".zip"] == []
