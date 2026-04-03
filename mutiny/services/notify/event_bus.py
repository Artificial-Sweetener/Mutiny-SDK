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
from collections import defaultdict
from typing import Dict, List, Union

from mutiny.domain.progress import ProgressEvent
from mutiny.types import Job, JobStatus


class JobUpdateBus:
    """Event bus for job lifecycle updates."""

    def publish_job(self, job: Job) -> None:
        raise NotImplementedError

    def subscribe(self, job_id: str) -> asyncio.Queue[Job]:
        raise NotImplementedError

    def unsubscribe(self, job_id: str, queue: asyncio.Queue[Job]) -> None:
        raise NotImplementedError

    def publish_progress(self, event: ProgressEvent) -> None:
        raise NotImplementedError

    def subscribe_progress(self, job_id: str) -> asyncio.Queue[ProgressEvent]:
        raise NotImplementedError

    def unsubscribe_progress(self, job_id: str, queue: asyncio.Queue[ProgressEvent]) -> None:
        raise NotImplementedError

    def subscribe_all(self) -> asyncio.Queue[Union[Job, ProgressEvent]]:
        raise NotImplementedError

    def unsubscribe_all(self, queue: asyncio.Queue[Union[Job, ProgressEvent]]) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class StreamingJobUpdateBus(JobUpdateBus):
    """Non-blocking pub/sub bus for job updates."""

    def __init__(self) -> None:
        self._subs: Dict[str, List[asyncio.Queue[Job]]] = defaultdict(list)
        self._progress_subs: Dict[str, List[asyncio.Queue[ProgressEvent]]] = defaultdict(list)
        self._global_subs: List[asyncio.Queue[Union[Job, ProgressEvent]]] = []

    def subscribe(self, job_id: str) -> asyncio.Queue[Job]:
        q: asyncio.Queue[Job] = asyncio.Queue(maxsize=100)
        self._subs[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, queue: asyncio.Queue[Job]) -> None:
        self._remove_queue(self._subs, job_id, queue)

    def subscribe_progress(self, job_id: str) -> asyncio.Queue[ProgressEvent]:
        q: asyncio.Queue[ProgressEvent] = asyncio.Queue(maxsize=100)
        self._progress_subs[job_id].append(q)
        return q

    def unsubscribe_progress(self, job_id: str, queue: asyncio.Queue[ProgressEvent]) -> None:
        self._remove_queue(self._progress_subs, job_id, queue)

    def subscribe_all(self) -> asyncio.Queue[Union[Job, ProgressEvent]]:
        q: asyncio.Queue[Union[Job, ProgressEvent]] = asyncio.Queue(maxsize=500)
        self._global_subs.append(q)
        return q

    def unsubscribe_all(self, queue: asyncio.Queue[Union[Job, ProgressEvent]]) -> None:
        try:
            self._global_subs.remove(queue)
        except ValueError:
            return

    def publish_job(self, job: Job) -> None:
        self._publish(job)

    def _publish(self, job: Job) -> None:
        # Push to job-specific subscribers
        qs = self._subs.get(job.id) or []
        for q in list(qs):
            self._push_idx_queue(q, job)

        # Push to global subscribers
        for q in list(self._global_subs):
            self._push_idx_queue(q, job)

        if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
            self._subs.pop(job.id, None)
            self._progress_subs.pop(job.id, None)

    def publish_progress(self, event: ProgressEvent) -> None:
        self._publish_progress(event)

    def _publish_progress(self, event: ProgressEvent) -> None:
        qs = self._progress_subs.get(event.job_id) or []
        for q in list(qs):
            self._push_idx_queue(q, event)

        # Push to global subscribers
        for q in list(self._global_subs):
            self._push_idx_queue(q, event)

    def _push_idx_queue(self, q: asyncio.Queue, item):
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            try:
                _ = q.get_nowait()
            except Exception:
                pass
            try:
                q.put_nowait(item)
            except Exception:
                pass

    @staticmethod
    def _remove_queue(
        mapping: Dict[str, List[asyncio.Queue]],
        job_id: str,
        queue: asyncio.Queue,
    ) -> None:
        queues = mapping.get(job_id)
        if not queues:
            return
        try:
            queues.remove(queue)
        except ValueError:
            return
        if not queues:
            mapping.pop(job_id, None)

    async def close(self) -> None:
        self._subs.clear()
        self._progress_subs.clear()
        self._global_subs.clear()


__all__ = ["JobUpdateBus", "StreamingJobUpdateBus"]
