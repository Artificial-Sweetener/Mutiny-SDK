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

from mutiny.discord.constants import ERROR_EMBED_COLOR
from mutiny.discord.message_interpreter import InterpretedMessage, MessageKind
from mutiny.domain.state_machine import JobTransition
from mutiny.engine.reactors.base import MessageReactor
from mutiny.services.error_catalog import format_moderation_rejection_reason
from mutiny.types import Job, JobStatus


class ErrorReactor(MessageReactor):
    """Fail running jobs when Midjourney sends a referenced error reply."""

    ERROR_COLOR = ERROR_EMBED_COLOR

    def handle_message(self, instance, event_type: str, message: InterpretedMessage) -> bool:
        """Apply a fail transition for referenced Midjourney error replies."""
        if not message.has_kind(MessageKind.ERROR):
            return False

        title = message.error_title or ""
        description = message.error_description or ""
        footer = (message.error_footer or "").strip()
        referenced_message_id = message.referenced_message_id

        if not referenced_message_id:
            return False

        def predicate(j: Job):
            return (
                j.context.progress_message_id == referenced_message_id
                or j.context.message_id == referenced_message_id
            ) and j.status != JobStatus.SUCCEEDED

        job = instance.get_running_job_by_condition(predicate)
        if not job:
            return False

        fail_reason = _build_fail_reason(title=title, description=description, footer=footer)
        instance.apply_transition(job, JobTransition.FAIL, fail_reason)
        instance.save_and_notify(job)
        self._safe_dump(
            instance,
            "dump_error",
            message=message.raw,
            error_title=title or None,
            error_description=description or None,
            error_footer=footer or None,
        )

        return True


_RELATIVE_TIMESTAMP_RE = re.compile(r"<t:\d+:R>")
_UNRECOGNIZED_PARAMETER_RE = re.compile(r"(?i)\bunrecognized parameter\(s\)\s*:\s*(.+)")


def _build_fail_reason(*, title: str, description: str, footer: str) -> str:
    """Return a stable job failure reason for a Midjourney error reply."""

    if title.strip().lower() == "slow down!":
        relative_timestamp = _extract_relative_timestamp(description)
        if relative_timestamp:
            return (
                f"Midjourney rate-limited this follow-up. You can try again {relative_timestamp}."
            )
        return "Midjourney rate-limited this follow-up. Try again after the cooldown expires."
    if footer.lower().startswith("decline-"):
        return format_moderation_rejection_reason(footer)
    parameter_validation_reason = _extract_parameter_validation_reason(title, description)
    if parameter_validation_reason is not None:
        return parameter_validation_reason
    if title and description:
        return f"[{title}] {description}"
    return title or description or "Midjourney reported an error"


def _extract_relative_timestamp(description: str) -> str | None:
    """Return one Discord relative timestamp token from an error description."""

    match = _RELATIVE_TIMESTAMP_RE.search(description or "")
    if match is None:
        return None
    return match.group(0)


def _extract_parameter_validation_reason(title: str, description: str) -> str | None:
    """Return a stable failure string for Midjourney parameter-validation replies."""

    title_text = (title or "").strip()
    description_text = (description or "").strip()
    if title_text.lower() != "invalid parameter" and not _UNRECOGNIZED_PARAMETER_RE.search(
        description_text
    ):
        return None

    match = _UNRECOGNIZED_PARAMETER_RE.search(description_text)
    if match is not None:
        return (
            "Midjourney rejected the prompt: "
            f"Unrecognized parameter(s): {match.group(1).strip()}."
        )
    return "Midjourney rejected the prompt because one or more parameters were invalid."


__all__ = ["ErrorReactor"]
