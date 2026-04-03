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

"""Helpers for preparing image artifacts before provider submission."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from mimetypes import guess_extension
from typing import TYPE_CHECKING, Callable

from mutiny.domain.state_machine import JobStateMachine, JobTransition
from mutiny.services.image_utils import parse_data_url

if TYPE_CHECKING:  # pragma: no cover - for type checkers only
    from mutiny.engine.action_dispatcher import ActionContext
    from mutiny.types import Job


@dataclass
class ImagePrepResult:
    cdn_url: str | None
    uploaded_name: str | None
    digest: str | None
    cache_hit: bool
    error: str | None


def _format_reason(base: str, index_label: str) -> str:
    return f"{base} at {index_label}" if index_label else base


async def prepare_image_input(
    ctx: "ActionContext",
    job: "Job",
    b64: str,
    *,
    index_label: str,
    filename_factory: Callable[[str], str],
    use_cache: bool,
    fetch_cdn: bool,
    cdn_required: bool,
) -> ImagePrepResult:
    """Parse data-url, hash, cache, upload, and optionally fetch CDN URL."""

    data_url = parse_data_url(b64)
    if not data_url:
        reason = _format_reason("Invalid Base64 Data URL", index_label)
        JobStateMachine.apply(job, JobTransition.FAIL, reason)
        return ImagePrepResult(None, None, None, False, reason)

    file_ext = guess_extension(data_url.mime_type) or ".png"
    filename = filename_factory(file_ext)
    digest = hashlib.sha256(data_url.data).hexdigest() if use_cache else None

    if use_cache and digest:
        cached = ctx.artifact_cache.get_image_upload_url(digest)
        if cached:
            return ImagePrepResult(cached, None, digest, True, None)

    uploaded_name = await ctx.commands.upload(filename, data_url.data, data_url.mime_type)
    if not uploaded_name:
        reason = _format_reason("Failed to upload file", index_label)
        JobStateMachine.apply(job, JobTransition.FAIL, reason)
        return ImagePrepResult(None, None, digest, False, reason)

    if not fetch_cdn:
        return ImagePrepResult(None, uploaded_name, digest, False, None)

    image_url = await ctx.commands.send_image_message("", uploaded_name)
    if not image_url:
        if cdn_required:
            reason = _format_reason("Failed to get CDN URL for file", index_label)
            JobStateMachine.apply(job, JobTransition.FAIL, reason)
            return ImagePrepResult(None, uploaded_name, digest, False, reason)
        return ImagePrepResult(None, uploaded_name, digest, False, None)

    if use_cache and digest:
        ctx.artifact_cache.put_image_upload(digest, image_url)

    return ImagePrepResult(image_url, uploaded_name, digest, False, None)


__all__ = ["ImagePrepResult", "prepare_image_input"]
