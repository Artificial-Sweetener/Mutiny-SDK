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

"""RAM-only session cache for live Discord interaction state.

This cache stores transient observation data such as modal payloads, iframe
tokens, and message component ids. It is intentionally not part of Mutiny's
restart-safe artifact recovery contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set


@dataclass
class InteractionCache:
    """Hold live-session interaction data that is safe to lose on restart."""

    custom_zoom_modals: Dict[str, dict] = field(default_factory=dict)
    inpaint_iframe_tokens: Dict[str, str] = field(default_factory=dict)
    message_components: Dict[str, Set[str]] = field(default_factory=dict)

    def get_custom_zoom_modal(self, message_hash: str) -> dict | None:
        return self.custom_zoom_modals.get(message_hash)

    def set_custom_zoom_modal(self, message_hash: str, data: dict) -> None:
        self.custom_zoom_modals[message_hash] = data

    def get_inpaint_token(self, channel_key: str) -> str | None:
        return self.inpaint_iframe_tokens.get(channel_key)

    def set_inpaint_token(self, channel_key: str, token: str) -> None:
        self.inpaint_iframe_tokens[channel_key] = token

    def set_message_components(self, message_id: str, custom_ids: Set[str]) -> None:
        self.message_components[str(message_id)] = set(custom_ids)

    def get_message_components(self, message_id: str) -> Set[str]:
        return self.message_components.get(str(message_id), set())


__all__ = ["InteractionCache"]
