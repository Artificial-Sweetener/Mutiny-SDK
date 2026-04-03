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

import hashlib

import pytest

from mutiny.domain.job import JobAction
from mutiny.interfaces.image import ImageProcessor
from mutiny.services.context import AppContext
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.job_requests import JobImageChangeCommand
from mutiny.services.job_submission import JobSubmissionService
from mutiny.services.metrics.service import MetricsService
from mutiny.services.notify.event_bus import StreamingJobUpdateBus
from mutiny.services.response_dump import ResponseDumpService
from mutiny.types import TileFollowUpMode
from tests.image_helpers import make_png_data_url

_png_data_url = make_png_data_url


class FakeJobRef:
    def __init__(self):
        self.message_id = "mid"
        self.message_hash = "mh"
        self.flags = 0
        self.index = 1
        self.kind = None


class RecordingIndex:
    def __init__(self):
        self.calls = []

    def find_image_context_by_signature(
        self,
        *,
        digest=None,
        phash=None,
        expected_kind=None,
        width=None,
        height=None,
        phash_threshold=6,
    ):
        self.calls.append(
            {
                "method": "find_image_context_by_signature",
                "expected_kind": expected_kind,
                "digest": digest,
                "phash": phash,
                "width": width,
                "height": height,
            }
        )
        return type(
            "_Context",
            (),
            {
                "message_id": "mid",
                "message_hash": "mh",
                "flags": 0,
                "index": 1,
                "kind": expected_kind,
                "prompt_text": None,
                "tile_follow_up_mode": TileFollowUpMode.MODERN,
                "action_custom_ids": {},
            },
        )()


class FakeProcessor(ImageProcessor):
    def get_dimensions(self, data: bytes):  # pragma: no cover - unused in these tests
        return (2, 2)

    def compute_digest(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def compute_phash(self, data: bytes):  # pragma: no cover - unused in these tests
        return None

    def crop_split_grid(self, data: bytes):  # pragma: no cover - unused in these tests
        return []


class _FakeJobStore:
    def __init__(self):
        self.saved = []

    def save(self, job):  # pragma: no cover - simple recorder
        self.saved.append(job)


class _FakeEngine:
    async def submit_job(self, job):  # pragma: no cover - always accept
        return True


@pytest.mark.asyncio
async def test_image_change_prefers_upscale_lookup_for_vary_subtle(test_config):
    rec = RecordingIndex()
    ctx = AppContext(
        config=test_config,
        job_store=_FakeJobStore(),
        notify_bus=StreamingJobUpdateBus(),
        artifact_cache=rec,
        image_processor=FakeProcessor(),
        response_dump=ResponseDumpService(enabled=False),
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        engine=_FakeEngine(),
    )
    cmd = JobImageChangeCommand(base64=_png_data_url(), action=JobAction.VARY_SUBTLE)
    service = JobSubmissionService(ctx)
    res = await service.submit_image_change(cmd)
    assert res.code == 1
    assert rec.calls and rec.calls[0]["expected_kind"] == "upscale"


@pytest.mark.asyncio
async def test_image_change_expected_kind_upscale_for_v7(test_config):
    rec = RecordingIndex()
    ctx = AppContext(
        config=test_config,
        job_store=_FakeJobStore(),
        notify_bus=StreamingJobUpdateBus(),
        artifact_cache=rec,
        image_processor=FakeProcessor(),
        response_dump=ResponseDumpService(enabled=False),
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        engine=_FakeEngine(),
    )
    cmd = JobImageChangeCommand(base64=_png_data_url(), action=JobAction.UPSCALE_V7_2X_SUBTLE)
    service = JobSubmissionService(ctx)
    res = await service.submit_image_change(cmd)
    assert res.code == 1
    assert rec.calls and rec.calls[0]["expected_kind"] == "upscale"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    [
        JobAction.ZOOM_OUT_1_5X,
        JobAction.ZOOM_OUT_2X,
        JobAction.PAN_LEFT,
        JobAction.PAN_RIGHT,
        JobAction.PAN_UP,
        JobAction.PAN_DOWN,
    ],
)
async def test_image_change_prefers_upscale_lookup_for_pan_and_zoom_actions(test_config, action):
    """Try the promoted-image surface first for pan and fixed zoom actions."""
    rec = RecordingIndex()
    ctx = AppContext(
        config=test_config,
        job_store=_FakeJobStore(),
        notify_bus=StreamingJobUpdateBus(),
        artifact_cache=rec,
        image_processor=FakeProcessor(),
        response_dump=ResponseDumpService(enabled=False),
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        engine=_FakeEngine(),
    )
    cmd = JobImageChangeCommand(base64=_png_data_url(), action=action)
    service = JobSubmissionService(ctx)

    res = await service.submit_image_change(cmd)

    assert res.code == 1
    assert rec.calls and rec.calls[0]["expected_kind"] == "upscale"
