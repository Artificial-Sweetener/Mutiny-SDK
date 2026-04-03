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

from mutiny.services.metrics.service import MetricsService
from mutiny.types import Job

logger = logging.getLogger(__name__)


class QueuePolicy:
    def __init__(self, queue: asyncio.Queue[Job], *, metrics: MetricsService):
        self._queue = queue
        self._metrics = metrics
        self._update_queue_size()

    async def enqueue(self, job: Job) -> bool:
        try:
            self._queue.put_nowait(job)
            self._update_queue_size()
            logger.info(f"[queue] put {job.id}; size={self._queue.qsize()}/{self._queue.maxsize}")
            return True
        except asyncio.QueueFull:
            self._update_queue_size()
            logger.warning(f"[queue] full; size={self._queue.qsize()}/{self._queue.maxsize}")
            return False

    def status(self) -> dict:
        try:
            return {"size": self._queue.qsize(), "max": self._queue.maxsize}
        except Exception:
            return {"size": None, "max": None}

    def record_dequeue(self) -> None:
        self._update_queue_size()

    def update_limits(self, maxsize: int) -> None:
        """Update queue maxsize for hot-applied execution policies."""

        try:
            self._queue._maxsize = maxsize  # type: ignore[attr-defined]
        except Exception:
            pass
        self._update_queue_size()

    def _update_queue_size(self) -> None:
        self._metrics.set_queue_size(self._queue.qsize())


__all__ = ["QueuePolicy"]
