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
from mutiny.domain.result_shapes import produces_grid_result
from mutiny.engine.reactors.base import MessageReactor
from mutiny.types import JobAction


class VariationReactor(MessageReactor):
    def handle_message(self, instance, event_type: str, message: InterpretedMessage) -> bool:
        if not message.has_kind(MessageKind.VARIATION_SUCCESS):
            return False
        prompt = message.prompt
        if not prompt or not message.attachments:
            return False

        actions = [
            JobAction.VARIATION,
            JobAction.VARY_SUBTLE,
            JobAction.VARY_STRONG,
            JobAction.INPAINT,
        ]
        matched_job = None
        for act in actions:
            matched_job = self.find_and_finish_image_job(
                instance,
                act,
                prompt,
                message,
                require_new_message=True,
            )
            if matched_job is not None:
                if produces_grid_result(act):
                    instance.schedule_image_indexing(act, message.raw, matched_job)
                break
        if matched_job is not None:
            self._safe_dump(instance, "dump_variation", message=message.raw, prompt=prompt)
        return matched_job is not None


__all__ = ["VariationReactor"]
