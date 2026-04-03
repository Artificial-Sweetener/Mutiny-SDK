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

"""Context wrapper exposed to reactors to avoid engine coupling."""

from __future__ import annotations

from typing import Callable

from mutiny.engine.indexing import IndexingCoordinator
from mutiny.engine.runtime.job_lookup import JobLookupService
from mutiny.services.notify.event_bus import JobUpdateBus
from mutiny.types import Job, JobAction


class ReactorContext:
    """Read-only view for reactors plus safe mutation hooks."""

    def __init__(
        self,
        *,
        lookup: JobLookupService,
        indexer: IndexingCoordinator,
        apply_transition: Callable[..., bool],
        save_and_notify: Callable[[Job], None],
        schedule_prompt_video_follow_up: Callable[..., None],
        schedule_internal_follow_up_action: Callable[[Job], None],
        notify_bus: JobUpdateBus,
        response_dump,
    ) -> None:
        self.lookup = lookup
        self.indexer = indexer
        self._apply_transition = apply_transition
        self._save_and_notify = save_and_notify
        self._schedule_prompt_video_follow_up = schedule_prompt_video_follow_up
        self._schedule_internal_follow_up_action = schedule_internal_follow_up_action
        self.notify_bus = notify_bus
        self.response_dump = response_dump

    # Lookup surface
    def get_running_job_by_condition(self, predicate):
        return self.lookup.find_running_by_condition(predicate)

    def get_running_job_by_nonce(self, nonce: str | None):
        return self.lookup.find_running_by_nonce(nonce)

    def get_running_job_by_query(self, query):
        return self.lookup.find_running_by_query(query)

    # Mutations
    def apply_transition(self, job: Job, transition, reason: str | None = None) -> bool:
        return self._apply_transition(job, transition, reason)

    def save_and_notify(self, job: Job) -> None:
        self._save_and_notify(job)

    def schedule_prompt_video_follow_up(
        self,
        job: Job,
        *,
        message_id: str,
        custom_id: str,
        message_flags: int,
    ) -> None:
        """Queue the prompt-video follow-up interaction for one animate job."""

        self._schedule_prompt_video_follow_up(
            job,
            message_id=message_id,
            custom_id=custom_id,
            message_flags=message_flags,
        )

    def schedule_internal_follow_up_action(self, job: Job) -> None:
        """Queue the next provider action for one in-flight multi-step job."""

        self._schedule_internal_follow_up_action(job)

    # Indexing delegation
    def schedule_image_indexing(self, action: JobAction, message: dict, job: Job) -> None:
        self.indexer.schedule_image_indexing(action, message, job)

    def schedule_video_indexing(self, message: dict, job: Job) -> None:
        """Queue indexing for one final animate-family video artifact."""
        self.indexer.schedule_video_indexing(message, job)


__all__ = ["ReactorContext"]
