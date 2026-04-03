#    Mutiny - Unofficial Midjourney integration SDK
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""mutiny package public API."""

from __future__ import annotations

import importlib
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomllib

# Install a global logging scrubber to ensure secrets never hit logs
try:
    from .services.logging_utils import install_logging_scrubber

    install_logging_scrubber()
except Exception:
    # Best-effort; logging should not fail import
    pass

_LAZY_SYMBOLS = {
    "Mutiny": "mutiny.mutiny",
    "Config": "mutiny.config",
    "JobHandle": "mutiny.public_models",
    "JobSnapshot": "mutiny.public_models",
    "ProgressUpdate": "mutiny.public_models",
    "JobStatus": "mutiny.public_models",
    "ImageResolution": "mutiny.public_models",
    "VideoResolution": "mutiny.public_models",
    "ImageTile": "mutiny.public_models",
    "ImageOutput": "mutiny.public_models",
    "VideoOutput": "mutiny.public_models",
    "TextOutput": "mutiny.public_models",
}

_DISTRIBUTION_NAME = "mutiny-sdk"

__all__ = [
    "Mutiny",
    "Config",
    "JobHandle",
    "JobSnapshot",
    "ProgressUpdate",
    "JobStatus",
    "ImageResolution",
    "VideoResolution",
    "ImageTile",
    "ImageOutput",
    "VideoOutput",
    "TextOutput",
    "__version__",
]

if TYPE_CHECKING:
    from .config import Config  # noqa: F401
    from .mutiny import Mutiny  # noqa: F401
    from .public_models import (  # noqa: F401
        ImageOutput,
        ImageResolution,
        ImageTile,
        JobHandle,
        JobSnapshot,
        JobStatus,
        ProgressUpdate,
        TextOutput,
        VideoOutput,
        VideoResolution,
    )

    __version__: str


def _read_pyproject_version() -> str:
    """Return the package version from the repository pyproject fallback.

    This keeps ``mutiny.__version__`` available even when the package is imported
    directly from a source checkout without installed distribution metadata.
    """
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)
    return str(data["project"]["version"])


def _load_package_version() -> str:
    """Return the runtime package version from local source or metadata."""
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if pyproject_path.exists():
        return _read_pyproject_version()
    try:
        return metadata.version(_DISTRIBUTION_NAME)
    except metadata.PackageNotFoundError:
        return "0+unknown"


__version__ = _load_package_version()


def __getattr__(name: str) -> Any:
    module_name = _LAZY_SYMBOLS.get(name)
    if not module_name:
        raise AttributeError(f"module {__name__} has no attribute {name}")
    module = importlib.import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
