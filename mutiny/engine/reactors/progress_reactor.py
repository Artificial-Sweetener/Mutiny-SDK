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
from mutiny.engine.progress import JobProgress
from mutiny.engine.reactors.base import MessageReactor


class ProgressReactor(MessageReactor):
    def handle_message(self, instance, event_type: str, message: InterpretedMessage) -> bool:
        if not message.has_kind(MessageKind.PROGRESS):
            return False
        progress = JobProgress()
        parsed = message.as_progress()
        if not parsed:
            return False

        status_text = (parsed.status or "").strip().lower()
        if status_text and ("%" not in status_text) and ("wait" not in status_text):
            return False

        interaction_id = message.interaction_id
        nonce = message.nonce

        message_hash = message.message_hash
        progress_message_id = message.message_id
        ref_id = message.referenced_message_id
        job = progress.match_job(
            instance,
            interaction_id=interaction_id,
            nonce=nonce,
            progress_message_id=progress_message_id,
            referenced_message_id=ref_id,
            message_hash=message_hash,
            prompt=parsed.prompt,
        )
        if not job:
            return False

        if interaction_id:
            job.context.interaction_id = interaction_id

        if not job.context.progress_message_id:
            event = progress.apply_start(job, message, parsed)
        else:
            event = progress.apply_progress_update(job, message, parsed)
        instance.save_and_notify(job)
        instance.notify_bus.publish_progress(event)
        if message.attachments or message.components:
            self._safe_dump(
                instance,
                "dump_progress",
                message=message.raw,
                prompt=parsed.prompt if hasattr(parsed, "prompt") else None,
            )
        return True


__all__ = ["ProgressReactor"]
