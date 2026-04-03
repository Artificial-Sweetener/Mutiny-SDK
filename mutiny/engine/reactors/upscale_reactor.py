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
from mutiny.engine.progress import build_promotion_progress
from mutiny.engine.prompt_matching import normalize_prompt_for_matching
from mutiny.engine.reactors.base import MessageReactor
from mutiny.types import JobAction, JobStatus


class UpscaleReactor(MessageReactor):
    def _find_pending_tile_promotion_job(self, instance, message: InterpretedMessage):
        """Return one in-flight job waiting for the hidden `U#` promotion result."""

        prompt = message.prompt
        if not prompt:
            return None

        def _base_match(job) -> bool:
            return (
                job.status == JobStatus.IN_PROGRESS
                and job.context.implicit_tile_promotion_pending
                and normalize_prompt_for_matching(job.context.final_prompt or job.prompt)
                == normalize_prompt_for_matching(prompt)
            )

        if message.referenced_message_id:
            task = instance.get_running_job_by_condition(
                lambda job: _base_match(job)
                and job.context.message_id == message.referenced_message_id
            )
            if task:
                return task
        return instance.get_running_job_by_condition(_base_match)

    def _handle_pending_tile_promotion(self, instance, message: InterpretedMessage) -> bool:
        """Consume the intermediate promoted single-image result for one tile job."""

        if message.upscale_variant != "tile_promotion" or not message.message_id:
            return False

        task = self._find_pending_tile_promotion_job(instance, message)
        if task is None:
            return False

        if message.image_url:
            task.image_url = message.image_url
        task.context.message_id = message.message_id
        if message.message_hash:
            task.context.message_hash = message.message_hash
        if message.flags is not None:
            task.context.flags = message.flags
        task.context.index = 1
        task.context.implicit_tile_promotion_pending = False
        task.context.implicit_tile_promotion_index = None
        if message.prompt:
            task.context.final_prompt = message.prompt
        instance.save_and_notify(task)
        instance.notify_bus.publish_progress(build_promotion_progress(task))
        instance.schedule_internal_follow_up_action(task)
        return True

    def handle_message(self, instance, event_type: str, message: InterpretedMessage) -> bool:
        if not message.has_kind(MessageKind.UPSCALE_SUCCESS):
            return False
        prompt = message.prompt
        if not prompt or not message.attachments:
            return False
        if self._handle_pending_tile_promotion(instance, message):
            return True

        actions = [
            JobAction.UPSCALE,
            JobAction.UPSCALE_V7_2X_SUBTLE,
            JobAction.UPSCALE_V7_2X_CREATIVE,
            JobAction.ZOOM_OUT_2X,
            JobAction.ZOOM_OUT_1_5X,
            JobAction.PAN_LEFT,
            JobAction.PAN_RIGHT,
            JobAction.PAN_UP,
            JobAction.PAN_DOWN,
            JobAction.CUSTOM_ZOOM,
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
                break
        if matched_job is not None:
            instance.schedule_image_indexing(matched_job.action, message.raw, matched_job)
            self._safe_dump(instance, "dump_upscale", message=message.raw, prompt=prompt)
        return matched_job is not None


__all__ = ["UpscaleReactor"]
