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

from mutiny.services.animate_prompt_builder import (
    build_video_prompt,
    normalize_animate_prompt_text,
)
from mutiny.types import AnimateMotion


def test_normalize_animate_prompt_text_collapses_whitespace():
    assert (
        normalize_animate_prompt_text("  camera   push\nthrough   fog  ")
        == "camera push through fog"
    )


def test_build_video_prompt_renders_expected_flags():
    prompt = build_video_prompt(
        start_frame_url="https://cdn.example/start.png",
        prompt_text="camera push through fog",
        motion=AnimateMotion.HIGH,
        end_frame_url="https://cdn.example/end.png",
        batch_size=4,
    )

    assert (
        prompt == "https://cdn.example/start.png camera push through fog --video --motion high "
        "--end https://cdn.example/end.png --bs 4"
    )


def test_build_video_prompt_omits_optional_tokens():
    prompt = build_video_prompt(
        start_frame_url="https://cdn.example/start.png",
        prompt_text="",
        motion=AnimateMotion.LOW,
    )

    assert prompt == "https://cdn.example/start.png --video --motion low"
