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

"""Decide how recognized grid tiles should behave for follow-up actions.

Modern Midjourney models treat split grid tiles as the user-facing stand-in for the
promoted single-image surface, even though Midjourney still requires an internal
`U#` hop before many solo-only actions. Older models keep the historical tile versus
upscale distinction. This module centralizes those rules so submission, indexing,
and runtime validation do not drift.
"""

from __future__ import annotations

import re

from mutiny.types import JobAction, TileFollowUpMode

_MODERN_DIRECT_TILE_ACTIONS = frozenset(
    {
        JobAction.UPSCALE,
        JobAction.VARIATION,
        JobAction.VARY_STRONG,
    }
)

_MODERN_PROMOTION_REQUIRED_ACTIONS = frozenset(
    {
        JobAction.VARY_SUBTLE,
        JobAction.UPSCALE_V7_2X_SUBTLE,
        JobAction.UPSCALE_V7_2X_CREATIVE,
        JobAction.ZOOM_OUT_2X,
        JobAction.ZOOM_OUT_1_5X,
        JobAction.PAN_LEFT,
        JobAction.PAN_RIGHT,
        JobAction.PAN_UP,
        JobAction.PAN_DOWN,
        JobAction.ANIMATE_HIGH,
        JobAction.ANIMATE_LOW,
        JobAction.CUSTOM_ZOOM,
        JobAction.INPAINT,
    }
)

_VERSION_FLAG_RE = re.compile(r"--(?:v|version)\s+(?P<value>[^\s]+)", re.IGNORECASE)
_NIJI_FLAG_RE = re.compile(r"--niji\s+(?P<value>[^\s]+)", re.IGNORECASE)
_NUMERIC_PREFIX_RE = re.compile(r"(?P<major>\d+)")


def resolve_tile_follow_up_mode(prompt_text: str | None) -> TileFollowUpMode:
    """Return the tile follow-up mode implied by one originating prompt.

    The modern/default path is the mainline:
    - explicit Midjourney `v5+`
    - explicit `Niji 5+`
    - prompts with no explicit version/model flag

    Legacy behavior is reserved for explicitly old model selections only.
    """

    prompt_text = prompt_text or ""
    explicit_versions = [match.group("value") for match in _VERSION_FLAG_RE.finditer(prompt_text)]
    explicit_niji_versions = [match.group("value") for match in _NIJI_FLAG_RE.finditer(prompt_text)]

    if any(_is_legacy_version(value) for value in explicit_versions):
        return TileFollowUpMode.LEGACY
    if any(_is_legacy_version(value) for value in explicit_niji_versions):
        return TileFollowUpMode.LEGACY
    return TileFollowUpMode.MODERN


def is_direct_tile_action(action: JobAction, *, mode: TileFollowUpMode) -> bool:
    """Return whether one action can run directly from a recognized grid tile."""

    if mode is TileFollowUpMode.LEGACY:
        return action in {JobAction.UPSCALE, JobAction.VARIATION, JobAction.VARY_STRONG}
    return action in _MODERN_DIRECT_TILE_ACTIONS


def requires_tile_promotion(action: JobAction, *, mode: TileFollowUpMode) -> bool:
    """Return whether one tile action needs an internal `U#` hop first."""

    if mode is TileFollowUpMode.LEGACY:
        return False
    return action in _MODERN_PROMOTION_REQUIRED_ACTIONS


def is_tile_capable_action(action: JobAction) -> bool:
    """Return whether one action can originate from a recognized grid tile at all."""

    return action in _MODERN_DIRECT_TILE_ACTIONS | _MODERN_PROMOTION_REQUIRED_ACTIONS


def _is_legacy_version(value: str) -> bool:
    """Return whether one version token selects an explicitly old model."""

    match = _NUMERIC_PREFIX_RE.match((value or "").strip().lower())
    if match is None:
        return False
    try:
        major = int(match.group("major"))
    except ValueError:
        return False
    return major < 5


__all__ = [
    "TileFollowUpMode",
    "is_direct_tile_action",
    "is_tile_capable_action",
    "requires_tile_promotion",
    "resolve_tile_follow_up_mode",
]
