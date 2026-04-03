from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from .types import JobStatus as JobStatus

ImageInput: TypeAlias = bytes | str | Path
VideoInput: TypeAlias = bytes | str | Path


@dataclass(frozen=True)
class JobHandle:
    """Stable public handle returned when one job is submitted."""

    id: str


@dataclass(frozen=True)
class ImageOutput:
    """Public image output details for one completed job."""

    image_url: str
    local_file_path: str | None = None


@dataclass(frozen=True)
class VideoOutput:
    """Public video output details for one completed job."""

    video_url: str | None = None
    local_file_path: str | None = None
    website_url: str | None = None


@dataclass(frozen=True)
class TextOutput:
    """Public text output details for one completed job."""

    text: str


@dataclass(frozen=True)
class ProgressUpdate:
    """Public non-terminal progress update."""

    job_id: str
    status_text: str | None = None
    preview_image_url: str | None = None


@dataclass(frozen=True)
class JobSnapshot:
    """Public snapshot of one job's current or terminal state."""

    id: str
    kind: str
    status: JobStatus
    progress_text: str | None = None
    preview_image_url: str | None = None
    fail_reason: str | None = None
    prompt_text: str | None = None
    output: ImageOutput | VideoOutput | TextOutput | None = None


@dataclass(frozen=True)
class ImageResolution:
    """Resolved source metadata for one recognized image result."""

    job_id: str
    index: int


@dataclass(frozen=True)
class VideoResolution:
    """Resolved source metadata for one recognized video result."""

    job_id: str


@dataclass(frozen=True)
class ImageTile:
    """Public tile projection for one recognized or split image result."""

    job_id: str
    index: int
    image_bytes: bytes


__all__ = [
    "ImageInput",
    "ImageOutput",
    "ImageResolution",
    "ImageTile",
    "JobHandle",
    "JobSnapshot",
    "JobStatus",
    "ProgressUpdate",
    "TextOutput",
    "VideoInput",
    "VideoOutput",
    "VideoResolution",
]
