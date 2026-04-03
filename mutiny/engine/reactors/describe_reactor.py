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

from mutiny.discord.message_interpreter import InterpretedMessage, MessageKind
from mutiny.domain.state_machine import JobTransition
from mutiny.engine.reactors.base import MessageReactor
from mutiny.types import Job, JobAction


class DescribeReactor(MessageReactor):
    def handle_message(self, instance, event_type: str, message: InterpretedMessage) -> bool:
        interaction_name = message.interaction_name
        nonce = message.nonce

        if (
            message.has_kind(MessageKind.DESCRIBE_START)
            and interaction_name == "describe"
            and nonce
        ):
            job = instance.get_running_job_by_nonce(nonce)
            if not job:
                return False

            job.context.progress_message_id = message.message_id
            instance.save_and_notify(job)
            return True

        if message.has_kind(MessageKind.DESCRIBE_DONE):
            progress_message_id = message.message_id
            if not progress_message_id:
                return False

            def predicate(j: Job):
                return (
                    j.context.progress_message_id == progress_message_id
                    and j.action == JobAction.DESCRIBE
                )

            job = instance.get_running_job_by_condition(predicate)
            if not job:
                return False

            description = message.prompt or ""
            job.prompt = description
            job.prompt_en = description
            job.context.final_prompt = description
            if message.image_url:
                job.image_url = message.image_url

            instance.apply_transition(job, JobTransition.SUCCEED)
            instance.save_and_notify(job)
            self._safe_dump(
                instance,
                "dump_describe",
                message=message.raw,
                prompt=description,
            )
            return True

        return False


__all__ = ["DescribeReactor"]
