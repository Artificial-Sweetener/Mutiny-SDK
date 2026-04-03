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

"""Normalize prompts for correlation when Midjourney rewrites attached image URLs."""

from __future__ import annotations

import re

_URL_TOKEN = re.compile(r"<?https?://[^\s>]+>?")
_TRAILING_REFERENCE_OPTIONS = re.compile(
    r"(?:\s+--sref\s+(?:<url>(?:::\S+)?\s*)+"
    r"|\s+--cref\s+(?:<url>\s*)+"
    r"|\s+--oref\s+<url>\s*)+\s*$",
    re.IGNORECASE,
)
_WHITESPACE = re.compile(r"\s+")
_VIDEO_ONE_OPTION = re.compile(r"(?i)(?<!\S)--video\s+1(?!\S)")
_VIDEO_FLAG = re.compile(r"(?i)(?<!\S)--video(?:\s+1)?(?!\S)")
_VIDEO_MOTION_FLAG = re.compile(r"(?i)(?<!\S)--motion\s+(low|high)(?!\S)")
_VIDEO_BATCH_FLAG = re.compile(r"(?i)(?<!\S)--bs\s+(\d+)(?!\S)")
_VIDEO_END_FLAG = re.compile(r"(?i)(?<!\S)--end\s+(\S+)")
_VIDEO_ASPECT_FLAG = re.compile(r"(?i)(?<!\S)--(?:aspect|ar)\s+\S+(?!\S)")


def normalize_prompt_for_matching(prompt: str | None) -> str:
    """Return a comparison-safe prompt string for Midjourney correlation.

    Midjourney rewrites some command text before echoing it back in Discord. The
    normalize step keeps correlation stable without changing the user-facing
    stored prompt text.
    """
    if not prompt:
        return ""
    without_urls = _URL_TOKEN.sub("<url>", prompt.strip())
    without_reference_options = _TRAILING_REFERENCE_OPTIONS.sub("", without_urls)
    canonical_video_option = _VIDEO_ONE_OPTION.sub("--video", without_reference_options)
    collapsed = _WHITESPACE.sub(" ", canonical_video_option).strip()
    return _canonicalize_prompt_video_flags(collapsed)


def _canonicalize_prompt_video_flags(prompt: str) -> str:
    """Return one stable form for prompt-video commands after Discord rewrites."""

    if not _VIDEO_FLAG.search(prompt):
        return prompt

    motion_match = _VIDEO_MOTION_FLAG.search(prompt)
    batch_match = _VIDEO_BATCH_FLAG.search(prompt)
    end_match = _VIDEO_END_FLAG.search(prompt)

    stripped = _VIDEO_END_FLAG.sub("", prompt)
    stripped = _VIDEO_BATCH_FLAG.sub("", stripped)
    stripped = _VIDEO_MOTION_FLAG.sub("", stripped)
    stripped = _VIDEO_FLAG.sub("", stripped)
    stripped = _VIDEO_ASPECT_FLAG.sub("", stripped)
    body = _WHITESPACE.sub(" ", stripped).strip()

    parts = []
    if body:
        parts.append(body)
    parts.append("--video")
    if motion_match is not None:
        parts.append(f"--motion {motion_match.group(1).lower()}")
    if end_match is not None:
        parts.append(f"--end {end_match.group(1)}")
    if batch_match is not None:
        parts.append(f"--bs {batch_match.group(1)}")
    return " ".join(parts).strip()


__all__ = ["normalize_prompt_for_matching"]
