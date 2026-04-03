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

from typing import Optional

from mutiny.discord.custom_ids import CustomIdKind, parse_custom_id
from mutiny.discord.message_interpreter import InterpretedMessage, ProgressParse
from mutiny.domain.progress import ProgressEvent
from mutiny.domain.state_machine import JobStateMachine, JobTransition
from mutiny.engine.prompt_matching import normalize_prompt_for_matching
from mutiny.types import Job, JobStatus

PROMOTION_PROGRESS_KIND = "promotion"
PROMOTION_STATUS_TEXT = "Preparing tile follow-up"


class JobProgress:
    """Owns progress parsing and progress_message_id assignment."""

    def apply_start(
        self, job: Job, message: InterpretedMessage, parsed: ProgressParse
    ) -> ProgressEvent:
        if job.status == JobStatus.SUBMITTED:
            JobStateMachine.apply(job, JobTransition.START)
        job.context.progress_message_id = message.message_id
        if parsed.prompt:
            job.context.final_prompt = parsed.prompt
        self._apply_cancel_context(job, message.raw)
        not_fast = self._is_not_fast(parsed.status)
        if not_fast:
            job.context.not_fast = True
        return ProgressEvent(
            job_id=job.id,
            kind="start",
            status_text=parsed.status,
            prompt=parsed.prompt,
            progress_message_id=job.context.progress_message_id,
            message_id=message.message_id,
            flags=None,
            image_url=None,
            message_hash=None,
            not_fast=not_fast,
        )

    def apply_progress_update(
        self, job: Job, message: InterpretedMessage, parsed: ProgressParse
    ) -> ProgressEvent:
        job.progress = parsed.status
        not_fast = self._is_not_fast(parsed.status)
        if not_fast:
            job.context.not_fast = True
        flags = None
        if message.flags is not None:
            flags = message.flags
            job.context.flags = flags
        image_url = message.image_url
        message_hash = message.message_hash
        if image_url:
            job.image_url = image_url
        if message_hash:
            job.context.message_hash = message_hash
        self._apply_cancel_context(job, message.raw)
        return ProgressEvent(
            job_id=job.id,
            kind="progress",
            status_text=parsed.status,
            prompt=parsed.prompt,
            progress_message_id=job.context.progress_message_id,
            message_id=message.message_id,
            flags=flags,
            image_url=image_url,
            message_hash=message_hash,
            not_fast=not_fast,
        )

    def match_job(
        self,
        instance,
        *,
        interaction_id: Optional[str],
        nonce: Optional[str],
        progress_message_id: Optional[str],
        referenced_message_id: Optional[str],
        message_hash: Optional[str],
        prompt: Optional[str],
    ) -> Job | None:
        if interaction_id:
            job = instance.get_running_job_by_condition(
                lambda j: j.context.interaction_id == interaction_id
            )
            if job:
                return job
        if nonce:
            job = instance.get_running_job_by_condition(lambda j: j.context.nonce == nonce)
            if job:
                return job
        if progress_message_id:
            job = instance.get_running_job_by_condition(
                lambda j: j.context.progress_message_id == progress_message_id
            )
            if job:
                return job
        if referenced_message_id:
            job = instance.get_running_job_by_condition(
                lambda j: j.status == JobStatus.IN_PROGRESS
                and j.context.message_id == referenced_message_id
            )
            if job:
                return job
        if message_hash:
            job = instance.get_running_job_by_condition(
                lambda j: j.status == JobStatus.IN_PROGRESS
                and j.context.message_hash == message_hash
            )
            if job:
                return job
        norm_prompt = normalize_prompt_for_matching(prompt)
        if not norm_prompt:
            return None
        return instance.get_running_job_by_condition(
            lambda j: j.status == JobStatus.IN_PROGRESS
            and normalize_prompt_for_matching(j.context.final_prompt or j.prompt) == norm_prompt
        )

    def _apply_cancel_context(self, job: Job, message: dict) -> None:
        try:
            comps = message.get("components") or []
            for row in comps:
                for comp in row.get("components") or []:
                    cid = comp.get("custom_id")
                    if isinstance(cid, str):
                        parsed = parse_custom_id(cid)
                        if parsed and parsed.kind == CustomIdKind.CANCEL:
                            job.context.cancel_message_id = message.get("id")
                            job.context.cancel_job_id = parsed.job_id
                            if "flags" in message and message.get("flags") is not None:
                                job.context.flags = int(message.get("flags") or 0)
                            raise StopIteration
        except StopIteration:
            pass

    @staticmethod
    def _is_not_fast(status: Optional[str]) -> bool:
        try:
            status_text = (status or "").strip().lower()
            return bool(status_text and ("fast" not in status_text))
        except Exception:
            return False


def build_promotion_progress(job: Job) -> ProgressEvent:
    """Return one internal progress event for a completed modern tile promotion hop."""

    return ProgressEvent(
        job_id=job.id,
        kind=PROMOTION_PROGRESS_KIND,
        status_text=PROMOTION_STATUS_TEXT,
        prompt=job.context.final_prompt or job.prompt,
        progress_message_id=None,
        message_id=job.context.message_id,
        flags=job.context.flags,
        image_url=job.image_url,
        message_hash=job.context.message_hash,
        not_fast=True if job.context.not_fast else None,
    )


__all__ = [
    "JobProgress",
    "PROMOTION_PROGRESS_KIND",
    "PROMOTION_STATUS_TEXT",
    "build_promotion_progress",
]
