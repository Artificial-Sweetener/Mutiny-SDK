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

import pytest

from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.context import AppContext
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.job_requests import JobCustomZoomCommand
from mutiny.services.job_store import InMemoryJobStoreService
from mutiny.services.job_submission import JobSubmissionService
from mutiny.services.metrics.service import MetricsService
from mutiny.services.notify.event_bus import StreamingJobUpdateBus
from mutiny.services.response_dump import ResponseDumpService


@pytest.mark.asyncio
async def test_custom_zoom_requires_zoom_flag(test_config):
    ctx = AppContext(
        config=test_config,
        job_store=InMemoryJobStoreService(),
        notify_bus=StreamingJobUpdateBus(),
        artifact_cache=ArtifactCacheService(),
        response_dump=ResponseDumpService(enabled=False),
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        engine=None,
    )
    cmd = JobCustomZoomCommand(job_id="t1", zoom_text="no flags here")
    service = JobSubmissionService(ctx)
    res = await service.submit_custom_zoom(cmd)
    assert res.code == 400
    assert "--zoom" in (res.message or "")
