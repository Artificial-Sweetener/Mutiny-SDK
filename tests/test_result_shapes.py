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

"""Test shared Midjourney result-shape classification rules."""

from __future__ import annotations

from mutiny.domain.job import JobAction
from mutiny.domain.result_shapes import (
    produces_grid_result,
    produces_single_image_result,
)


def test_grid_result_actions_match_current_midjourney_grid_outputs() -> None:
    """Keep all known grid-producing actions on the shared grid path."""
    for action in (
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
    ):
        assert produces_grid_result(action) is True
        assert produces_single_image_result(action) is False


def test_single_image_result_actions_match_current_follow_up_outputs() -> None:
    """Keep all known single-image actions on the shared single-image path."""
    for action in (
        JobAction.UPSCALE,
        JobAction.UPSCALE_V7_2X_SUBTLE,
        JobAction.UPSCALE_V7_2X_CREATIVE,
        JobAction.ANIMATE_HIGH,
        JobAction.ANIMATE_LOW,
    ):
        assert produces_single_image_result(action) is True
        assert produces_grid_result(action) is False


def test_none_does_not_match_any_result_shape() -> None:
    """Keep missing action values off both shape branches."""
    assert produces_grid_result(None) is False
    assert produces_single_image_result(None) is False
