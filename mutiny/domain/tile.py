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

from dataclasses import dataclass, field

from mutiny.domain.job import JobAction


@dataclass
class JobTile:
    """A logical slice of a Job's image output (e.g. one quadrant of a grid)."""

    job_id: str
    index: int  # 1-4 for grid tiles, 0 for single images
    original_action: JobAction
    image_bytes: bytes = field(repr=False)

    @property
    def is_grid_tile(self) -> bool:
        return self.index > 0
