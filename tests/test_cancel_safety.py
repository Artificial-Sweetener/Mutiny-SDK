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

from mutiny.domain.job import Job, JobAction, JobStatus
from mutiny.services.cancel_safety import can_cancel


def _base_job() -> Job:
    return Job(
        id="t",
        action=JobAction.VARIATION,
        prompt="p",
        status=JobStatus.IN_PROGRESS,
    )


def test_can_cancel_missing_progress_message():
    t = _base_job()
    ctx = can_cancel(t)
    assert not ctx.can_cancel
    assert ctx.error_code == 400
    assert "no progress message" in (ctx.error_message or "")


def test_can_cancel_missing_job_id():
    t = _base_job()
    t.context.progress_message_id = "m1"
    ctx = can_cancel(t)
    assert not ctx.can_cancel
    assert ctx.error_code == 400
    assert "no job id" in (ctx.error_message or "")


def test_can_cancel_waiting_for_button_flags():
    t = _base_job()
    t.context.progress_message_id = "m1"
    t.context.message_hash = "hash"
    t.context.flags = 0
    ctx = can_cancel(t)
    assert not ctx.can_cancel
    assert ctx.error_code == 409
    assert "awaiting Cancel button" in (ctx.error_message or "")


def test_can_cancel_ok_with_explicit_cancel_ids():
    t = _base_job()
    t.context.cancel_message_id = "m_cancel"
    t.context.cancel_job_id = "job-1"
    t.context.flags = 64
    ctx = can_cancel(t)
    assert ctx.can_cancel
    assert ctx.message_id == "m_cancel"
    assert ctx.job_id == "job-1"
    assert ctx.message_flags == 64
