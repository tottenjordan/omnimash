from __future__ import annotations

import json
from unittest.mock import MagicMock
import pytest

from omnimash.storage.gcs import GcsStorageManager, validate_safe_identifier


@pytest.fixture(autouse=True)
def _reset_shared_clients():
    GcsStorageManager._SHARED_CLIENTS.clear()
    yield
    GcsStorageManager._SHARED_CLIENTS.clear()


def test_fork_session_creates_new_session_and_copies_roster():
    storage = GcsStorageManager(mock_mode=True)
    storage.create_session("orig_session", project_id="prj_test")
    storage.save_project_character(
        "prj_test",
        {"role_id": "Role A", "name": "Harry", "reference_url": "https://img.jpg"},
    )
    storage.save_session_roster(
        "orig_session",
        [{"role_id": "Role A", "name": "Harry", "reference_url": "https://img.jpg"}],
    )

    res = storage.fork_session(
        source_session="orig_session",
        new_session="orig_session_v2",
        project_id="prj_test",
        copy_roster=True,
    )

    assert res["success"] is True
    assert res["session_name"] == "orig_session_v2"
    assert res["parent_session_name"] == "orig_session"
    assert res["project_id"] == "prj_test"
    assert res["gcs_uri"].startswith("gs://")
    assert "orig_session_v2" in storage.list_sessions("prj_test")

    # Check manifest was created and stored in mock cache
    manifest = storage.get_session_manifest("orig_session_v2", project_id="prj_test")
    assert manifest is not None
    assert manifest["session_name"] == "orig_session_v2"
    assert manifest["parent_session"] == "orig_session"
    assert manifest["copied_from"] == "orig_session"
    assert manifest["iteration_number"] == 2
    assert "created_at" in manifest

    # Check roster was copied to new session
    copied_roster = storage.load_session_roster("orig_session_v2")
    assert copied_roster is not None
    assert len(copied_roster) == 1
    assert copied_roster[0]["name"] == "Harry"


def test_fork_session_iteration_number_logic():
    storage = GcsStorageManager(mock_mode=True)
    storage.create_session("shot_v1", project_id="prj_iter")

    # Fork shot_v1 -> shot_v2 (explicit version in name)
    res_v2 = storage.fork_session(
        source_session="shot_v1",
        new_session="shot_v2",
        project_id="prj_iter",
    )
    assert res_v2["success"] is True
    manifest_v2 = storage.get_session_manifest("shot_v2", project_id="prj_iter")
    assert manifest_v2 is not None
    assert manifest_v2["iteration_number"] == 2

    # Fork shot_v2 -> shot_v3 (explicit version in name)
    res_v3 = storage.fork_session(
        source_session="shot_v2",
        new_session="shot_v3",
        project_id="prj_iter",
    )
    assert res_v3["success"] is True
    manifest_v3 = storage.get_session_manifest("shot_v3", project_id="prj_iter")
    assert manifest_v3 is not None
    assert manifest_v3["iteration_number"] == 3

    # Fork shot_v3 -> custom_fork (no version in name; should auto-increment parent's iteration)
    res_custom = storage.fork_session(
        source_session="shot_v3",
        new_session="custom_fork",
        project_id="prj_iter",
    )
    assert res_custom["success"] is True
    manifest_custom = storage.get_session_manifest("custom_fork", project_id="prj_iter")
    assert manifest_custom is not None
    assert manifest_custom["iteration_number"] == 4

    # Fork an unversioned parent without manifest -> default to 2
    storage.create_session("unversioned_base", project_id="prj_iter")
    res_unversioned = storage.fork_session(
        source_session="unversioned_base",
        new_session="unversioned_child",
        project_id="prj_iter",
    )
    assert res_unversioned["success"] is True
    manifest_unversioned = storage.get_session_manifest("unversioned_child", project_id="prj_iter")
    assert manifest_unversioned is not None
    assert manifest_unversioned["iteration_number"] == 2


def test_fork_session_safe_identifier_validation():
    storage = GcsStorageManager(mock_mode=True)
    storage.create_session("valid_session", project_id="valid_project")

    invalid_identifiers = [
        "../traversal",
        "..\\traversal",
        "has/slash",
        "has\\backslash",
        "null\x00byte",
        "spaces not allowed",
        "",
        "   ",
        "special!chars@#$",
    ]

    for bad_id in invalid_identifiers:
        with pytest.raises(ValueError):
            storage.fork_session(
                source_session="valid_session",
                new_session=bad_id,
                project_id="valid_project",
            )

        with pytest.raises(ValueError):
            storage.fork_session(
                source_session=bad_id,
                new_session="valid_session_v2",
                project_id="valid_project",
            )

        with pytest.raises(ValueError):
            storage.fork_session(
                source_session="valid_session",
                new_session="valid_session_v2",
                project_id=bad_id,
            )


def test_fork_session_identical_source_and_target_raises():
    storage = GcsStorageManager(mock_mode=True)
    storage.create_session("s1", project_id="prj_identical")

    with pytest.raises(
        ValueError, match="Target session 's1' cannot be identical to source session."
    ):
        storage.fork_session(
            source_session="s1",
            new_session="s1",
            project_id="prj_identical",
        )


def test_validate_safe_identifier_standalone():
    assert validate_safe_identifier("clean_session-123") == "clean_session-123"
    assert validate_safe_identifier("Project_Alpha") == "Project_Alpha"

    with pytest.raises(ValueError, match="path traversal"):
        validate_safe_identifier("../escaped")

    with pytest.raises(ValueError):
        validate_safe_identifier("")


def test_fork_session_copy_roster_false():
    storage = GcsStorageManager(mock_mode=True)
    storage.create_session("parent_sess", project_id="prj_test")
    storage.save_session_roster(
        "parent_sess",
        [{"role_id": "Role A", "name": "Gandalf"}],
    )

    res = storage.fork_session(
        source_session="parent_sess",
        new_session="child_sess",
        project_id="prj_test",
        copy_roster=False,
    )
    assert res["success"] is True

    # Roster should NOT be copied to child_sess
    assert storage.load_session_roster("child_sess") is None
    manifest = storage.get_session_manifest("child_sess", project_id="prj_test")
    assert manifest is not None
    assert "roster" not in manifest


def test_copy_session_roster_direct():
    storage = GcsStorageManager(mock_mode=True)
    roster_data = [
        {"role_id": "Role 1", "name": "Neo"},
        {"role_id": "Role 2", "name": "Trinity"},
    ]
    storage.save_session_roster("matrix_v1", roster_data)

    # Direct copy
    copied = storage.copy_session_roster("matrix_v1", "matrix_v2", project_id="cyber_prj")
    assert copied == roster_data
    assert storage.load_session_roster("matrix_v2") == roster_data

    # Copying from non-existent session returns None
    assert storage.copy_session_roster("non_existent", "target") is None


def test_copy_session_roster_fallback_character_roles():
    storage = GcsStorageManager(mock_mode=True)
    storage.create_session("sess_roles_list", project_id="roles_prj")
    # Manually store a manifest with character_roles as a list
    manifest_list = {
        "session_name": "sess_roles_list",
        "character_roles": [{"role_id": "Hero", "name": "Arthur"}],
    }
    storage._mock_session_manifests["roles_prj/sess_roles_list"] = manifest_list

    copied = storage.copy_session_roster("sess_roles_list", "sess_target_1", project_id="roles_prj")
    assert copied == [{"role_id": "Hero", "name": "Arthur"}]

    # Test with character_roles as a dict
    storage.create_session("sess_roles_dict", project_id="roles_prj")
    manifest_dict = {
        "session_name": "sess_roles_dict",
        "character_roles": {"hero": {"role_id": "Hero", "name": "Lancelot"}},
    }
    storage._mock_session_manifests["roles_prj/sess_roles_dict"] = manifest_dict

    copied_dict = storage.copy_session_roster(
        "sess_roles_dict", "sess_target_2", project_id="roles_prj"
    )
    assert copied_dict == [{"role_id": "Hero", "name": "Lancelot"}]


def test_fork_session_cloud_mode():
    storage = GcsStorageManager(bucket_name="cloud-bucket", mock_mode=False)
    mock_bucket = MagicMock()
    mock_client = MagicMock()
    storage._bucket = mock_bucket
    storage._client = mock_client

    uploaded_blobs: dict[str, str | bytes] = {}

    def mock_blob(name: str):
        blob = MagicMock()
        blob.name = name

        def upload_from_string(data, content_type=None, timeout=None):
            uploaded_blobs[name] = data

        blob.upload_from_string.side_effect = upload_from_string

        # Manifest reading behavior
        if name == "projects/prj_cloud/sessions/source_sess/manifest.json":
            blob.exists.return_value = True
            blob.download_as_text.return_value = json.dumps(
                {
                    "session_name": "source_sess",
                    "iteration_number": 1,
                    "character_roles": [{"role_id": "Role A", "name": "CloudHero"}],
                }
            )
        elif name == "projects/prj_cloud/sessions/source_sess/characters/roster.json":
            blob.exists.return_value = True
            blob.download_as_text.return_value = json.dumps(
                [{"role_id": "Role A", "name": "CloudHero"}]
            )
        else:
            blob.exists.return_value = False

        return blob

    mock_bucket.blob.side_effect = mock_blob
    mock_bucket.list_blobs.return_value = []

    res = storage.fork_session(
        source_session="source_sess",
        new_session="source_sess_v2",
        project_id="prj_cloud",
        copy_roster=True,
    )

    assert res["success"] is True
    assert res["session_name"] == "source_sess_v2"
    assert res["parent_session_name"] == "source_sess"

    # Verify keep blob and manifest blob were uploaded
    assert "projects/prj_cloud/sessions/source_sess_v2/.keep" in uploaded_blobs
    assert "projects/prj_cloud/sessions/source_sess_v2/manifest.json" in uploaded_blobs

    uploaded_manifest = json.loads(
        uploaded_blobs["projects/prj_cloud/sessions/source_sess_v2/manifest.json"]
    )
    assert uploaded_manifest["session_name"] == "source_sess_v2"
    assert uploaded_manifest["parent_session"] == "source_sess"
    assert uploaded_manifest["iteration_number"] == 2
