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

"""Async artifact indexing coordinator extracted from DiscordEngine."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from mutiny.discord.custom_ids import CustomIdKind, parse_custom_id
from mutiny.discord.message_interpreter import extract_message_hash
from mutiny.domain.result_shapes import produces_grid_result
from mutiny.interfaces.image import ImageProcessor
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.image_tiles import ImageTilesService
from mutiny.services.video_signature import VideoSignatureService
from mutiny.types import Job, JobAction, TileFollowUpMode

logger = logging.getLogger(__name__)


class IndexingCoordinator:
    """Fetch artifacts, compute signatures, and persist recognized job refs."""

    def __init__(
        self,
        *,
        commands: Any,
        image_processor: ImageProcessor,
        artifact_cache: ArtifactCacheService,
        video_signature_service: VideoSignatureService,
        report_system_error=None,
    ) -> None:
        self._commands = commands
        self._image_processor = image_processor
        self._artifact_cache = artifact_cache
        self._video_signature_service = video_signature_service
        self._tiles_service = ImageTilesService(image_processor)
        self._report_system_error = report_system_error
        self._pending_tasks: set[asyncio.Task[None]] = set()

    def schedule_image_indexing(self, action: JobAction, message: dict, job: Job) -> None:
        self._schedule_task(self._index_image(action, message, job))

    def schedule_video_indexing(self, message: dict, job: Job) -> None:
        """Schedule indexing for one successful final animate-family video reply."""
        self._schedule_task(self._index_video(message, job))

    async def drain_pending(self, *, timeout_seconds: float = 30.0) -> None:
        """Wait for in-flight indexing work before provider shutdown."""

        if not self._pending_tasks:
            return
        done, pending = await asyncio.wait(
            list(self._pending_tasks),
            timeout=timeout_seconds,
        )
        for task in done:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if not pending:
            return
        logger.warning(
            "Timed out draining artifact indexing tasks",
            extra={"pending_count": len(pending), "timeout_seconds": timeout_seconds},
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    def _schedule_task(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _index_image(self, action: JobAction, message: dict, job: Job) -> None:
        try:
            proc = self._image_processor

            attachment = _first_attachment(message)
            if not attachment:
                return
            url = attachment.get("url")
            if not url:
                return
            data = await self._commands.fetch_cdn_bytes(url)
            if not data:
                return
            width, height = proc.get_dimensions(data)
            flags = int(message.get("flags") or 0)

            if produces_grid_result(action):
                tiles = self._tiles_service.expand_tiles(job, data)
                if not tiles or not tiles[0].is_grid_tile:
                    return

                msg_hash = job.context.message_hash or extract_message_hash(url) or ""
                action_custom_ids = _extract_action_custom_ids(message)
                message_id = message.get("id")
                if not message_id:
                    return
                for tile in tiles:
                    digest = proc.compute_digest(tile.image_bytes)
                    phv = proc.compute_phash(tile.image_bytes)
                    tw, th = proc.get_dimensions(tile.image_bytes)
                    self._artifact_cache.put_image_job_ref(
                        digest,
                        message_id=str(message_id),
                        message_hash=msg_hash,
                        flags=flags,
                        index=tile.index,
                        prompt_text=job.context.final_prompt or job.prompt,
                        tile_follow_up_mode=job.context.tile_follow_up_mode,
                        action_custom_ids=action_custom_ids,
                        phash=phv,
                        width=tw,
                        height=th,
                        kind="tile",
                    )
            elif action == JobAction.UPSCALE:
                if job.context.tile_follow_up_mode is TileFollowUpMode.MODERN and int(
                    job.context.index or 0
                ) in {1, 2, 3, 4}:
                    # For modern/default models the visual bytes of the split tile and the
                    # `U#` promotion result are identical. Keep the canonical recognized
                    # artifact tied to the tile surface so later V#/promotion flows still
                    # resolve back to the original grid context.
                    return
                digest = proc.compute_digest(data)
                phv = proc.compute_phash(data)
                msg_id = message.get("id")
                if not msg_id:
                    return
                msg_hash = job.context.message_hash or extract_message_hash(url) or ""
                self._artifact_cache.put_image_job_ref(
                    digest,
                    message_id=str(msg_id),
                    message_hash=msg_hash,
                    flags=flags,
                    prompt_text=job.context.final_prompt or job.prompt,
                    action_custom_ids=_extract_action_custom_ids(message),
                    # Public lookup treats already-upscaled images as single-image results.
                    # Follow-up actions normalize this to their concrete button index later.
                    index=0,
                    phash=phv,
                    width=width,
                    height=height,
                    kind="upscale",
                )
        except Exception as exc:
            self._log_indexing_error(action=action, message=message, job=job)
            self._report_failure(
                error=exc,
                action=action,
                message=message,
                job=job,
            )

    async def _index_video(self, message: dict, job: Job) -> None:
        """Index one final Discord video reply for later video-based recognition."""
        try:
            attachment = _first_video_attachment(message)
            if not attachment:
                return
            url = attachment.get("url")
            if not url:
                return
            if not job.context.message_hash:
                logger.warning(
                    "Skipping video indexing without message hash",
                    extra={"job_id": job.id, "message_id": message.get("id")},
                )
                return
            data = await self._commands.fetch_cdn_bytes(url)
            if not data:
                return
            message_id = message.get("id")
            if not message_id:
                return
            signature = self._video_signature_service.compute_signature(data)
            self._artifact_cache.put_video_job_ref(
                signature.digest,
                message_id=str(message_id),
                message_hash=job.context.message_hash,
                flags=int(message.get("flags") or 0),
                signature_version=signature.version,
                prompt_text=job.context.final_prompt or job.prompt,
                action_custom_ids=_extract_action_custom_ids(message),
            )
        except Exception as exc:
            self._log_indexing_error(action=job.action, message=message, job=job)
            self._report_failure(
                error=exc,
                action=job.action,
                message=message,
                job=job,
            )

    def _log_indexing_error(
        self, *, action: JobAction | None, message: dict, job: Job | None = None
    ) -> None:
        logger.exception(
            "Artifact indexing failed",
            extra={
                "job_id": getattr(job, "id", None),
                "action": action.value if action else None,
                "message_id": message.get("id") if isinstance(message, dict) else None,
            },
        )

    def _report_failure(
        self,
        *,
        error: Exception,
        action: JobAction | None,
        message: dict,
        job: Job | None,
    ) -> None:
        if not callable(self._report_system_error):
            return
        self._report_system_error(
            error,
            {
                "job_id": getattr(job, "id", None),
                "action": action.value if action else None,
                "message_id": message.get("id") if isinstance(message, dict) else None,
            },
        )


def _first_attachment(message: dict) -> dict | None:
    attachments = message.get("attachments") if isinstance(message, dict) else None
    if not attachments:
        return None
    return attachments[0] if isinstance(attachments, list) else None


def _first_video_attachment(message: dict) -> dict | None:
    attachments = message.get("attachments") if isinstance(message, dict) else None
    if not isinstance(attachments, list):
        return None
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        content_type = str(
            attachment.get("content_type") or attachment.get("contentType") or ""
        ).lower()
        filename = str(attachment.get("filename") or "").lower()
        if content_type.startswith("video/") or filename.endswith((".mp4", ".webm", ".gif")):
            return attachment
    return None


__all__ = ["IndexingCoordinator"]


def _extract_action_custom_ids(message: dict) -> dict[str, str]:
    """Extract persisted follow-up component ids from one Midjourney message."""

    action_custom_ids: dict[str, str] = {}
    for custom_id in _iter_message_custom_ids(message):
        parsed = parse_custom_id(custom_id)
        if parsed is None:
            continue
        if parsed.kind is CustomIdKind.UPSCALE_SOLO and parsed.mode in {"subtle", "creative"}:
            action_custom_ids[f"upscale_{parsed.mode}"] = custom_id
        elif parsed.kind is CustomIdKind.ANIMATE_EXTEND and parsed.level in {"high", "low"}:
            action_custom_ids[f"animate_extend_{parsed.level}"] = custom_id
    return action_custom_ids


def _iter_message_custom_ids(message: dict) -> list[str]:
    """Return every component custom id found on one Discord message payload."""

    custom_ids: list[str] = []
    for row in message.get("components") or []:
        if not isinstance(row, dict):
            continue
        for component in row.get("components") or []:
            if not isinstance(component, dict):
                continue
            custom_id = component.get("custom_id")
            if custom_id:
                custom_ids.append(str(custom_id))
    return custom_ids
