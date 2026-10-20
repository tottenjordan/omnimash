from omnimash.ingestion.models import (
    DEFAULT_KEYFRAME_SPECS,
    JPEG_QUALITY,
    KEYFRAME_HEIGHT,
    KEYFRAME_WIDTH,
    ParodyResearchResult,
    build_parody_research_result,
)


def test_build_parody_research_result_incorporates_custom_subject_and_aesthetic():
    res = build_parody_research_result(
        subject="Darth Vader and Luke Skywalker",
        aesthetic="80s Miami Synthwave",
    )
    assert isinstance(res, ParodyResearchResult)
    assert "Darth Vader" in res.synopsis
    assert "80s Miami Synthwave" in res.synopsis or "Synthwave" in res.suggested_vibe
    assert len(res.suggested_props) >= 3
    assert res.vibe_intensity > 0


def test_build_parody_research_result_preserves_default_hogwarts_trap_clash():
    res = build_parody_research_result(
        subject="Harry Potter and Draco Malfoy",
        aesthetic="Atlanta Trap Disstrack",
    )
    assert "Dripwarts" in res.synopsis
    assert "Diamond Lightning Bolt Chain" in res.suggested_props
    assert "Trap" in res.suggested_audio


def test_default_keyframe_specs_and_constants():
    assert KEYFRAME_WIDTH == 1280
    assert KEYFRAME_HEIGHT == 720
    assert JPEG_QUALITY == 90
    assert len(DEFAULT_KEYFRAME_SPECS) == 3
    assert DEFAULT_KEYFRAME_SPECS[0].filename == "frame_1.jpg"
