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

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProgressEvent:
    """Describe one transient in-flight update for a job.

    Known ``kind`` values currently include:

    - ``start`` for the first parsed Midjourney progress carrier
    - ``progress`` for later parsed Midjourney progress updates
    - ``promotion`` for Mutiny's internal modern tile-promotion hop
    """

    job_id: str
    kind: str
    status_text: Optional[str]
    prompt: Optional[str]
    progress_message_id: Optional[str]
    message_id: Optional[str]
    flags: Optional[int]
    image_url: Optional[str]
    message_hash: Optional[str]
    not_fast: Optional[bool]


__all__ = ["ProgressEvent"]
