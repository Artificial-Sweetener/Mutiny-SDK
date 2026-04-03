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

from mutiny.discord.constants import (
    APPLICATION_ID,
    BLEND,
    CUSTOM_ZOOM_PROMPT_INPUT_ID,
    DESCRIBE,
    IMAGINE,
    ComponentType,
    InteractionType,
)


def test_application_ids_frozen() -> None:
    assert APPLICATION_ID == "936929561302675456"


def test_enum_values_frozen() -> None:
    assert InteractionType.COMMAND == 2
    assert InteractionType.COMPONENT == 3
    assert InteractionType.MODAL_SUBMIT == 5
    assert ComponentType.BUTTON == 2


def test_command_metadata_frozen() -> None:
    assert IMAGINE == {
        "id": "938956540159881230",
        "version": "1237876415471554623",
        "name": "imagine",
    }
    assert DESCRIBE == {
        "id": "1092492867185950852",
        "version": "1237876415471554625",
        "name": "describe",
    }
    assert BLEND == {
        "id": "1062880104792997970",
        "version": "1237876415471554624",
        "name": "blend",
    }


def test_custom_zoom_prompt_id_frozen() -> None:
    assert CUSTOM_ZOOM_PROMPT_INPUT_ID == "MJ::OutpaintCustomZoomModal::prompt"
