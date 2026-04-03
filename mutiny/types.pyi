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

from __future__ import annotations

from dataclasses import dataclass

from .domain.job import AnimateMotion, Job, JobAction, JobStatus, TileFollowUpMode  # noqa: TID251
from .domain.progress import ProgressEvent  # noqa: TID251
from .domain.result import Result  # noqa: TID251
from .domain.tile import JobTile  # noqa: TID251
from .services.cache.artifact_cache import (  # noqa: TID251
    RecognizedImageContext,
    RecognizedVideoContext,
)

@dataclass(frozen=True)
class StyleReferenceImages:
    images: tuple[str, ...] = ...
    multipliers: tuple[float, ...] = ...

@dataclass(frozen=True)
class CharacterReferenceImages:
    images: tuple[str, ...] = ...

@dataclass(frozen=True)
class OmniReferenceImage:
    image: str

@dataclass(frozen=True)
class ImagineImageInputs:
    prompt_images: tuple[str, ...] = ...
    style_reference: StyleReferenceImages | None = ...
    character_reference: CharacterReferenceImages | None = ...
    omni_reference: OmniReferenceImage | None = ...

__all__ = [
    "AnimateMotion",
    "CharacterReferenceImages",
    "ImagineImageInputs",
    "Job",
    "JobAction",
    "JobStatus",
    "OmniReferenceImage",
    "ProgressEvent",
    "RecognizedImageContext",
    "RecognizedVideoContext",
    "Result",
    "JobTile",
    "StyleReferenceImages",
    "TileFollowUpMode",
]
