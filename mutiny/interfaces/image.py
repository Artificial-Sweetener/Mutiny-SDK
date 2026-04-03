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

"""Image processing contract for Mutiny's internal image runtime."""

from __future__ import annotations

from typing import List, Protocol, runtime_checkable

RGBBytes = bytes
PNGBytes = bytes


@runtime_checkable
class ImageProcessor(Protocol):
    """Image processing contract used by Mutiny services.

    Args:
        data: Input image bytes. Methods specify whether these are raw RGB bytes or encoded bytes.

    Returns:
        Method-specific return types as described below.
    """

    def get_dimensions(self, data: bytes) -> tuple[int, int]:
        """Return `(width, height)` for encoded image bytes."""

    def compute_digest(self, data: bytes) -> str:
        """Return a SHA256 hex digest of raw RGB pixel bytes derived from the input image."""

    def compute_phash(self, data: bytes) -> int | None:
        """Return a perceptual hash integer for the input image; return None when unavailable."""

    def crop_split_grid(self, data: bytes) -> List[PNGBytes]:
        """Split a 2x2 image grid into four PNG-encoded tile byte blobs."""


__all__ = ["ImageProcessor", "RGBBytes", "PNGBytes"]
