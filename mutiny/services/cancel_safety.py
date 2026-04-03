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

from dataclasses import dataclass
from typing import Optional

from mutiny.types import Job


@dataclass
class CancelContext:
    can_cancel: bool
    message_id: Optional[str] = None
    job_id: Optional[str] = None
    message_flags: Optional[int] = None
    error_code: Optional[int] = None
    error_message: Optional[str] = None


def can_cancel(job: Job) -> CancelContext:
    """Determine if a job can be safely cancelled.

    Relaxed from action-based checks to rely on ephemeral Cancel context observed on
    progress messages (flags==64) and presence of cancel identifiers. This avoids having
    to manually tack on new actions as MJ evolves.
    """
    # Require a progress/ephemeral message context to target
    cancel_message_id = job.context.cancel_message_id or job.context.progress_message_id
    if not cancel_message_id:
        return CancelContext(
            can_cancel=False,
            error_code=400,
            error_message="Cancel not available yet (no progress message)",
        )

    # Prefer explicit cancel job id; otherwise fall back to base message hash
    job_id = job.context.cancel_job_id or job.context.message_hash
    if not job_id:
        return CancelContext(
            can_cancel=False,
            error_code=400,
            error_message="Cancel not available yet (no job id)",
        )

    # Cancel button appears on an ephemeral message with flags=64
    message_flags = int(job.context.flags or 0)
    if message_flags != 64:
        return CancelContext(
            can_cancel=False,
            error_code=409,
            error_message="Cancel not available yet (awaiting Cancel button)",
        )

    return CancelContext(
        can_cancel=True,
        message_id=cancel_message_id,
        job_id=job_id,
        message_flags=message_flags,
    )


__all__ = ["CancelContext", "can_cancel"]
