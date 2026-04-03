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

import logging
from enum import Enum

from mutiny.domain.job import Job, JobStatus
from mutiny.domain.time import get_current_timestamp_ms

logger = logging.getLogger(__name__)


class JobTransition(str, Enum):
    SUBMIT = "SUBMIT"
    START = "START"
    SUCCEED = "SUCCEED"
    FAIL = "FAIL"


_TRANSITIONS: dict[JobStatus, set[JobTransition]] = {
    JobStatus.PENDING: {JobTransition.SUBMIT, JobTransition.FAIL},
    JobStatus.SUBMITTED: {JobTransition.START, JobTransition.FAIL},
    JobStatus.IN_PROGRESS: {JobTransition.SUCCEED, JobTransition.FAIL},
    JobStatus.SUCCEEDED: set(),
    JobStatus.FAILED: set(),
}


class JobStateMachine:
    """Apply job state transitions with validation."""

    @staticmethod
    def apply(job: Job, transition: JobTransition, reason: str | None = None) -> bool:
        allowed = _TRANSITIONS.get(job.status, set())
        if transition not in allowed:
            logger.warning(
                "Invalid job transition job_id=%s status=%s transition=%s",
                job.id,
                job.status.value,
                transition.value,
            )
            return False

        now_ms = get_current_timestamp_ms()
        if transition == JobTransition.SUBMIT:
            job.status = JobStatus.SUBMITTED
        elif transition == JobTransition.START:
            job.status = JobStatus.IN_PROGRESS
            job.start_time = now_ms
        elif transition == JobTransition.SUCCEED:
            job.status = JobStatus.SUCCEEDED
            job.finish_time = now_ms
            job.completion_event.set()
        elif transition == JobTransition.FAIL:
            job.status = JobStatus.FAILED
            job.fail_reason = reason
            job.finish_time = now_ms
            job.completion_event.set()
        return True


__all__ = ["JobStateMachine", "JobTransition"]
