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

import base64
import hashlib

import pytest

from mutiny.interfaces.image import ImageProcessor
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.context import AppContext
from mutiny.services.error_catalog import MISSING_CONTEXT
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.job_requests import (
    JobAnimateCommand,
    JobAnimateExtendCommand,
    JobCustomZoomCommand,
    JobImageChangeCommand,
    JobInpaintCommand,
)
from mutiny.services.job_store import InMemoryJobStoreService
from mutiny.services.job_submission import JobSubmissionService
from mutiny.services.metrics.service import MetricsService
from mutiny.services.notify.event_bus import StreamingJobUpdateBus
from mutiny.services.response_dump import ResponseDumpService
from mutiny.services.video_signature import VideoSignature
from mutiny.types import AnimateMotion, Job, JobAction, JobStatus, TileFollowUpMode
from tests.image_helpers import make_png_data_url

_png_data_url = make_png_data_url


def _ctx(
    test_config,
    *,
    image_processor=None,
    artifact_cache=None,
    video_signature_service=None,
    job_store=None,
    engine=None,
) -> AppContext:
    kwargs = {}
    if image_processor is not None:
        kwargs["image_processor"] = image_processor
    if video_signature_service is not None:
        kwargs["video_signature_service"] = video_signature_service
    return AppContext(
        config=test_config,
        job_store=job_store or InMemoryJobStoreService(),
        notify_bus=StreamingJobUpdateBus(),
        artifact_cache=artifact_cache or ArtifactCacheService(),
        response_dump=ResponseDumpService(enabled=False),
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        engine=engine,
        **kwargs,
    )


class _RecordingJobStore:
    def __init__(self):
        self.items = {}

    def save(self, job):  # pragma: no cover - simple storage
        self.items[job.id] = job

    def get(self, job_id):  # pragma: no cover - unused in these tests
        return self.items.get(job_id)

    def find_one(self, query):
        for job in self.items.values():
            if query.message_id is not None and job.context.message_id != query.message_id:
                continue
            return job
        return None


class _RecordingEngine:
    def __init__(self):
        self.submitted = []

    async def submit_job(self, job):  # pragma: no cover - simple recorder
        self.submitted.append(job)
        return True


class _RecordingIndex:
    """Return a configurable image reference and capture lookup inputs."""

    def __init__(
        self,
        *,
        ref_index: int | None = None,
        message_id: str = "mid",
        message_hash: str = "mh",
    ):
        self.ref_index = ref_index
        self.message_id = message_id
        self.message_hash = message_hash
        self.calls = []
        self.video_digests = {}

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
                "digest": digest,
                "phash": phash,
                "expected_kind": expected_kind,
                "width": width,
                "height": height,
                "phash_threshold": phash_threshold,
            }
        )

        return type(
            "_Context",
            (),
            {
                "message_id": self.message_id,
                "message_hash": self.message_hash,
                "flags": 0,
                "index": self.ref_index,
                "kind": expected_kind,
                "prompt_text": None,
                "tile_follow_up_mode": TileFollowUpMode.MODERN,
                "action_custom_ids": {},
            },
        )()

    def put_video_job_ref(
        self,
        digest,
        *,
        message_id,
        message_hash,
        flags,
        signature_version,
        prompt_text=None,
        action_custom_ids=None,
        kind="video",
        index=1,
    ):
        self.video_digests[digest] = {
            "message_id": message_id,
            "message_hash": message_hash,
            "flags": flags,
            "signature_version": signature_version,
            "prompt_text": prompt_text,
            "action_custom_ids": action_custom_ids or {},
            "kind": kind,
            "index": index,
        }

    def find_video_context_by_digest(self, digest):
        record = self.video_digests.get(digest)
        if record is None:
            return None

        return type(
            "_VideoContext",
            (),
            {
                "message_id": record["message_id"],
                "message_hash": record["message_hash"],
                "flags": record["flags"],
                "index": record["index"],
                "prompt_text": record.get("prompt_text"),
                "action_custom_ids": record.get("action_custom_ids", {}),
            },
        )()


class _RecordingVideoSignatureService:
    def __init__(self, digest: str = "video-digest"):
        self.digest = digest
        self.calls = []

    def compute_signature(self, video_bytes: bytes) -> VideoSignature:
        self.calls.append(video_bytes)
        return VideoSignature(digest=self.digest)


class _FakeProcessor(ImageProcessor):
    def get_dimensions(self, data: bytes):  # pragma: no cover - unused in these tests
        return (2, 2)

    def compute_digest(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def compute_phash(self, data: bytes):  # pragma: no cover - unused in these tests
        return None

    def crop_split_grid(self, data: bytes):  # pragma: no cover - unused in these tests
        return []


@pytest.mark.asyncio
async def test_custom_zoom_requires_context(test_config):
    service = JobSubmissionService(_ctx(test_config))
    cmd = JobCustomZoomCommand(job_id=None, base64=None, zoom_text="--zoom 1.2")

    res = await service.submit_custom_zoom(cmd)

    assert res.code == MISSING_CONTEXT.code
    assert (res.message or "") == MISSING_CONTEXT.message


@pytest.mark.asyncio
async def test_custom_zoom_base64_path_requires_upscaled_image_lookup(test_config):
    """Keep custom zoom image resolution pinned to upscaled-image lookup semantics."""
    assert not hasattr(test_config, "features")
    engine = _RecordingEngine()
    job_store = _RecordingJobStore()
    image_index = _RecordingIndex(
        ref_index=0,
        message_id="upscaled-message",
        message_hash="upscaled-hash",
    )
    service = JobSubmissionService(
        _ctx(
            test_config,
            image_processor=_FakeProcessor(),
            artifact_cache=image_index,
            job_store=job_store,
            engine=engine,
        )
    )
    cmd = JobCustomZoomCommand(base64=_png_data_url(), zoom_text="tight crop --zoom 1.24")

    res = await service.submit_custom_zoom(cmd)

    assert res.code == 1
    saved_job = next(iter(job_store.items.values()))
    assert image_index.calls and image_index.calls[0]["expected_kind"] == "upscale"
    assert saved_job.context.message_id == "upscaled-message"
    assert saved_job.context.message_hash == "upscaled-hash"
    assert saved_job.context.zoom_text == "tight crop --zoom 1.24"


@pytest.mark.asyncio
async def test_inpaint_requires_context(test_config):
    service = JobSubmissionService(_ctx(test_config))
    cmd = JobInpaintCommand(job_id=None, base64=None, mask=_png_data_url())

    res = await service.submit_inpaint(cmd)

    assert res.code == MISSING_CONTEXT.code
    assert (res.message or "") == MISSING_CONTEXT.message


@pytest.mark.asyncio
async def test_inpaint_base64_path_defaults_index(test_config):
    assert not hasattr(test_config, "features")
    engine = _RecordingEngine()
    job_store = _RecordingJobStore()
    image_index = _RecordingIndex(
        ref_index=0,
        message_id="upscaled-message",
        message_hash="upscaled-hash",
    )
    service = JobSubmissionService(
        _ctx(
            test_config,
            image_processor=_FakeProcessor(),
            artifact_cache=image_index,
            job_store=job_store,
            engine=engine,
        )
    )
    cmd = JobInpaintCommand(base64=_png_data_url(), mask=_png_data_url())

    res = await service.submit_inpaint(cmd)

    assert res.code == 1
    saved_job = next(iter(job_store.items.values()))
    assert image_index.calls and image_index.calls[0]["expected_kind"] == "upscale"
    assert saved_job.context.message_id == "upscaled-message"
    assert saved_job.context.message_hash == "upscaled-hash"
    assert saved_job.context.index == 1


@pytest.mark.asyncio
async def test_animate_prefers_follow_up_route_for_recognized_upscaled_images(test_config):
    engine = _RecordingEngine()
    job_store = _RecordingJobStore()
    image_index = _RecordingIndex(
        ref_index=0,
        message_id="upscaled-message",
        message_hash="upscaled-hash",
    )
    service = JobSubmissionService(
        _ctx(
            test_config,
            image_processor=_FakeProcessor(),
            artifact_cache=image_index,
            job_store=job_store,
            engine=engine,
        )
    )

    res = await service.submit_animate(
        JobAnimateCommand(
            start_frame_data_url=_png_data_url(),
            motion=AnimateMotion.HIGH,
        )
    )

    assert res.code == 1
    saved_job = next(iter(job_store.items.values()))
    assert image_index.calls and image_index.calls[0]["expected_kind"] == "upscale"
    assert saved_job.action.name == "ANIMATE_HIGH"
    assert saved_job.context.message_id == "upscaled-message"
    assert saved_job.context.message_hash == "upscaled-hash"
    assert saved_job.context.index == 1
    assert saved_job.inputs.base64 is None


@pytest.mark.asyncio
async def test_animate_falls_back_to_prompt_video_when_image_is_unrecognized(test_config):
    engine = _RecordingEngine()
    job_store = _RecordingJobStore()

    class _MissIndex:
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
                    "digest": digest,
                    "phash": phash,
                    "expected_kind": expected_kind,
                    "width": width,
                    "height": height,
                    "phash_threshold": phash_threshold,
                }
            )
            return None

    image_index = _MissIndex()
    service = JobSubmissionService(
        _ctx(
            test_config,
            image_processor=_FakeProcessor(),
            artifact_cache=image_index,
            job_store=job_store,
            engine=engine,
        )
    )

    res = await service.submit_animate(
        JobAnimateCommand(
            start_frame_data_url=_png_data_url(),
            motion=AnimateMotion.LOW,
        )
    )

    assert res.code == 1
    saved_job = next(iter(job_store.items.values()))
    assert image_index.calls and image_index.calls[0]["expected_kind"] == "upscale"
    assert saved_job.action.name == "ANIMATE_LOW"
    assert saved_job.inputs.base64 == _png_data_url()
    assert saved_job.context.message_id is None
    assert saved_job.context.index is None


@pytest.mark.asyncio
async def test_animate_end_frame_forces_prompt_video_route(test_config):
    engine = _RecordingEngine()
    job_store = _RecordingJobStore()
    image_index = _RecordingIndex(
        ref_index=0,
        message_id="upscaled-message",
        message_hash="upscaled-hash",
    )
    service = JobSubmissionService(
        _ctx(
            test_config,
            image_processor=_FakeProcessor(),
            artifact_cache=image_index,
            job_store=job_store,
            engine=engine,
        )
    )

    res = await service.submit_animate(
        JobAnimateCommand(
            start_frame_data_url=_png_data_url(),
            end_frame_data_url=_png_data_url(color=(0, 255, 0)),
            prompt="camera push",
            motion=AnimateMotion.HIGH,
        )
    )

    assert res.code == 1
    saved_job = next(iter(job_store.items.values()))
    assert image_index.calls == []
    assert saved_job.inputs.base64 == _png_data_url()
    assert saved_job.inputs.end_frame_base64 == _png_data_url(color=(0, 255, 0))
    assert saved_job.inputs.prompt == "camera push"


@pytest.mark.asyncio
async def test_animate_rejects_invalid_batch_size(test_config):
    service = JobSubmissionService(_ctx(test_config))

    res = await service.submit_animate(
        JobAnimateCommand(
            start_frame_data_url=_png_data_url(),
            motion=AnimateMotion.HIGH,
            batch_size=3,
        )
    )

    assert res.code == 400
    assert "1, 2, or 4" in (res.message or "")


@pytest.mark.asyncio
async def test_animate_extend_resolves_by_job_id(test_config):
    engine = _RecordingEngine()
    job_store = _RecordingJobStore()
    service = JobSubmissionService(
        _ctx(
            test_config,
            job_store=job_store,
            engine=engine,
        )
    )
    original = Job(id="job-animate", action=JobAction.ANIMATE_LOW)
    original.status = JobStatus.SUCCEEDED
    original.context.message_id = "video-message"
    original.context.message_hash = "video-hash"
    original.context.flags = 64
    original.context.index = 1
    original.context.final_prompt = (
        "<https://s.mj.run/FDtsRp5JlgI> idle animation --motion low --bs 1 --video 1 --aspect 1:1"
    )
    job_store.save(original)

    res = await service.submit_animate_extend(
        JobAnimateExtendCommand(job_id="job-animate", motion=AnimateMotion.HIGH)
    )

    assert res.code == 1
    saved_job = next(job for job_id, job in job_store.items.items() if job_id != "job-animate")
    assert saved_job.action is JobAction.ANIMATE_EXTEND_HIGH
    assert saved_job.prompt == "idle animation --motion low --bs 1 --video 1 --aspect 1:1"
    assert saved_job.context.message_id == "video-message"
    assert saved_job.context.message_hash == "video-hash"
    assert saved_job.context.index == 1


@pytest.mark.asyncio
async def test_animate_extend_resolves_by_video_bytes(test_config):
    engine = _RecordingEngine()
    job_store = _RecordingJobStore()
    image_index = _RecordingIndex(
        ref_index=0,
        message_id="unused",
        message_hash="unused",
    )
    video_signature_service = _RecordingVideoSignatureService()
    image_index.put_video_job_ref(
        "video-digest",
        message_id="video-message",
        message_hash="video-hash",
        flags=64,
        signature_version=1,
    )
    original = Job(id="job-animate", action=JobAction.ANIMATE_LOW)
    original.status = JobStatus.SUCCEEDED
    original.context.message_id = "video-message"
    original.context.message_hash = "video-hash"
    original.context.flags = 64
    original.context.index = 1
    original.context.final_prompt = (
        "<https://s.mj.run/FDtsRp5JlgI> idle animation --motion low --bs 1 --video 1 --aspect 1:1"
    )
    job_store.save(original)
    service = JobSubmissionService(
        _ctx(
            test_config,
            image_processor=_FakeProcessor(),
            artifact_cache=image_index,
            video_signature_service=video_signature_service,
            job_store=job_store,
            engine=engine,
        )
    )

    res = await service.submit_animate_extend(
        JobAnimateExtendCommand(video_bytes=b"video-bytes", motion=AnimateMotion.LOW)
    )

    assert res.code == 1
    assert video_signature_service.calls == [b"video-bytes"]
    saved_job = next(job for job_id, job in job_store.items.items() if job_id != "job-animate")
    assert saved_job.action is JobAction.ANIMATE_EXTEND_LOW
    assert saved_job.prompt == "idle animation --motion low --bs 1 --video 1 --aspect 1:1"
    assert saved_job.context.message_id == "video-message"
    assert saved_job.context.message_hash == "video-hash"


@pytest.mark.asyncio
async def test_image_change_resolves_from_persisted_cache_without_source_job(test_config):
    """Image follow-up resolution should work after restart with an empty job store."""

    engine = _RecordingEngine()
    job_store = _RecordingJobStore()
    artifact_cache = ArtifactCacheService()
    image_bytes = base64.b64decode(_png_data_url().split(",", 1)[1])
    digest = _FakeProcessor().compute_digest(image_bytes)
    artifact_cache.put_image_job_ref(
        digest,
        message_id="cached-grid-message",
        message_hash="cached-grid-hash",
        flags=64,
        index=2,
        prompt_text="castle at sunrise",
        kind="tile",
    )
    service = JobSubmissionService(
        _ctx(
            test_config,
            image_processor=_FakeProcessor(),
            artifact_cache=artifact_cache,
            job_store=job_store,
            engine=engine,
        )
    )

    res = await service.submit_image_change(
        JobImageChangeCommand(base64=_png_data_url(), action=JobAction.VARY_STRONG)
    )

    assert res.code == 1
    saved_job = next(iter(job_store.items.values()))
    assert saved_job.context.message_id == "cached-grid-message"
    assert saved_job.context.message_hash == "cached-grid-hash"
    assert saved_job.context.index == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "kind", "expected_index"),
    [
        (JobAction.PAN_LEFT, "tile", 2),
        (JobAction.ZOOM_OUT_2X, "upscale", 1),
    ],
)
async def test_image_change_restart_resolution_supports_pan_and_zoom_from_persisted_cache(
    test_config,
    action,
    kind,
    expected_index,
):
    """Saved-artifact image changes should rebuild action context after restart."""

    engine = _RecordingEngine()
    job_store = _RecordingJobStore()
    artifact_cache = ArtifactCacheService()
    image_bytes = base64.b64decode(_png_data_url().split(",", 1)[1])
    digest = _FakeProcessor().compute_digest(image_bytes)
    artifact_cache.put_image_job_ref(
        digest,
        message_id="cached-message",
        message_hash="cached-hash",
        flags=64,
        index=expected_index,
        prompt_text="castle at sunrise",
        kind=kind,
    )
    service = JobSubmissionService(
        _ctx(
            test_config,
            image_processor=_FakeProcessor(),
            artifact_cache=artifact_cache,
            job_store=job_store,
            engine=engine,
        )
    )

    res = await service.submit_image_change(
        JobImageChangeCommand(base64=_png_data_url(), action=action)
    )

    assert res.code == 1
    saved_job = next(iter(job_store.items.values()))
    assert saved_job.context.message_id == "cached-message"
    assert saved_job.context.message_hash == "cached-hash"
    assert saved_job.context.index == expected_index


@pytest.mark.asyncio
async def test_custom_zoom_resolves_from_persisted_upscale_cache_without_source_job(test_config):
    """Custom zoom should remain restart-safe when the saved source image is recognized."""

    engine = _RecordingEngine()
    job_store = _RecordingJobStore()
    artifact_cache = ArtifactCacheService()
    image_bytes = base64.b64decode(_png_data_url().split(",", 1)[1])
    digest = _FakeProcessor().compute_digest(image_bytes)
    artifact_cache.put_image_job_ref(
        digest,
        message_id="cached-upscale-message",
        message_hash="cached-upscale-hash",
        flags=64,
        index=1,
        prompt_text="castle at sunrise",
        kind="upscale",
    )
    service = JobSubmissionService(
        _ctx(
            test_config,
            image_processor=_FakeProcessor(),
            artifact_cache=artifact_cache,
            job_store=job_store,
            engine=engine,
        )
    )

    res = await service.submit_custom_zoom(
        JobCustomZoomCommand(base64=_png_data_url(), zoom_text="tight crop --zoom 1.24")
    )

    assert res.code == 1
    saved_job = next(iter(job_store.items.values()))
    assert saved_job.context.message_id == "cached-upscale-message"
    assert saved_job.context.message_hash == "cached-upscale-hash"
    assert saved_job.context.index == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [JobAction.VARY_STRONG, JobAction.PAN_LEFT])
async def test_saved_zoom_tiles_resolve_from_persisted_cache_like_other_grid_tiles(
    test_config,
    action: JobAction,
):
    """Completed zoom grids should recover as tile surfaces for later tile-aware follow-ups."""

    engine = _RecordingEngine()
    job_store = _RecordingJobStore()
    artifact_cache = ArtifactCacheService()
    image_bytes = base64.b64decode(_png_data_url().split(",", 1)[1])
    digest = _FakeProcessor().compute_digest(image_bytes)
    artifact_cache.put_image_job_ref(
        digest,
        message_id="cached-zoom-message",
        message_hash="cached-zoom-hash",
        flags=64,
        index=3,
        prompt_text="cathedral aisle",
        kind="tile",
    )
    service = JobSubmissionService(
        _ctx(
            test_config,
            image_processor=_FakeProcessor(),
            artifact_cache=artifact_cache,
            job_store=job_store,
            engine=engine,
        )
    )

    res = await service.submit_image_change(
        JobImageChangeCommand(base64=_png_data_url(), action=action)
    )

    assert res.code == 1
    saved_job = next(iter(job_store.items.values()))
    assert saved_job.context.message_id == "cached-zoom-message"
    assert saved_job.context.message_hash == "cached-zoom-hash"
    assert saved_job.context.index == 3


@pytest.mark.asyncio
async def test_inpaint_resolves_from_persisted_upscale_cache_without_source_job(test_config):
    """Inpaint should remain restart-safe when the saved source image is recognized."""

    engine = _RecordingEngine()
    job_store = _RecordingJobStore()
    artifact_cache = ArtifactCacheService()
    image_bytes = base64.b64decode(_png_data_url().split(",", 1)[1])
    digest = _FakeProcessor().compute_digest(image_bytes)
    artifact_cache.put_image_job_ref(
        digest,
        message_id="cached-upscale-message",
        message_hash="cached-upscale-hash",
        flags=64,
        index=1,
        prompt_text="castle at sunrise",
        kind="upscale",
    )
    service = JobSubmissionService(
        _ctx(
            test_config,
            image_processor=_FakeProcessor(),
            artifact_cache=artifact_cache,
            job_store=job_store,
            engine=engine,
        )
    )

    res = await service.submit_inpaint(
        JobInpaintCommand(base64=_png_data_url(), mask=_png_data_url())
    )

    assert res.code == 1
    saved_job = next(iter(job_store.items.values()))
    assert saved_job.context.message_id == "cached-upscale-message"
    assert saved_job.context.message_hash == "cached-upscale-hash"
    assert saved_job.context.index == 1


@pytest.mark.asyncio
async def test_animate_extend_resolves_from_persisted_video_cache_without_source_job(test_config):
    """Video extend should work after restart using persisted video context alone."""

    engine = _RecordingEngine()
    job_store = _RecordingJobStore()
    artifact_cache = ArtifactCacheService()
    video_signature_service = _RecordingVideoSignatureService()
    artifact_cache.put_video_job_ref(
        "video-digest",
        message_id="cached-video-message",
        message_hash="cached-video-hash",
        flags=64,
        signature_version=1,
        prompt_text="idle animation --motion low --bs 1 --video 1 --aspect 1:1",
    )
    service = JobSubmissionService(
        _ctx(
            test_config,
            image_processor=_FakeProcessor(),
            artifact_cache=artifact_cache,
            video_signature_service=video_signature_service,
            job_store=job_store,
            engine=engine,
        )
    )

    res = await service.submit_animate_extend(
        JobAnimateExtendCommand(video_bytes=b"video-bytes", motion=AnimateMotion.HIGH)
    )

    assert res.code == 1
    saved_job = next(iter(job_store.items.values()))
    assert saved_job.action is JobAction.ANIMATE_EXTEND_HIGH
    assert saved_job.prompt == "idle animation --motion low --bs 1 --video 1 --aspect 1:1"
    assert saved_job.context.message_id == "cached-video-message"
    assert saved_job.context.message_hash == "cached-video-hash"


def test_normalize_extend_prompt_strips_leading_prompt_image_urls(test_config):
    service = JobSubmissionService(_ctx(test_config))

    normalized = service._normalize_extend_prompt(
        "<https://s.mj.run/FDtsRp5JlgI> <https://cdn.example.com/extra.png> "
        "idle animation --motion low --bs 1 --video 1 --aspect 1:1"
    )

    assert normalized == "idle animation --motion low --bs 1 --video 1 --aspect 1:1"
