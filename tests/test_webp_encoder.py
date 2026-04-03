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

import base64

from mutiny.services.webp_encoder import encode_mask_to_webp_base64
from tests.image_helpers import make_mask_data_url


def test_encoder_converts_png_mask_to_webp():
    out = encode_mask_to_webp_base64(make_mask_data_url())

    assert out is not None
    assert out.startswith("UklG")


def test_encoder_passthroughs_webp_input():
    original = encode_mask_to_webp_base64(make_mask_data_url())
    assert original is not None

    out = encode_mask_to_webp_base64(f"data:image/webp;base64,{original}")

    assert out == original


def test_encoder_rejects_invalid_data_url():
    assert encode_mask_to_webp_base64("not-a-data-url") is None


def test_encoder_rejects_invalid_image_payload():
    invalid = base64.b64encode(b"bad-image").decode("ascii")
    assert encode_mask_to_webp_base64(f"data:image/png;base64,{invalid}") is None
