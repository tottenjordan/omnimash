import os
import time
from typing import Any
import wave

from omnimash.engine.procedural_renderer import (
    _generate_dynamic_audio_wav,
    ensure_rendered_video,
    extract_clean_dialogue_summary,
)
from omnimash.engine.guardrails import (
    _FULL_NAME_PATTERN,
    _PROTECTED_TOKEN_PATTERN,
    _RAI_REPLACEMENT_PATTERNS,
    _abstract_prompt_for_responsible_ai,
    _get_relaxed_safety_settings,
    parse_guardrail_error_guidance,
)


def test_precompiled_rai_regex_constants_exist_and_sanitize() -> None:
    assert len(_RAI_REPLACEMENT_PATTERNS) >= 70
    assert hasattr(_PROTECTED_TOKEN_PATTERN, "sub")
    assert hasattr(_FULL_NAME_PATTERN, "search")

    res = _abstract_prompt_for_responsible_ai("Harry Potter and Darth Vader in a wizard duel")
    assert "harry potter" not in res.lower()
    assert "darth vader" not in res.lower()
    assert "hip-hop wizard musical contest" in res.lower()


def test_dynamic_audio_wav_fast_array_synthesis(tmp_path: Any) -> None:
    wav_file = str(tmp_path / "fast_10s.wav")
    start = time.perf_counter()
    bpm = _generate_dynamic_audio_wav(wav_file, prompt="140 BPM UK Drill", duration=10)
    elapsed = time.perf_counter() - start

    assert bpm == 140
    assert elapsed < 0.50
    with wave.open(wav_file, "rb") as wf:
        assert wf.getnframes() == 44100 * 10


def test_extract_clean_dialogue_summary_and_guardrails(tmp_path: Any) -> None:
    summary = extract_clean_dialogue_summary('Dialogue: "Turn to page 394!"')
    assert summary == "Turn to page 394!"

    guidance = parse_guardrail_error_guidance(
        error_msg="400 Policy violation: real_people_likeness",
        char_objs=[{"name": "Jordan Totten", "reference_url": "https://example.com/photo.jpg"}],
        prompt_text="Jordan Totten holding a Lightsaber",
    )
    assert "real_people_likeness" in guidance["triggers"]
    assert "real_people_photo" in guidance["triggers"]
    assert "third_party_content" in guidance["triggers"]

    fallback_settings = _get_relaxed_safety_settings(genai_module=None)
    assert fallback_settings is not None
    assert len(fallback_settings) == 5

    # Verify ensure_rendered_video works for /static/ paths
    mp4_url = "/static/rendered/test_proc_mod_render.mp4"
    rel_mp4 = mp4_url.lstrip("/")
    if os.path.exists(rel_mp4):
        os.remove(rel_mp4)
    try:
        ensure_rendered_video(mp4_url, prompt="110 BPM Cyberpunk synth", duration=1)
        assert os.path.exists(rel_mp4)
        assert os.path.getsize(rel_mp4) > 0
    finally:
        if os.path.exists(rel_mp4):
            os.remove(rel_mp4)
