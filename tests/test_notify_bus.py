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

from mutiny.domain.progress import ProgressEvent
from mutiny.services.notify.event_bus import StreamingJobUpdateBus
from mutiny.types import Job, JobAction, JobStatus


def test_streaming_job_update_bus_preserves_job_then_progress_publish_order():
    bus = StreamingJobUpdateBus()
    queue = bus.subscribe_all()
    job = Job(id="j1", action=JobAction.PAN_LEFT, status=JobStatus.IN_PROGRESS)
    event = ProgressEvent(
        job_id="j1",
        kind="promotion",
        status_text="Preparing tile follow-up",
        prompt="castle on a cliff at sunrise",
        progress_message_id=None,
        message_id="promoted-message",
        flags=64,
        image_url="https://cdn.example/promoted.png",
        message_hash="aa11",
        not_fast=None,
    )

    bus.publish_job(job)
    bus.publish_progress(event)

    assert queue.get_nowait() is job
    assert queue.get_nowait() == event
