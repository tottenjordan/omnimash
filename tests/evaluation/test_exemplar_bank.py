from __future__ import annotations

import pytest

from omnimash.evaluation.exemplar_bank import ExemplarBankManager
from omnimash.evaluation.models import (
    DefectCategory,
    DimensionScore,
    ExemplarPromptRecord,
    VideoEvaluationScorecard,
)
from omnimash.storage.gcs import GcsStorageManager


def _create_scorecard(passed: bool = True, rating: float = 94.0) -> VideoEvaluationScorecard:
    dim = DimensionScore(score=rating, passed=passed, evidence="Evaluation check")
    return VideoEvaluationScorecard(
        session_id="sess_test",
        turn_id="turn_0",
        overall_rating=rating,
        video_text_adherence=dim,
        character_likeness=dim,
        audio_visual_harmony=dim,
        tag_and_index_integrity=dim,
        detected_defects=[] if passed else [DefectCategory.LIKENESS_DRIFT],
        verbal_critique="Clean render." if passed else "Defect detected.",
        pass_verdict=passed,
    )


def test_exemplar_bank_initialization():
    storage = GcsStorageManager(mock_mode=True)
    bank = ExemplarBankManager(storage=storage, mock_mode=True)
    assert bank.storage is storage
    assert bank.mock_mode is True


def test_ingest_5star_prompt_success():
    storage = GcsStorageManager(mock_mode=True)
    bank = ExemplarBankManager(storage=storage, mock_mode=True)

    scorecard = _create_scorecard(passed=True, rating=98.0)
    prompt = (
        "### VISUAL & AUDIO FOUNDATION\n"
        "[Environment: Midnight rain in Neo-Tokyo]\n\n"
        "### CHARACTER PROFILES\n"
        "- Role A <IMAGE_REF_0>: Cyber Ninja\n"
        "- Role B <IMAGE_REF_1>: Android Courier\n\n"
        "### DIRECTORIAL CONTINUITY & CAMERA STAGING\n"
        "[Camera: Low-angle tracking shot]\n\n"
        "### CANONICAL TIMELINE & AUDIO SCRIPT\n"
        "[0-3s] Footsteps splash in puddles."
    )

    record = bank.ingest_5star_prompt(
        session_id="sess_neo_tokyo",
        concept="Cyber ninja confronts courier in neon rain",
        compiled_prompt=prompt,
        scorecard=scorecard,
        user_rating=5,
        style_preset="cyberpunk",
        project_id="studio_prime",
    )

    assert isinstance(record, ExemplarPromptRecord)
    assert record.exemplar_id.startswith("ex_")
    assert record.session_id == "sess_neo_tokyo"
    assert record.concept == "Cyber ninja confronts courier in neon rain"
    assert record.style_preset == "cyberpunk"
    assert record.user_rating == 5
    assert record.scorecard is not None
    assert record.scorecard.pass_verdict is True

    # Check persistence in storage
    saved = storage.get_exemplar(record.exemplar_id, project_id="studio_prime")
    assert saved is not None
    assert saved["exemplar_id"] == record.exemplar_id


def test_ingest_5star_prompt_validation_failures():
    bank = ExemplarBankManager(mock_mode=True)

    # 1. Rating below 4 stars
    with pytest.raises(ValueError, match="below 4-star minimum"):
        bank.ingest_5star_prompt(
            session_id="sess_low",
            concept="Bad scene",
            compiled_prompt="### Prompt",
            user_rating=3,
        )

    # 2. Rating above 5 stars
    with pytest.raises(ValueError, match="exceeds maximum"):
        bank.ingest_5star_prompt(
            session_id="sess_high",
            concept="Over rated scene",
            compiled_prompt="### Prompt",
            user_rating=6,
        )

    # 3. Failed scorecard (pass_verdict=False)
    failed_scorecard = _create_scorecard(passed=False, rating=55.0)
    with pytest.raises(ValueError, match="pass_verdict=True"):
        bank.ingest_5star_prompt(
            session_id="sess_fail_sc",
            concept="Defective render",
            compiled_prompt="### Prompt",
            scorecard=failed_scorecard,
            user_rating=5,
        )


def test_query_relevant_exemplars_ranking():
    storage = GcsStorageManager(mock_mode=True)
    bank = ExemplarBankManager(storage=storage, mock_mode=True)

    # Exemplar 1: Cyberpunk, 2 characters, neon duel
    bank.ingest_5star_prompt(
        session_id="sess_cyber",
        concept="Cyberpunk street duel with katana",
        compiled_prompt=(
            "### CHARACTER PROFILES\n"
            "- Role A <IMAGE_REF_0>: Cyber Samurai\n"
            "- Role B <IMAGE_REF_1>: Street Brawler\n"
        ),
        user_rating=5,
        style_preset="cyberpunk",
    )

    # Exemplar 2: Anime, 4 characters, sports contest
    bank.ingest_5star_prompt(
        session_id="sess_anime",
        concept="High school basketball championship game",
        compiled_prompt=(
            "### CHARACTER PROFILES\n"
            "- Role A: Point Guard\n"
            "- Role B: Center\n"
            "- Role C: Coach\n"
            "- Role D: Referee\n"
        ),
        user_rating=5,
        style_preset="anime",
    )

    # Exemplar 3: Cinematic, 1 character, solo desert monologue
    bank.ingest_5star_prompt(
        session_id="sess_cinematic",
        concept="Lone wanderer traversing barren desert dunes",
        compiled_prompt=("### CHARACTER PROFILES\n- Role A <IMAGE_REF_0>: Wanderer\n"),
        user_rating=5,
        style_preset="cinematic",
    )

    # Query matching cyber katana duel (cyberpunk, 2 characters)
    results = bank.query_relevant_exemplars(
        concept="katana duel in neon cyberpunk alley",
        style_preset="cyberpunk",
        character_count=2,
        limit=2,
    )

    assert len(results) > 0
    assert results[0].style_preset == "cyberpunk"
    assert "katana" in results[0].concept or "duel" in results[0].concept

    # Query matching anime sports
    anime_results = bank.query_relevant_exemplars(
        concept="high school tournament match",
        style_preset="anime",
        character_count=4,
        limit=1,
    )
    assert len(anime_results) == 1
    assert anime_results[0].style_preset == "anime"


def test_query_relevant_exemplars_project_layering():
    storage = GcsStorageManager(mock_mode=True)
    bank = ExemplarBankManager(storage=storage, mock_mode=True)

    # Global exemplar
    bank.ingest_5star_prompt(
        session_id="sess_global",
        concept="Global corporate luxury commercial",
        compiled_prompt="### Prompt Global",
        user_rating=5,
        style_preset="commercial",
        project_id=None,
    )

    # Project-specific exemplar for tenant_delta
    bank.ingest_5star_prompt(
        session_id="sess_delta",
        concept="Custom delta luxury brand showcase",
        compiled_prompt="### Prompt Delta",
        user_rating=5,
        style_preset="commercial",
        project_id="tenant_delta",
    )

    # Query without project_id returns only global
    global_res = bank.query_relevant_exemplars(
        concept="luxury commercial",
        style_preset="commercial",
        project_id=None,
    )
    assert any(e.session_id == "sess_global" for e in global_res)
    assert not any(e.session_id == "sess_delta" for e in global_res)

    # Query with project_id tenant_delta layers project exemplar
    delta_res = bank.query_relevant_exemplars(
        concept="luxury commercial",
        style_preset="commercial",
        project_id="tenant_delta",
    )
    delta_sessions = [e.session_id for e in delta_res]
    assert "sess_delta" in delta_sessions
    assert "sess_global" in delta_sessions
    # Project-specific exemplar ranks highest due to tenant relevance
    assert delta_sessions[0] == "sess_delta"


def test_format_exemplars_as_few_shot_block():
    bank = ExemplarBankManager(mock_mode=True)

    # Empty list case
    assert bank.format_exemplars_as_few_shot_block([]) == ""

    ex1 = ExemplarPromptRecord(
        exemplar_id="ex_test1",
        session_id="sess_1",
        concept="Cinematic trap parody heist",
        style_preset="cinematic",
        compiled_4block_prompt=(
            "### VISUAL & AUDIO FOUNDATION\n"
            "[Lighting: Neon blue and amber rim lighting]\n\n"
            "### CHARACTER PROFILES\n"
            "- Role A <IMAGE_REF_0>: Mastermind Drip\n\n"
            "### DIRECTORIAL CONTINUITY & CAMERA STAGING\n"
            "[Camera: Dynamic dolly zoom]\n\n"
            "### CANONICAL TIMELINE & AUDIO SCRIPT\n"
            "[0-3s] Vault door cracks open."
        ),
        user_rating=5,
    )

    ex2 = ExemplarPromptRecord(
        exemplar_id="ex_test2",
        session_id="sess_2",
        concept="Anime magical girl showdown",
        style_preset="anime",
        compiled_4block_prompt="### VISUAL & AUDIO FOUNDATION...",
        user_rating=5,
    )

    formatted = bank.format_exemplars_as_few_shot_block([ex1, ex2])

    assert "### DIRECTORIAL FEW-SHOT EXEMPLARS (5-STAR MASTER REFERENCE PROMPTS)" in formatted
    assert (
        "Example 1 (Style: Cinematic)" in formatted or "Example 1 (Style: cinematic)" in formatted
    )
    assert "Cinematic trap parody heist" in formatted
    assert "Mastermind Drip" in formatted
    assert "Example 2" in formatted


def test_ingest_boundary_ratings_and_dict_scorecard():
    bank = ExemplarBankManager(mock_mode=True)

    # 4-star boundary passes
    rec4 = bank.ingest_5star_prompt(
        session_id="sess_4star",
        concept="Solid four star clip",
        compiled_prompt="### Prompt",
        user_rating=4,
    )
    assert rec4.user_rating == 4

    # Dict-based scorecard passes
    scorecard_dict = {
        "session_id": "sess_dict_sc",
        "turn_id": "turn_0",
        "overall_rating": 90.0,
        "video_text_adherence": {"score": 90.0, "passed": True},
        "character_likeness": {"score": 90.0, "passed": True},
        "audio_visual_harmony": {"score": 90.0, "passed": True},
        "tag_and_index_integrity": {"score": 90.0, "passed": True},
        "detected_defects": [],
        "verbal_critique": "Solid performance.",
        "pass_verdict": True,
    }
    rec_dict_sc = bank.ingest_5star_prompt(
        session_id="sess_dict_sc",
        concept="Five star with dict scorecard",
        compiled_prompt="### Prompt",
        scorecard=scorecard_dict,  # type: ignore[arg-type]
        user_rating=5,
    )
    assert rec_dict_sc.scorecard is not None
    assert rec_dict_sc.scorecard.pass_verdict is True


def test_query_relevant_exemplars_empty_bank():
    storage = GcsStorageManager(mock_mode=True)
    bank = ExemplarBankManager(storage=storage, mock_mode=True)
    assert bank.query_relevant_exemplars(concept="anything") == []


def test_memory_bank_graceful_error_handling():
    storage = GcsStorageManager(mock_mode=True)
    bank = ExemplarBankManager(storage=storage, agent_engine_id="engine_test", mock_mode=False)

    class FailingMemoryClient:
        def create_memory(self, **kwargs):
            raise RuntimeError("Memory Bank API unavailable")

    bank._memory_client = FailingMemoryClient()

    record = ExemplarPromptRecord(
        session_id="sess_mem",
        concept="Prompt with memory bank sync",
        style_preset="cinematic",
        compiled_4block_prompt="### VISUAL...",
        user_rating=5,
    )
    # save_exemplar must not raise even if memory bank fails
    uri = bank.save_exemplar(record)
    assert uri.startswith("gs://")


def test_query_relevant_exemplars_none_concept_and_negative_limit():
    storage = GcsStorageManager(mock_mode=True)
    bank = ExemplarBankManager(storage=storage, mock_mode=True)

    bank.ingest_5star_prompt(
        session_id="sess_q1",
        concept="Noir detective monologue",
        compiled_prompt="### VISUAL...",
        user_rating=5,
        style_preset="cinematic",
    )

    # Calling with concept=None must not raise TypeError
    results = bank.query_relevant_exemplars(concept=None, style_preset="cinematic")
    assert len(results) == 1

    # Calling with limit <= 0 must return empty list
    assert bank.query_relevant_exemplars(concept="detective", limit=0) == []
    assert bank.query_relevant_exemplars(concept="detective", limit=-2) == []


def test_format_few_shot_block_with_nested_code_fences():
    bank = ExemplarBankManager(mock_mode=True)

    prompt_with_fences = (
        "### VISUAL & AUDIO FOUNDATION\n"
        "```json\n"
        '{"lighting": "neon"}\n'
        "```\n"
        "### CHARACTER PROFILES\n"
        "- Role A: Detective"
    )
    ex = ExemplarPromptRecord(
        session_id="sess_fence",
        concept="Scene with embedded code block",
        compiled_4block_prompt=prompt_with_fences,
        user_rating=5,
        style_preset="cinematic",
    )

    block = bank.format_exemplars_as_few_shot_block([ex])
    # The outer fence must use at least 4 backticks so it doesn't break on inner ```
    assert "````" in block
    assert "```json" in block


def test_format_few_shot_block_with_dicts_and_dict_scorecard():
    bank = ExemplarBankManager(mock_mode=True)

    dict_ex = {
        "exemplar_id": "ex_d1",
        "session_id": "sess_d1",
        "concept": "Synthwave chase",
        "style_preset": "synthwave",
        "compiled_4block_prompt": "### Prompt...",
        "user_rating": 5,
        "scorecard": {
            "session_id": "sess_d1",
            "turn_id": "turn_0",
            "overall_rating": 95.0,
            "video_text_adherence": {"score": 95.0, "passed": True},
            "character_likeness": {"score": 95.0, "passed": True},
            "audio_visual_harmony": {"score": 95.0, "passed": True},
            "tag_and_index_integrity": {"score": 95.0, "passed": True},
            "verbal_critique": "Outstanding visual coherence.",
            "pass_verdict": True,
        },
    }

    # Must accept list of dicts without AttributeError
    block = bank.format_exemplars_as_few_shot_block([dict_ex])
    assert "Example 1 (Style: Synthwave)" in block
    assert "Synthwave chase" in block
    assert "**Screening Room Verdict:** Outstanding visual coherence." in block


def test_character_count_extraction_heuristics():
    from omnimash.evaluation.exemplar_bank import _extract_character_count

    # Role with colon
    p1 = "### CHARACTER PROFILES\n- Role: Detective Vance\n- Character: Deputy Miller"
    assert _extract_character_count(p1, "") == 2

    # Role with letter and reference image tag
    p2 = "### CHARACTER PROFILES\n- Role A <IMAGE_REF_0>: Samurai\n- Role B <IMAGE_REF_1>: Ninja"
    assert _extract_character_count(p2, "") == 2

    # Solo concept hint
    p3 = "### Prompt\nLone wanderer in empty desert"
    assert _extract_character_count(p3, "solo desert monologue") == 1

    # Duo concept hint
    p4 = "### Prompt\nTwo warriors face off"
    assert _extract_character_count(p4, "epic duel between warriors") == 2

    # None prompt and concept should not raise
    assert _extract_character_count(None, None) == 1


def test_ingest_empty_prompt_or_concept_fails():
    bank = ExemplarBankManager(mock_mode=True)

    with pytest.raises(ValueError, match="compiled_prompt must be a non-empty string"):
        bank.ingest_5star_prompt("s1", "concept", "   ", user_rating=5)

    with pytest.raises(ValueError, match="concept must be a non-empty string"):
        bank.ingest_5star_prompt("s1", "   ", "### Prompt", user_rating=5)

    with pytest.raises(ValueError, match="session_id must be a non-empty string"):
        bank.ingest_5star_prompt("   ", "concept", "### Prompt", user_rating=5)


def test_save_exemplar_as_dict_in_bank():
    storage = GcsStorageManager(mock_mode=True)
    bank = ExemplarBankManager(storage=storage, mock_mode=True)

    dict_ex = {
        "session_id": "sess_save_dict",
        "concept": "Cyberpunk chase",
        "style_preset": "cyberpunk",
        "compiled_4block_prompt": "### Prompt...",
        "user_rating": 5,
        "project_id": "proj_dict_test",
    }
    uri = bank.save_exemplar(dict_ex)
    assert "projects/proj_dict_test/exemplars/" in uri
