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

"""Build Discord interaction payloads for Midjourney flows."""

import os
from typing import List, Optional

from mutiny.discord.constants import (
    APPLICATION_ID,
    BLEND,
    CUSTOM_ZOOM_PROMPT_INPUT_ID,
    DESCRIBE,
    IMAGINE,
    CommandMeta,
    ComponentType,
    InteractionType,
)
from mutiny.discord.identity import DiscordIdentity
from mutiny.discord.payload_types import (
    ButtonInteraction,
    CommandAttachment,
    CommandInteraction,
    CommandOption,
    InpaintSubmitBody,
    InteractionWithSession,
    ModalSubmitInteraction,
)


class DiscordPayloadBuilder:
    """Construct Discord payloads for Discord slash commands and components."""

    def _base_interaction(
        self,
        identity: DiscordIdentity,
        nonce: str,
        type_: InteractionType,
        *,
        session_id: Optional[str],
    ) -> InteractionWithSession:
        """Build the shared interaction envelope with optional session id."""
        payload: InteractionWithSession = {
            "type": int(type_),
            "application_id": APPLICATION_ID,
            "guild_id": identity.guild_id,
            "channel_id": identity.channel_id,
            "nonce": nonce,
        }
        if session_id is not None:
            payload["session_id"] = session_id
        return payload

    def _command_base(
        self, meta: CommandMeta, identity: DiscordIdentity, nonce: str, *, session_id: Optional[str]
    ) -> CommandInteraction:
        """Initialize an application command payload with empty data/options."""
        payload: CommandInteraction = self._base_interaction(
            identity, nonce, InteractionType.COMMAND, session_id=session_id
        )
        payload["data"] = {
            "version": meta["version"],
            "id": meta["id"],
            "name": meta["name"],
            "type": 1,
            "options": [],
            "attachments": [],
        }
        return payload

    def build_imagine(
        self, identity: DiscordIdentity, prompt: str, nonce: str, *, session_id: Optional[str]
    ) -> CommandInteraction:
        """Create the imagine command payload with a single prompt option and no attachments."""
        payload = self._command_base(IMAGINE, identity, nonce, session_id=session_id)
        payload["data"]["options"] = [
            {
                "type": 3,
                "name": "prompt",
                "value": prompt,
            }
        ]
        payload["data"]["attachments"] = []
        return payload

    def build_describe_upload(
        self,
        identity: DiscordIdentity,
        uploaded_filename: str,
        nonce: str,
        *,
        session_id: Optional[str],
    ) -> CommandInteraction:
        """Create describe payload that binds an uploaded image to option index 0."""
        payload = self._command_base(DESCRIBE, identity, nonce, session_id=session_id)
        file_name_only = os.path.basename(uploaded_filename)
        payload["data"]["options"] = [
            {
                "type": 11,
                "name": "image",
                "value": 0,
            }
        ]
        payload["data"]["attachments"] = [
            {
                "id": "0",
                "filename": file_name_only,
                "uploaded_filename": uploaded_filename,
            }
        ]
        return payload

    def build_describe_url(
        self, identity: DiscordIdentity, image_url: str, nonce: str, *, session_id: Optional[str]
    ) -> CommandInteraction:
        """Create describe payload pointing Discord to a URL-based image with no attachments."""
        payload = self._command_base(DESCRIBE, identity, nonce, session_id=session_id)
        payload["data"]["options"] = [
            {
                "type": 3,
                "name": "image",
                "value": image_url,
            }
        ]
        payload["data"]["attachments"] = []
        return payload

    def build_blend(
        self,
        identity: DiscordIdentity,
        uploaded_filenames: List[str],
        dimensions: str,
        nonce: str,
        *,
        session_id: Optional[str],
    ) -> CommandInteraction:
        """Create blend payload mapping attachments to options plus an aspect ratio flag.

        Each filename is normalized to its basename and mapped to sequential attachment ids and
        `image{i}` options, followed by a dimensions option formatted as `--ar <value>`.
        """
        payload = self._command_base(BLEND, identity, nonce, session_id=session_id)

        options: List[CommandOption] = []
        attachments: List[CommandAttachment] = []

        for i, filename in enumerate(uploaded_filenames):
            file_name_only = os.path.basename(filename)
            attachments.append(
                {
                    "id": str(i),
                    "filename": file_name_only,
                    "uploaded_filename": filename,
                }
            )
            options.append({"type": 11, "name": f"image{i + 1}", "value": i})

        ar_value = str(dimensions).strip()
        options.append({"type": 3, "name": "dimensions", "value": f"--ar {ar_value}"})

        payload["data"]["options"] = options
        payload["data"]["attachments"] = attachments
        return payload

    def build_button_interaction(
        self,
        identity: DiscordIdentity,
        nonce: str,
        *,
        message_id: str,
        message_flags: int,
        custom_id: str,
        session_id: Optional[str] = None,
    ) -> ButtonInteraction:
        """Create a component interaction for a button tied to a specific message context.

        Preserves the upstream `custom_id` so downstream handlers route to the exact action
        encoded in Discord component metadata.
        """
        payload: ButtonInteraction = self._base_interaction(
            identity, nonce, InteractionType.COMPONENT, session_id=session_id
        )
        payload["message_id"] = message_id
        payload["message_flags"] = int(message_flags)
        payload["data"] = {
            "component_type": int(ComponentType.BUTTON),
            "custom_id": custom_id,
        }
        return payload

    def build_custom_zoom_modal(
        self,
        identity: DiscordIdentity,
        nonce: str,
        *,
        custom_id: str,
        zoom_text: str,
        modal_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> ModalSubmitInteraction:
        """Create a custom zoom modal submit with prompt text pre-filled in the input field."""
        payload: ModalSubmitInteraction = self._base_interaction(
            identity, nonce, InteractionType.MODAL_SUBMIT, session_id=session_id
        )
        data = {
            "id": modal_id or nonce,
            "custom_id": custom_id,
            "components": [
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 4,
                            "custom_id": CUSTOM_ZOOM_PROMPT_INPUT_ID,
                            "value": zoom_text,
                        }
                    ],
                }
            ],
        }
        payload["data"] = data
        return payload

    def build_inpaint_submit_body(
        self,
        *,
        mask_webp_base64: str,
        prompt: str | None,
    ) -> InpaintSubmitBody:
        """Construct the current inpaint submit payload for the Midjourney iframe app."""
        return {
            "mask": mask_webp_base64,
            "prompt": prompt or "",
        }


__all__ = ["DiscordPayloadBuilder"]
