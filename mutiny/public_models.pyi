from __future__ import annotations

from pathlib import Path

from .types import JobStatus as JobStatus

ImageInput = bytes | str | Path
VideoInput = bytes | str | Path

class JobHandle:
    id: str

class ImageOutput:
    image_url: str
    local_file_path: str | None

class VideoOutput:
    video_url: str | None
    local_file_path: str | None
    website_url: str | None

class TextOutput:
    text: str

class ProgressUpdate:
    job_id: str
    status_text: str | None
    preview_image_url: str | None

class JobSnapshot:
    id: str
    kind: str
    status: JobStatus
    progress_text: str | None
    preview_image_url: str | None
    fail_reason: str | None
    prompt_text: str | None
    output: ImageOutput | VideoOutput | TextOutput | None

class ImageResolution:
    job_id: str
    index: int

class VideoResolution:
    job_id: str

class ImageTile:
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
