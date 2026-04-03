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

import pytest

from mutiny import (
    ImageOutput,
    ImageResolution,
    ImageTile,
    JobHandle,
    JobSnapshot,
    JobStatus,
    Mutiny,
    ProgressUpdate,
    TextOutput,
    VideoResolution,
)
from mutiny.domain.job import Job, JobAction
from mutiny.domain.progress import ProgressEvent
from mutiny.domain.result import Result
from mutiny.engine.runtime.state import State
from mutiny.interfaces.image import ImageProcessor
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.context import AppContext
from mutiny.services.image_tiles import ImageTilesService
from mutiny.services.image_utils import parse_data_url
from mutiny.services.interaction_cache import InteractionCache
from mutiny.services.job_store import InMemoryJobStoreService
from mutiny.services.metrics.service import MetricsService
from mutiny.services.notify.event_bus import StreamingJobUpdateBus
from mutiny.services.response_dump import ResponseDumpService
from mutiny.services.video_signature import VideoSignature
from tests.image_helpers import decode_rgb, encode_image


class _FakeProcessor(ImageProcessor):
    def get_dimensions(self, data: bytes) -> tuple[int, int]:
        return (2, 2)

    def compute_digest(self, data: bytes) -> str:
        return f"digest-{data.hex()}"

    def compute_phash(self, data: bytes) -> int | None:
        return None

    def crop_split_grid(self, data: bytes) -> list[bytes]:
        return [data, data[::-1], data, data[::-1]]


def _ctx(test_config, *, video_signature_service=None) -> AppContext:
    return AppContext(
        config=test_config,
        job_store=InMemoryJobStoreService(),
        notify_bus=StreamingJobUpdateBus(),
        artifact_cache=ArtifactCacheService(),
        video_signature_service=video_signature_service,
        response_dump=ResponseDumpService(enabled=False),
        interaction_cache=InteractionCache(),
        metrics=MetricsService(),
        engine=None,
    )


def _client(test_config, *, ctx: AppContext | None = None) -> Mutiny:
    client = Mutiny(test_config)
    client._state = State(context=ctx or _ctx(test_config))
    return client


@pytest.mark.asyncio
async def test_imagine_projects_public_handle_and_normalizes_image_inputs(
    monkeypatch, test_config, sample_png_bytes
):
    async def _fake_imagine(self, dto):  # type: ignore[no-redef]
        assert dto.prompt == "dragon"
        assert dto.image_inputs is not None
        assert dto.image_inputs.prompt_images
        assert dto.image_inputs.style_reference is not None
        assert dto.image_inputs.omni_reference is not None
        assert dto.image_inputs.character_reference is None
        assert all(
            value.startswith("data:image/png;base64,") for value in dto.image_inputs.prompt_images
        )
        assert all(
            value.startswith("data:image/png;base64,")
            for value in dto.image_inputs.style_reference.images
        )
        assert dto.image_inputs.omni_reference.image.startswith("data:image/png;base64,")
        return Result(code=1, message="ok", value="job-1")

    monkeypatch.setattr(
        "mutiny.services.job_submission.JobSubmissionService.submit_imagine",
        _fake_imagine,
    )
    client = _client(test_config)

    handle = await client.imagine(
        "dragon",
        prompt_images=(sample_png_bytes,),
        style_references=(sample_png_bytes,),
        omni_reference=sample_png_bytes,
    )

    assert handle == JobHandle(id="job-1")


@pytest.mark.asyncio
async def test_describe_projects_public_handle(monkeypatch, test_config):
    async def _fake_describe(self, dto):  # type: ignore[no-redef]
        assert dto.base64 == "data:image/png;base64,AA=="
        assert dto.state == "describe-state"
        return Result(code=1, message="ok", value="job-describe")

    monkeypatch.setattr(
        "mutiny.services.job_submission.JobSubmissionService.submit_describe",
        _fake_describe,
    )
    client = _client(test_config)

    handle = await client.describe("data:image/png;base64,AA==", state="describe-state")

    assert handle == JobHandle(id="job-describe")


@pytest.mark.asyncio
async def test_describe_preserves_jpeg_bytes_and_mime(
    monkeypatch, test_config, sample_png_bytes, tmp_path
):
    jpeg_bytes = encode_image(decode_rgb(sample_png_bytes), extension=".jpg")
    jpeg_path = tmp_path / "subject.jpg"
    jpeg_path.write_bytes(jpeg_bytes)

    async def _fake_describe(self, dto):  # type: ignore[no-redef]
        parsed = parse_data_url(dto.base64)
        assert parsed is not None
        assert parsed.mime_type == "image/jpeg"
        assert parsed.data == jpeg_bytes
        return Result(code=1, message="ok", value="job-jpeg")

    monkeypatch.setattr(
        "mutiny.services.job_submission.JobSubmissionService.submit_describe",
        _fake_describe,
    )
    client = _client(test_config)

    handle = await client.describe(jpeg_path)

    assert handle == JobHandle(id="job-jpeg")


@pytest.mark.asyncio
async def test_blend_preserves_webp_bytes_and_mime(
    monkeypatch, test_config, sample_png_bytes, tmp_path
):
    webp_bytes = encode_image(decode_rgb(sample_png_bytes), extension=".webp")
    webp_path = tmp_path / "subject.webp"
    webp_path.write_bytes(webp_bytes)

    async def _fake_blend(self, dto):  # type: ignore[no-redef]
        assert len(dto.base64_array) == 2
        first = parse_data_url(dto.base64_array[0])
        second = parse_data_url(dto.base64_array[1])
        assert first is not None and second is not None
        assert first.mime_type == "image/webp"
        assert first.data == webp_bytes
        assert second.mime_type == "image/png"
        assert second.data == sample_png_bytes
        return Result(code=1, message="ok", value="job-blend")

    monkeypatch.setattr(
        "mutiny.services.job_submission.JobSubmissionService.submit_blend",
        _fake_blend,
    )
    client = _client(test_config)

    handle = await client.blend((webp_path, sample_png_bytes))

    assert handle == JobHandle(id="job-blend")


@pytest.mark.asyncio
async def test_vary_region_projects_public_handle(monkeypatch, test_config):
    async def _fake_vary_region(self, dto):  # type: ignore[no-redef]
        assert dto.base64 == "data:image/png;base64,AA=="
        assert dto.mask == "data:image/png;base64,BB=="
        assert dto.prompt == "add ivy"
        return Result(code=1, message="ok", value="job-vary-region")

    monkeypatch.setattr(
        "mutiny.services.job_submission.JobSubmissionService.submit_inpaint",
        _fake_vary_region,
    )
    client = _client(test_config)

    handle = await client.vary_region(
        "data:image/png;base64,AA==",
        "data:image/png;base64,BB==",
        prompt="add ivy",
    )

    assert handle == JobHandle(id="job-vary-region")


@pytest.mark.asyncio
async def test_upscale_vary_pan_zoom_map_to_internal_actions(monkeypatch, test_config):
    captured: list[tuple[JobAction, int | None]] = []

    async def _fake_change(self, dto):  # type: ignore[no-redef]
        captured.append((dto.action, dto.index))
        return Result(code=1, message="ok", value=f"job-{dto.action.value.lower()}")

    async def _fake_custom_zoom(self, dto):  # type: ignore[no-redef]
        captured.append((JobAction.CUSTOM_ZOOM, dto.index))
        assert dto.zoom_text == "tight crop --zoom 1.75"
        return Result(code=1, message="ok", value="job-custom-zoom")

    monkeypatch.setattr(
        "mutiny.services.job_submission.JobSubmissionService.submit_change",
        _fake_change,
    )
    monkeypatch.setattr(
        "mutiny.services.job_submission.JobSubmissionService.submit_custom_zoom",
        _fake_custom_zoom,
    )
    client = _client(test_config)

    assert await client.upscale("job-1", index=1) == JobHandle(id="job-upscale")
    assert await client.upscale("job-1", index=1, mode="subtle") == JobHandle(
        id="job-upscale_v7_2x_subtle"
    )
    assert await client.vary("job-1", index=2, mode="strong") == JobHandle(id="job-vary_strong")
    assert await client.pan("job-1", direction="left", index=1) == JobHandle(id="job-pan_left")
    assert await client.zoom("job-1", index=1, factor=2.0) == JobHandle(id="job-zoom_out_2x")
    assert await client.zoom("job-1", index=1, factor=1.75, prompt="tight crop") == JobHandle(
        id="job-custom-zoom"
    )

    assert captured == [
        (JobAction.UPSCALE, 1),
        (JobAction.UPSCALE_V7_2X_SUBTLE, 1),
        (JobAction.VARY_STRONG, 2),
        (JobAction.PAN_LEFT, 1),
        (JobAction.ZOOM_OUT_2X, 1),
        (JobAction.CUSTOM_ZOOM, 1),
    ]


@pytest.mark.asyncio
async def test_animate_extend_and_blend_project_public_handles(monkeypatch, test_config):
    async def _fake_animate(self, dto):  # type: ignore[no-redef]
        assert dto.prompt == "camera push"
        assert dto.motion.value == "high"
        return Result(code=1, message="ok", value="job-animate")

    async def _fake_extend(self, dto):  # type: ignore[no-redef]
        assert dto.job_id == "video-job"
        assert dto.motion.value == "low"
        return Result(code=1, message="ok", value="job-extend")

    async def _fake_blend(self, dto):  # type: ignore[no-redef]
        assert len(dto.base64_array) == 2
        return Result(code=1, message="ok", value="job-blend")

    monkeypatch.setattr(
        "mutiny.services.job_submission.JobSubmissionService.submit_animate",
        _fake_animate,
    )
    monkeypatch.setattr(
        "mutiny.services.job_submission.JobSubmissionService.submit_animate_extend",
        _fake_extend,
    )
    monkeypatch.setattr(
        "mutiny.services.job_submission.JobSubmissionService.submit_blend",
        _fake_blend,
    )
    client = _client(test_config)

    assert await client.animate(
        "data:image/png;base64,AA==",
        end_frame="data:image/png;base64,BB==",
        prompt="camera push",
        motion="high",
    ) == JobHandle(id="job-animate")
    assert await client.extend(job_id="video-job", motion="low") == JobHandle(id="job-extend")
    assert await client.blend(
        ("data:image/png;base64,AA==", "data:image/png;base64,BB==")
    ) == JobHandle(id="job-blend")


@pytest.mark.parametrize(
    "action",
    [
        JobAction.IMAGINE,
        JobAction.PAN_LEFT,
        JobAction.ZOOM_OUT_2X,
        JobAction.CUSTOM_ZOOM,
    ],
)
def test_split_image_result_projects_public_tiles(test_config, action: JobAction):
    ctx = _ctx(test_config)
    ctx.image_processor = _FakeProcessor()
    job = Job(id=f"job-{action.value.lower()}", action=action)
    job.status = JobStatus.SUCCEEDED
    ctx.job_store.save(job)
    client = _client(test_config, ctx=ctx)
    client._tiles_service = ImageTilesService(_FakeProcessor())

    tiles = client.split_image_result(job.id, b"abcdef")

    assert tiles == (
        ImageTile(job_id=job.id, index=1, image_bytes=b"abcdef"),
        ImageTile(job_id=job.id, index=2, image_bytes=b"fedcba"),
        ImageTile(job_id=job.id, index=3, image_bytes=b"abcdef"),
        ImageTile(job_id=job.id, index=4, image_bytes=b"fedcba"),
    )


def test_resolve_image_and_video_project_public_resolution_types(test_config):
    class _FakeVideoSignatureService:
        def compute_signature(self, video_bytes: bytes) -> VideoSignature:
            assert video_bytes == b"video-bytes"
            return VideoSignature(digest="video-digest")

    ctx = _ctx(test_config, video_signature_service=_FakeVideoSignatureService())
    ctx.image_processor = _FakeProcessor()
    image_bytes = b"image-bytes"
    image_digest = ctx.image_processor.compute_digest(image_bytes)
    pan_tile_bytes = b"pan-tile-bytes"
    pan_tile_digest = ctx.image_processor.compute_digest(pan_tile_bytes)
    video_job = Job(id="job-video", action=JobAction.ANIMATE_LOW)
    video_job.context.message_id = "video-message"
    video_job.context.message_hash = "video-hash"
    image_job = Job(id="job-image", action=JobAction.UPSCALE)
    image_job.context.message_id = "image-message"
    image_job.context.message_hash = "image-hash"
    pan_job = Job(id="job-pan", action=JobAction.PAN_LEFT)
    pan_job.context.message_id = "pan-message"
    pan_job.context.message_hash = "pan-hash"
    ctx.job_store.save(video_job)
    ctx.job_store.save(image_job)
    ctx.job_store.save(pan_job)
    ctx.artifact_cache.put_image_job_ref(
        image_digest,
        message_id="image-message",
        message_hash="image-hash",
        flags=64,
        index=2,
        kind="tile",
    )
    ctx.artifact_cache.put_image_job_ref(
        pan_tile_digest,
        message_id="pan-message",
        message_hash="pan-hash",
        flags=64,
        index=3,
        kind="tile",
    )
    ctx.artifact_cache.put_video_job_ref(
        "video-digest",
        message_id="video-message",
        message_hash="video-hash",
        flags=64,
        signature_version=1,
    )
    client = _client(test_config, ctx=ctx)

    assert client.resolve_image(image_bytes) == ImageResolution(job_id="job-image", index=2)
    assert client.resolve_image(pan_tile_bytes) == ImageResolution(job_id="job-pan", index=3)
    assert client.resolve_video(b"video-bytes") == VideoResolution(job_id="job-video")


def test_resolve_image_projects_zoom_tile_recovery_from_persisted_cache(test_config):
    ctx = _ctx(test_config)
    ctx.image_processor = _FakeProcessor()
    zoom_tile_bytes = b"zoom-tile-bytes"
    zoom_tile_digest = ctx.image_processor.compute_digest(zoom_tile_bytes)
    zoom_job = Job(id="job-zoom", action=JobAction.ZOOM_OUT_2X)
    zoom_job.context.message_id = "zoom-message"
    zoom_job.context.message_hash = "zoom-hash"
    ctx.job_store.save(zoom_job)
    ctx.artifact_cache.put_image_job_ref(
        zoom_tile_digest,
        message_id="zoom-message",
        message_hash="zoom-hash",
        flags=64,
        index=4,
        kind="tile",
    )
    client = _client(test_config, ctx=ctx)

    assert client.resolve_image(zoom_tile_bytes) == ImageResolution(job_id="job-zoom", index=4)


@pytest.mark.asyncio
async def test_events_and_getters_project_public_snapshots(test_config):
    ctx = _ctx(test_config)
    client = _client(test_config, ctx=ctx)
    job = Job(id="job-1", action=JobAction.IMAGINE, prompt="castle")
    job.status = JobStatus.SUCCEEDED
    job.image_url = "https://cdn.example/job.png"
    job.progress = "done"
    job.context.final_prompt = "castle at sunrise"
    ctx.job_store.save(job)
    events = client.events(job_id="job-1")

    async def _publish_updates() -> None:
        await asyncio.sleep(0.01)
        ctx.notify_bus.publish_progress(
            ProgressEvent(
                job_id="job-1",
                kind="progress",
                status_text="50%",
                prompt="castle",
                progress_message_id=None,
                message_id=None,
                flags=None,
                image_url="https://cdn.example/preview.png",
                message_hash=None,
                not_fast=None,
            )
        )
        await asyncio.sleep(0.01)
        ctx.notify_bus.publish_job(job)

    publisher = asyncio.create_task(_publish_updates())
    progress = await asyncio.wait_for(anext(events), timeout=1.0)
    snapshot = await asyncio.wait_for(anext(events), timeout=1.0)
    await publisher
    await events.aclose()

    assert progress == ProgressUpdate(
        job_id="job-1",
        status_text="50%",
        preview_image_url="https://cdn.example/preview.png",
    )
    assert snapshot == JobSnapshot(
        id="job-1",
        kind="imagine",
        status=JobStatus.SUCCEEDED,
        progress_text="done",
        preview_image_url="https://cdn.example/job.png",
        fail_reason=None,
        prompt_text="castle at sunrise",
        output=ImageOutput(image_url="https://cdn.example/job.png", local_file_path=None),
    )
    assert await client.get_job("job-1") == snapshot
    assert await client.list_jobs(status=JobStatus.SUCCEEDED) == [snapshot]


@pytest.mark.asyncio
async def test_job_filtered_events_ignore_unrelated_global_traffic(test_config):
    ctx = _ctx(test_config)
    client = _client(test_config, ctx=ctx)
    target_job = Job(id="job-target", action=JobAction.IMAGINE)
    target_job.status = JobStatus.SUCCEEDED
    target_job.image_url = "https://cdn.example/target.png"
    ctx.job_store.save(target_job)
    events = client.events(job_id="job-target")

    async def _publish_updates() -> None:
        await asyncio.sleep(0.01)
        for idx in range(800):
            ctx.notify_bus.publish_progress(
                ProgressEvent(
                    job_id=f"noise-{idx}",
                    kind="progress",
                    status_text=f"noise-{idx}",
                    prompt=None,
                    progress_message_id=None,
                    message_id=None,
                    flags=None,
                    image_url=None,
                    message_hash=None,
                    not_fast=None,
                )
            )
        ctx.notify_bus.publish_progress(
            ProgressEvent(
                job_id="job-target",
                kind="progress",
                status_text="target-progress",
                prompt=None,
                progress_message_id=None,
                message_id=None,
                flags=None,
                image_url="https://cdn.example/preview.png",
                message_hash=None,
                not_fast=None,
            )
        )
        await asyncio.sleep(0.01)
        ctx.notify_bus.publish_job(target_job)

    publisher = asyncio.create_task(_publish_updates())
    progress = await asyncio.wait_for(anext(events), timeout=1.0)
    snapshot = await asyncio.wait_for(anext(events), timeout=1.0)
    await publisher
    await events.aclose()

    assert progress == ProgressUpdate(
        job_id="job-target",
        status_text="target-progress",
        preview_image_url="https://cdn.example/preview.png",
    )
    assert snapshot == JobSnapshot(
        id="job-target",
        kind="imagine",
        status=JobStatus.SUCCEEDED,
        progress_text=None,
        preview_image_url="https://cdn.example/target.png",
        fail_reason=None,
        prompt_text=None,
        output=ImageOutput(image_url="https://cdn.example/target.png", local_file_path=None),
    )


@pytest.mark.asyncio
async def test_filtered_events_release_bus_subscriptions_on_close(test_config):
    ctx = _ctx(test_config)
    client = _client(test_config, ctx=ctx)
    job = Job(id="job-1", action=JobAction.IMAGINE)
    ctx.job_store.save(job)
    events = client.events(job_id="job-1")
    next_update = asyncio.create_task(anext(events))
    await asyncio.sleep(0)

    ctx.notify_bus.publish_progress(
        ProgressEvent(
            job_id="job-1",
            kind="progress",
            status_text="warmup",
            prompt=None,
            progress_message_id=None,
            message_id=None,
            flags=None,
            image_url=None,
            message_hash=None,
            not_fast=None,
        )
    )
    update = await asyncio.wait_for(next_update, timeout=1.0)
    assert update == ProgressUpdate(job_id="job-1", status_text="warmup", preview_image_url=None)
    assert ctx.notify_bus._subs["job-1"]
    assert ctx.notify_bus._progress_subs["job-1"]

    await events.aclose()

    assert "job-1" not in ctx.notify_bus._subs
    assert "job-1" not in ctx.notify_bus._progress_subs


@pytest.mark.asyncio
async def test_global_events_release_global_subscription_on_close(test_config):
    ctx = _ctx(test_config)
    client = _client(test_config, ctx=ctx)
    job = Job(id="job-1", action=JobAction.IMAGINE)
    job.status = JobStatus.SUCCEEDED
    ctx.job_store.save(job)
    events = client.events()
    next_update = asyncio.create_task(anext(events))
    await asyncio.sleep(0)

    ctx.notify_bus.publish_job(job)
    snapshot = await asyncio.wait_for(next_update, timeout=1.0)
    assert snapshot.id == "job-1"
    assert len(ctx.notify_bus._global_subs) == 1

    await events.aclose()

    assert ctx.notify_bus._global_subs == []


@pytest.mark.asyncio
async def test_wait_for_job_returns_terminal_snapshot(test_config):
    ctx = _ctx(test_config)
    client = _client(test_config, ctx=ctx)
    job = Job(id="job-1", action=JobAction.DESCRIBE)
    ctx.job_store.save(job)

    async def _complete_job() -> None:
        await asyncio.sleep(0.01)
        job.status = JobStatus.SUCCEEDED
        job.description = "weathered stone arch in rain"
        job.completion_event.set()

    asyncio.create_task(_complete_job())
    snapshot = await client.wait_for_job("job-1", timeout_s=1.0)

    assert snapshot == JobSnapshot(
        id="job-1",
        kind="describe",
        status=JobStatus.SUCCEEDED,
        progress_text=None,
        preview_image_url=None,
        fail_reason=None,
        prompt_text=None,
        output=TextOutput(text="weathered stone arch in rain"),
    )


@pytest.mark.asyncio
async def test_non_success_raises_runtime_error(monkeypatch, test_config):
    async def _fake_imagine_fail(self, dto):  # type: ignore[no-redef]
        return Result(code=400, message="bad request")

    monkeypatch.setattr(
        "mutiny.services.job_submission.JobSubmissionService.submit_imagine",
        _fake_imagine_fail,
    )
    client = _client(test_config)

    with pytest.raises(RuntimeError, match="bad request"):
        await client.imagine("x")
