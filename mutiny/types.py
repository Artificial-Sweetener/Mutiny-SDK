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

"""Expose the supported public type surface for Mutiny consumers."""

from __future__ import annotations

from dataclasses import dataclass

from mutiny.domain.job import AnimateMotion, Job, JobAction, JobStatus, TileFollowUpMode
from mutiny.domain.progress import ProgressEvent
from mutiny.domain.result import Result
from mutiny.domain.tile import JobTile
from mutiny.services.cache.artifact_cache import RecognizedImageContext, RecognizedVideoContext


@dataclass(frozen=True)
class StyleReferenceImages:
    """Describe attached style-reference images for one imagine submission."""

    images: tuple[str, ...] = ()
    multipliers: tuple[float, ...] = ()


@dataclass(frozen=True)
class CharacterReferenceImages:
    """Describe attached character-reference images for one imagine submission."""

    images: tuple[str, ...] = ()


@dataclass(frozen=True)
class OmniReferenceImage:
    """Describe the single Omni Reference image for one imagine submission."""

    image: str


@dataclass(frozen=True)
class ImagineImageInputs:
    """Describe every attached image channel accepted by ``Mutiny.imagine``."""

    prompt_images: tuple[str, ...] = ()
    style_reference: StyleReferenceImages | None = None
    character_reference: CharacterReferenceImages | None = None
    omni_reference: OmniReferenceImage | None = None


__all__ = [
    "CharacterReferenceImages",
    "AnimateMotion",
    "ImagineImageInputs",
    "Job",
    "JobAction",
    "JobStatus",
    "JobTile",
    "OmniReferenceImage",
    "ProgressEvent",
    "RecognizedImageContext",
    "RecognizedVideoContext",
    "Result",
    "StyleReferenceImages",
    "TileFollowUpMode",
]
