"""Tests for GenerativeTitleCardRenderer and preset-driven positive title card prompts."""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from omnimash.stitching.title_card_generator import (
    GenerativeTitleCardRenderer,
    build_title_card_image_prompt,
)


def _assert_positive_phrasing(prompt: str) -> None:
    lowered = prompt.lower()
    for forbidden in ("no ", "not ", "don't", "do not", "without", "never "):
        assert forbidden not in lowered, f"Forbidden negative phrase {forbidden!r} in: {prompt}"


def test_build_title_card_image_prompt_supports_presets_and_image1_style_anchor() -> None:
    for preset in ("gothic_24k_gold", "neon_cyber", "editorial_minimal"):
        card1_prompt = build_title_card_image_prompt(
            title_text="Act I: The Awakening",
            subtitle_text="Directed by OmniMash",
            style_preset=preset,
            has_style_anchor_image=False,
        )
        _assert_positive_phrasing(card1_prompt)
        assert "ACT I: THE AWAKENING" in card1_prompt
        assert "DIRECTED BY OMNIMASH" in card1_prompt
        assert "#000000" in card1_prompt
        assert "@Image1" not in card1_prompt

        card2_prompt = build_title_card_image_prompt(
            title_text="Act II: The Finale",
            subtitle_text="4K Master",
            style_preset=preset,
            has_style_anchor_image=True,
        )
        _assert_positive_phrasing(card2_prompt)
        assert "@Image1" in card2_prompt
        assert "ACT II: THE FINALE" in card2_prompt
        assert "4K MASTER" in card2_prompt
        assert "#000000" in card2_prompt

    brand_prompt = build_title_card_image_prompt(
        title_text="Maison Nocturne",
        subtitle_text="Autumn Capsule",
        style_preset="brand_palette_lock",
        has_style_anchor_image=True,
        brand_palette={"primary": "#E11D48", "secondary": "#D4C5B0", "background": "#0A0B10"},
    )
    _assert_positive_phrasing(brand_prompt)
    assert "@Image1" in brand_prompt
    assert "#E11D48" in brand_prompt
    assert "#D4C5B0" in brand_prompt
    assert "#0A0B10" in brand_prompt
    assert "MAISON NOCTURNE" in brand_prompt


def test_generative_title_card_renderer_creates_1080p24_clip_in_mock_mode(tmp_path) -> None:
    renderer = GenerativeTitleCardRenderer(mock_mode=True)
    clip_path = renderer.render_title_card_clip(
        title_text="TRAPWARTS",
        subtitle_text="ACT I",
        duration_seconds=1.5,
        style_preset="gothic_24k_gold",
        aspect_ratio="16:9",
        resolution="1080p",
        output_dir=str(tmp_path),
    )

    assert os.path.isfile(clip_path)
    assert clip_path.endswith(".mp4")
    assert os.path.getsize(clip_path) > 512

    if shutil.which("ffprobe"):
        res = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type,width,height,r_frame_rate,sample_rate,channels",
                "-of",
                "json",
                clip_path,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30.0,
        )
        streams = json.loads(res.stdout).get("streams", [])
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        assert len(video_streams) == 1
        assert video_streams[0]["width"] == 1920
        assert video_streams[0]["height"] == 1080
        assert video_streams[0]["r_frame_rate"] == "24/1"
        assert len(audio_streams) == 1
        assert str(audio_streams[0]["sample_rate"]) == "48000"
        assert audio_streams[0]["channels"] == 2
