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

"""Characterize modern/default tile follow-up behavior."""

from __future__ import annotations

import hashlib

import pytest

from mutiny.domain.job import TileFollowUpMode
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.context import AppContext
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.job_requests import JobChangeCommand
from mutiny.services.job_store import InMemoryJobStoreService
from mutiny.services.job_submission import JobSubmissionService
from mutiny.services.metrics.service import MetricsService
from mutiny.services.notify.event_bus import StreamingJobUpdateBus
from mutiny.services.response_dump import ResponseDumpService
from mutiny.services.tile_follow_up import resolve_tile_follow_up_mode
from mutiny.types import Job, JobAction, JobStatus


class _Engine:
    async def submit_job(self, job):  # pragma: no cover - simple recorder
        return True


def _ctx(test_config) -> AppContext:
    return AppContext(
        config=test_config,
        job_store=InMemoryJobStoreService(),
        notify_bus=StreamingJobUpdateBus(),
        artifact_cache=ArtifactCacheService(),
        response_dump=ResponseDumpService(enabled=False),
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        engine=_Engine(),
    )


def _succeeded_grid_job(*, prompt: str, mode: TileFollowUpMode) -> Job:
    job = Job(id="grid-job", action=JobAction.IMAGINE, prompt=prompt)
    job.status = JobStatus.SUCCEEDED
    job.context.message_id = "grid-message"
    job.context.message_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    job.context.flags = 64
    job.context.index = 1
    job.context.tile_follow_up_mode = mode
    return job


def test_tile_follow_up_mode_defaults_to_modern_when_prompt_omits_version() -> None:
    """Treat unspecified prompt versions as the modern/default tile behavior path."""

    assert resolve_tile_follow_up_mode("castle on a cliff at sunrise") is TileFollowUpMode.MODERN


@pytest.mark.parametrize(
    ("prompt_text", "expected_mode"),
    [
        ("castle --v 5", TileFollowUpMode.MODERN),
        ("castle --v 6.1", TileFollowUpMode.MODERN),
        ("castle --niji 5", TileFollowUpMode.MODERN),
        ("castle --niji 7", TileFollowUpMode.MODERN),
        ("castle --v 4", TileFollowUpMode.LEGACY),
        ("castle --niji 4", TileFollowUpMode.LEGACY),
    ],
)
def test_tile_follow_up_mode_honors_explicit_model_exceptions(
    prompt_text: str, expected_mode: TileFollowUpMode
) -> None:
    """Treat only explicit old-model selections as legacy tile behavior."""

    assert resolve_tile_follow_up_mode(prompt_text) is expected_mode


@pytest.mark.asyncio
async def test_modern_tile_pan_submission_marks_hidden_promotion_hop(test_config) -> None:
    """Modern/default tile pan requests should stage an implicit `U#` promotion first."""

    ctx = _ctx(test_config)
    service = JobSubmissionService(ctx)
    original = _succeeded_grid_job(
        prompt="castle on a cliff at sunrise",
        mode=TileFollowUpMode.MODERN,
    )
    ctx.job_store.save(original)

    result = await service.submit_change(
        JobChangeCommand(job_id=original.id, action=JobAction.PAN_LEFT, index=2)
    )

    assert result.code == 1
    saved_job = ctx.job_store.get(result.value or "")
    assert saved_job is not None
    assert saved_job.context.implicit_tile_promotion_pending is True
    assert saved_job.context.implicit_tile_promotion_index == 2
    assert saved_job.context.index == 2


@pytest.mark.asyncio
async def test_modern_tile_strong_variation_stays_direct(test_config) -> None:
    """Modern/default strong variation should keep the direct tile path."""

    ctx = _ctx(test_config)
    service = JobSubmissionService(ctx)
    original = _succeeded_grid_job(
        prompt="castle on a cliff at sunrise",
        mode=TileFollowUpMode.MODERN,
    )
    ctx.job_store.save(original)

    result = await service.submit_change(
        JobChangeCommand(job_id=original.id, action=JobAction.VARY_STRONG, index=3)
    )

    assert result.code == 1
    saved_job = ctx.job_store.get(result.value or "")
    assert saved_job is not None
    assert saved_job.context.implicit_tile_promotion_pending is False
    assert saved_job.context.index == 3


@pytest.mark.asyncio
async def test_legacy_tile_pan_submission_rejects_solo_only_action(test_config) -> None:
    """Explicit old-model tiles should preserve the legacy restriction surface."""

    ctx = _ctx(test_config)
    service = JobSubmissionService(ctx)
    original = _succeeded_grid_job(
        prompt="castle --v 4",
        mode=TileFollowUpMode.LEGACY,
    )
    ctx.job_store.save(original)

    result = await service.submit_change(
        JobChangeCommand(job_id=original.id, action=JobAction.PAN_LEFT, index=2)
    )

    assert result.code == 400
    assert "promoted single-image result" in (result.message or "")
