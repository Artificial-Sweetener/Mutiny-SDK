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

import asyncio
from typing import Awaitable, Callable

from ..config import Config
from ..services.interaction_cache import InteractionCache
from ..services.metrics.service import MetricsService
from ..services.response_dump import ResponseDumpService
from .gateway_client import DiscordGatewayClient
from .identity import DiscordIdentity, DiscordSessionState
from .rest_client import DiscordRestClient

MessageHandler = Callable[[str, dict], Awaitable[None] | None]


class DiscordProvider:
    """Coordinates Discord gateway lifecycle and exposes REST commands."""

    def __init__(
        self,
        *,
        identity: DiscordIdentity,
        config: Config,
        interaction_cache: InteractionCache,
        metrics: MetricsService,
        response_dump: ResponseDumpService,
        message_handler: MessageHandler,
    ) -> None:
        self._identity = identity
        self._config = config
        self._interaction_cache = interaction_cache
        self._metrics = metrics
        self._response_dump = response_dump
        self._message_handler = message_handler
        self._session = DiscordSessionState()
        self._apply_lock = asyncio.Lock()
        self.commands = DiscordRestClient(
            identity=identity,
            session=self._session,
            config=config,
            interaction_cache=interaction_cache,
            metrics=metrics,
        )
        self.gateway = DiscordGatewayClient(
            identity=identity,
            session=self._session,
            config=config,
            interaction_cache=interaction_cache,
            metrics=metrics,
            response_dump=response_dump,
            message_handler=message_handler,
        )

    async def apply_config(self, *, config: Config, response_dump: ResponseDumpService) -> None:
        """Hot-apply config across REST and gateway clients."""

        async with self._apply_lock:
            self._config = config
            self._response_dump = response_dump
            self.gateway.response_dump = response_dump
            await self.commands.apply_config(config)
            await self.gateway.reconnect_with_config(config)

    async def start(self) -> None:
        await self.gateway.connect()

    async def close(self) -> None:
        await self.gateway.close()
        await self.commands.close()

    def is_ready(self) -> bool:
        return self.gateway.is_ready()


__all__ = ["DiscordProvider", "MessageHandler"]
