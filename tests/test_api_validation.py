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

import pytest

from mutiny.domain.job import JobAction
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.context import AppContext
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.job_requests import (
    JobBlendCommand,
    JobChangeCommand,
    JobImageChangeCommand,
    JobImagineCommand,
)
from mutiny.services.job_store import InMemoryJobStoreService
from mutiny.services.job_submission import (
    CHANGE_ACTIONS,
    IMAGE_CHANGE_ACTIONS,
    INDEX_REQUIRED_ACTIONS,
    TILE_VARIATION_ACTIONS,
    JobSubmissionService,
)
from mutiny.services.metrics.service import MetricsService
from mutiny.services.notify.event_bus import StreamingJobUpdateBus
from mutiny.services.response_dump import ResponseDumpService
from mutiny.types import ImagineImageInputs, StyleReferenceImages


def _dupe_data_url() -> str:
    # small 1x1 PNG; content duplication is what matters here
    return (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    )


def _ctx(test_config) -> AppContext:
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
async def test_blend_duplicate_validation_short_circuits(test_config):
    dupe = _dupe_data_url()
    cmd = JobBlendCommand(base64_array=[dupe, dupe], dimensions="1:1")
    service = JobSubmissionService(_ctx(test_config))
    res = await service.submit_blend(cmd)
    assert res.code == 400
    assert "Duplicate images" in (res.message or "")


@pytest.mark.asyncio
async def test_change_requires_index_for_v7_and_variants(test_config):
    # Early validation should reject missing index before looking up tasks
    for action in INDEX_REQUIRED_ACTIONS:
        cmd = JobChangeCommand(job_id="nonexistent", action=action, index=None)
        service = JobSubmissionService(_ctx(test_config))
        res = await service.submit_change(cmd)
        assert res.code == 400
        assert "Index is required" in (res.message or "")


def test_action_sets_are_consistent():
    expected_image_change = frozenset(
        {
            JobAction.UPSCALE,
            JobAction.VARIATION,
            JobAction.VARY_SUBTLE,
            JobAction.VARY_STRONG,
            JobAction.UPSCALE_V7_2X_SUBTLE,
            JobAction.UPSCALE_V7_2X_CREATIVE,
            JobAction.ZOOM_OUT_2X,
            JobAction.ZOOM_OUT_1_5X,
            JobAction.PAN_LEFT,
            JobAction.PAN_RIGHT,
            JobAction.PAN_UP,
            JobAction.PAN_DOWN,
            JobAction.ANIMATE_HIGH,
            JobAction.ANIMATE_LOW,
        }
    )

    assert IMAGE_CHANGE_ACTIONS == expected_image_change
    assert CHANGE_ACTIONS == expected_image_change | {JobAction.REROLL}
    assert INDEX_REQUIRED_ACTIONS == expected_image_change
    assert TILE_VARIATION_ACTIONS == frozenset(
        {JobAction.VARIATION, JobAction.VARY_SUBTLE, JobAction.VARY_STRONG}
    )


@pytest.mark.asyncio
async def test_image_change_rejects_invalid_action(test_config):
    cmd = JobImageChangeCommand(base64="", action=JobAction.DESCRIBE)
    service = JobSubmissionService(_ctx(test_config))
    res = await service.submit_image_change(cmd)
    assert res.code == 400
    assert "Invalid action" in (res.message or "")


@pytest.mark.asyncio
async def test_change_rejects_invalid_action(test_config):
    cmd = JobChangeCommand(job_id="nonexistent", action=JobAction.DESCRIBE, index=1)
    service = JobSubmissionService(_ctx(test_config))
    res = await service.submit_change(cmd)
    assert res.code == 400
    assert "Invalid action" in (res.message or "")


@pytest.mark.asyncio
async def test_imagine_rejects_misaligned_style_reference_multipliers(test_config):
    cmd = JobImagineCommand(
        prompt="editorial portrait",
        image_inputs=ImagineImageInputs(
            style_reference=StyleReferenceImages(
                images=(_dupe_data_url(), _dupe_data_url()),
                multipliers=(2.0,),
            )
        ),
    )
    service = JobSubmissionService(_ctx(test_config))

    res = await service.submit_imagine(cmd)

    assert res.code == 400
    assert "style_reference.multipliers" in (res.message or "")
