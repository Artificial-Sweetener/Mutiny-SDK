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

import asyncio

from mutiny.discord.identity import DiscordIdentity
from mutiny.engine.discord_engine import DiscordEngine
from mutiny.engine.execution_policy import EnginePolicy, ExecutionPolicy
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.image_processor import OpenCVImageProcessor
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.job_store import InMemoryJobStoreService
from mutiny.services.metrics.service import MetricsService
from mutiny.services.notify.event_bus import StreamingJobUpdateBus
from mutiny.services.response_dump import ResponseDumpService
from mutiny.services.video_signature import VideoSignatureService


def test_engine_semaphores_use_account_limits(test_config) -> None:
    class _TokenProvider:
        def get_token(self) -> str:
            return "t"

    identity = DiscordIdentity(
        guild_id="g",
        channel_id="c",
        token_provider=_TokenProvider(),
        user_agent="ua",
    )
    queue_size = 7
    core_size = 5
    video_core_size = 2
    policy = EnginePolicy(
        ExecutionPolicy(
            queue_size=queue_size,
            core_size=core_size,
            video_core_size=video_core_size,
            task_timeout_minutes=test_config.engine.execution.task_timeout_minutes,
        )
    )
    eng = DiscordEngine(
        identity=identity,
        job_store=InMemoryJobStoreService(),
        notify_bus=StreamingJobUpdateBus(),
        config=test_config,
        policy=policy,
        artifact_cache=ArtifactCacheService(),
        video_signature_service=VideoSignatureService(),
        image_processor=OpenCVImageProcessor(),
        interaction_cache=InteractionCache(),
        response_dump=ResponseDumpService(enabled=False),
        metrics=MetricsService(),
    )
    assert isinstance(eng.semaphore, asyncio.Semaphore)
    assert isinstance(eng.video_semaphore, asyncio.Semaphore)
    assert eng.semaphore._value == core_size  # type: ignore[attr-defined]
    assert eng.video_semaphore._value == video_core_size  # type: ignore[attr-defined]
    assert eng.queue.maxsize == queue_size
