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

"""Test deterministic sampled-frame signatures for recognized Midjourney videos."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mutiny.services.video_signature import (
    VIDEO_SIGNATURE_VERSION,
    VideoSignatureService,
)

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")


def _make_frame(color: tuple[int, int, int], *, width: int = 64, height: int = 64):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :] = color
    return frame


def _encode_mp4(frames: list, *, fps: int) -> bytes:
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "test.mp4"
        writer = cv2.VideoWriter(
            str(path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (frames[0].shape[1], frames[0].shape[0]),
        )
        if not writer.isOpened():
            pytest.skip("OpenCV mp4 writer is not available in this environment.")
        try:
            for frame in frames:
                writer.write(frame)
        finally:
            writer.release()
        return path.read_bytes()


def test_video_signature_is_stable_for_same_decoded_frames():
    service = VideoSignatureService()
    frames = [
        _make_frame((0, 0, 255)),
        _make_frame((0, 255, 0)),
        _make_frame((255, 0, 0)),
        _make_frame((128, 128, 0)),
        _make_frame((0, 128, 128)),
        _make_frame((128, 0, 128)),
    ]
    slow_bytes = _encode_mp4(frames, fps=12)
    fast_bytes = _encode_mp4(frames, fps=24)

    slow_signature = service.compute_signature(slow_bytes)
    fast_signature = service.compute_signature(fast_bytes)

    assert slow_signature.version == VIDEO_SIGNATURE_VERSION
    assert slow_signature.digest == fast_signature.digest


def test_video_signature_distinguishes_base_render_from_extended_render():
    service = VideoSignatureService()
    base_frames = [
        _make_frame((0, 0, 255)),
        _make_frame((0, 64, 192)),
        _make_frame((0, 128, 128)),
        _make_frame((0, 192, 64)),
        _make_frame((0, 255, 0)),
        _make_frame((64, 192, 0)),
        _make_frame((128, 128, 0)),
        _make_frame((192, 64, 0)),
        _make_frame((255, 0, 0)),
    ]
    extended_frames = base_frames + [
        _make_frame((192, 0, 64)),
        _make_frame((128, 0, 128)),
        _make_frame((64, 0, 192)),
        _make_frame((0, 0, 255)),
    ]

    base_signature = service.compute_signature(_encode_mp4(base_frames, fps=24))
    extended_signature = service.compute_signature(_encode_mp4(extended_frames, fps=24))

    assert base_signature.digest != extended_signature.digest
