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
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, PrivateAttr

from mutiny.domain.time import get_current_timestamp_ms


class JobAction(str, Enum):
    IMAGINE = "IMAGINE"
    UPSCALE = "UPSCALE"
    VARIATION = "VARIATION"
    REROLL = "REROLL"
    DESCRIBE = "DESCRIBE"
    BLEND = "BLEND"
    UPSCALE_V7_2X_SUBTLE = "UPSCALE_V7_2X_SUBTLE"
    UPSCALE_V7_2X_CREATIVE = "UPSCALE_V7_2X_CREATIVE"
    VARY_SUBTLE = "VARY_SUBTLE"
    VARY_STRONG = "VARY_STRONG"
    ZOOM_OUT_2X = "ZOOM_OUT_2X"
    ZOOM_OUT_1_5X = "ZOOM_OUT_1_5X"
    PAN_LEFT = "PAN_LEFT"
    PAN_RIGHT = "PAN_RIGHT"
    PAN_UP = "PAN_UP"
    PAN_DOWN = "PAN_DOWN"
    ANIMATE_HIGH = "ANIMATE_HIGH"
    ANIMATE_LOW = "ANIMATE_LOW"
    ANIMATE_EXTEND_HIGH = "ANIMATE_EXTEND_HIGH"
    ANIMATE_EXTEND_LOW = "ANIMATE_EXTEND_LOW"
    CUSTOM_ZOOM = "CUSTOM_ZOOM"
    INPAINT = "INPAINT"


class AnimateMotion(str, Enum):
    """Represent the supported public motion levels for Midjourney video generation."""

    LOW = "low"
    HIGH = "high"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    IN_PROGRESS = "IN_PROGRESS"
    FAILED = "FAILED"
    SUCCEEDED = "SUCCEEDED"


class TileFollowUpMode(str, Enum):
    """Describe how split grid tiles should behave for downstream follow-up actions."""

    MODERN = "modern"
    LEGACY = "legacy"


class JobContext(BaseModel):
    """Execution correlation details for Discord and Midjourney messages.

    Attributes:
        message_id: Primary Discord message id for the job's grid or upscale.
        message_hash: Midjourney message hash extracted from attachment URLs.
        progress_message_id: Discord message id that carries progress updates.
        interaction_id: Interaction id associated with the originating command.
        nonce: Client nonce assigned during submission for tracking.
        final_prompt: Prompt text after any Midjourney-side expansion.
        flags: Discord message flags forwarded to follow-up actions.
        cancel_message_id: Discord message id that carried a cancel action.
        cancel_job_id: Midjourney job id used during cancel flows.
        original_job_id: Prior job id when this job depends on a completed run.
        index: Grid index (1-based) used for follow-up actions.
        not_fast: Whether the job was submitted outside of fast mode.
        zoom_text: User-entered zoom text for custom zoom flows.
        custom_id: Discord custom_id for modal-driven flows.
        prompt_video_follow_up_requested: Whether prompt-video animate has already
            triggered the observed follow-up interaction on the public result message.
        tile_follow_up_mode: Whether split tiles from this job should use modern or
            legacy follow-up behavior when recognized later.
        implicit_tile_promotion_pending: Whether this in-flight follow-up is waiting
            for the intermediate `U#` promotion result before the real requested action
            can be dispatched.
        implicit_tile_promotion_index: Original tile index used for the hidden `U#`
            promotion hop when one is required.
        action_custom_ids: Persisted exact component ids harvested from the recognized
            message surface for follow-up actions that are not safe to synthesize.
        cancelled: Whether the job has been cancelled locally.
    """

    message_id: Optional[str] = None
    message_hash: Optional[str] = None
    progress_message_id: Optional[str] = None
    interaction_id: Optional[str] = None
    nonce: Optional[str] = None
    final_prompt: Optional[str] = None
    flags: Optional[int] = None
    cancel_message_id: Optional[str] = None
    cancel_job_id: Optional[str] = None
    original_job_id: Optional[str] = None
    index: Optional[int] = None
    not_fast: bool = False
    zoom_text: Optional[str] = None
    custom_id: Optional[str] = None
    prompt_video_follow_up_requested: bool = False
    tile_follow_up_mode: TileFollowUpMode = TileFollowUpMode.MODERN
    implicit_tile_promotion_pending: bool = False
    implicit_tile_promotion_index: Optional[int] = None
    action_custom_ids: dict[str, str] = Field(default_factory=dict)
    cancelled: bool = False


class JobInputs(BaseModel):
    """User-supplied payloads captured at submission time.

    Attributes:
        base64: Single image Data URL for describe, image-change, or animate start-frame flows.
        base64_array: Prompt-image Data URLs for imagine or multiple images for blend.
        style_reference_images: Attached style-reference image Data URLs.
        style_reference_multipliers: Optional style multipliers aligned with style refs.
        character_reference_images: Attached character-reference image Data URLs.
        omni_reference_image: One attached Omni Reference image Data URL.
        dimensions: Aspect ratio string used by blend.
        mask_webp_base64: WebP Data URL for inpaint masks.
        prompt: Optional prompt delta for inpaint or prompt text for animate video generation.
        full_prompt: Full prompt replacement for inpaint when provided.
        end_frame_base64: Optional ending-frame Data URL for animate video generation.
        batch_size: Optional Midjourney video batch size.
    """

    base64: Optional[str] = None
    base64_array: Optional[list[str]] = None
    style_reference_images: Optional[list[str]] = None
    style_reference_multipliers: Optional[list[float]] = None
    character_reference_images: Optional[list[str]] = None
    omni_reference_image: Optional[str] = None
    dimensions: Optional[str] = None
    mask_webp_base64: Optional[str] = None
    prompt: Optional[str] = None
    full_prompt: Optional[str] = None
    end_frame_base64: Optional[str] = None
    batch_size: Optional[int] = None


class JobArtifacts(BaseModel):
    """Store resolved output artifacts and external provenance for one job."""

    video_url: Optional[str] = None
    website_url: Optional[str] = None
    website_video_url: Optional[str] = None
    video_file_path: Optional[str] = None


class Job(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    completion_event: asyncio.Event = Field(default_factory=asyncio.Event, exclude=True)

    _context: JobContext = PrivateAttr(default_factory=JobContext)
    _inputs: JobInputs = PrivateAttr(default_factory=JobInputs)
    _artifacts: JobArtifacts = PrivateAttr(default_factory=JobArtifacts)

    id: str
    action: JobAction
    prompt: Optional[str] = None
    prompt_en: Optional[str] = None
    description: Optional[str] = None
    state: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    image_url: Optional[str] = None
    progress: Optional[str] = None
    fail_reason: Optional[str] = None
    submit_time: int = Field(default_factory=get_current_timestamp_ms)
    start_time: Optional[int] = None
    finish_time: Optional[int] = None

    @property
    def context(self) -> JobContext:
        return self._context

    @property
    def inputs(self) -> JobInputs:
        return self._inputs

    @property
    def artifacts(self) -> JobArtifacts:
        return self._artifacts
