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
import logging
from typing import Optional

import cv2
import numpy as np

from .image_utils import parse_data_url

logger = logging.getLogger(__name__)


def encode_mask_to_webp_base64(data_url: str) -> Optional[str]:
    """Encode a mask data URL to base64-encoded WebP bytes."""

    parsed = parse_data_url(data_url)
    if not parsed:
        return None

    if parsed.mime_type.lower() == "image/webp":
        return base64.b64encode(parsed.data).decode("ascii")

    try:
        array = np.frombuffer(parsed.data, dtype=np.uint8)
        decoded = cv2.imdecode(array, cv2.IMREAD_UNCHANGED)
        if decoded is None:
            return None
        if decoded.ndim == 2:
            decoded = cv2.cvtColor(decoded, cv2.COLOR_GRAY2BGRA)
        elif decoded.shape[2] == 3:
            decoded = cv2.cvtColor(decoded, cv2.COLOR_BGR2BGRA)
        params = [cv2.IMWRITE_WEBP_QUALITY, 90]
        if hasattr(cv2, "IMWRITE_WEBP_LOSSLESS"):
            params.extend([cv2.IMWRITE_WEBP_LOSSLESS, 1])
        ok, buffer = cv2.imencode(".webp", decoded, params)
        if not ok:
            return None
        return base64.b64encode(buffer.tobytes()).decode("ascii")
    except Exception as exc:
        logger.debug("OpenCV WebP conversion failed", exc_info=exc)
        return None


__all__ = ["encode_mask_to_webp_base64"]
