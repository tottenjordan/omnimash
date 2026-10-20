"""Unit tests for Model Armor client caching, lifecycle teardown, and result model helpers."""

import threading
from unittest.mock import MagicMock
import pytest

from omnimash.security.client import (
    _ASYNC_CLIENT_CACHE,
    _CLIENT_CACHE,
    close_model_armor_async_clients,
    close_model_armor_clients,
    get_model_armor_client,
)
from omnimash.security.models import GuardrailResult


def test_guardrail_result_helpers():
    """Verify is_blocked property and to_dict serialization on GuardrailResult."""
    approved_res = GuardrailResult(is_approved=True, sanitized_prompt="clean prompt")
    assert approved_res.is_blocked is False
    assert approved_res.to_dict()["is_approved"] is True
    assert approved_res.to_dict()["sanitized_prompt"] == "clean prompt"

    blocked_res = GuardrailResult(
        is_approved=False,
        sanitized_prompt="",
        rejection_reason="Blocked",
        filter_match_state="MATCH_FOUND",
        triggers=["injection"],
    )
    assert blocked_res.is_blocked is True
    d = blocked_res.to_dict()
    assert d["is_approved"] is False
    assert d["filter_match_state"] == "MATCH_FOUND"
    assert d["triggers"] == ["injection"]


def test_client_cache_thread_safety_and_keying():
    """Verify concurrent threads receive the exact same cached client instance."""
    close_model_armor_clients()

    clients: list[object] = []
    errors: list[Exception] = []

    def _worker():
        try:
            c = get_model_armor_client("us-central1")
            clients.append(c)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(clients) == 8
    # All threads must share the exact same cached singleton
    assert all(c is clients[0] for c in clients)
    assert ("us-central1", None) in _CLIENT_CACHE


def test_close_model_armor_clients_clears_cache():
    """Verify close_model_armor_clients shuts down transports and flushes the cache."""
    # Seed cache with mock
    mock_client = MagicMock()
    _CLIENT_CACHE[("europe-west1", None)] = mock_client

    close_model_armor_clients()
    mock_client.transport.close.assert_called_once()
    assert len(_CLIENT_CACHE) == 0


@pytest.mark.anyio
async def test_close_model_armor_async_clients_clears_cache():
    """Verify async client teardown clears async cache."""
    mock_async_client = MagicMock()
    mock_transport = MagicMock()
    mock_async_client.transport = mock_transport
    _ASYNC_CLIENT_CACHE[("us-central1", None)] = mock_async_client

    await close_model_armor_async_clients()
    mock_transport.close.assert_called_once()
    assert len(_ASYNC_CLIENT_CACHE) == 0
