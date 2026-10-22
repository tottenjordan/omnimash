from __future__ import annotations

from omnimash.evaluation.models import (
    DefectCategory,
    DimensionScore,
    ExemplarPromptRecord,
    UserFeedbackRecord,
    VideoEvaluationScorecard,
)
from omnimash.storage.gcs import GcsStorageManager


def _create_sample_scorecard(session_id: str, turn_id: str) -> VideoEvaluationScorecard:
    dim = DimensionScore(score=95.0, passed=True, evidence="Excellent quality")
    return VideoEvaluationScorecard(
        session_id=session_id,
        turn_id=turn_id,
        overall_rating=95.0,
        video_text_adherence=dim,
        character_likeness=dim,
        audio_visual_harmony=dim,
        tag_and_index_integrity=dim,
        detected_defects=[],
        verbal_critique="Masterpiece.",
        pass_verdict=True,
    )


def test_save_and_get_exemplar_global():
    storage = GcsStorageManager(mock_mode=True)
    scorecard = _create_sample_scorecard("sess_1", "turn_0")
    record = ExemplarPromptRecord(
        session_id="sess_1",
        concept="Noir detective monologue in heavy rain",
        style_preset="cinematic",
        compiled_4block_prompt="### CHARACTER PROFILES\n- Role A <IMAGE_REF_0>: Detective Vance...",
        scorecard=scorecard,
        user_rating=5,
    )

    gcs_uri = storage.save_exemplar(record)
    assert gcs_uri.startswith("gs://")
    assert f"meta/exemplars/{record.exemplar_id}.json" in gcs_uri

    # Retrieve and verify
    retrieved = storage.get_exemplar(record.exemplar_id)
    assert retrieved is not None
    assert retrieved["exemplar_id"] == record.exemplar_id
    assert retrieved["concept"] == "Noir detective monologue in heavy rain"
    assert retrieved["style_preset"] == "cinematic"
    assert retrieved["user_rating"] == 5


def test_save_and_get_exemplar_project_scoped_and_cross_tenant_isolation():
    storage = GcsStorageManager(mock_mode=True)
    record = ExemplarPromptRecord(
        session_id="sess_proj",
        concept="Cyberpunk drone delivery chase",
        style_preset="cyberpunk",
        compiled_4block_prompt="### CHARACTER PROFILES\n- Role A: Drone Operator...",
        user_rating=5,
    )

    # Save under tenant project_alpha
    gcs_uri = storage.save_exemplar(record, project_id="project_alpha")
    assert f"projects/project_alpha/exemplars/{record.exemplar_id}.json" in gcs_uri

    # Retrieve within the same project
    retrieved = storage.get_exemplar(record.exemplar_id, project_id="project_alpha")
    assert retrieved is not None
    assert retrieved["exemplar_id"] == record.exemplar_id

    # Verify cross-tenant isolation: tenant project_beta cannot retrieve project_alpha exemplar
    isolated = storage.get_exemplar(record.exemplar_id, project_id="project_beta")
    assert isolated is None

    # Global lookup without project_id should not find the project-scoped exemplar
    global_lookup = storage.get_exemplar(record.exemplar_id, project_id=None)
    assert global_lookup is None


def test_list_exemplars_filtering_and_project_scoping():
    storage = GcsStorageManager(mock_mode=True)

    # Global exemplars
    ex_global_1 = ExemplarPromptRecord(
        session_id="sess_g1",
        concept="Epic space opera space fleet battle",
        style_preset="cinematic",
        compiled_4block_prompt="### VISUAL & AUDIO FOUNDATION...",
        user_rating=5,
    )
    ex_global_2 = ExemplarPromptRecord(
        session_id="sess_g2",
        concept="Chibi anime cooking competition",
        style_preset="anime",
        compiled_4block_prompt="### VISUAL & AUDIO FOUNDATION...",
        user_rating=4,
    )
    storage.save_exemplar(ex_global_1, project_id=None)
    storage.save_exemplar(ex_global_2, project_id=None)

    # Project exemplars for studio_x
    ex_proj_1 = ExemplarPromptRecord(
        session_id="sess_p1",
        concept="Hyper-realistic sports car drifting on mountain pass",
        style_preset="cinematic",
        compiled_4block_prompt="### VISUAL & AUDIO FOUNDATION...",
        user_rating=5,
    )
    storage.save_exemplar(ex_proj_1, project_id="studio_x")

    # Global listing
    global_list = storage.list_exemplars(project_id=None)
    global_ids = {e["exemplar_id"] for e in global_list}
    assert ex_global_1.exemplar_id in global_ids
    assert ex_global_2.exemplar_id in global_ids
    assert ex_proj_1.exemplar_id not in global_ids

    # Global listing filtered by style_preset
    anime_list = storage.list_exemplars(project_id=None, style_preset="anime")
    assert len(anime_list) == 1
    assert anime_list[0]["exemplar_id"] == ex_global_2.exemplar_id

    # Project listing for studio_x
    proj_list = storage.list_exemplars(project_id="studio_x")
    proj_ids = {e["exemplar_id"] for e in proj_list}
    assert ex_proj_1.exemplar_id in proj_ids
    assert ex_global_1.exemplar_id not in proj_ids

    # Project listing for another project should be empty
    other_list = storage.list_exemplars(project_id="studio_y")
    assert len(other_list) == 0


def test_list_feedback_records():
    storage = GcsStorageManager(mock_mode=True)
    fb1 = UserFeedbackRecord(
        session_id="sess_f1",
        turn_id="turn_0",
        rating=5,
        defects=[],
        critique_text="Flawless cinematography.",
    )
    fb2 = UserFeedbackRecord(
        session_id="sess_f2",
        turn_id="turn_1",
        project_id="proj_studio",
        rating=2,
        defects=[DefectCategory.AUDIO_DROWNED],
        critique_text="Music masked the dialogue.",
    )

    storage.save_feedback("sess_f1", "turn_0", fb1, project_id=None)
    storage.save_feedback("sess_f2", "turn_1", fb2, project_id="proj_studio")

    # Project-specific list
    proj_feedbacks = storage.list_feedback_records(project_id="proj_studio")
    assert len(proj_feedbacks) == 1
    assert proj_feedbacks[0]["session_id"] == "sess_f2"
    assert proj_feedbacks[0]["rating"] == 2

    # Global / all list
    all_feedbacks = storage.list_feedback_records(limit=10)
    assert len(all_feedbacks) >= 2


def test_list_scorecards():
    storage = GcsStorageManager(mock_mode=True)
    sc1 = _create_sample_scorecard("sess_sc1", "turn_0")
    sc2 = _create_sample_scorecard("sess_sc2", "turn_1")

    storage.save_scorecard("sess_sc1", "turn_0", sc1, project_id=None)
    storage.save_scorecard("sess_sc2", "turn_1", sc2, project_id="proj_sc")

    # Project-specific list
    proj_scorecards = storage.list_scorecards(project_id="proj_sc")
    assert len(proj_scorecards) == 1
    assert proj_scorecards[0]["session_id"] == "sess_sc2"

    # All list
    all_scorecards = storage.list_scorecards(limit=10)
    assert len(all_scorecards) >= 2


def test_get_nonexistent_exemplar_returns_none():
    storage = GcsStorageManager(mock_mode=True)
    assert storage.get_exemplar("nonexistent_id") is None
    assert storage.get_exemplar("nonexistent_id", project_id="proj_x") is None


def test_empty_storage_listings():
    storage = GcsStorageManager(mock_mode=True)
    assert storage.list_exemplars() == []
    assert storage.list_exemplars(project_id="unknown") == []
    assert storage.list_feedback_records() == []
    assert storage.list_scorecards() == []


def test_save_exemplar_as_dict_and_auto_id():
    storage = GcsStorageManager(mock_mode=True)
    payload = {
        "session_id": "sess_dict",
        "concept": "Retro synthwave cruise",
        "style_preset": "synthwave",
        "compiled_4block_prompt": "### VISUAL & AUDIO FOUNDATION...",
        "user_rating": 5,
    }
    uri = storage.save_exemplar(payload)
    assert uri.startswith("gs://")
    assert "meta/exemplars/ex_" in uri
    retrieved = storage.get_exemplar(str(payload["exemplar_id"]))
    assert retrieved is not None
    assert retrieved["concept"] == "Retro synthwave cruise"


def test_save_exemplar_extracts_project_id_from_model_or_payload_when_unspecified():
    storage = GcsStorageManager(mock_mode=True)
    # Exemplar model with project_id defined
    record = ExemplarPromptRecord(
        session_id="sess_auto_proj",
        concept="Mecha battle in orbital station",
        style_preset="anime",
        compiled_4block_prompt="### Prompt...",
        user_rating=5,
        project_id="tenant_mecha",
    )
    # Save without explicitly providing project_id parameter
    uri = storage.save_exemplar(record)
    assert "projects/tenant_mecha/exemplars/" in uri

    # Verify retrievable under project scope
    retrieved = storage.get_exemplar(record.exemplar_id, project_id="tenant_mecha")
    assert retrieved is not None
    assert retrieved["exemplar_id"] == record.exemplar_id
    assert retrieved["project_id"] == "tenant_mecha"

    # Dict payload with project_id
    dict_payload = {
        "exemplar_id": "ex_custom_dict",
        "session_id": "sess_d",
        "concept": "Film noir mystery",
        "style_preset": "noir",
        "compiled_4block_prompt": "### Prompt...",
        "user_rating": 5,
        "project_id": "tenant_noir",
    }
    uri_dict = storage.save_exemplar(dict_payload)
    assert "projects/tenant_noir/exemplars/ex_custom_dict.json" in uri_dict
    retrieved_dict = storage.get_exemplar("ex_custom_dict", project_id="tenant_noir")
    assert retrieved_dict is not None
    assert retrieved_dict["concept"] == "Film noir mystery"


def test_list_feedback_and_scorecards_limit_boundaries():
    storage = GcsStorageManager(mock_mode=True)
    fb = UserFeedbackRecord(
        session_id="sess_lim",
        turn_id="turn_0",
        rating=5,
        critique_text="Fine",
    )
    storage.save_feedback("sess_lim", "turn_0", fb)

    sc = _create_sample_scorecard("sess_lim", "turn_0")
    storage.save_scorecard("sess_lim", "turn_0", sc)

    # limit <= 0 returns empty list, not negative slices
    assert storage.list_feedback_records(limit=0) == []
    assert storage.list_feedback_records(limit=-5) == []
    assert storage.list_scorecards(limit=0) == []
    assert storage.list_scorecards(limit=-5) == []


def test_list_exemplars_deduplication_and_whitespace_preset():
    storage = GcsStorageManager(mock_mode=True)
    ex = ExemplarPromptRecord(
        exemplar_id="ex_dup_test",
        session_id="sess_dup",
        concept="Testing deduplication",
        style_preset="cinematic",
        compiled_4block_prompt="### Prompt",
        user_rating=5,
    )
    storage.save_exemplar(ex)
    # Intentionally populate another reference under mock cache
    storage._mock_exemplars["other_alias_for_ex_dup_test"] = ex.model_dump(mode="json")

    results = storage.list_exemplars(project_id=None)
    matching = [r for r in results if r.get("exemplar_id") == "ex_dup_test"]
    assert len(matching) == 1

    # Whitespace-only style preset should not filter out all records
    assert len(storage.list_exemplars(style_preset="   ")) >= 1
