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

from typing import List

import httpx

from mutiny.domain.result_shapes import (
    produces_grid_result,
    produces_single_image_result,
)
from mutiny.interfaces.image import ImageProcessor
from mutiny.services.context import AppContext
from mutiny.services.error_catalog import (
    TILE_EXTRACT_FAILED,
    TILE_FETCH_FAILED,
    TILE_INDEX_INVALID,
    TILE_JOB_NOT_FOUND,
    TILE_NOT_AVAILABLE,
    error_result,
)
from mutiny.services.image_processor import OpenCVImageProcessor
from mutiny.types import Job, JobTile, Result


async def fetch_job_tile_bytes(job_id: str, index: int, ctx: AppContext) -> Result[bytes]:
    """Fetch one tile image for a completed grid-producing job."""

    if index not in (1, 2, 3, 4):
        return error_result(TILE_INDEX_INVALID)

    job = ctx.job_store.get(job_id)
    if not job:
        return error_result(TILE_JOB_NOT_FOUND)
    if not produces_grid_result(job.action) or not job.image_url:
        return error_result(TILE_NOT_AVAILABLE)

    timeout = httpx.Timeout(
        connect=ctx.config.cdn.connect_timeout,
        read=ctx.config.cdn.read_timeout,
        write=ctx.config.cdn.write_timeout,
        pool=ctx.config.cdn.pool_timeout,
    )
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(job.image_url)
            resp.raise_for_status()
            data = resp.content
    except httpx.HTTPError as exc:
        return error_result(TILE_FETCH_FAILED, message=f"Failed to fetch image: {exc}")

    try:
        tiles = ctx.image_processor.crop_split_grid(data)
        if index > len(tiles):
            return error_result(TILE_INDEX_INVALID)
        return Result(code=1, message="Tile extracted", value=tiles[index - 1])
    except Exception:
        return error_result(TILE_EXTRACT_FAILED)


class ImageTilesService:
    """Split completed Midjourney images into the public logical tile surface."""

    def __init__(self, image_processor: ImageProcessor | None = None) -> None:
        self._image_processor = image_processor or OpenCVImageProcessor()

    def expand_tiles(self, job: Job, image_data: bytes) -> List[JobTile]:
        """
        Split a job's image data into logical tiles.

        - Single-image result actions return one tile with index ``0``.
        - Grid-producing actions return four tiles with indices ``1..4``.
        """
        if not image_data:
            return []

        if produces_single_image_result(job.action) or not produces_grid_result(job.action):
            return [
                JobTile(job_id=job.id, index=0, original_action=job.action, image_bytes=image_data)
            ]

        try:
            processor_tiles = self._image_processor.crop_split_grid(image_data)
        except Exception:
            processor_tiles = []

        if len(processor_tiles) == 4:
            return [
                JobTile(
                    job_id=job.id,
                    index=index,
                    original_action=job.action,
                    image_bytes=tile_bytes,
                )
                for index, tile_bytes in enumerate(processor_tiles, start=1)
            ]
        return [JobTile(job_id=job.id, index=0, original_action=job.action, image_bytes=image_data)]


__all__ = ["fetch_job_tile_bytes", "ImageTilesService"]
