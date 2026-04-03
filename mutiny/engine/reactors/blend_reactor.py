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
from mutiny.engine.reactors.base import MessageReactor
from mutiny.types import JobAction


class BlendReactor(MessageReactor):
    """Handles messages indicating a successful blend task."""

    def handle_message(self, instance, event_type: str, message: InterpretedMessage) -> bool:
        if not message.has_kind(MessageKind.BLEND_SUCCESS):
            return False
        prompt = message.prompt
        if not prompt or not message.attachments:
            return False

        if not prompt.startswith("<https://s.mj.run"):
            return False

        job = self.find_and_finish_image_job(instance, JobAction.BLEND, prompt, message)
        if job is not None:
            instance.schedule_image_indexing(job.action, message.raw, job)
            self._safe_dump(instance, "dump_blend", message=message.raw, prompt=prompt)
        return job is not None


__all__ = ["BlendReactor"]
