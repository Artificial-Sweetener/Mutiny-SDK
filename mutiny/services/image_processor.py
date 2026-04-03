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

"""Core OpenCV-backed image processing runtime used by Mutiny."""

from __future__ import annotations

import logging

import cv2
import numpy as np

from mutiny.interfaces.image import ImageProcessor, PNGBytes
from mutiny.services.image_utils import compute_phash_array, rgb_sha256

logger = logging.getLogger(__name__)


def decode_rgb(data: bytes) -> np.ndarray:
    """Decode encoded image bytes to a normalized RGB array."""

    arr = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError("Failed to decode image bytes")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    if image.shape[2] == 4:
        blue, green, red, alpha = cv2.split(image)
        alpha_scale = (alpha.astype(np.float32) / 255.0)[:, :, None]
        rgb = cv2.merge((red, green, blue)).astype(np.float32)
        return (rgb * alpha_scale).astype(np.uint8)
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def encode_png(rgb: np.ndarray) -> PNGBytes:
    """Encode an RGB array as PNG bytes."""

    ok, buffer = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    if not ok:
        raise ValueError("Failed to encode image as PNG")
    return buffer.tobytes()


class OpenCVImageProcessor(ImageProcessor):
    """Image processing runtime backed by OpenCV and NumPy."""

    def get_dimensions(self, data: bytes) -> tuple[int, int]:
        rgb = decode_rgb(data)
        height, width = rgb.shape[:2]
        return width, height

    def compute_digest(self, data: bytes) -> str:
        return rgb_sha256(decode_rgb(data).tobytes())

    def compute_phash(self, data: bytes) -> int | None:
        try:
            return compute_phash_array(decode_rgb(data))
        except Exception as exc:  # pragma: no cover - phash failures are non-fatal
            logger.debug("OpenCV phash failed", exc_info=exc)
            return None

    def crop_split_grid(self, data: bytes) -> list[PNGBytes]:
        rgb = decode_rgb(data)
        height, width = rgb.shape[:2]
        half_width = width // 2
        half_height = height // 2
        boxes = (
            (0, 0, half_width, half_height),
            (half_width, 0, width, half_height),
            (0, half_height, half_width, height),
            (half_width, half_height, width, height),
        )
        return [encode_png(rgb[top:bottom, left:right]) for left, top, right, bottom in boxes]


__all__ = ["OpenCVImageProcessor", "decode_rgb", "encode_png"]
