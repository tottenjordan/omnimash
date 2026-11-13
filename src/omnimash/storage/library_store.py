"""Vault CRUD helpers for characters, character sheets, and products stored in GCS."""

from __future__ import annotations

import base64
from collections.abc import Callable
import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


def slugify(name: str) -> str:
    """Converts a character or entity name into a normalized lowercase slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return slug or "character"


def _upsert_project_cache(
    storage: Any,
    cache: dict[str, list[dict[str, Any]]],
    project_id: str,
    item: dict[str, Any],
    key_fn: Callable[[dict[str, Any]], str],
) -> None:
    """Registers project_id and upserts an item into a project-scoped mock cache list."""
    if project_id not in storage._mock_projects:
        storage._mock_projects.append(project_id)
    if project_id not in cache:
        cache[project_id] = []
    item_key = key_fn(item)
    existing = [entry for entry in cache[project_id] if key_fn(entry) != item_key]
    existing.append(item)
    cache[project_id] = existing


def save_character(
    storage: Any,
    character: dict[str, Any],
    session_id: str | None = None,
    is_library: bool = True,
    project_id: str | None = None,
) -> tuple[str, str]:
    """Persists character definitions as JSON in GCS under project, library, or session scope."""
    name = str(character.get("name", "character"))
    slug = storage._slugify(name)
    if project_id:
        blob_path = f"projects/{project_id}/saved_characters/{slug}.json"
    elif is_library or session_id is None:
        blob_path = f"library/characters/{slug}.json"
    else:
        blob_path = f"sessions/{session_id}/characters/{slug}.json"

    pub_url, gcs_uri = storage._upload_json_payload(
        blob_path,
        character,
        mock_cache_dict=storage._mock_characters,
        mock_cache_key=slug,
    )

    if project_id:
        _upsert_project_cache(
            storage,
            storage._mock_project_characters,
            project_id,
            character,
            lambda c: storage._slugify(str(c.get("name", ""))),
        )

    return pub_url, gcs_uri


def save_character_sheet(
    storage: Any,
    image_data: str | bytes,
    custom_name: str,
    session_id: str | None = None,
    project_id: str | None = None,
) -> tuple[str, str]:
    """Saves a character reference sheet image to GCS under project or session scope."""
    name_base = (
        custom_name.removesuffix(".png") if isinstance(custom_name, str) else "character_sheet_v1"
    )
    clean_name = storage._slugify(name_base) or "character_sheet_v1"

    filename = f"{clean_name}.png"
    if project_id:
        if session_id:
            blob_path = f"projects/{project_id}/sessions/{session_id}/character_sheets/{filename}"
        else:
            blob_path = f"projects/{project_id}/saved_reference_sheets/{filename}"
    elif session_id:
        blob_path = f"sessions/{session_id}/character_sheets/{filename}"
    else:
        blob_path = f"character_sheets/{filename}"

    raw_bytes = b""
    if isinstance(image_data, bytes):
        raw_bytes = image_data
    elif isinstance(image_data, str):
        from omnimash.engine.media_loader import fetch_media_bytes

        raw_bytes, _ = fetch_media_bytes(image_data, storage=storage)
        if not raw_bytes:
            # Fallback: try decoding as raw base64 string
            try:
                raw_bytes = base64.b64decode(image_data)
            except Exception as exc:
                logger.warning(
                    "save_character_sheet fallback base64 decode failed for %s: %s",
                    clean_name,
                    exc,
                )

    if not raw_bytes and storage.mock_mode:
        raw_bytes = b"mock_character_sheet_bytes"

    storage.upload_bytes(raw_bytes, blob_path, content_type="image/png")
    pub_url = storage.get_public_url(blob_path)
    gcs_uri = storage.get_gcs_uri(blob_path)

    if project_id:
        sheet_meta = {
            "name": clean_name,
            "filename": filename,
            "url": pub_url,
            "gcs_uri": gcs_uri,
        }
        _upsert_project_cache(
            storage,
            storage._mock_project_reference_sheets,
            project_id,
            sheet_meta,
            lambda s: str(s.get("name", "")),
        )

    return pub_url, gcs_uri


def save_product(
    storage: Any,
    product: dict[str, Any],
    project_id: str | None = None,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Persists product definition JSON in GCS under project, session, or library scope."""
    name = str(product.get("name", "product"))
    slug = storage._slugify(name)
    if project_id:
        if session_id:
            blob_path = f"projects/{project_id}/sessions/{session_id}/products/{slug}.json"
        else:
            blob_path = f"projects/{project_id}/saved_products/{slug}.json"
    elif session_id:
        blob_path = f"sessions/{session_id}/products/{slug}.json"
    else:
        blob_path = f"library/products/{slug}.json"

    pub_url, gcs_uri = storage._upload_json_payload(blob_path, product)

    if project_id:
        _upsert_project_cache(
            storage,
            storage._mock_project_products,
            project_id,
            product,
            lambda p: storage._slugify(str(p.get("name", ""))),
        )

    return pub_url, gcs_uri


def save_project_character(
    storage: Any,
    project_id: str,
    character: dict[str, Any],
) -> tuple[str, str]:
    """Saves a character definition under a project in GCS."""
    return save_character(storage, character, project_id=project_id)


def list_project_characters(
    storage: Any,
    project_id: str = "default_project",
) -> list[dict[str, Any]]:
    """Lists character dicts from projects/{project_id}/saved_characters/ and legacy session subfolders."""
    characters: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()

    if not storage.mock_mode and storage._bucket:
        prefix = f"projects/{project_id}/saved_characters/"
        try:
            blobs = storage._bucket.list_blobs(prefix=prefix, timeout=storage.timeout)
            json_blobs = [b for b in blobs if getattr(b, "name", "").endswith(".json")]
            for data in storage._download_blobs_concurrently(json_blobs):
                slug = storage._slugify(str(data.get("name", "")))
                if slug not in seen_slugs:
                    seen_slugs.add(slug)
                    characters.append(data)
        except Exception as exc:
            logger.warning("list_project_characters failed on prefix %s: %s", prefix, exc)

        prefix_sessions = f"projects/{project_id}/sessions/"
        try:
            blobs = storage._bucket.list_blobs(prefix=prefix_sessions, timeout=storage.timeout)
            json_blobs = [
                b
                for b in blobs
                if "/characters/" in getattr(b, "name", "")
                and getattr(b, "name", "").endswith(".json")
            ]
            for data in storage._download_blobs_concurrently(json_blobs):
                slug = storage._slugify(str(data.get("name", "")))
                if slug not in seen_slugs:
                    seen_slugs.add(slug)
                    characters.append(data)
        except Exception as exc:
            logger.warning(
                "list_project_characters failed on session prefix %s: %s",
                prefix_sessions,
                exc,
            )

    if characters:
        return characters

    if project_id in storage._mock_project_characters:
        return storage._mock_project_characters[project_id]

    if project_id == "default_project":
        return list(storage._mock_characters.values())

    return []


def list_project_products(
    storage: Any,
    project_id: str = "default_project",
) -> list[dict[str, Any]]:
    """Lists product dicts from projects/{project_id}/saved_products/."""
    products: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()

    if not storage.mock_mode and storage._bucket:
        prefix = f"projects/{project_id}/saved_products/"
        try:
            blobs = storage._bucket.list_blobs(prefix=prefix, timeout=storage.timeout)
            for blob in blobs:
                if blob.name.endswith(".json"):
                    try:
                        data = json.loads(blob.download_as_text(timeout=storage.timeout))
                        if isinstance(data, dict):
                            slug = storage._slugify(str(data.get("name", "")))
                            if slug not in seen_slugs:
                                seen_slugs.add(slug)
                                products.append(data)
                    except Exception as exc:
                        logger.warning("Failed to load product blob %s: %s", blob.name, exc)
        except Exception as exc:
            logger.warning("list_project_products failed on prefix %s: %s", prefix, exc)

    if products:
        return products

    return storage._mock_project_products.get(project_id, [])


def list_project_reference_sheets(
    storage: Any,
    project_id: str = "default_project",
) -> list[dict[str, Any]]:
    """Lists turnaround/reference sheet dicts from projects/{project_id}/saved_reference_sheets/."""
    sheets: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    if not storage.mock_mode and storage._bucket:
        prefix = f"projects/{project_id}/saved_reference_sheets/"
        try:
            blobs = storage._bucket.list_blobs(prefix=prefix, timeout=storage.timeout)
            for blob in blobs:
                name = os.path.basename(blob.name)
                if name and name not in seen_names:
                    seen_names.add(name)
                    sheets.append(
                        {
                            "name": name.removesuffix(".png").removesuffix(".jpg"),
                            "filename": name,
                            "url": storage.get_public_url(blob.name),
                            "gcs_uri": storage.get_gcs_uri(blob.name),
                        }
                    )
        except Exception as exc:
            logger.warning("list_project_reference_sheets failed on prefix %s: %s", prefix, exc)

    if sheets:
        return sheets

    return storage._mock_project_reference_sheets.get(project_id, [])


def list_characters(
    storage: Any,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    """Returns list of character dicts from library and session scope."""
    if not storage.mock_mode and storage._bucket:
        try:
            characters: list[dict[str, Any]] = []
            seen_slugs: set[str] = set()

            prefixes = ["library/characters/"]
            if session_id:
                prefixes.append(f"sessions/{session_id}/characters/")

            for prefix in prefixes:
                blobs = storage._bucket.list_blobs(prefix=prefix, timeout=storage.timeout)
                json_blobs = [
                    b
                    for b in blobs
                    if getattr(b, "name", "").endswith(".json")
                    and not getattr(b, "name", "").endswith("roster.json")
                ]
                for data in storage._download_blobs_concurrently(json_blobs):
                    slug = storage._slugify(str(data.get("name", "")))
                    if slug not in seen_slugs:
                        seen_slugs.add(slug)
                        characters.append(data)
                        storage._mock_characters[slug] = data
            if characters:
                return characters
        except Exception as exc:
            logger.warning("list_characters failed: %s", exc)

    return list(storage._mock_characters.values())


def load_character(
    storage: Any,
    slug: str,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    """Fetches character dict for a given slug from session scope, library scope, or mock cache."""
    clean_slug = storage._slugify(slug)

    paths_to_try: list[str] = []
    if session_id:
        paths_to_try.append(f"sessions/{session_id}/characters/{clean_slug}.json")
    paths_to_try.append(f"library/characters/{clean_slug}.json")

    for blob_path in paths_to_try:
        data = storage._download_json_payload(
            blob_path,
            mock_cache_dict=storage._mock_characters,
            mock_cache_key=clean_slug,
        )
        if isinstance(data, dict):
            return data

    if slug in storage._mock_characters:
        return storage._mock_characters[slug]
    if clean_slug in storage._mock_characters:
        return storage._mock_characters[clean_slug]

    for key, char in storage._mock_characters.items():
        if (
            key == clean_slug
            or key.startswith(f"{clean_slug}_")
            or storage._slugify(str(char.get("name", ""))) == clean_slug
        ):
            return char

    return None
