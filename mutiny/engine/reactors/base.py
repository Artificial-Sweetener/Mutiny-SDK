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
from abc import ABC, abstractmethod
from typing import Any

from mutiny.discord.message_interpreter import InterpretedMessage
from mutiny.domain.state_machine import JobTransition
from mutiny.engine.events import ProviderMessageReceived
from mutiny.engine.prompt_matching import normalize_prompt_for_matching
from mutiny.types import Job, JobAction, JobStatus

logger = logging.getLogger(__name__)


class MessageReactor(ABC):
    def handle(self, event: object) -> bool | None:
        if not isinstance(event, ProviderMessageReceived):
            return None
        return self.handle_message(event.context, event.event_type, event.message)

    @abstractmethod
    def handle_message(self, instance, event_type: str, message: InterpretedMessage) -> bool:
        raise NotImplementedError

    def find_and_finish_image_job(
        self,
        instance,
        action: JobAction,
        final_prompt: str,
        message: InterpretedMessage,
        *,
        require_new_message: bool = False,
    ) -> Job | None:
        normalized_prompt = normalize_prompt_for_matching(final_prompt)
        if not normalized_prompt:
            return None

        image_url = message.image_url
        message_hash = message.message_hash
        referenced_message_id = message.referenced_message_id

        def predicate(j: Job):
            return (
                j.action == action
                and normalize_prompt_for_matching(j.context.final_prompt) == normalized_prompt
                and j.status == JobStatus.IN_PROGRESS
            )

        if referenced_message_id:
            job = instance.get_running_job_by_condition(
                lambda j: j.action == action
                and j.status == JobStatus.IN_PROGRESS
                and j.context.message_id == referenced_message_id
            )
        else:
            job = None

        if not job:
            job = instance.get_running_job_by_condition(
                lambda j: predicate(j) and j.context.message_hash == message_hash
            )
        if not job:
            job = instance.get_running_job_by_condition(predicate)

        if not job:
            return None

        if (
            require_new_message
            and message.message_id
            and job.context.message_id
            and message.message_id == job.context.message_id
        ):
            return None

        job.image_url = image_url
        job.context.message_id = message.message_id
        job.context.message_hash = message_hash
        if message.flags is not None:
            job.context.flags = message.flags
        instance.apply_transition(job, JobTransition.SUCCEED)
        instance.save_and_notify(job)

        return job

    def _safe_dump(
        self,
        instance,
        dump_method: str,
        *,
        message: dict[str, Any],
        prompt: str | None = None,
        **kwargs: Any,
    ) -> None:
        dumper = getattr(instance, "response_dump", None)
        if not dumper:
            return
        fn = getattr(dumper, dump_method, None)
        if not callable(fn):
            return
        try:
            fn(message=message, prompt=prompt, **kwargs)
        except Exception:
            msg_id = None
            if isinstance(message, dict):
                msg_id = message.get("id")
            logger.warning(
                "Response dump failed via %s (reactor=%s, message_id=%s)",
                dump_method,
                type(self).__name__,
                msg_id,
                exc_info=True,
            )


__all__ = ["MessageReactor"]
