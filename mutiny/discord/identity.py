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

from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..services.token_provider import TokenProvider


class DiscordIdentity(BaseModel):
    """Represents the Discord identity and credential provider."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    guild_id: str
    channel_id: str
    token_provider: TokenProvider
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )


class DiscordSessionState:
    """Tracks mutable Discord session data separate from identity."""

    def __init__(self) -> None:
        self.session_id: Optional[str] = None
        self.resume_gateway_url: Optional[str] = None

    def set_ready(self, session_id: Optional[str], resume_gateway_url: Optional[str]) -> None:
        self.session_id = session_id
        self.resume_gateway_url = resume_gateway_url

    def clear(self) -> None:
        self.session_id = None
        self.resume_gateway_url = None

    def has_session(self) -> bool:
        return self.session_id is not None


__all__ = ["DiscordIdentity", "DiscordSessionState"]
