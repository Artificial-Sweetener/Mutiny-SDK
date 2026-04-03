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

import hashlib

from mutiny.services.image_processor import OpenCVImageProcessor, decode_rgb
from tests.image_helpers import make_grid_png


def test_opencv_processor_computes_stable_digest(sample_png_bytes):
    processor = OpenCVImageProcessor()

    digest = processor.compute_digest(sample_png_bytes)

    assert digest == hashlib.sha256(decode_rgb(sample_png_bytes).tobytes()).hexdigest()


def test_opencv_processor_returns_phash_for_valid_image(sample_png_bytes):
    processor = OpenCVImageProcessor()

    assert isinstance(processor.compute_phash(sample_png_bytes), int)


def test_opencv_processor_splits_grid_into_four_tiles():
    processor = OpenCVImageProcessor()

    tiles = processor.crop_split_grid(make_grid_png())

    assert len(tiles) == 4
    assert all(processor.get_dimensions(tile) == (100, 50) for tile in tiles)


def test_opencv_processor_rejects_invalid_bytes():
    processor = OpenCVImageProcessor()

    try:
        processor.compute_digest(b"not-an-image")
    except ValueError as exc:
        assert "decode" in str(exc).lower()
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected invalid image bytes to raise ValueError")
