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

from typing import List, Literal, TypedDict, Union


class InteractionEnvelope(TypedDict):
    application_id: str
    guild_id: str
    channel_id: str
    nonce: str


class InteractionWithSession(TypedDict, total=False):
    application_id: str
    guild_id: str
    channel_id: str
    nonce: str
    session_id: str


class CommandOptionPrompt(TypedDict):
    type: Literal[3]
    name: Literal["prompt"]
    value: str


class CommandOptionImageUpload(TypedDict):
    type: Literal[11]
    name: Literal["image"]
    value: int


class CommandOptionImageUrl(TypedDict):
    type: Literal[3]
    name: Literal["image"]
    value: str


class CommandOptionBlendImage(TypedDict):
    type: Literal[11]
    name: str
    value: int


class CommandOptionDimensions(TypedDict):
    type: Literal[3]
    name: Literal["dimensions"]
    value: str


CommandOption = Union[
    CommandOptionPrompt,
    CommandOptionImageUpload,
    CommandOptionImageUrl,
    CommandOptionBlendImage,
    CommandOptionDimensions,
]


class CommandAttachment(TypedDict):
    id: str
    filename: str
    uploaded_filename: str


class CommandData(TypedDict):
    version: str
    id: str
    name: str
    type: Literal[1]
    options: List[CommandOption]
    attachments: List[CommandAttachment]


class CommandInteraction(InteractionWithSession):
    type: Literal[2]
    data: CommandData


class ComponentData(TypedDict):
    component_type: Literal[2]
    custom_id: str


class ButtonInteraction(InteractionWithSession):
    type: Literal[3]
    message_id: str
    message_flags: int
    data: ComponentData


class ModalTextInput(TypedDict):
    type: Literal[4]
    custom_id: str
    value: str


class ModalActionRow(TypedDict):
    type: Literal[1]
    components: List[ModalTextInput]


class ModalSubmitData(TypedDict):
    id: str
    custom_id: str
    components: List[ModalActionRow]


class ModalSubmitInteraction(InteractionWithSession):
    type: Literal[5]
    data: ModalSubmitData


class InpaintSubmitBody(TypedDict):
    mask: str
    prompt: str


__all__ = [
    "InteractionWithSession",
    "CommandOptionPrompt",
    "CommandOptionImageUpload",
    "CommandOptionImageUrl",
    "CommandOptionBlendImage",
    "CommandOptionDimensions",
    "CommandOption",
    "CommandAttachment",
    "CommandData",
    "CommandInteraction",
    "ComponentData",
    "ButtonInteraction",
    "ModalTextInput",
    "ModalActionRow",
    "ModalSubmitData",
    "ModalSubmitInteraction",
    "InpaintSubmitBody",
]
