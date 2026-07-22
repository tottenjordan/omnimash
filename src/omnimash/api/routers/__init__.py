"""API routers grouped by domain: generation, characters, sessions, media."""

from omnimash.api.routers import characters, generation, media, sessions

__all__ = ["characters", "generation", "media", "sessions"]
