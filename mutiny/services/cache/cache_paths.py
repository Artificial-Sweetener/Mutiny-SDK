"""Stable cache-path helpers shared by core runtime and host integrations."""

from __future__ import annotations

import os
from pathlib import Path


def cache_base_directory() -> Path:
    """Return the stable per-user base used for relative cache paths."""

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data)
    return Path.home()


def resolve_cache_directory(path: str | Path) -> Path:
    """Resolve one configured cache directory without depending on process cwd."""

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (cache_base_directory() / candidate).resolve()


__all__ = ["cache_base_directory", "resolve_cache_directory"]
