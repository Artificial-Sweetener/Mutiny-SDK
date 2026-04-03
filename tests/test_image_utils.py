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

from mutiny.services.image_utils import compute_phash_array, phash_to_int, rgb_sha256
from tests.image_helpers import decode_rgb, make_solid_png


def test_rgb_sha256_deterministic():
    data = b"abc" * 5
    digest1 = rgb_sha256(data)
    digest2 = rgb_sha256(data)
    assert digest1 == digest2
    assert digest1 == hashlib.sha256(data).hexdigest()


def test_rgb_sha256_differs_on_content():
    assert rgb_sha256(b"a") != rgb_sha256(b"b")


def test_phash_to_int_handles_int_and_hex():
    assert phash_to_int(123) == 123
    assert phash_to_int("ff") == 255


def test_compute_phash_array_returns_int_for_rgb_array():
    phash = compute_phash_array(decode_rgb(make_solid_png(size=(8, 8), color=(50, 100, 150))))
    assert isinstance(phash, int)


def test_compute_phash_array_returns_none_on_invalid_input():
    assert compute_phash_array(object()) is None
