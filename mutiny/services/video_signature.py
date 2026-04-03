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

"""Compute deterministic sampled-frame signatures for recognized videos.

The signature deliberately ignores raw container bytes so harmless metadata or
wrapper changes do not break recognition. Only a few interior frames are
decoded because Mutiny needs stable identity for videos it produced, not full
fuzzy video matching.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass

import cv2
import numpy

VIDEO_SIGNATURE_VERSION = 1
_SAMPLE_POSITIONS = (0.30, 0.50, 0.70)


class VideoSignatureError(RuntimeError):
    """Base error for deterministic video-signature generation failures."""


@dataclass(frozen=True)
class VideoSignature:
    """Represent the persisted identity of one decoded video artifact."""

    digest: str
    version: int = VIDEO_SIGNATURE_VERSION


class VideoSignatureService:
    """Generate stable video signatures from a small interior frame sample."""

    def compute_signature(self, video_bytes: bytes) -> VideoSignature:
        """Return the normalized sampled-frame signature for one encoded video."""
        if not video_bytes:
            raise VideoSignatureError("Video bytes are required to compute a signature.")

        suffix = ".mp4"
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
                handle.write(video_bytes)
                temp_path = handle.name

            capture = cv2.VideoCapture(temp_path)
            try:
                if not capture.isOpened():
                    raise VideoSignatureError("Failed to open video for signature generation.")

                frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                if frame_count <= 0:
                    raise VideoSignatureError(
                        "Failed to read video frame count for signature generation."
                    )

                frame_indices = _normalized_frame_indices(frame_count)
                hasher = hashlib.sha256()
                hasher.update(f"video-signature:v{VIDEO_SIGNATURE_VERSION}".encode("ascii"))
                for frame_index in frame_indices:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        raise VideoSignatureError(
                            f"Failed to decode sampled video frame at index {frame_index}."
                        )
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    contiguous_rgb = numpy.ascontiguousarray(rgb_frame)
                    hasher.update(contiguous_rgb.tobytes())
                return VideoSignature(digest=hasher.hexdigest())
            finally:
                capture.release()
        finally:
            if temp_path is not None:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass


def _normalized_frame_indices(frame_count: int) -> tuple[int, ...]:
    """Return deterministic interior sample indices for one video length."""
    if frame_count <= 1:
        return (0,)

    if frame_count == 2:
        return (0, 1)

    upper_bound = max(1, frame_count - 2)
    indices: list[int] = []
    for position in _SAMPLE_POSITIONS:
        frame_index = int(round((frame_count - 1) * position))
        frame_index = max(1, min(upper_bound, frame_index))
        if frame_index not in indices:
            indices.append(frame_index)
    if not indices:
        indices.append(frame_count // 2)
    return tuple(indices)


__all__ = [
    "VIDEO_SIGNATURE_VERSION",
    "VideoSignature",
    "VideoSignatureError",
    "VideoSignatureService",
]
