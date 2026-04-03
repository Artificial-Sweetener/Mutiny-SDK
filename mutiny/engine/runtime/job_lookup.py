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

"""Active job registry and lookup helpers for reactors.

This keeps active job tracking out of the engine surface and provides
query helpers for reactors and progress matchers without exposing engine
internals.
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional

from mutiny.services.job_store import JobQuery, JobStore
from mutiny.types import Job


class ActiveJobRegistry:
    """Track active job ids and hydrate job objects from the store."""

    def __init__(self, job_store: JobStore) -> None:
        self._job_store = job_store
        self._active_ids: set[str] = set()

    def add(self, job_id: str) -> None:
        self._active_ids.add(job_id)

    def discard(self, job_id: str) -> None:
        self._active_ids.discard(job_id)

    def iter_active(self) -> Iterable[Job]:
        for job_id in list(self._active_ids):
            job = self._job_store.get(job_id)
            if job:
                yield job
            else:
                # Keep registry clean when jobs disappear from the store.
                self._active_ids.discard(job_id)

    def has_active(self) -> bool:
        return bool(self._active_ids)


class JobLookupService:
    """Read-only active job lookup for reactors and progress matching."""

    def __init__(self, registry: ActiveJobRegistry, job_store: JobStore) -> None:
        self._registry = registry
        self._job_store = job_store

    def find_running_by_condition(self, predicate: Callable[[Job], bool]) -> Optional[Job]:
        return next((job for job in self._registry.iter_active() if predicate(job)), None)

    def find_running_by_nonce(self, nonce: str | None) -> Optional[Job]:
        if not nonce:
            return None
        return self.find_running_by_condition(lambda job: job.context.nonce == nonce)

    def find_running_by_query(self, query: JobQuery) -> Optional[Job]:
        return next(
            (job for job in self._registry.iter_active() if _matches_query(job, query)), None
        )

    def iter_active(self) -> Iterable[Job]:
        return self._registry.iter_active()

    def has_active(self) -> bool:
        return self._registry.has_active()


def _matches_query(job: Job, query: JobQuery) -> bool:
    if query.status is not None and job.status != query.status:
        return False
    if query.action is not None and job.action != query.action:
        return False
    ctx = job.context
    if query.nonce is not None and ctx.nonce != query.nonce:
        return False
    if query.message_id is not None and ctx.message_id != query.message_id:
        return False
    if query.message_hash is not None and ctx.message_hash != query.message_hash:
        return False
    if (
        query.progress_message_id is not None
        and ctx.progress_message_id != query.progress_message_id
    ):
        return False
    if query.interaction_id is not None and ctx.interaction_id != query.interaction_id:
        return False
    if query.final_prompt is not None and ctx.final_prompt != query.final_prompt:
        return False
    if query.cancel_message_id is not None and ctx.cancel_message_id != query.cancel_message_id:
        return False
    if query.cancel_job_id is not None and ctx.cancel_job_id != query.cancel_job_id:
        return False
    if query.index is not None and ctx.index != query.index:
        return False
    if query.original_job_id is not None and ctx.original_job_id != query.original_job_id:
        return False
    return True


__all__ = ["ActiveJobRegistry", "JobLookupService"]
