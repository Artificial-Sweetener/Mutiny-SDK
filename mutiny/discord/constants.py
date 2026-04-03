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

"""Discord/Midjourney command metadata and interaction constants.

Values must mirror Midjourney application IDs/versions; changing them alters
wire payloads and would break behavior-freeze guarantees.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Final, Literal, TypedDict

CommandName = Literal["imagine", "describe", "blend"]


class CommandMeta(TypedDict):
    """Metadata for a Discord application command."""

    id: str
    version: str
    name: CommandName


class InteractionType(IntEnum):
    COMMAND = 2
    COMPONENT = 3
    MODAL_SUBMIT = 5


class ComponentType(IntEnum):
    BUTTON = 2


APPLICATION_ID: Final[str] = "936929561302675456"

ERROR_EMBED_COLOR: Final[int] = 15548997

CUSTOM_ZOOM_PROMPT_INPUT_ID: Final[str] = "MJ::OutpaintCustomZoomModal::prompt"

IMAGINE: Final[CommandMeta] = {
    "id": "938956540159881230",
    "version": "1237876415471554623",
    "name": "imagine",
}

DESCRIBE: Final[CommandMeta] = {
    "id": "1092492867185950852",
    "version": "1237876415471554625",
    "name": "describe",
}

BLEND: Final[CommandMeta] = {
    "id": "1062880104792997970",
    "version": "1237876415471554624",
    "name": "blend",
}
