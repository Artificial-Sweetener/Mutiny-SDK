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

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mutiny.types import Result


@dataclass(frozen=True)
class ErrorSpec:
    """Standard error mapping for job commands."""

    code: int
    http_status: int
    message: str


NO_AVAILABLE_ACCOUNTS = ErrorSpec(500, 503, "No available accounts")
QUEUE_FULL = ErrorSpec(500, 503, "Queue is full")
INVALID_ACTION = ErrorSpec(400, 400, "Invalid action")
INVALID_BASE64 = ErrorSpec(400, 400, "Invalid Base64 Data URL")
INDEX_REQUIRED = ErrorSpec(400, 400, "Index is required for this action")
ORIGINAL_NOT_FOUND = ErrorSpec(404, 404, "Original task not found")
ORIGINAL_NOT_FINISHED = ErrorSpec(400, 400, "Original task has not finished")
IMAGE_INDEX_UNAVAILABLE = ErrorSpec(500, 503, "Image index not available")
IMAGE_NOT_RECOGNIZED = ErrorSpec(404, 404, "Image not recognized; cannot map to a prior job")
VIDEO_INDEX_UNAVAILABLE = ErrorSpec(500, 503, "Video index not available")
VIDEO_NOT_RECOGNIZED = ErrorSpec(404, 404, "Video not recognized; cannot map to a prior job")
INVALID_BLEND_COUNT = ErrorSpec(400, 400, "Must provide 2-5 base64 images")
DUPLICATE_IMAGES = ErrorSpec(400, 400, "Duplicate images are not allowed")
INVALID_IMAGE_INPUTS = ErrorSpec(400, 400, "Invalid imagine image inputs")
INVALID_ZOOM_TEXT = ErrorSpec(400, 400, 'Invalid zoomText: Custom Zoom requires "--zoom <value>"')
INVALID_MASK = ErrorSpec(400, 400, "Invalid mask; must be a valid image Data URL")
INVALID_ANIMATE_BATCH_SIZE = ErrorSpec(
    400, 400, "Invalid batch size; Midjourney video supports only 1, 2, or 4"
)
MISSING_CONTEXT = ErrorSpec(400, 400, "Provide job_id or base64 image to map context")
MISSING_VIDEO_CONTEXT = ErrorSpec(400, 400, "Provide job_id or video bytes to map context")
CANCEL_NOT_FOUND = ErrorSpec(404, 404, "Task not found")
CANCEL_NOT_RUNNING = ErrorSpec(400, 409, "Task is not running")
CANCEL_FAILED = ErrorSpec(500, 503, "Failed to send cancel command")
TILE_INDEX_INVALID = ErrorSpec(400, 400, "Tile index must be 1..4")
TILE_JOB_NOT_FOUND = ErrorSpec(404, 404, "Job not found")
TILE_NOT_AVAILABLE = ErrorSpec(400, 400, "Tiles are only available for imagine results")
TILE_FETCH_FAILED = ErrorSpec(500, 503, "Failed to fetch tile image")
TILE_EXTRACT_FAILED = ErrorSpec(500, 500, "Failed to extract tile")
PROMPT_REJECTED = ErrorSpec(
    400,
    400,
    "Prompt was rejected by Midjourney moderation. Try revising the prompt.",
)


def error_result(
    spec: ErrorSpec,
    *,
    message: Optional[str] = None,
    validation_error: bool = False,
) -> Result[None]:
    """Create a Result from the error catalog."""

    return Result(
        code=spec.code,
        message=message or spec.message,
        http_status=spec.http_status,
        validation_error=validation_error,
    )


def format_moderation_rejection_reason(decline_code: Optional[str] = None) -> str:
    """Return a stable job failure reason for Midjourney moderation declines."""

    if decline_code:
        return f"{PROMPT_REJECTED.message} (Midjourney code: {decline_code})"
    return PROMPT_REJECTED.message


__all__ = [
    "ErrorSpec",
    "NO_AVAILABLE_ACCOUNTS",
    "QUEUE_FULL",
    "INVALID_ACTION",
    "INVALID_BASE64",
    "INDEX_REQUIRED",
    "ORIGINAL_NOT_FOUND",
    "ORIGINAL_NOT_FINISHED",
    "IMAGE_INDEX_UNAVAILABLE",
    "IMAGE_NOT_RECOGNIZED",
    "VIDEO_INDEX_UNAVAILABLE",
    "VIDEO_NOT_RECOGNIZED",
    "INVALID_BLEND_COUNT",
    "DUPLICATE_IMAGES",
    "INVALID_IMAGE_INPUTS",
    "INVALID_ZOOM_TEXT",
    "INVALID_MASK",
    "INVALID_ANIMATE_BATCH_SIZE",
    "MISSING_CONTEXT",
    "MISSING_VIDEO_CONTEXT",
    "CANCEL_NOT_FOUND",
    "CANCEL_NOT_RUNNING",
    "CANCEL_FAILED",
    "TILE_INDEX_INVALID",
    "TILE_JOB_NOT_FOUND",
    "TILE_NOT_AVAILABLE",
    "TILE_FETCH_FAILED",
    "TILE_EXTRACT_FAILED",
    "PROMPT_REJECTED",
    "format_moderation_rejection_reason",
    "error_result",
]
