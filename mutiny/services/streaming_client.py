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

from contextlib import asynccontextmanager
from dataclasses import replace
from typing import AsyncIterator, Optional, Tuple

import httpx

from ..config import CdnConfig, Config
from ..domain.progress import ProgressEvent
from ..engine.runtime.state import State
from ..mutiny import Mutiny
from ..types import Job, JobStatus
from .context import ContextOverrides
from .notify.event_bus import StreamingJobUpdateBus


async def build_streaming_client(
    overrides: Optional[ContextOverrides] = None, config: Optional[Config] = None
) -> Tuple[Mutiny, StreamingJobUpdateBus]:
    """Construct a Mutiny facade pre-wired with StreamingJobUpdateBus.

    Returns the facade (not started) and the notify service. The caller can
    modify the facade/config before calling start().
    """
    notify = StreamingJobUpdateBus()
    if overrides and overrides.notify_bus is not None:
        raise ValueError("Streaming client manages notify_bus")
    applied = overrides or ContextOverrides()
    applied = replace(applied, notify_bus=notify)
    state = State(config=config, overrides=applied)
    client = Mutiny(state.settings)
    client._state = state
    return client, notify


async def stream_job_updates(notify: StreamingJobUpdateBus, job_id: str) -> AsyncIterator[Job]:
    """Yield Job updates until it reaches a terminal status.

    Consumers can render progress or previews from the yielded Job objects.
    """
    q = notify.subscribe(job_id)
    while True:
        job = await q.get()
        yield job
        if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
            return


async def stream_job_progress(
    notify: StreamingJobUpdateBus, job_id: str
) -> AsyncIterator[ProgressEvent]:
    """Yield structured progress events for a job."""
    q = notify.subscribe_progress(job_id)
    while True:
        event = await q.get()
        yield event


@asynccontextmanager
async def cdn_client(config: Optional[Config] = None):
    """Async context manager for a CDN-tuned httpx client (timeouts only).

    Use for preview downloads in client-only flows.
    """
    if config:
        cdn = config.cdn
    else:
        cdn = CdnConfig()
    timeout = httpx.Timeout(
        connect=cdn.connect_timeout,
        read=cdn.read_timeout,
        write=cdn.write_timeout,
        pool=cdn.pool_timeout,
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        yield client
