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

from mutiny.domain.job import Job, JobAction, JobStatus
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.context import AppContext
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.job_requests import JobCancelCommand
from mutiny.services.job_store import InMemoryJobStoreService
from mutiny.services.job_submission import JobSubmissionService
from mutiny.services.metrics.service import MetricsService
from mutiny.services.response_dump import ResponseDumpService


class FakeNotifyBus:
    def __init__(self):
        self.notified = []
        self.progress_events = []

    def publish_job(self, job: Job):
        self.notified.append(job.id)

    def publish_progress(self, event):  # pragma: no cover - not used
        self.progress_events.append(event)

    def subscribe(self, job_id: str):
        raise NotImplementedError

    def subscribe_progress(self, job_id: str):  # pragma: no cover - not used
        raise NotImplementedError

    async def close(self) -> None:
        return None


class FakeProvider:
    def __init__(self, result="Success"):
        self.calls = []
        self.result = result

    async def cancel_job(self, message_id: str, job_id: str, message_flags: int, nonce: str):
        self.calls.append(
            {
                "message_id": message_id,
                "job_id": job_id,
                "message_flags": message_flags,
                "nonce": nonce,
            }
        )
        return self.result


class FakeInstance:
    def __init__(self, provider, notify):
        self.provider = provider
        self.commands = provider
        self.notify_bus = notify


@pytest.mark.asyncio
async def test_cancel_success_marks_job_failed_and_sends_interaction(monkeypatch, test_config):
    # Arrange state
    store = InMemoryJobStoreService()
    notify = FakeNotifyBus()
    provider = FakeProvider(result="Success")
    instance = FakeInstance(provider, notify)
    ctx = AppContext(
        config=test_config,
        job_store=store,
        notify_bus=notify,
        artifact_cache=ArtifactCacheService(),
        response_dump=ResponseDumpService(enabled=False),
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        engine=instance,
    )

    job = Job(
        id="t1",
        action=JobAction.VARIATION,
        prompt="a prompt",
        status=JobStatus.IN_PROGRESS,
    )
    job.context.progress_message_id = "m123"
    job.context.message_hash = "job-uuid"
    job.context.flags = 64
    store.save(job)

    # Act
    cmd = JobCancelCommand(job_id="t1")
    service = JobSubmissionService(ctx)
    res = await service.submit_cancel(cmd)
    # Assert endpoint result
    assert res.code == 1
    assert res.value == "t1"
    # Assert task updated
    saved = store.get("t1")
    assert saved.status == JobStatus.FAILED
    assert "Cancelled" in (saved.fail_reason or "")
    # Assert we sent the right interaction payload
    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call["message_id"] == "m123"
    assert call["job_id"] == "job-uuid"
    assert call["message_flags"] == 64
    # Assert notification fired
    assert "t1" in notify.notified
