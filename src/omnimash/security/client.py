"""Client factory and connection management for Google Cloud Model Armor."""

import logging
import threading
from typing import TYPE_CHECKING, Any

from google.api_core.client_options import ClientOptions

try:
    from google.cloud import modelarmor_v1

    _MODEL_ARMOR_AVAILABLE = True
except ImportError:
    modelarmor_v1 = None  # type: ignore[assignment]
    _MODEL_ARMOR_AVAILABLE = False

if TYPE_CHECKING:
    from google.cloud.modelarmor_v1 import (
        ModelArmorAsyncClient as ModelArmorAsyncClientType,
        ModelArmorClient as ModelArmorClientType,
    )

logger = logging.getLogger("omnimash.security.client")

_CLIENT_CACHE: dict[tuple[str, Any], Any] = {}
_ASYNC_CLIENT_CACHE: dict[tuple[str, Any], Any] = {}
_CACHE_LOCK = threading.Lock()


def is_model_armor_available() -> bool:
    """Returns True if the google-cloud-modelarmor package is installed and importable."""
    return _MODEL_ARMOR_AVAILABLE


def get_model_armor_endpoint(location: str) -> str:
    """Returns the regional Model Armor endpoint for a given GCP location."""
    return f"modelarmor.{location}.rep.googleapis.com"


def get_model_armor_client(
    location: str | None = None,
    credentials: Any | None = None,
) -> "ModelArmorClientType | Any":
    """Returns a cached synchronous ModelArmorClient targeting the regional endpoint.

    Args:
        location: GCP region (e.g. 'us-central1'). Defaults to settings.model_armor_location.
        credentials: Optional Google Auth credentials object.

    Returns:
        modelarmor_v1.ModelArmorClient instance.
    """
    if not _MODEL_ARMOR_AVAILABLE or modelarmor_v1 is None:
        raise ImportError(
            "google-cloud-modelarmor is not installed. Install it with: "
            "uv add 'google-cloud-modelarmor>=0.7.2'"
        )

    from omnimash.config import settings

    effective_loc = location or getattr(settings, "model_armor_location", "us-central1")
    cache_key = (effective_loc, credentials)

    with _CACHE_LOCK:
        if cache_key not in _CLIENT_CACHE:
            endpoint = get_model_armor_endpoint(effective_loc)
            client_options = ClientOptions(api_endpoint=endpoint)
            logger.info(
                "Initializing synchronous ModelArmorClient for location %s (endpoint: %s)",
                effective_loc,
                endpoint,
            )
            _CLIENT_CACHE[cache_key] = modelarmor_v1.ModelArmorClient(
                credentials=credentials,
                client_options=client_options,
            )

        return _CLIENT_CACHE[cache_key]


def get_model_armor_async_client(
    location: str | None = None,
    credentials: Any | None = None,
) -> "ModelArmorAsyncClientType | Any":
    """Returns a cached asynchronous ModelArmorAsyncClient targeting the regional endpoint.

    Args:
        location: GCP region (e.g. 'us-central1'). Defaults to settings.model_armor_location.
        credentials: Optional Google Auth credentials object.

    Returns:
        modelarmor_v1.ModelArmorAsyncClient instance.
    """
    if not _MODEL_ARMOR_AVAILABLE or modelarmor_v1 is None:
        raise ImportError(
            "google-cloud-modelarmor is not installed. Install it with: "
            "uv add 'google-cloud-modelarmor>=0.7.2'"
        )

    from omnimash.config import settings

    effective_loc = location or getattr(settings, "model_armor_location", "us-central1")
    cache_key = (effective_loc, credentials)

    with _CACHE_LOCK:
        if cache_key not in _ASYNC_CLIENT_CACHE:
            endpoint = get_model_armor_endpoint(effective_loc)
            client_options = ClientOptions(api_endpoint=endpoint)
            logger.info(
                "Initializing asynchronous ModelArmorAsyncClient for location %s (endpoint: %s)",
                effective_loc,
                endpoint,
            )
            _ASYNC_CLIENT_CACHE[cache_key] = modelarmor_v1.ModelArmorAsyncClient(
                credentials=credentials,
                client_options=client_options,
            )

        return _ASYNC_CLIENT_CACHE[cache_key]


def close_model_armor_clients() -> None:
    """Closes all cached synchronous ModelArmorClient instances and clears the cache."""
    with _CACHE_LOCK:
        for client in _CLIENT_CACHE.values():
            try:
                if hasattr(client, "transport") and hasattr(client.transport, "close"):
                    client.transport.close()
            except Exception as err:
                logger.debug("Error closing ModelArmorClient transport: %s", err)
        _CLIENT_CACHE.clear()


async def close_model_armor_async_clients() -> None:
    """Closes all cached asynchronous ModelArmorAsyncClient instances and clears the cache."""
    with _CACHE_LOCK:
        for client in _ASYNC_CLIENT_CACHE.values():
            try:
                if hasattr(client, "transport") and hasattr(client.transport, "close"):
                    close_coro = client.transport.close()
                    if close_coro is not None:
                        await close_coro
            except Exception as err:
                logger.debug("Error closing ModelArmorAsyncClient transport: %s", err)
        _ASYNC_CLIENT_CACHE.clear()
