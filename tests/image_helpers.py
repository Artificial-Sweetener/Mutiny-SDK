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

import cv2
import numpy as np


def encode_image(
    array: np.ndarray, *, extension: str = ".png", params: list[int] | None = None
) -> bytes:
    ok, buffer = cv2.imencode(extension, array, params or [])
    if not ok:
        raise ValueError(f"Failed to encode image as {extension}")
    return buffer.tobytes()


def decode_rgb(image_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    decoded = cv2.imdecode(array, cv2.IMREAD_UNCHANGED)
    if decoded is None:
        raise ValueError("Failed to decode image bytes")
    if decoded.ndim == 2:
        return cv2.cvtColor(decoded, cv2.COLOR_GRAY2RGB)
    if decoded.shape[2] == 4:
        decoded = cv2.cvtColor(decoded, cv2.COLOR_BGRA2RGBA)
        return decoded[:, :, :3]
    return cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)


def make_solid_png(
    *, size: tuple[int, int] = (2, 2), color: tuple[int, int, int] = (255, 0, 0)
) -> bytes:
    width, height = size
    rgb = np.zeros((height, width, 3), dtype=np.uint8)
    rgb[:, :] = color
    return encode_image(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def make_rect_mask_png(
    *,
    size: tuple[int, int] = (512, 512),
    rect: tuple[int, int, int, int] = (96, 96, 416, 416),
) -> bytes:
    width, height = size
    mask = np.zeros((height, width), dtype=np.uint8)
    left, top, right, bottom = rect
    mask[top:bottom, left:right] = 255
    return encode_image(mask, extension=".png")


def make_png_data_url(
    *,
    size: tuple[int, int] = (2, 2),
    color: tuple[int, int, int] = (255, 0, 0),
) -> str:
    encoded = base64.b64encode(make_solid_png(size=size, color=color)).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def make_mask_data_url(
    *,
    size: tuple[int, int] = (512, 512),
    rect: tuple[int, int, int, int] = (96, 96, 416, 416),
) -> str:
    encoded = base64.b64encode(make_rect_mask_png(size=size, rect=rect)).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def make_grid_png() -> bytes:
    rgb = np.zeros((100, 200, 3), dtype=np.uint8)
    rgb[0:50, 0:100] = (255, 0, 0)
    rgb[0:50, 100:200] = (0, 255, 0)
    rgb[50:100, 0:100] = (0, 0, 255)
    rgb[50:100, 100:200] = (255, 255, 0)
    return encode_image(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))


def rgb_pixel(image_bytes: bytes, x: int, y: int) -> tuple[int, int, int]:
    rgb = decode_rgb(image_bytes)
    pixel = rgb[y, x]
    return int(pixel[0]), int(pixel[1]), int(pixel[2])
