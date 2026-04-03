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

import pytest

from mutiny.domain.job import Job, JobAction, JobStatus
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.context import AppContext
from mutiny.services.image_tiles import ImageTilesService, fetch_job_tile_bytes
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.job_store import InMemoryJobStoreService
from mutiny.services.metrics.service import MetricsService
from mutiny.services.notify.event_bus import StreamingJobUpdateBus
from mutiny.services.response_dump import ResponseDumpService
from tests.image_helpers import make_grid_png, make_solid_png, rgb_pixel


@pytest.mark.parametrize(
    ("action", "image_bytes", "expected_indices"),
    [
        (JobAction.IMAGINE, make_grid_png(), (1, 2, 3, 4)),
        (JobAction.INPAINT, make_grid_png(), (1, 2, 3, 4)),
        (JobAction.PAN_LEFT, make_grid_png(), (1, 2, 3, 4)),
        (JobAction.ZOOM_OUT_2X, make_grid_png(), (1, 2, 3, 4)),
        (JobAction.CUSTOM_ZOOM, make_grid_png(), (1, 2, 3, 4)),
        (JobAction.UPSCALE, make_solid_png(size=(120, 80), color=(123, 45, 67)), (0,)),
    ],
)
def test_expand_tiles_matches_shared_result_shape_rules(action, image_bytes, expected_indices):
    service = ImageTilesService()
    job = Job(id="job-shape", action=action)

    tiles = service.expand_tiles(job, image_bytes)

    assert tuple(tile.index for tile in tiles) == expected_indices


def _context(test_config) -> AppContext:
    return AppContext(
        config=test_config,
        job_store=InMemoryJobStoreService(),
        notify_bus=StreamingJobUpdateBus(),
        artifact_cache=ArtifactCacheService(),
        response_dump=ResponseDumpService(enabled=False),
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        engine=None,
    )


@pytest.mark.asyncio
async def test_tile_endpoint_crops_correct_quadrants(monkeypatch, test_config):
    ctx = _context(test_config)
    job = Job(id="grid1", action=JobAction.IMAGINE)
    job.status = JobStatus.SUCCEEDED
    job.image_url = "https://cdn.example/fake-grid.png"
    ctx.job_store.save(job)
    grid_bytes = make_grid_png()

    async def fake_get(self, url):  # noqa: ANN001, ARG001
        class Response:
            def __init__(self, content):
                self.content = content

            def raise_for_status(self):
                return None

        return Response(grid_bytes)

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    result_1 = await fetch_job_tile_bytes("grid1", 1, ctx)
    result_2 = await fetch_job_tile_bytes("grid1", 2, ctx)
    result_3 = await fetch_job_tile_bytes("grid1", 3, ctx)
    result_4 = await fetch_job_tile_bytes("grid1", 4, ctx)

    assert result_1.value is not None and rgb_pixel(result_1.value, 10, 10) == (255, 0, 0)
    assert result_2.value is not None and rgb_pixel(result_2.value, 10, 10) == (0, 255, 0)
    assert result_3.value is not None and rgb_pixel(result_3.value, 10, 10) == (0, 0, 255)
    assert result_4.value is not None and rgb_pixel(result_4.value, 10, 10) == (255, 255, 0)


@pytest.mark.asyncio
async def test_inpaint_tile_endpoint_crops_correct_quadrants(monkeypatch, test_config):
    ctx = _context(test_config)
    job = Job(id="grid-inpaint", action=JobAction.INPAINT)
    job.status = JobStatus.SUCCEEDED
    job.image_url = "https://cdn.example/fake-inpaint-grid.png"
    ctx.job_store.save(job)
    grid_bytes = make_grid_png()

    async def fake_get(self, url):  # noqa: ANN001, ARG001
        class Response:
            def __init__(self, content):
                self.content = content

            def raise_for_status(self):
                return None

        return Response(grid_bytes)

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    result = await fetch_job_tile_bytes("grid-inpaint", 4, ctx)

    assert result.value is not None
    assert rgb_pixel(result.value, 10, 10) == (255, 255, 0)


@pytest.mark.asyncio
async def test_pan_tile_endpoint_crops_correct_quadrants(monkeypatch, test_config):
    ctx = _context(test_config)
    job = Job(id="grid-pan", action=JobAction.PAN_LEFT)
    job.status = JobStatus.SUCCEEDED
    job.image_url = "https://cdn.example/fake-pan-grid.png"
    ctx.job_store.save(job)
    grid_bytes = make_grid_png()

    async def fake_get(self, url):  # noqa: ANN001, ARG001
        class Response:
            def __init__(self, content):
                self.content = content

            def raise_for_status(self):
                return None

        return Response(grid_bytes)

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    result_1 = await fetch_job_tile_bytes("grid-pan", 1, ctx)
    result_2 = await fetch_job_tile_bytes("grid-pan", 2, ctx)
    result_3 = await fetch_job_tile_bytes("grid-pan", 3, ctx)
    result_4 = await fetch_job_tile_bytes("grid-pan", 4, ctx)

    assert result_1.value is not None and rgb_pixel(result_1.value, 10, 10) == (255, 0, 0)
    assert result_2.value is not None and rgb_pixel(result_2.value, 10, 10) == (0, 255, 0)
    assert result_3.value is not None and rgb_pixel(result_3.value, 10, 10) == (0, 0, 255)
    assert result_4.value is not None and rgb_pixel(result_4.value, 10, 10) == (255, 255, 0)


@pytest.mark.asyncio
async def test_zoom_tile_endpoint_crops_correct_quadrants(monkeypatch, test_config):
    ctx = _context(test_config)
    job = Job(id="grid-zoom", action=JobAction.ZOOM_OUT_2X)
    job.status = JobStatus.SUCCEEDED
    job.image_url = "https://cdn.example/fake-zoom-grid.png"
    ctx.job_store.save(job)
    grid_bytes = make_grid_png()

    async def fake_get(self, url):  # noqa: ANN001, ARG001
        class Response:
            def __init__(self, content):
                self.content = content

            def raise_for_status(self):
                return None

        return Response(grid_bytes)

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    result_1 = await fetch_job_tile_bytes("grid-zoom", 1, ctx)
    result_2 = await fetch_job_tile_bytes("grid-zoom", 2, ctx)
    result_3 = await fetch_job_tile_bytes("grid-zoom", 3, ctx)
    result_4 = await fetch_job_tile_bytes("grid-zoom", 4, ctx)

    assert result_1.value is not None and rgb_pixel(result_1.value, 10, 10) == (255, 0, 0)
    assert result_2.value is not None and rgb_pixel(result_2.value, 10, 10) == (0, 255, 0)
    assert result_3.value is not None and rgb_pixel(result_3.value, 10, 10) == (0, 0, 255)
    assert result_4.value is not None and rgb_pixel(result_4.value, 10, 10) == (255, 255, 0)
