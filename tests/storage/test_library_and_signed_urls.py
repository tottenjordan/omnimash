"""Tests for extracted library_store and signed_urls storage helpers."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from omnimash.storage import library_store, signed_urls
from omnimash.storage.gcs import GcsStorageManager


def test_library_store_saves_and_lists_characters_sheets_and_products_via_upload_json_payload() -> (
    None
):
    storage = GcsStorageManager(bucket_name="test-vault-bucket", mock_mode=True)

    with patch.object(
        storage, "_upload_json_payload", wraps=storage._upload_json_payload
    ) as upload_spy:
        char_pub, char_uri = library_store.save_character(
            storage,
            {"name": "Neo Wizard", "role_id": "Role A", "description": "Trenchcoat mage"},
            project_id="proj_vault",
        )
        assert (
            char_uri
            == "gs://test-vault-bucket/projects/proj_vault/saved_characters/neo_wizard.json"
        )
        assert (
            char_pub
            == "https://storage.googleapis.com/test-vault-bucket/projects/proj_vault/saved_characters/neo_wizard.json"
        )

        # Also verify project helper & library-level save/load/list delegation
        proj_pub, proj_uri = storage.save_project_character(
            "proj_vault",
            {"name": "Morpheus Mentor", "role_id": "Role B"},
        )
        assert (
            proj_uri
            == "gs://test-vault-bucket/projects/proj_vault/saved_characters/morpheus_mentor.json"
        )
        assert "morpheus_mentor.json" in proj_pub

        lib_pub, lib_uri = storage.save_character(
            {"name": "Library Sage", "role_id": "Role C"},
            is_library=True,
        )
        assert lib_uri == "gs://test-vault-bucket/library/characters/library_sage.json"
        assert "library/characters/library_sage.json" in lib_pub

        # Character sheet
        sheet_pub, sheet_uri = storage.save_character_sheet(
            image_data=b"fake_png_bytes",
            custom_name="Neo Turnaround.png",
            project_id="proj_vault",
        )
        assert (
            sheet_uri
            == "gs://test-vault-bucket/projects/proj_vault/saved_reference_sheets/neo_turnaround.png"
        )
        assert "neo_turnaround.png" in sheet_pub

        # Product must delegate JSON serialization & upload to _upload_json_payload
        prod_pub, prod_uri = storage.save_product(
            {"name": "Red Pill Elixir", "tier": "legendary"},
            project_id="proj_vault",
        )
        assert (
            prod_uri
            == "gs://test-vault-bucket/projects/proj_vault/saved_products/red_pill_elixir.json"
        )
        assert "red_pill_elixir.json" in prod_pub

        product_upload_calls = [
            call
            for call in upload_spy.call_args_list
            if call.args
            and call.args[0] == "projects/proj_vault/saved_products/red_pill_elixir.json"
        ]
        assert len(product_upload_calls) == 1

    # Verify listing & loading delegation
    proj_chars = storage.list_project_characters("proj_vault")
    assert {c["name"] for c in proj_chars} == {"Neo Wizard", "Morpheus Mentor"}

    proj_sheets = storage.list_project_reference_sheets("proj_vault")
    assert len(proj_sheets) == 1
    assert proj_sheets[0]["name"] == "neo_turnaround"

    proj_prods = storage.list_project_products("proj_vault")
    assert len(proj_prods) == 1
    assert proj_prods[0]["name"] == "Red Pill Elixir"

    all_chars = storage.list_characters()
    assert any(c["name"] == "Library Sage" for c in all_chars)

    loaded = storage.load_character("library_sage")
    assert loaded is not None
    assert loaded["name"] == "Library Sage"


def test_save_character_sheet_logs_structured_warning_on_invalid_base64_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    storage = GcsStorageManager(bucket_name="test-vault-bucket", mock_mode=True)

    with caplog.at_level(logging.WARNING):
        pub_url, gcs_uri = storage.save_character_sheet(
            image_data="not-valid-b64",
            custom_name="broken_sheet",
            session_id="sess_warn",
        )

    assert gcs_uri == "gs://test-vault-bucket/sessions/sess_warn/character_sheets/broken_sheet.png"
    assert "broken_sheet.png" in pub_url
    warning_messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "save_character_sheet fallback base64 decode failed for broken_sheet:" in msg
        for msg in warning_messages
    )


def test_signed_url_helper_generates_7day_v4_share_and_download_urls_and_rejects_out_of_range_days() -> (
    None
):
    mock_storage = GcsStorageManager(
        bucket_name="test-signed-bucket", project_id="test-proj", mock_mode=True
    )

    for bad_days in (0, 8, -1):
        with pytest.raises(ValueError, match="Expiration days must be between 1 and 7"):
            signed_urls.create_v4_shareable_link(
                mock_storage,
                "gs://test-signed-bucket/sessions/s1/final_masters/cut.mp4",
                expiration_days=bad_days,
            )

    mock_res = signed_urls.create_v4_shareable_link(
        mock_storage,
        blob_path_or_uri="gs://test-signed-bucket/sessions/s1/final_masters/cut.mp4",
        expiration_days=7,
        master_title="final_cut",
    )
    assert mock_res["success"] is True
    assert mock_res["lifespan_days"] == 7
    assert "X-Goog-Expires=604800" in mock_res["share_url"]
    assert "X-Goog-Expires=604800" in mock_res["download_url"]
    assert "response-content-disposition=inline" in mock_res["share_url"]
    assert "attachment" in mock_res["download_url"]
    assert "final_cut.mp4" in mock_res["download_url"]

    # Live mode V4 signing path via bucket.blob(...).generate_signed_url
    live_storage = GcsStorageManager(
        bucket_name="test-signed-bucket", project_id="test-proj", mock_mode=False
    )
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.generate_signed_url.side_effect = [
        "https://storage.googleapis.com/test-signed-bucket/cut.mp4?X-Goog-Signature=inline_sig",
        "https://storage.googleapis.com/test-signed-bucket/cut.mp4?X-Goog-Signature=dl_sig",
    ]
    mock_bucket.blob.return_value = mock_blob
    live_storage._bucket_instance = mock_bucket

    live_res = live_storage.create_shareable_link(
        blob_path_or_uri="gs://test-signed-bucket/cut.mp4",
        expiration_days=7,
        master_title="final_cut",
    )
    assert live_res["success"] is True
    assert live_res["signed_v4"] is True
    assert live_res["share_url"].endswith("inline_sig")
    assert live_res["download_url"].endswith("dl_sig")
    assert mock_blob.generate_signed_url.call_count == 2
