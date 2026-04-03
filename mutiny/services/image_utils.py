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

"""Helpers for Midjourney image payloads, data URLs, and image hashing."""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from typing import Optional, cast

import cv2
import numpy as np


@dataclass
class DataUrl:
    mime_type: str
    data: bytes


def parse_data_url(data_url: str) -> Optional[DataUrl]:
    match = re.match(r"data:(.*?);base64,(.*)", data_url)
    if not match:
        return None
    mime_type = match.group(1)
    base64_data = match.group(2)
    try:
        data = base64.b64decode(base64_data)
    except Exception:
        return None
    return DataUrl(mime_type=mime_type, data=data)


def rgb_sha256(rgb_bytes: bytes) -> str:
    """Return the SHA256 hex digest of RGB pixel bytes."""

    return hashlib.sha256(rgb_bytes).hexdigest()


def phash_to_int(phash: object) -> int:
    """Convert an integer-like or hex-string perceptual hash to an integer."""

    if isinstance(phash, str):
        try:
            return int(phash, 16)
        except Exception:
            return int(phash)
    if isinstance(phash, (bytes, bytearray)):
        return int(phash)
    try:
        return int(cast(int | float | str, phash))
    except Exception:
        return int(str(phash), 16)


def compute_phash_array(rgb: object, *, hash_size: int = 8, highfreq_factor: int = 4) -> int | None:
    """Compute a perceptual hash for an RGB array and normalize to int."""
    try:
        arr = np.asarray(rgb)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        size = hash_size * highfreq_factor
        resized = cv2.resize(gray, (size, size), interpolation=cv2.INTER_LANCZOS4)
        dct = cv2.dct(resized.astype(np.float32))
        lowfreq = dct[:hash_size, :hash_size]
        flat = lowfreq.flatten()
        if flat.size <= 1:
            return None
        median = float(np.median(flat[1:].astype(np.float32).tolist()))
        diff = lowfreq > median
        bits = 0
        for value in diff.flatten():
            bits = (bits << 1) | int(bool(value))
        return bits
    except Exception:
        return None


__all__ = [
    "DataUrl",
    "parse_data_url",
    "rgb_sha256",
    "phash_to_int",
    "compute_phash_array",
]
