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

from mutiny.domain.job import Job, JobAction, JobStatus
from mutiny.domain.state_machine import JobStateMachine, JobTransition


def test_task_lifecycle_success():
    t = Job(id="1", action=JobAction.IMAGINE, prompt="hi")
    assert t.status == JobStatus.PENDING
    assert t.start_time is None and t.finish_time is None

    assert JobStateMachine.apply(t, JobTransition.SUBMIT)
    assert JobStateMachine.apply(t, JobTransition.START)
    assert t.status == JobStatus.IN_PROGRESS
    assert t.start_time is not None

    assert JobStateMachine.apply(t, JobTransition.SUCCEED)
    assert t.status == JobStatus.SUCCEEDED
    assert t.finish_time is not None
    # completion_event is set on success
    assert isinstance(t.completion_event, asyncio.Event)
    assert t.completion_event.is_set()


def test_task_lifecycle_failure():
    t = Job(id="2", action=JobAction.REROLL)
    assert JobStateMachine.apply(t, JobTransition.SUBMIT)
    assert JobStateMachine.apply(t, JobTransition.START)
    assert JobStateMachine.apply(t, JobTransition.FAIL, "boom")
    assert t.status == JobStatus.FAILED
    assert t.fail_reason == "boom"
    assert t.finish_time is not None
    assert t.completion_event.is_set()


def test_task_rejects_invalid_transition():
    t = Job(id="3", action=JobAction.IMAGINE)
    assert JobStateMachine.apply(t, JobTransition.SUBMIT)
    assert JobStateMachine.apply(t, JobTransition.START)
    assert JobStateMachine.apply(t, JobTransition.SUCCEED)
    assert not JobStateMachine.apply(t, JobTransition.FAIL, "late error")
    assert t.status == JobStatus.SUCCEEDED


def test_task_transition_matrix_is_strict():
    job = Job(id="matrix", action=JobAction.IMAGINE)
    cases = [
        (JobStatus.PENDING, JobTransition.SUBMIT, True),
        (JobStatus.PENDING, JobTransition.START, False),
        (JobStatus.SUBMITTED, JobTransition.START, True),
        (JobStatus.SUBMITTED, JobTransition.SUCCEED, False),
        (JobStatus.IN_PROGRESS, JobTransition.SUCCEED, True),
        (JobStatus.IN_PROGRESS, JobTransition.SUBMIT, False),
        (JobStatus.SUCCEEDED, JobTransition.FAIL, False),
        (JobStatus.FAILED, JobTransition.SUCCEED, False),
    ]
    for status, transition, expected in cases:
        job.status = status
        assert JobStateMachine.apply(job, transition) is expected
