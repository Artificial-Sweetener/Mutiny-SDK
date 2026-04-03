from __future__ import annotations

from typing import AsyncIterator, Literal

from .config import Config
from .public_models import (
    ImageInput,
    ImageResolution,
    ImageTile,
    JobHandle,
    JobSnapshot,
    JobStatus,
    ProgressUpdate,
    VideoInput,
    VideoResolution,
)

UpscaleMode = Literal["standard", "subtle", "creative"]
VaryMode = Literal["standard", "subtle", "strong"]
PanDirection = Literal["left", "right", "up", "down"]
MotionLevel = Literal["low", "high"]

class Mutiny:
    def __init__(self, config: Config) -> None: ...
    async def start(self) -> None: ...
    async def close(self) -> None: ...
    async def wait_ready(self, timeout_s: int | None = ...) -> bool: ...
    async def events(
        self, job_id: str | None = ...
    ) -> AsyncIterator[ProgressUpdate | JobSnapshot]: ...
    async def imagine(
        self,
        prompt: str,
        *,
        prompt_images: tuple[ImageInput, ...] = ...,
        style_references: tuple[ImageInput, ...] = ...,
        character_references: tuple[ImageInput, ...] = ...,
        omni_reference: ImageInput | None = ...,
        state: str | None = ...,
    ) -> JobHandle: ...
    async def describe(self, image: ImageInput, *, state: str | None = ...) -> JobHandle: ...
    async def vary_region(
        self,
        image: ImageInput,
        mask: ImageInput,
        *,
        prompt: str | None = ...,
        state: str | None = ...,
    ) -> JobHandle: ...
    async def upscale(
        self,
        job_id: str,
        *,
        index: int,
        mode: UpscaleMode = ...,
        state: str | None = ...,
    ) -> JobHandle: ...
    async def vary(
        self,
        job_id: str,
        *,
        index: int,
        mode: VaryMode = ...,
        state: str | None = ...,
    ) -> JobHandle: ...
    async def pan(
        self,
        job_id: str,
        *,
        index: int | None = ...,
        direction: PanDirection,
        state: str | None = ...,
    ) -> JobHandle: ...
    async def zoom(
        self,
        job_id: str,
        *,
        index: int | None = ...,
        factor: float,
        prompt: str | None = ...,
        state: str | None = ...,
    ) -> JobHandle: ...
    async def animate(
        self,
        start_frame: ImageInput,
        *,
        end_frame: ImageInput | None = ...,
        prompt: str | None = ...,
        motion: MotionLevel = ...,
        batch_size: int | None = ...,
        state: str | None = ...,
    ) -> JobHandle: ...
    async def extend(
        self,
        *,
        job_id: str | None = ...,
        video: VideoInput | None = ...,
        motion: MotionLevel = ...,
        state: str | None = ...,
    ) -> JobHandle: ...
    async def blend(
        self,
        images: tuple[ImageInput, ...],
        *,
        dimensions: str = ...,
        state: str | None = ...,
    ) -> JobHandle: ...
    async def get_job(self, job_id: str) -> JobSnapshot: ...
    async def wait_for_job(self, job_id: str, *, timeout_s: float | None = ...) -> JobSnapshot: ...
    async def list_jobs(
        self,
        *,
        status: JobStatus | None = ...,
        active_only: bool = ...,
    ) -> list[JobSnapshot]: ...
    def resolve_image(self, image: ImageInput) -> ImageResolution | None: ...
    def resolve_video(self, video: VideoInput) -> VideoResolution | None: ...
    def split_image_result(self, job_id: str, image: ImageInput) -> tuple[ImageTile, ...]: ...
