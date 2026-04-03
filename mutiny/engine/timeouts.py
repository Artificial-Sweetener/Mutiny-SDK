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
import logging
import time

from ..domain.state_machine import JobStateMachine, JobTransition
from ..services.job_store import JobStore
from ..services.logging_utils import clear_job_context, set_job_context
from ..services.notify.event_bus import JobUpdateBus
from ..types import JobStatus
from .execution_policy import EnginePolicy

logger = logging.getLogger(__name__)


class JobTimeoutScheduler:
    def __init__(self, job_store: JobStore, notify_bus: JobUpdateBus, policy: EnginePolicy):
        self._job_store = job_store
        self._notify_bus = notify_bus
        self._policy = policy

    def update_policy(self, policy: EnginePolicy) -> None:
        self._policy = policy

    async def run(self):
        while True:
            await asyncio.sleep(30)
            now = time.time()
            timeout_seconds = self._policy.timeout_seconds

            active_jobs = [
                j
                for j in self._job_store.list()
                if j.status == JobStatus.IN_PROGRESS and j.start_time
            ]

            for job in active_jobs:
                if job.start_time is not None and (now - (job.start_time / 1000)) > timeout_seconds:
                    JobStateMachine.apply(
                        job,
                        JobTransition.FAIL,
                        f"Task timed out after {self._policy.task_timeout_minutes} minutes",
                    )
                    set_job_context(job_id=job.id, action=job.action.value, status=job.status.value)
                    logger.warning(f"Job {job.id} timed out; marked as failed.")
                    self._job_store.save(job)
                    self._notify_bus.publish_job(job)
                    clear_job_context()


__all__ = ["JobTimeoutScheduler"]
