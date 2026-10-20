"""Shared GenAI client factory and cache for OmniMash prompt and storyboard agents."""

from __future__ import annotations

import logging
import os
from typing import Any

from omnimash.config import settings

logger = logging.getLogger(__name__)


def get_genai_client(location: str = "global") -> Any:
    """Returns a google-genai Client instance configured for the specified location.

    Adheres to Gemini Omni Flash and Vertex AI global/regional endpoint rules.
    """
    try:
        from google import genai

        api_key = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or getattr(settings, "gemini_api_key", None)
            or getattr(settings, "google_api_key", None)
        )
        project = os.environ.get(
            "GOOGLE_CLOUD_PROJECT",
            getattr(settings, "google_cloud_project", "hybrid-vertex"),
        )
        if api_key:
            return genai.Client(api_key=api_key)
        return genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )
    except Exception as exc:
        logger.warning("Failed to initialize GenAI client for location '%s': %s", location, exc)
        return None


__all__ = ["get_genai_client"]
