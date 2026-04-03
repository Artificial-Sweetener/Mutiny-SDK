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

"""Define shared result-shape rules for completed Midjourney job actions."""

from __future__ import annotations

from mutiny.domain.job import JobAction

_GRID_RESULT_ACTIONS = frozenset(
    {
        JobAction.IMAGINE,
        JobAction.VARIATION,
        JobAction.REROLL,
        JobAction.VARY_SUBTLE,
        JobAction.VARY_STRONG,
        JobAction.INPAINT,
        JobAction.BLEND,
        JobAction.PAN_LEFT,
        JobAction.PAN_RIGHT,
        JobAction.PAN_UP,
        JobAction.PAN_DOWN,
        JobAction.ZOOM_OUT_2X,
        JobAction.ZOOM_OUT_1_5X,
        JobAction.CUSTOM_ZOOM,
    }
)

_SINGLE_IMAGE_RESULT_ACTIONS = frozenset(
    {
        JobAction.UPSCALE,
        JobAction.UPSCALE_V7_2X_SUBTLE,
        JobAction.UPSCALE_V7_2X_CREATIVE,
        JobAction.ANIMATE_HIGH,
        JobAction.ANIMATE_LOW,
    }
)


def produces_grid_result(action: JobAction | None) -> bool:
    """Return whether the completed action yields a 2x2 Midjourney grid."""
    return action in _GRID_RESULT_ACTIONS


def produces_single_image_result(action: JobAction | None) -> bool:
    """Return whether the completed action yields one final image artifact."""
    return action in _SINGLE_IMAGE_RESULT_ACTIONS


__all__ = [
    "produces_grid_result",
    "produces_single_image_result",
]
