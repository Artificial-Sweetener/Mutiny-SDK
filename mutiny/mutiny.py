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

"""Mutiny facade for single-account Midjourney integration."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Literal

from ._public_inputs import normalize_image_input, normalize_image_inputs, read_binary_input
from .config import Config
from .engine.runtime.state import State
from .public_models import (
    ImageInput,
    ImageOutput,
    ImageResolution,
    ImageTile,
    JobHandle,
    JobSnapshot,
    ProgressUpdate,
    TextOutput,
    VideoInput,
    VideoOutput,
    VideoResolution,
)
from .services.image_tiles import ImageTilesService
from .services.job_requests import (
    JobAnimateCommand,
    JobAnimateExtendCommand,
    JobBlendCommand,
    JobChangeCommand,
    JobCustomZoomCommand,
    JobDescribeCommand,
    JobImagineCommand,
    JobInpaintCommand,
)
from .services.job_submission import JobSubmissionService
from .types import (
    AnimateMotion,
    CharacterReferenceImages,
    ImagineImageInputs,
    Job,
    JobAction,
    JobStatus,
    OmniReferenceImage,
    ProgressEvent,
    Result,
    StyleReferenceImages,
)

UpscaleMode = Literal["standard", "subtle", "creative"]
VaryMode = Literal["standard", "subtle", "strong"]
PanDirection = Literal["left", "right", "up", "down"]
MotionLevel = Literal["low", "high"]


class Mutiny:
    """Public facade for Mutiny job submission and lifecycle control."""

    def __init__(self, config: Config) -> None:
        """Construct the facade from one owned configuration snapshot."""

        self._state = State(config=config)
        self._job_service: JobSubmissionService | None = None
        self._tiles_service: ImageTilesService | None = None

    def _service(self) -> JobSubmissionService:
        ctx = self._state.require_context()
        if self._job_service is None:
            self._job_service = JobSubmissionService(ctx)
        return self._job_service

    def _tiles(self) -> ImageTilesService:
        if self._tiles_service is None:
            self._tiles_service = ImageTilesService()
        return self._tiles_service

    @staticmethod
    def _raise_for_result(result: Result[str]) -> None:
        if result.validation_error:
            raise ValueError(result.message)
        if result.code == 1:
            return
        raise RuntimeError(result.message)

    @staticmethod
    def _job_handle(job_id: str) -> JobHandle:
        return JobHandle(id=job_id)

    @staticmethod
    def _motion_from_value(motion: MotionLevel) -> AnimateMotion:
        if motion == "high":
            return AnimateMotion.HIGH
        return AnimateMotion.LOW

    @staticmethod
    def _output_for_job(job: Job) -> ImageOutput | VideoOutput | TextOutput | None:
        if job.description:
            return TextOutput(text=job.description)

        if any(
            [
                job.artifacts.video_url,
                job.artifacts.video_file_path,
                job.artifacts.website_video_url,
                job.artifacts.website_url,
            ]
        ):
            return VideoOutput(
                video_url=job.artifacts.video_url,
                local_file_path=job.artifacts.video_file_path,
                website_url=job.artifacts.website_video_url or job.artifacts.website_url,
            )

        if job.image_url:
            return ImageOutput(image_url=job.image_url)

        return None

    @classmethod
    def _snapshot_for_job(cls, job: Job) -> JobSnapshot:
        prompt_text = job.context.final_prompt or job.prompt_en or job.prompt
        return JobSnapshot(
            id=job.id,
            kind=job.action.value.lower(),
            status=job.status,
            progress_text=job.progress,
            preview_image_url=job.image_url,
            fail_reason=job.fail_reason,
            prompt_text=prompt_text,
            output=cls._output_for_job(job),
        )

    @staticmethod
    def _progress_for_event(event: ProgressEvent) -> ProgressUpdate:
        return ProgressUpdate(
            job_id=event.job_id,
            status_text=event.status_text,
            preview_image_url=event.image_url,
        )

    @staticmethod
    def _upscale_action(mode: UpscaleMode) -> JobAction:
        if mode == "subtle":
            return JobAction.UPSCALE_V7_2X_SUBTLE
        if mode == "creative":
            return JobAction.UPSCALE_V7_2X_CREATIVE
        return JobAction.UPSCALE

    @staticmethod
    def _vary_action(mode: VaryMode) -> JobAction:
        if mode == "subtle":
            return JobAction.VARY_SUBTLE
        if mode == "strong":
            return JobAction.VARY_STRONG
        return JobAction.VARIATION

    @staticmethod
    def _pan_action(direction: PanDirection) -> JobAction:
        mapping = {
            "left": JobAction.PAN_LEFT,
            "right": JobAction.PAN_RIGHT,
            "up": JobAction.PAN_UP,
            "down": JobAction.PAN_DOWN,
        }
        return mapping[direction]

    @staticmethod
    def _zoom_action(factor: float) -> JobAction | None:
        if abs(factor - 2.0) < 1e-9:
            return JobAction.ZOOM_OUT_2X
        if abs(factor - 1.5) < 1e-9:
            return JobAction.ZOOM_OUT_1_5X
        return None

    @staticmethod
    def _zoom_text(factor: float, prompt: str | None) -> str:
        zoom_flag = f"--zoom {factor:g}"
        if prompt and prompt.strip():
            return f"{prompt.strip()} {zoom_flag}"
        return zoom_flag

    def _require_job(self, job_id: str) -> Job:
        job = self._state.require_context().job_store.get(job_id)
        if job is None:
            raise RuntimeError("Job not found")
        return job

    async def start(self) -> None:
        """Start the runtime engine and gateway connections."""

        await self._state.start()

    async def close(self) -> None:
        """Shut down the runtime engine and gateway connections."""

        await self._state.close()

    async def wait_ready(self, timeout_s: int | None = None) -> bool:
        """Wait for the gateway connection to become ready."""

        return await self._state.wait_ready(timeout_s=timeout_s)

    async def events(
        self, job_id: str | None = None
    ) -> AsyncIterator[ProgressUpdate | JobSnapshot]:
        """Stream public progress updates and job snapshots."""

        notify_bus = self._state.require_context().notify_bus
        if job_id is None:
            queue = notify_bus.subscribe_all()
            try:
                while True:
                    event = await queue.get()
                    if isinstance(event, Job):
                        yield self._snapshot_for_job(event)
                        continue
                    yield self._progress_for_event(event)
            finally:
                notify_bus.unsubscribe_all(queue)
            return

        job_queue = notify_bus.subscribe(job_id)
        progress_queue = notify_bus.subscribe_progress(job_id)
        try:
            while True:
                job_task = asyncio.create_task(job_queue.get())
                progress_task = asyncio.create_task(progress_queue.get())
                done, pending = await asyncio.wait(
                    {job_task, progress_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                for task in pending:
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                event = next(iter(done)).result()
                if isinstance(event, Job):
                    yield self._snapshot_for_job(event)
                    continue
                yield self._progress_for_event(event)
        finally:
            notify_bus.unsubscribe(job_id, job_queue)
            notify_bus.unsubscribe_progress(job_id, progress_queue)

    async def imagine(
        self,
        prompt: str,
        *,
        prompt_images: tuple[ImageInput, ...] = (),
        style_references: tuple[ImageInput, ...] = (),
        character_references: tuple[ImageInput, ...] = (),
        omni_reference: ImageInput | None = None,
        state: str | None = None,
    ) -> JobHandle:
        """Submit a text-to-image request."""

        image_inputs = ImagineImageInputs(
            prompt_images=await normalize_image_inputs(tuple(prompt_images)),
            style_reference=(
                StyleReferenceImages(images=await normalize_image_inputs(tuple(style_references)))
                if style_references
                else None
            ),
            character_reference=(
                CharacterReferenceImages(
                    images=await normalize_image_inputs(tuple(character_references))
                )
                if character_references
                else None
            ),
            omni_reference=(
                OmniReferenceImage(await normalize_image_input(omni_reference))
                if omni_reference is not None
                else None
            ),
        )
        result = await self._service().submit_imagine(
            JobImagineCommand(
                prompt=prompt,
                base64_array=list(image_inputs.prompt_images) or None,
                image_inputs=(
                    image_inputs
                    if any(
                        [
                            image_inputs.prompt_images,
                            image_inputs.style_reference,
                            image_inputs.character_reference,
                            image_inputs.omni_reference,
                        ]
                    )
                    else None
                ),
                state=state,
            )
        )
        self._raise_for_result(result)
        return self._job_handle(result.value or "")

    async def describe(self, image: ImageInput, *, state: str | None = None) -> JobHandle:
        """Submit one describe request for an image."""

        result = await self._service().submit_describe(
            JobDescribeCommand(base64=await normalize_image_input(image), state=state)
        )
        self._raise_for_result(result)
        return self._job_handle(result.value or "")

    async def vary_region(
        self,
        image: ImageInput,
        mask: ImageInput,
        *,
        prompt: str | None = None,
        state: str | None = None,
    ) -> JobHandle:
        """Submit one vary-region request using a base image and mask."""

        result = await self._service().submit_inpaint(
            JobInpaintCommand(
                base64=await normalize_image_input(image),
                mask=await normalize_image_input(mask),
                prompt=prompt,
                state=state,
            )
        )
        self._raise_for_result(result)
        return self._job_handle(result.value or "")

    async def upscale(
        self,
        job_id: str,
        *,
        index: int,
        mode: UpscaleMode = "standard",
        state: str | None = None,
    ) -> JobHandle:
        """Submit one upscale-style follow-up request."""

        result = await self._service().submit_change(
            JobChangeCommand(
                job_id=job_id,
                action=self._upscale_action(mode),
                index=index,
                state=state,
            )
        )
        self._raise_for_result(result)
        return self._job_handle(result.value or "")

    async def vary(
        self,
        job_id: str,
        *,
        index: int,
        mode: VaryMode = "standard",
        state: str | None = None,
    ) -> JobHandle:
        """Submit one vary-style follow-up request."""

        result = await self._service().submit_change(
            JobChangeCommand(
                job_id=job_id,
                action=self._vary_action(mode),
                index=index,
                state=state,
            )
        )
        self._raise_for_result(result)
        return self._job_handle(result.value or "")

    async def pan(
        self,
        job_id: str,
        *,
        index: int | None = None,
        direction: PanDirection,
        state: str | None = None,
    ) -> JobHandle:
        """Submit one pan follow-up request."""

        result = await self._service().submit_change(
            JobChangeCommand(
                job_id=job_id,
                action=self._pan_action(direction),
                index=index,
                state=state,
            )
        )
        self._raise_for_result(result)
        return self._job_handle(result.value or "")

    async def zoom(
        self,
        job_id: str,
        *,
        index: int | None = None,
        factor: float,
        prompt: str | None = None,
        state: str | None = None,
    ) -> JobHandle:
        """Submit one zoom follow-up request."""

        action = self._zoom_action(factor)
        if action is not None:
            result = await self._service().submit_change(
                JobChangeCommand(
                    job_id=job_id,
                    action=action,
                    index=index,
                    state=state,
                )
            )
        else:
            result = await self._service().submit_custom_zoom(
                JobCustomZoomCommand(
                    job_id=job_id,
                    index=index,
                    zoom_text=self._zoom_text(factor, prompt),
                    state=state,
                )
            )
        self._raise_for_result(result)
        return self._job_handle(result.value or "")

    async def animate(
        self,
        start_frame: ImageInput,
        *,
        end_frame: ImageInput | None = None,
        prompt: str | None = None,
        motion: MotionLevel = "low",
        batch_size: int | None = None,
        state: str | None = None,
    ) -> JobHandle:
        """Submit one animate request."""

        result = await self._service().submit_animate(
            JobAnimateCommand(
                start_frame_data_url=await normalize_image_input(start_frame),
                end_frame_data_url=(
                    await normalize_image_input(end_frame) if end_frame is not None else None
                ),
                prompt=prompt,
                motion=self._motion_from_value(motion),
                batch_size=batch_size,
                state=state,
            )
        )
        self._raise_for_result(result)
        return self._job_handle(result.value or "")

    async def extend(
        self,
        *,
        job_id: str | None = None,
        video: VideoInput | None = None,
        motion: MotionLevel = "low",
        state: str | None = None,
    ) -> JobHandle:
        """Submit one animate-extend follow-up request."""

        result = await self._service().submit_animate_extend(
            JobAnimateExtendCommand(
                job_id=job_id,
                video_bytes=read_binary_input(video) if video is not None else None,
                motion=self._motion_from_value(motion),
                state=state,
            )
        )
        self._raise_for_result(result)
        return self._job_handle(result.value or "")

    async def blend(
        self,
        images: tuple[ImageInput, ...],
        *,
        dimensions: str = "1:1",
        state: str | None = None,
    ) -> JobHandle:
        """Submit one blend request."""

        normalized_images = await normalize_image_inputs(tuple(images))
        result = await self._service().submit_blend(
            JobBlendCommand(
                base64_array=list(normalized_images),
                dimensions=dimensions,
                state=state,
            )
        )
        self._raise_for_result(result)
        return self._job_handle(result.value or "")

    async def get_job(self, job_id: str) -> JobSnapshot:
        """Return the current public snapshot for one job."""

        return self._snapshot_for_job(self._require_job(job_id))

    async def wait_for_job(self, job_id: str, *, timeout_s: float | None = None) -> JobSnapshot:
        """Wait until one job reaches a terminal state and return its public snapshot."""

        job = self._require_job(job_id)
        if job.status not in {JobStatus.SUCCEEDED, JobStatus.FAILED}:
            await asyncio.wait_for(job.completion_event.wait(), timeout=timeout_s)
        return self._snapshot_for_job(job)

    async def list_jobs(
        self,
        *,
        status: JobStatus | None = None,
        active_only: bool = False,
    ) -> list[JobSnapshot]:
        """Return public snapshots for the known jobs in the store."""

        jobs = self._state.require_context().job_store.list()
        if active_only:
            jobs = [
                job for job in jobs if job.status in {JobStatus.SUBMITTED, JobStatus.IN_PROGRESS}
            ]
        if status is not None:
            jobs = [job for job in jobs if job.status == status]
        return [self._snapshot_for_job(job) for job in jobs]

    def resolve_image(self, image: ImageInput) -> ImageResolution | None:
        """Resolve one image back to its source job when Mutiny recognizes it."""

        image_bytes = read_binary_input(image)
        job, index = self._find_job_by_image(image_bytes)
        if job is None:
            return None
        return ImageResolution(job_id=job.id, index=index)

    def resolve_video(self, video: VideoInput) -> VideoResolution | None:
        """Resolve one video back to its source job when Mutiny recognizes it."""

        video_bytes = read_binary_input(video)
        job = self._find_job_by_video(video_bytes)
        if job is None:
            return None
        return VideoResolution(job_id=job.id)

    def split_image_result(self, job_id: str, image: ImageInput) -> tuple[ImageTile, ...]:
        """Split one image result into the facade-owned tile projection."""

        job = self._require_job(job_id)
        image_bytes = read_binary_input(image)
        return tuple(
            ImageTile(job_id=tile.job_id, index=tile.index, image_bytes=tile.image_bytes)
            for tile in self._tiles().expand_tiles(job, image_bytes)
        )

    def _find_job_by_image(self, image_bytes: bytes) -> tuple[Job | None, int]:
        context = self._service().find_image_context(image_bytes)
        if context is None:
            return None, 0
        job = self._service()._hydrate_recognized_image_job(context)
        return job, context.index

    def _find_job_by_video(self, video_bytes: bytes) -> Job | None:
        return self._service().find_job_by_video(video_bytes)


__all__ = ["Mutiny"]
