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

"""Build Midjourney prompt text for prompt-based video generation."""

from __future__ import annotations

import re

from mutiny.types import AnimateMotion

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_animate_prompt_text(prompt: str | None) -> str:
    """Collapse animate prompt whitespace into Midjourney-safe single spaces."""
    return _WHITESPACE_RE.sub(" ", (prompt or "").strip())


def build_video_prompt(
    *,
    start_frame_url: str,
    prompt_text: str,
    motion: AnimateMotion,
    end_frame_url: str | None = None,
    batch_size: int | None = None,
) -> str:
    """Render the final prompt text for Midjourney's prompt-based video flow.

    Args:
        start_frame_url: Uploaded CDN URL for the required starting frame.
        prompt_text: Normalized optional user prompt text.
        motion: Public motion enum to translate into Midjourney flags.
        end_frame_url: Optional uploaded CDN URL for the ending frame.
        batch_size: Optional Midjourney batch size.

    Returns:
        The final prompt string submitted to Midjourney.
    """
    parts = [start_frame_url]
    if prompt_text:
        parts.append(prompt_text)
    parts.append("--video")
    parts.append(f"--motion {motion.value}")
    if end_frame_url:
        parts.append(f"--end {end_frame_url}")
    if batch_size is not None:
        parts.append(f"--bs {batch_size}")
    return " ".join(parts)


__all__ = ["build_video_prompt", "normalize_animate_prompt_text"]
