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

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from mutiny.types import Job, JobAction, JobStatus


@dataclass(frozen=True)
class JobQuery:
    status: Optional[JobStatus] = None
    action: Optional[JobAction] = None
    nonce: Optional[str] = None
    message_id: Optional[str] = None
    message_hash: Optional[str] = None
    progress_message_id: Optional[str] = None
    interaction_id: Optional[str] = None
    final_prompt: Optional[str] = None
    cancel_message_id: Optional[str] = None
    cancel_job_id: Optional[str] = None
    index: Optional[int] = None
    original_job_id: Optional[str] = None


class JobStore:
    def save(self, job: Job) -> None:
        raise NotImplementedError

    def get(self, job_id: str) -> Optional[Job]:
        raise NotImplementedError

    def list(self) -> List[Job]:
        raise NotImplementedError

    def find_one(self, query: JobQuery) -> Optional[Job]:
        raise NotImplementedError

    def find_all(self, query: JobQuery) -> List[Job]:
        raise NotImplementedError


class InMemoryJobStoreService(JobStore):
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}

    def save(self, job: Job) -> None:
        self._jobs[job.id] = job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list(self) -> List[Job]:
        return list(self._jobs.values())

    def find_one(self, query: JobQuery) -> Optional[Job]:
        return next((job for job in self._iter_matches(query)), None)

    def find_all(self, query: JobQuery) -> List[Job]:
        return list(self._iter_matches(query))

    def _iter_matches(self, query: JobQuery) -> Iterable[Job]:
        for job in self._jobs.values():
            if query.status is not None and job.status != query.status:
                continue
            if query.action is not None and job.action != query.action:
                continue
            ctx = job.context
            if query.nonce is not None and ctx.nonce != query.nonce:
                continue
            if query.message_id is not None and ctx.message_id != query.message_id:
                continue
            if query.message_hash is not None and ctx.message_hash != query.message_hash:
                continue
            if query.progress_message_id is not None:
                if ctx.progress_message_id != query.progress_message_id:
                    continue
            if query.interaction_id is not None and ctx.interaction_id != query.interaction_id:
                continue
            if query.final_prompt is not None and ctx.final_prompt != query.final_prompt:
                continue
            if (
                query.cancel_message_id is not None
                and ctx.cancel_message_id != query.cancel_message_id
            ):
                continue
            if query.cancel_job_id is not None and ctx.cancel_job_id != query.cancel_job_id:
                continue
            if query.index is not None and ctx.index != query.index:
                continue
            if query.original_job_id is not None and ctx.original_job_id != query.original_job_id:
                continue
            yield job


__all__ = ["InMemoryJobStoreService", "JobQuery", "JobStore"]
