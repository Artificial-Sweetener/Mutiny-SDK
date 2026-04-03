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

"""API-facing DTOs for job submission and change commands.

These frozen dataclasses mirror request payloads received by Mutiny surfaces;
they contain no behavior and feed the domain layer directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from mutiny.types import AnimateMotion, ImagineImageInputs, JobAction


@dataclass(frozen=True)
class JobRequestBase:
    """Base fields shared by job commands."""

    state: Optional[str] = None
    notify_hook: Optional[str] = None


@dataclass(frozen=True)
class JobImagineCommand(JobRequestBase):
    """Command for imagine submission."""

    prompt: str = ""
    base64_array: Optional[list[str]] = None
    image_inputs: ImagineImageInputs | None = None


@dataclass(frozen=True)
class JobChangeCommand(JobRequestBase):
    """Command for job change actions."""

    job_id: str = ""
    action: JobAction = JobAction.UPSCALE
    index: Optional[int] = None


@dataclass(frozen=True)
class JobImageChangeCommand(JobRequestBase):
    """Command for image-based change actions."""

    base64: str = ""
    action: JobAction = JobAction.UPSCALE


@dataclass(frozen=True)
class JobDescribeCommand(JobRequestBase):
    """Command for describe submissions."""

    base64: str = ""


@dataclass(frozen=True)
class JobAnimateCommand(JobRequestBase):
    """Command for unified animate submissions."""

    start_frame_data_url: str = ""
    end_frame_data_url: str | None = None
    prompt: str | None = None
    motion: AnimateMotion = AnimateMotion.LOW
    batch_size: int | None = None


@dataclass(frozen=True)
class JobAnimateExtendCommand(JobRequestBase):
    """Command for animate-extend follow-up submission."""

    job_id: str | None = None
    video_bytes: bytes | None = None
    motion: AnimateMotion = AnimateMotion.LOW


@dataclass(frozen=True)
class JobBlendCommand(JobRequestBase):
    """Command for blend submissions."""

    base64_array: list[str] = field(default_factory=list)
    dimensions: str = "1:1"


@dataclass(frozen=True)
class JobCustomZoomCommand(JobRequestBase):
    """Command for custom zoom submissions."""

    job_id: Optional[str] = None
    index: Optional[int] = None
    base64: Optional[str] = None
    zoom_text: str = ""


@dataclass(frozen=True)
class JobInpaintCommand(JobRequestBase):
    """Command for inpaint submissions."""

    job_id: Optional[str] = None
    base64: Optional[str] = None
    mask: str = ""
    prompt: Optional[str] = None
    full_prompt: Optional[str] = None
    custom_id: Optional[str] = None


@dataclass(frozen=True)
class JobCancelCommand(JobRequestBase):
    """Command for cancel submissions."""

    job_id: str = ""


__all__ = [
    "JobRequestBase",
    "JobImagineCommand",
    "JobChangeCommand",
    "JobImageChangeCommand",
    "JobDescribeCommand",
    "JobAnimateCommand",
    "JobAnimateExtendCommand",
    "JobBlendCommand",
    "JobCustomZoomCommand",
    "JobInpaintCommand",
    "JobCancelCommand",
]
