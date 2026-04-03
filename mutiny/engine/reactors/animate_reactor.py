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

import re

from mutiny.discord.message_interpreter import InterpretedMessage
from mutiny.domain.state_machine import JobTransition
from mutiny.engine.prompt_matching import normalize_prompt_for_matching
from mutiny.engine.reactors.base import MessageReactor
from mutiny.types import JobAction, JobStatus

_WEBSITE_URL_RE = re.compile(r"https://(?:www\.)?midjourney\.com/jobs/[^\s)>]+", re.IGNORECASE)


class AnimateReactor(MessageReactor):
    """Complete ANIMATE_* tasks when a reply with a video attachment arrives."""

    @staticmethod
    def _is_source_video_echo_for_extend(task, message: InterpretedMessage) -> bool:
        """Ignore replayed updates for the source video while one extend is still pending.

        Midjourney emits updates to the original source video message after an extend
        button press. Those updates are not the new extend result and must not finish
        the in-flight extend job before the new preview/U1 stage arrives.
        """

        if task.action not in {JobAction.ANIMATE_EXTEND_HIGH, JobAction.ANIMATE_EXTEND_LOW}:
            return False
        if task.context.prompt_video_follow_up_requested:
            return False
        return bool(message.message_hash and message.message_hash == task.context.message_hash)

    def _is_video_attachment(self, att: dict) -> bool:
        ctype = (att.get("content_type") or att.get("contentType") or "").lower()
        filename = (att.get("filename") or "").lower()
        url = (att.get("url") or "").lower()
        if ctype.startswith("video/"):
            return True
        if filename.endswith(".mp4") or filename.endswith(".webm") or filename.endswith(".gif"):
            return True
        if url.endswith(".mp4") or url.endswith(".webm") or url.endswith(".gif"):
            return True
        return False

    @staticmethod
    def _find_prompt_video_follow_up_custom_id(message: InterpretedMessage) -> str | None:
        """Return the observed prompt-video follow-up custom id when present."""

        for row in message.components or []:
            for component in row.get("components") or []:
                custom_id = component.get("custom_id")
                if isinstance(custom_id, str) and custom_id.startswith(
                    "MJ::JOB::video_virtual_upscale::"
                ):
                    return custom_id
        return None

    @staticmethod
    def _extract_website_url(message: InterpretedMessage) -> str | None:
        """Extract the exact Midjourney website URL supplied by the bot message."""

        for row in message.components or []:
            for component in row.get("components") or []:
                url = component.get("url")
                if isinstance(url, str) and _WEBSITE_URL_RE.match(url):
                    return url

        content_match = _WEBSITE_URL_RE.search(message.content or "")
        if content_match is not None:
            return content_match.group(0)
        return None

    def _find_running_animate_job(self, instance, message: InterpretedMessage):
        """Match one in-progress animate job against the supplied Discord message."""

        prompt = normalize_prompt_for_matching(message.prompt)
        ref_id = message.referenced_message_id
        message_hash = message.message_hash

        def _base_match(job) -> bool:
            return (
                job.action
                in {
                    JobAction.ANIMATE_HIGH,
                    JobAction.ANIMATE_LOW,
                    JobAction.ANIMATE_EXTEND_HIGH,
                    JobAction.ANIMATE_EXTEND_LOW,
                }
                and job.status == JobStatus.IN_PROGRESS
            )

        task = None
        if ref_id:
            task = instance.get_running_job_by_condition(
                lambda job: _base_match(job) and job.context.message_id == ref_id
            )
        if task is None and message_hash:
            task = instance.get_running_job_by_condition(
                lambda job: _base_match(job) and job.context.message_hash == message_hash
            )
        if task is None and prompt:
            task = instance.get_running_job_by_condition(
                lambda job: _base_match(job)
                and normalize_prompt_for_matching(job.context.final_prompt or job.prompt) == prompt
            )
        return task

    def _handle_prompt_video_intermediate(self, instance, message: InterpretedMessage) -> bool:
        """Promote one prompt-video still-image result into the observed follow-up flow."""

        custom_id = self._find_prompt_video_follow_up_custom_id(message)
        if not custom_id or not message.image_url or not message.message_id:
            return False

        task = self._find_running_animate_job(instance, message)
        if not task or task.context.prompt_video_follow_up_requested:
            return False

        task.image_url = message.image_url
        website_url = self._extract_website_url(message)
        if website_url:
            task.artifacts.website_url = website_url
        task.context.message_id = message.message_id
        task.context.message_hash = message.message_hash
        if message.flags is not None:
            task.context.flags = message.flags
        task.context.prompt_video_follow_up_requested = True
        task.context.index = 1
        instance.save_and_notify(task)
        instance.schedule_prompt_video_follow_up(
            task,
            message_id=message.message_id,
            custom_id=custom_id,
            message_flags=message.flags or 0,
        )
        return True

    def _handle_prompt_video_non_video_result(self, instance, message: InterpretedMessage) -> bool:
        """Capture one non-video animate result without completing the job prematurely."""

        task = self._find_running_animate_job(instance, message)
        if not task:
            return False
        if self._is_source_video_echo_for_extend(task, message):
            return False

        website_url = self._extract_website_url(message)
        if website_url:
            task.artifacts.website_url = website_url
        if message.image_url:
            task.image_url = message.image_url
        if message.message_id:
            task.context.message_id = message.message_id
        if message.message_hash:
            task.context.message_hash = message.message_hash
        if message.flags is not None:
            task.context.flags = message.flags

        instance.save_and_notify(task)
        return bool(website_url or message.image_url or message.message_id)

    def handle_message(self, instance, event_type: str, message: InterpretedMessage) -> bool:
        atts = message.attachments or []
        if not atts:
            if self._handle_prompt_video_intermediate(instance, message):
                return True
            return self._handle_prompt_video_non_video_result(instance, message)

        video_attachment = next((a for a in atts if self._is_video_attachment(a)), None)
        if video_attachment is None:
            if self._handle_prompt_video_intermediate(instance, message):
                return True
            return self._handle_prompt_video_non_video_result(instance, message)

        video_url = video_attachment.get("url")
        if not video_url:
            return False

        task = self._find_running_animate_job(instance, message)
        if not task:
            return False
        if self._is_source_video_echo_for_extend(task, message):
            return False

        website_url = self._extract_website_url(message)
        if website_url:
            task.artifacts.website_url = website_url
        task.artifacts.video_url = video_url
        for a in atts:
            if not self._is_video_attachment(a) and a.get("url"):
                task.image_url = a.get("url")
                break
        task.context.message_id = message.message_id
        if message.message_hash:
            task.context.message_hash = message.message_hash
        if message.flags is not None:
            task.context.flags = message.flags
        task.context.index = 1
        instance.apply_transition(task, JobTransition.SUCCEED)
        instance.save_and_notify(task)
        instance.schedule_video_indexing(message.raw, task)
        return True


__all__ = ["AnimateReactor"]
