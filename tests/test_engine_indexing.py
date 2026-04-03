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

import asyncio
import hashlib
import logging

import pytest

from mutiny.discord.identity import DiscordIdentity
from mutiny.domain.job import TileFollowUpMode
from mutiny.engine.discord_engine import DiscordEngine
from mutiny.engine.execution_policy import EnginePolicy
from mutiny.engine.indexing import IndexingCoordinator
from mutiny.interfaces.image import ImageProcessor
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.image_processor import OpenCVImageProcessor
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.job_store import InMemoryJobStoreService
from mutiny.services.metrics.service import MetricsService
from mutiny.services.notify.event_bus import StreamingJobUpdateBus
from mutiny.services.response_dump import ResponseDumpService
from mutiny.services.video_signature import VideoSignature
from mutiny.types import Job, JobAction
from tests.image_helpers import make_grid_png as build_grid_png
from tests.image_helpers import make_solid_png


class _TokenProvider:
    def get_token(self) -> str:
        return "token"


class _FailingProvider:
    """Raise a configured error when CDN bytes are requested."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def fetch_cdn_bytes(self, url: str) -> bytes | None:  # noqa: ARG002
        raise self._error


class _StaticProvider:
    """Return the same image bytes for every CDN request."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    async def fetch_cdn_bytes(self, url: str) -> bytes | None:  # noqa: ARG002
        return self._data


class _BlockingProvider:
    """Block CDN fetches until explicitly released."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def fetch_cdn_bytes(self, url: str) -> bytes | None:  # noqa: ARG002
        self.started.set()
        await self.release.wait()
        return self._data


class _FakeProcessor(ImageProcessor):
    """Provide deterministic signatures for indexing tests."""

    def __init__(self) -> None:
        self._opencv = OpenCVImageProcessor()

    def get_dimensions(self, data: bytes) -> tuple[int, int]:
        return self._opencv.get_dimensions(data)

    def compute_digest(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def compute_phash(self, data: bytes) -> int:
        return 321

    def crop_split_grid(self, data: bytes) -> list[bytes]:
        return self._opencv.crop_split_grid(data)


class _FakeVideoSignatureService:
    """Return deterministic video digests for indexing tests."""

    def compute_signature(self, data: bytes) -> VideoSignature:
        return VideoSignature(digest=f"video-{hashlib.sha256(data).hexdigest()}")


def _make_grid_png() -> bytes:
    return build_grid_png()


def _make_engine(config, provider) -> DiscordEngine:
    identity = DiscordIdentity(guild_id="g", channel_id="c", token_provider=_TokenProvider())
    engine = DiscordEngine(
        identity=identity,
        job_store=InMemoryJobStoreService(),
        notify_bus=StreamingJobUpdateBus(),
        config=config,
        policy=EnginePolicy(config.engine.execution),
        artifact_cache=ArtifactCacheService(),
        video_signature_service=_FakeVideoSignatureService(),
        image_processor=OpenCVImageProcessor(),
        interaction_cache=InteractionCache(),
        response_dump=ResponseDumpService(enabled=False),
        metrics=MetricsService(),
    )
    engine.provider = provider
    engine.indexer = IndexingCoordinator(
        commands=provider,
        image_processor=engine.image_processor,
        artifact_cache=engine.artifact_cache,
        video_signature_service=_FakeVideoSignatureService(),
    )
    return engine


@pytest.mark.asyncio
async def test_schedule_image_indexing_logs_error(test_config, caplog):
    provider = _FailingProvider(RuntimeError("boom"))
    engine = _make_engine(test_config, provider)
    job = Job(id="job-1", action=JobAction.IMAGINE)
    message = {"id": "msg-1", "attachments": [{"url": "https://cdn.example/test.png"}]}

    with caplog.at_level(logging.ERROR):
        engine.indexer.schedule_image_indexing(JobAction.IMAGINE, message, job)
        await asyncio.sleep(0)
        await asyncio.sleep(0.05)

    assert any("Artifact indexing failed" in record.message for record in caplog.records)
    assert any(getattr(record, "job_id", None) == "job-1" for record in caplog.records)
    assert any(
        getattr(record, "action", None) == JobAction.IMAGINE.value for record in caplog.records
    )
    assert any(getattr(record, "message_id", None) == "msg-1" for record in caplog.records)


@pytest.mark.asyncio
async def test_upscale_indexing_uses_actionable_upscaled_message_context() -> None:
    """Index explicit legacy upscales against the message that owns follow-up buttons."""

    image_bytes = make_solid_png(size=(8, 8), color=(10, 20, 30))
    processor = _FakeProcessor()
    image_index = ArtifactCacheService()
    job_store = InMemoryJobStoreService()

    original = Job(id="job-grid", action=JobAction.IMAGINE)
    original.context.message_id = "grid-message"
    original.context.message_hash = "grid-hash"
    original.context.index = 3
    job_store.save(original)

    upscale = Job(id="job-upscale", action=JobAction.UPSCALE)
    upscale.context.original_job_id = original.id
    upscale.context.message_hash = "upscaled-hash"
    upscale.context.index = 3
    upscale.context.tile_follow_up_mode = TileFollowUpMode.LEGACY
    job_store.save(upscale)

    coordinator = IndexingCoordinator(
        commands=_StaticProvider(image_bytes),
        image_processor=processor,
        artifact_cache=image_index,
        video_signature_service=_FakeVideoSignatureService(),
    )
    message = {
        "id": "upscaled-message",
        "flags": 64,
        "attachments": [{"url": "https://cdn.example/upscaled.png"}],
    }

    await coordinator._index_image(JobAction.UPSCALE, message, upscale)

    digest = processor.compute_digest(image_bytes)
    ref = image_index.get_image_job_ref(digest)

    assert ref is not None
    assert ref.kind == "upscale"
    assert ref.message_id == "upscaled-message"
    assert ref.message_hash == "upscaled-hash"
    assert ref.index == 0


@pytest.mark.asyncio
async def test_modern_tile_upscale_does_not_replace_canonical_tile_indexing() -> None:
    """Keep modern/default `U#` promotions from overwriting the original tile identity."""

    image_bytes = make_solid_png(size=(8, 8), color=(10, 20, 30))
    processor = _FakeProcessor()
    image_index = ArtifactCacheService()
    coordinator = IndexingCoordinator(
        commands=_StaticProvider(image_bytes),
        image_processor=processor,
        artifact_cache=image_index,
        video_signature_service=_FakeVideoSignatureService(),
    )
    job = Job(id="job-upscale", action=JobAction.UPSCALE)
    job.context.message_hash = "upscaled-hash"
    job.context.index = 3
    job.context.tile_follow_up_mode = TileFollowUpMode.MODERN
    message = {
        "id": "upscaled-message",
        "flags": 64,
        "attachments": [{"url": "https://cdn.example/upscaled.png"}],
    }

    await coordinator._index_image(JobAction.UPSCALE, message, job)

    digest = processor.compute_digest(image_bytes)
    assert image_index.get_image_job_ref(digest) is None


@pytest.mark.asyncio
async def test_inpaint_indexing_stores_each_grid_tile() -> None:
    """Index inpaint outputs as four actionable tile references."""
    image_bytes = _make_grid_png()
    processor = _FakeProcessor()
    image_index = ArtifactCacheService()
    coordinator = IndexingCoordinator(
        commands=_StaticProvider(image_bytes),
        image_processor=processor,
        artifact_cache=image_index,
        video_signature_service=_FakeVideoSignatureService(),
    )
    job = Job(id="job-inpaint", action=JobAction.INPAINT)
    job.context.message_hash = "inpaint-hash"
    message = {
        "id": "inpaint-message",
        "flags": 64,
        "attachments": [{"url": "https://cdn.example/inpaint-grid.png"}],
    }

    await coordinator._index_image(JobAction.INPAINT, message, job)

    tiles = coordinator._tiles_service.expand_tiles(job, image_bytes)
    refs = [
        image_index.get_image_job_ref(processor.compute_digest(tile.image_bytes)) for tile in tiles
    ]

    assert [ref.index for ref in refs if ref is not None] == [1, 2, 3, 4]
    assert all(ref is not None for ref in refs)
    assert all(ref.kind == "tile" for ref in refs)
    assert all(ref.message_id == "inpaint-message" for ref in refs)
    assert all(ref.message_hash == "inpaint-hash" for ref in refs)


@pytest.mark.asyncio
async def test_pan_indexing_stores_each_grid_tile() -> None:
    """Index Pan outputs as the same four actionable tile references used by other grids."""

    image_bytes = _make_grid_png()
    processor = _FakeProcessor()
    image_index = ArtifactCacheService()
    coordinator = IndexingCoordinator(
        commands=_StaticProvider(image_bytes),
        image_processor=processor,
        artifact_cache=image_index,
        video_signature_service=_FakeVideoSignatureService(),
    )
    job = Job(id="job-pan", action=JobAction.PAN_LEFT)
    job.context.message_hash = "pan-hash"
    message = {
        "id": "pan-message",
        "flags": 64,
        "attachments": [{"url": "https://cdn.example/pan-grid.png"}],
    }

    await coordinator._index_image(JobAction.PAN_LEFT, message, job)

    tiles = coordinator._tiles_service.expand_tiles(job, image_bytes)
    refs = [
        image_index.get_image_job_ref(processor.compute_digest(tile.image_bytes)) for tile in tiles
    ]

    assert [ref.index for ref in refs if ref is not None] == [1, 2, 3, 4]
    assert all(ref is not None for ref in refs)
    assert all(ref.kind == "tile" for ref in refs)
    assert all(ref.message_id == "pan-message" for ref in refs)
    assert all(ref.message_hash == "pan-hash" for ref in refs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "job_id", "message_id", "message_hash", "url"),
    [
        (
            JobAction.ZOOM_OUT_2X,
            "job-zoom-2x",
            "zoom-2x-message",
            "zoom-2x-hash",
            "https://cdn.example/zoom-2x-grid.png",
        ),
        (
            JobAction.ZOOM_OUT_1_5X,
            "job-zoom-1-5x",
            "zoom-1-5x-message",
            "zoom-1-5x-hash",
            "https://cdn.example/zoom-1-5x-grid.png",
        ),
        (
            JobAction.CUSTOM_ZOOM,
            "job-custom-zoom",
            "custom-zoom-message",
            "custom-zoom-hash",
            "https://cdn.example/custom-zoom-grid.png",
        ),
    ],
)
async def test_zoom_indexing_stores_each_grid_tile(
    action: JobAction,
    job_id: str,
    message_id: str,
    message_hash: str,
    url: str,
) -> None:
    """Index completed zoom outputs through the shared grid tile path."""

    image_bytes = _make_grid_png()
    processor = _FakeProcessor()
    image_index = ArtifactCacheService()
    coordinator = IndexingCoordinator(
        commands=_StaticProvider(image_bytes),
        image_processor=processor,
        artifact_cache=image_index,
        video_signature_service=_FakeVideoSignatureService(),
    )
    job = Job(id=job_id, action=action)
    job.context.message_hash = message_hash
    message = {
        "id": message_id,
        "flags": 64,
        "attachments": [{"url": url}],
    }

    await coordinator._index_image(action, message, job)

    tiles = coordinator._tiles_service.expand_tiles(job, image_bytes)
    refs = [
        image_index.get_image_job_ref(processor.compute_digest(tile.image_bytes)) for tile in tiles
    ]

    assert [ref.index for ref in refs if ref is not None] == [1, 2, 3, 4]
    assert all(ref is not None for ref in refs)
    assert all(ref.kind == "tile" for ref in refs)
    assert all(ref.message_id == message_id for ref in refs)
    assert all(ref.message_hash == message_hash for ref in refs)


@pytest.mark.asyncio
async def test_blend_indexing_stores_each_grid_tile() -> None:
    """Index blend outputs through the same shared grid artifact path."""

    image_bytes = _make_grid_png()
    processor = _FakeProcessor()
    image_index = ArtifactCacheService()
    coordinator = IndexingCoordinator(
        commands=_StaticProvider(image_bytes),
        image_processor=processor,
        artifact_cache=image_index,
        video_signature_service=_FakeVideoSignatureService(),
    )
    job = Job(id="job-blend", action=JobAction.BLEND)
    job.context.message_hash = "blend-hash"
    message = {
        "id": "blend-message",
        "flags": 64,
        "attachments": [{"url": "https://cdn.example/blend-grid.png"}],
    }

    await coordinator._index_image(JobAction.BLEND, message, job)

    tiles = coordinator._tiles_service.expand_tiles(job, image_bytes)
    refs = [
        image_index.get_image_job_ref(processor.compute_digest(tile.image_bytes)) for tile in tiles
    ]

    assert [ref.index for ref in refs if ref is not None] == [1, 2, 3, 4]
    assert all(ref is not None for ref in refs)
    assert all(ref.kind == "tile" for ref in refs)
    assert all(ref.message_id == "blend-message" for ref in refs)
    assert all(ref.message_hash == "blend-hash" for ref in refs)


@pytest.mark.asyncio
async def test_video_indexing_stores_final_animate_reply_context() -> None:
    """Index final animate Discord replies as recognized video artifacts."""
    video_bytes = b"video-bytes"
    image_index = ArtifactCacheService()
    coordinator = IndexingCoordinator(
        commands=_StaticProvider(video_bytes),
        image_processor=_FakeProcessor(),
        artifact_cache=image_index,
        video_signature_service=_FakeVideoSignatureService(),
    )
    job = Job(id="job-animate", action=JobAction.ANIMATE_LOW)
    job.context.message_hash = "video-hash"
    message = {
        "id": "video-message",
        "flags": 0,
        "attachments": [
            {
                "url": "https://cdn.example/video.mp4",
                "filename": "video.mp4",
                "content_type": "video/mp4",
            }
        ],
    }

    await coordinator._index_video(message, job)

    ref = image_index.find_video_by_digest(f"video-{hashlib.sha256(video_bytes).hexdigest()}")
    assert ref is not None
    assert ref.message_id == "video-message"
    assert ref.message_hash == "video-hash"
    assert ref.index == 1
    assert ref.kind == "video"


@pytest.mark.asyncio
async def test_indexing_drain_waits_for_pending_work() -> None:
    """Orderly drain should preserve pending artifact indexing before shutdown."""

    image_bytes = _make_grid_png()
    provider = _BlockingProvider(image_bytes)
    processor = _FakeProcessor()
    image_index = ArtifactCacheService()
    coordinator = IndexingCoordinator(
        commands=provider,
        image_processor=processor,
        artifact_cache=image_index,
        video_signature_service=_FakeVideoSignatureService(),
    )
    job = Job(id="job-imagine", action=JobAction.IMAGINE)
    job.context.message_hash = "imagine-hash"
    message = {
        "id": "imagine-message",
        "flags": 64,
        "attachments": [{"url": "https://cdn.example/imagine-grid.png"}],
    }

    coordinator.schedule_image_indexing(JobAction.IMAGINE, message, job)
    await provider.started.wait()
    provider.release.set()
    await coordinator.drain_pending(timeout_seconds=1.0)

    tiles = coordinator._tiles_service.expand_tiles(job, image_bytes)
    refs = [
        image_index.get_image_job_ref(processor.compute_digest(tile.image_bytes)) for tile in tiles
    ]
    assert all(ref is not None for ref in refs)
