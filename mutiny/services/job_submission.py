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

"""Validation and submission flows for Mutiny job requests."""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Callable, Final, Optional, TypeVar, cast

from mutiny.domain.state_machine import JobStateMachine, JobTransition
from mutiny.domain.time import get_current_timestamp_ms
from mutiny.engine.discord_engine import DiscordEngine
from mutiny.services.animate_prompt_builder import normalize_animate_prompt_text
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.cancel_safety import can_cancel as _can_cancel
from mutiny.services.context import AppContext
from mutiny.services.error_catalog import (
    CANCEL_FAILED,
    CANCEL_NOT_FOUND,
    CANCEL_NOT_RUNNING,
    DUPLICATE_IMAGES,
    IMAGE_INDEX_UNAVAILABLE,
    IMAGE_NOT_RECOGNIZED,
    INDEX_REQUIRED,
    INVALID_ACTION,
    INVALID_ANIMATE_BATCH_SIZE,
    INVALID_BASE64,
    INVALID_BLEND_COUNT,
    INVALID_IMAGE_INPUTS,
    INVALID_MASK,
    INVALID_ZOOM_TEXT,
    MISSING_CONTEXT,
    MISSING_VIDEO_CONTEXT,
    NO_AVAILABLE_ACCOUNTS,
    ORIGINAL_NOT_FINISHED,
    ORIGINAL_NOT_FOUND,
    QUEUE_FULL,
    VIDEO_INDEX_UNAVAILABLE,
    VIDEO_NOT_RECOGNIZED,
    ErrorSpec,
    error_result,
)
from mutiny.services.image_utils import parse_data_url
from mutiny.services.job_requests import (
    JobAnimateCommand,
    JobAnimateExtendCommand,
    JobBlendCommand,
    JobCancelCommand,
    JobChangeCommand,
    JobCustomZoomCommand,
    JobDescribeCommand,
    JobImageChangeCommand,
    JobImagineCommand,
    JobInpaintCommand,
)
from mutiny.services.job_store import JobQuery
from mutiny.services.logging_utils import clear_job_context, set_job_context
from mutiny.services.tile_follow_up import (
    is_direct_tile_action,
    is_tile_capable_action,
    requires_tile_promotion,
    resolve_tile_follow_up_mode,
)
from mutiny.services.video_signature import VideoSignatureError
from mutiny.services.webp_encoder import encode_mask_to_webp_base64
from mutiny.types import (
    AnimateMotion,
    ImagineImageInputs,
    Job,
    JobAction,
    JobStatus,
    RecognizedImageContext,
    RecognizedVideoContext,
    Result,
    TileFollowUpMode,
)

# Consolidated JobAction scopes for validation; keep these as the single source of truth.
TResultValue = TypeVar("TResultValue")


IMAGE_CHANGE_ACTIONS: Final[frozenset[JobAction]] = frozenset(
    {
        JobAction.UPSCALE,
        JobAction.VARIATION,
        JobAction.VARY_SUBTLE,
        JobAction.VARY_STRONG,
        JobAction.UPSCALE_V7_2X_SUBTLE,
        JobAction.UPSCALE_V7_2X_CREATIVE,
        JobAction.ZOOM_OUT_2X,
        JobAction.ZOOM_OUT_1_5X,
        JobAction.PAN_LEFT,
        JobAction.PAN_RIGHT,
        JobAction.PAN_UP,
        JobAction.PAN_DOWN,
        JobAction.ANIMATE_HIGH,
        JobAction.ANIMATE_LOW,
    }
)

CHANGE_ACTIONS: Final[frozenset[JobAction]] = IMAGE_CHANGE_ACTIONS | {JobAction.REROLL}

INDEX_REQUIRED_ACTIONS: Final[frozenset[JobAction]] = CHANGE_ACTIONS - {JobAction.REROLL}

TILE_VARIATION_ACTIONS: Final[frozenset[JobAction]] = frozenset(
    {JobAction.VARIATION, JobAction.VARY_SUBTLE, JobAction.VARY_STRONG}
)

GRID_TILE_ONLY_ACTIONS: Final[frozenset[JobAction]] = frozenset(
    {
        JobAction.UPSCALE,
        JobAction.VARIATION,
        JobAction.VARY_STRONG,
    }
)

SOLO_SURFACE_ACTIONS: Final[frozenset[JobAction]] = frozenset(
    {
        JobAction.VARY_SUBTLE,
        JobAction.UPSCALE_V7_2X_SUBTLE,
        JobAction.UPSCALE_V7_2X_CREATIVE,
        JobAction.ZOOM_OUT_2X,
        JobAction.ZOOM_OUT_1_5X,
        JobAction.PAN_LEFT,
        JobAction.PAN_RIGHT,
        JobAction.PAN_UP,
        JobAction.PAN_DOWN,
        JobAction.ANIMATE_HIGH,
        JobAction.ANIMATE_LOW,
        JobAction.CUSTOM_ZOOM,
        JobAction.INPAINT,
    }
)

_LEADING_COMMAND_URLS_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:(?:<)?https?://[^\s>]+(?:>)?\s+)+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _ImageRef:
    message_id: str
    message_hash: str
    flags: int
    index: Optional[int]
    kind: str | None


@dataclass(frozen=True)
class _ResolvedImageContext:
    message_id: str
    message_hash: str
    flags: int
    index: Optional[int]
    kind: str | None
    tile_follow_up_mode: TileFollowUpMode
    prompt_text: str | None
    action_custom_ids: dict[str, str]
    source_job_id: str | None = None
    implicit_tile_promotion_required: bool = False


@dataclass(frozen=True)
class _ResolvedVideoContext:
    message_id: str
    message_hash: str
    flags: int
    index: int
    prompt: str | None
    action_custom_ids: dict[str, str]


class JobSubmissionService:
    """Consolidated job submission and validation entrypoint."""

    def __init__(self, ctx: AppContext) -> None:
        self._ctx = ctx
        self._logger = logging.getLogger(__name__)

    def _require_image_processor(self):
        return self._ctx.image_processor

    def _validation_error(
        self, spec: ErrorSpec, *, message: str | None = None
    ) -> Result[TResultValue]:
        return error_result(spec, message=message, validation_error=True)

    def _validate_data_url_list(
        self,
        values: tuple[str, ...],
        *,
        label: str,
    ) -> Result[None] | None:
        """Validate one or more data URLs for a structured imagine image channel."""
        if not values:
            return self._validation_error(
                INVALID_IMAGE_INPUTS,
                message=f"{label} must contain at least one image.",
            )
        for index, value in enumerate(values):
            if not parse_data_url(value):
                return self._validation_error(
                    INVALID_BASE64,
                    message=f"Invalid Base64 Data URL in {label} at index {index}",
                )
        return None

    def _validate_imagine_image_inputs(
        self,
        image_inputs: ImagineImageInputs | None,
    ) -> Result[None] | None:
        """Validate structured attached-image channels for imagine submissions."""
        if image_inputs is None:
            return None

        if image_inputs.prompt_images:
            error = self._validate_data_url_list(
                image_inputs.prompt_images,
                label="prompt_images",
            )
            if error is not None:
                return error

        if image_inputs.style_reference is not None:
            error = self._validate_data_url_list(
                image_inputs.style_reference.images,
                label="style_reference.images",
            )
            if error is not None:
                return error
            multipliers = image_inputs.style_reference.multipliers
            if multipliers and len(multipliers) != len(image_inputs.style_reference.images):
                return self._validation_error(
                    INVALID_IMAGE_INPUTS,
                    message=("style_reference.multipliers must align with style_reference.images."),
                )

        if image_inputs.character_reference is not None:
            error = self._validate_data_url_list(
                image_inputs.character_reference.images,
                label="character_reference.images",
            )
            if error is not None:
                return error

        if image_inputs.omni_reference is not None:
            if not parse_data_url(image_inputs.omni_reference.image):
                return self._validation_error(
                    INVALID_BASE64,
                    message="Invalid Base64 Data URL in omni_reference.image",
                )

        return None

    def _require_engine(self) -> DiscordEngine | None:
        return self._ctx.engine

    @staticmethod
    def _normalize_extend_prompt(source_prompt: str | None) -> str | None:
        """Return the extend prompt form echoed by Midjourney progress messages.

        Midjourney extend progress omits the original prompt-image URL prefix even
        when the source animate job stored a final prompt that still includes it.
        Strip those leading command URLs so the existing prompt-matching fallback
        can correlate hidden extend progress before any new hash exists.
        """
        normalized = normalize_animate_prompt_text(source_prompt)
        if not normalized:
            return None
        stripped = _LEADING_COMMAND_URLS_RE.sub("", normalized).strip()
        return stripped or None

    @staticmethod
    def _tile_follow_up_mode_for_prompt(prompt_text: str | None) -> TileFollowUpMode:
        """Return the stored tile follow-up mode for one originating prompt."""

        return resolve_tile_follow_up_mode(prompt_text)

    def _tile_follow_up_mode_for_job(self, job: Job | None) -> TileFollowUpMode:
        """Return the recorded or inferred tile-follow-up mode for one source job."""

        if job is None:
            return TileFollowUpMode.MODERN
        return job.context.tile_follow_up_mode or self._tile_follow_up_mode_for_prompt(
            job.context.final_prompt or job.prompt
        )

    def _unsupported_legacy_tile_action(self, *, action: JobAction) -> Result[None]:
        """Return one validation error for tile actions that need promotion on old models."""

        return self._validation_error(
            INVALID_ACTION,
            message=(
                f"{action.value} requires a promoted single-image result on older "
                "Midjourney models."
            ),
        )

    def find_job_by_video(self, video_bytes: bytes) -> Job | None:
        """Return one recognized animate-family job, hydrating from cache if needed."""
        try:
            context = self.find_video_context(video_bytes)
        except VideoSignatureError:
            return None
        if context is None:
            return None
        return self._hydrate_recognized_video_job(context)

    def find_image_context(self, image_bytes: bytes) -> RecognizedImageContext | None:
        """Return one recognized image context from the unified artifact cache."""

        artifact_cache = self._ctx.artifact_cache
        proc = self._require_image_processor()
        digest = proc.compute_digest(image_bytes)
        phash = proc.compute_phash(image_bytes)
        width, height = proc.get_dimensions(image_bytes)

        upscale_context = artifact_cache.find_image_context_by_signature(
            digest=digest,
            phash=phash,
            expected_kind="upscale",
            width=width,
            height=height,
        )
        if upscale_context is not None:
            return upscale_context
        return artifact_cache.find_image_context_by_signature(
            digest=digest,
            phash=phash,
            expected_kind="tile",
            width=width,
            height=height,
        )

    def find_video_context(self, video_bytes: bytes) -> RecognizedVideoContext | None:
        """Return one recognized video context from the unified artifact cache."""

        digest = self._ctx.video_signature_service.compute_signature(video_bytes).digest
        return self._ctx.artifact_cache.find_video_context_by_digest(digest)

    def _resolve_image_ref(
        self,
        *,
        artifact_cache: ArtifactCacheService,
        image_bytes: bytes,
        expected_kind: str,
    ) -> Optional[_ImageRef]:
        """Resolve image references using processor-produced signatures."""

        proc = self._require_image_processor()
        digest = proc.compute_digest(image_bytes)
        phash = proc.compute_phash(image_bytes)
        width, height = proc.get_dimensions(image_bytes)
        ref = artifact_cache.find_image_by_signature(
            digest=digest,
            phash=phash,
            expected_kind=expected_kind,
            width=width,
            height=height,
        )
        if not ref:
            return None
        return _ImageRef(
            message_id=ref.message_id,
            message_hash=ref.message_hash,
            flags=int(ref.flags or 0),
            index=getattr(ref, "index", None),
            kind=getattr(ref, "kind", None),
        )

    def _normalize_index(self, *, value: int | None, fallback: int | None) -> int | None:
        if fallback is None:
            return value
        normalized = int(value or fallback)
        if not normalized:
            normalized = fallback
        return normalized

    def _find_source_job_by_message_id(self, message_id: str | None) -> Job | None:
        """Return one stored source job for the supplied message id when present."""

        if not message_id:
            return None
        finder = getattr(self._ctx.job_store, "find_one", None)
        if finder is None:
            return None
        return finder(JobQuery(message_id=message_id))

    def _hydrate_recognized_image_job(self, context: RecognizedImageContext) -> Job:
        """Return one recognized-image job, creating a synthetic succeeded job if needed."""

        existing = self._find_source_job_by_message_id(context.message_id)
        if existing is not None:
            return existing

        synthetic = Job(
            id=f"cached-image:{context.message_id}:{context.index}",
            action=JobAction.UPSCALE if context.kind == "upscale" else JobAction.IMAGINE,
            prompt=context.prompt_text,
        )
        synthetic.status = JobStatus.SUCCEEDED
        synthetic.context.message_id = context.message_id
        synthetic.context.message_hash = context.message_hash
        synthetic.context.flags = context.flags
        synthetic.context.index = context.index
        synthetic.context.final_prompt = context.prompt_text
        synthetic.context.tile_follow_up_mode = context.tile_follow_up_mode
        synthetic.context.action_custom_ids = dict(context.action_custom_ids)
        self._ctx.job_store.save(synthetic)
        return synthetic

    def _hydrate_recognized_video_job(self, context: RecognizedVideoContext) -> Job:
        """Return one recognized-video job, creating a synthetic succeeded job if needed."""

        existing = self._find_source_job_by_message_id(context.message_id)
        if existing is not None:
            return existing

        synthetic = Job(
            id=f"cached-video:{context.message_id}",
            action=JobAction.ANIMATE_LOW,
            prompt=context.prompt_text,
        )
        synthetic.status = JobStatus.SUCCEEDED
        synthetic.context.message_id = context.message_id
        synthetic.context.message_hash = context.message_hash
        synthetic.context.flags = context.flags
        synthetic.context.index = context.index
        synthetic.context.final_prompt = context.prompt_text
        synthetic.context.action_custom_ids = dict(context.action_custom_ids)
        self._ctx.job_store.save(synthetic)
        return synthetic

    def _resolve_direct_image_context(
        self,
        *,
        message_id: str,
        message_hash: str,
        flags: int,
        index: int | None,
        kind: str | None,
        tile_follow_up_mode: TileFollowUpMode,
        prompt_text: str | None,
        action_custom_ids: dict[str, str] | None = None,
        source_job_id: str | None = None,
        implicit_tile_promotion_required: bool = False,
    ) -> _ResolvedImageContext:
        """Build one normalized resolved-image context used by downstream submission flows."""

        return _ResolvedImageContext(
            message_id=message_id,
            message_hash=message_hash,
            flags=flags,
            index=index,
            kind=kind,
            tile_follow_up_mode=tile_follow_up_mode,
            prompt_text=prompt_text,
            action_custom_ids=dict(action_custom_ids or {}),
            source_job_id=source_job_id,
            implicit_tile_promotion_required=implicit_tile_promotion_required,
        )

    def _try_resolve_upscaled_image(
        self,
        *,
        base64_data_url: str,
        index_fallback: int,
    ) -> _ResolvedImageContext | None:
        """Best-effort resolve one image as a recognized upscaled Midjourney result."""
        resolved, err = self._resolve_image_context_for_action(
            job_id=None,
            base64=base64_data_url,
            action=JobAction.ANIMATE_LOW,
            index_fallback=index_fallback,
        )
        if err is not None:
            return None
        return resolved

    def _resolve_image_context_for_action(
        self,
        *,
        job_id: str | None,
        base64: str | None,
        action: JobAction,
        index_fallback: int | None,
    ) -> tuple[_ResolvedImageContext | None, Result[None] | None]:
        """Resolve one image for the requested action, allowing promotion when needed."""

        job_store = self._ctx.job_store

        if job_id:
            original_job = job_store.get(job_id)
            if not original_job:
                return None, error_result(ORIGINAL_NOT_FOUND)
            if original_job.status != JobStatus.SUCCEEDED:
                return None, error_result(ORIGINAL_NOT_FINISHED)

            index = self._normalize_index(
                value=index_fallback,
                fallback=original_job.context.index,
            )
            mode = self._tile_follow_up_mode_for_job(original_job)
            if action not in GRID_TILE_ONLY_ACTIONS and action not in SOLO_SURFACE_ACTIONS:
                return (
                    self._resolve_direct_image_context(
                        message_id=original_job.context.message_id or "",
                        message_hash=original_job.context.message_hash or "",
                        flags=int(original_job.context.flags or 0),
                        index=index,
                        kind="upscale" if index == 0 else "tile",
                        tile_follow_up_mode=mode,
                        prompt_text=original_job.context.final_prompt or original_job.prompt,
                        action_custom_ids=dict(original_job.context.action_custom_ids),
                        source_job_id=original_job.id,
                    ),
                    None,
                )
            if index in {1, 2, 3, 4} and is_tile_capable_action(action):
                if is_direct_tile_action(action, mode=mode):
                    return (
                        self._resolve_direct_image_context(
                            message_id=original_job.context.message_id or "",
                            message_hash=original_job.context.message_hash or "",
                            flags=int(original_job.context.flags or 0),
                            index=index,
                            kind="tile",
                            tile_follow_up_mode=mode,
                            prompt_text=original_job.context.final_prompt or original_job.prompt,
                            action_custom_ids=dict(original_job.context.action_custom_ids),
                            source_job_id=original_job.id,
                        ),
                        None,
                    )
                if requires_tile_promotion(action, mode=mode):
                    return (
                        self._resolve_direct_image_context(
                            message_id=original_job.context.message_id or "",
                            message_hash=original_job.context.message_hash or "",
                            flags=int(original_job.context.flags or 0),
                            index=index,
                            kind="tile",
                            tile_follow_up_mode=mode,
                            prompt_text=original_job.context.final_prompt or original_job.prompt,
                            action_custom_ids=dict(original_job.context.action_custom_ids),
                            source_job_id=original_job.id,
                            implicit_tile_promotion_required=True,
                        ),
                        None,
                    )
                return None, self._unsupported_legacy_tile_action(action=action)

            return (
                self._resolve_direct_image_context(
                    message_id=original_job.context.message_id or "",
                    message_hash=original_job.context.message_hash or "",
                    flags=int(original_job.context.flags or 0),
                    index=index,
                    kind="upscale",
                    tile_follow_up_mode=mode,
                    prompt_text=original_job.context.final_prompt or original_job.prompt,
                    action_custom_ids=dict(original_job.context.action_custom_ids),
                    source_job_id=original_job.id,
                ),
                None,
            )

        if not base64:
            return None, self._validation_error(MISSING_CONTEXT)

        data_url = parse_data_url(base64)
        if not data_url:
            return None, self._validation_error(INVALID_BASE64)

        artifact_cache = self._ctx.artifact_cache
        if not artifact_cache:
            return None, error_result(IMAGE_INDEX_UNAVAILABLE)

        processor = self._require_image_processor()
        digest = processor.compute_digest(data_url.data)
        phash = processor.compute_phash(data_url.data)
        width, height = processor.get_dimensions(data_url.data)

        if action in GRID_TILE_ONLY_ACTIONS:
            tile_context = artifact_cache.find_image_context_by_signature(
                digest=digest,
                phash=phash,
                expected_kind="tile",
                width=width,
                height=height,
            )
            if not tile_context:
                return None, error_result(IMAGE_NOT_RECOGNIZED)
            return (
                self._resolve_direct_image_context(
                    message_id=tile_context.message_id,
                    message_hash=tile_context.message_hash,
                    flags=tile_context.flags,
                    index=self._normalize_index(
                        value=tile_context.index,
                        fallback=index_fallback,
                    ),
                    kind=tile_context.kind,
                    tile_follow_up_mode=tile_context.tile_follow_up_mode,
                    prompt_text=tile_context.prompt_text,
                    action_custom_ids=tile_context.action_custom_ids,
                ),
                None,
            )

        if action in SOLO_SURFACE_ACTIONS:
            upscale_context = artifact_cache.find_image_context_by_signature(
                digest=digest,
                phash=phash,
                expected_kind="upscale",
                width=width,
                height=height,
            )
            if upscale_context:
                return (
                    self._resolve_direct_image_context(
                        message_id=upscale_context.message_id,
                        message_hash=upscale_context.message_hash,
                        flags=upscale_context.flags,
                        index=self._normalize_index(
                            value=upscale_context.index,
                            fallback=index_fallback,
                        ),
                        kind=upscale_context.kind,
                        tile_follow_up_mode=upscale_context.tile_follow_up_mode,
                        prompt_text=upscale_context.prompt_text,
                        action_custom_ids=upscale_context.action_custom_ids,
                    ),
                    None,
                )

            tile_context = artifact_cache.find_image_context_by_signature(
                digest=digest,
                phash=phash,
                expected_kind="tile",
                width=width,
                height=height,
            )
            if not tile_context:
                return None, error_result(IMAGE_NOT_RECOGNIZED)
            if not requires_tile_promotion(action, mode=tile_context.tile_follow_up_mode):
                return None, self._unsupported_legacy_tile_action(action=action)
            return (
                self._resolve_direct_image_context(
                    message_id=tile_context.message_id,
                    message_hash=tile_context.message_hash,
                    flags=tile_context.flags,
                    index=self._normalize_index(
                        value=tile_context.index,
                        fallback=index_fallback,
                    ),
                    kind=tile_context.kind,
                    tile_follow_up_mode=tile_context.tile_follow_up_mode,
                    prompt_text=tile_context.prompt_text,
                    action_custom_ids=tile_context.action_custom_ids,
                    implicit_tile_promotion_required=True,
                ),
                None,
            )
        return None, error_result(IMAGE_NOT_RECOGNIZED)

    def _resolve_video_ref(self, *, video_bytes: bytes) -> Optional[_ResolvedVideoContext]:
        """Resolve one video to stored final-message context using the shared job index."""
        context = self.find_video_context(video_bytes)
        if not context:
            return None
        return _ResolvedVideoContext(
            message_id=context.message_id,
            message_hash=context.message_hash,
            flags=int(context.flags or 0),
            index=int(context.index or 1),
            prompt=self._normalize_extend_prompt(context.prompt_text),
            action_custom_ids=dict(context.action_custom_ids),
        )

    def _resolve_target_video(
        self,
        *,
        job_id: str | None,
        video_bytes: bytes | None,
    ) -> tuple[_ResolvedVideoContext | None, Result[None] | None]:
        """Resolve extend context from either one succeeded job or recognized video bytes."""
        job_store = self._ctx.job_store

        if job_id:
            original_job = job_store.get(job_id)
            if not original_job:
                return None, error_result(ORIGINAL_NOT_FOUND)
            if original_job.status != JobStatus.SUCCEEDED:
                return None, error_result(ORIGINAL_NOT_FINISHED)
            if original_job.action not in {
                JobAction.ANIMATE_HIGH,
                JobAction.ANIMATE_LOW,
                JobAction.ANIMATE_EXTEND_HIGH,
                JobAction.ANIMATE_EXTEND_LOW,
            }:
                return None, error_result(INVALID_ACTION)
            if not original_job.context.message_id or not original_job.context.message_hash:
                return None, self._validation_error(MISSING_VIDEO_CONTEXT)

            return (
                _ResolvedVideoContext(
                    message_id=original_job.context.message_id,
                    message_hash=original_job.context.message_hash,
                    flags=int(original_job.context.flags or 0),
                    index=int(original_job.context.index or 1),
                    prompt=self._normalize_extend_prompt(
                        original_job.context.final_prompt or original_job.prompt
                    ),
                    action_custom_ids=dict(original_job.context.action_custom_ids),
                ),
                None,
            )

        if video_bytes is not None:
            artifact_cache = self._ctx.artifact_cache
            if not artifact_cache:
                return None, error_result(VIDEO_INDEX_UNAVAILABLE)
            try:
                ref = self._resolve_video_ref(video_bytes=video_bytes)
            except VideoSignatureError as exc:
                return None, error_result(VIDEO_NOT_RECOGNIZED, message=str(exc))

            if not ref:
                return None, error_result(VIDEO_NOT_RECOGNIZED)
            prompt_text = ref.prompt
            if prompt_text is None:
                job = job_store.find_one(JobQuery(message_id=ref.message_id))
                if job is not None:
                    prompt_text = self._normalize_extend_prompt(
                        job.context.final_prompt or job.prompt
                    )
            return (
                _ResolvedVideoContext(
                    message_id=ref.message_id,
                    message_hash=ref.message_hash,
                    flags=ref.flags,
                    index=ref.index,
                    prompt=prompt_text,
                    action_custom_ids=dict(ref.action_custom_ids),
                ),
                None,
            )

        return None, self._validation_error(MISSING_VIDEO_CONTEXT)

    async def _execute_job_flow(
        self,
        *,
        action: JobAction,
        state,
        prompt: str | None,
        pre_validation: Callable[[], Result[None] | None] | None = None,
        post_engine_validation: Callable[[], Result[None] | None] | None = None,
        populate_context: Callable[[Job], None] | None = None,
        populate_inputs: Callable[[Job], None] | None = None,
        instance: DiscordEngine | None = None,
        queue_full_detail_factory: Callable[[DiscordEngine], str | None] | None = None,
    ) -> Result[str]:
        if pre_validation:
            err = pre_validation()
            if err:
                return cast(Result[str], err)

        engine_instance = instance or self._require_engine()
        if not engine_instance:
            return cast(Result[str], error_result(NO_AVAILABLE_ACCOUNTS))

        if post_engine_validation:
            err = post_engine_validation()
            if err:
                return cast(Result[str], err)

        job = Job(id=str(uuid.uuid4()), action=action, prompt=prompt, state=state)

        if populate_context:
            populate_context(job)
        if populate_inputs:
            populate_inputs(job)

        queue_full_detail = None
        if queue_full_detail_factory:
            queue_full_detail = queue_full_detail_factory(engine_instance)

        set_job_context(job_id=job.id, action=job.action.value, status=job.status.value)
        try:
            self._logger.info("[%s] enqueue -> job_id=%s", job.action.value, job.id)
            res = await self._submit_lifecycle(
                job=job,
                instance=engine_instance,
                queue_full_detail=queue_full_detail,
            )
            self._logger.info(
                "[%s] enqueue result -> job_id=%s success=%s",
                job.action.value,
                job.id,
                res.code == 1,
            )
            return res
        finally:
            clear_job_context()

    async def _submit_lifecycle(
        self,
        *,
        job: Job,
        instance: DiscordEngine,
        queue_full_detail: str | None = None,
    ) -> Result[str]:
        JobStateMachine.apply(job, JobTransition.SUBMIT)
        self._ctx.job_store.save(job)

        success = await instance.submit_job(job)
        if not success:
            JobStateMachine.apply(job, JobTransition.FAIL, "Queue is full")
            self._ctx.job_store.save(job)
            detail = queue_full_detail or "Queue is full"
            return error_result(QUEUE_FULL, message=detail)

        return Result(code=1, message="Task submitted successfully", value=job.id)

    async def submit_imagine(self, cmd: JobImagineCommand) -> Result[str]:
        """Submit an imagine job to the engine."""

        def _validate() -> Result[None] | None:
            if cmd.base64_array:
                for i, b64 in enumerate(cmd.base64_array):
                    if not parse_data_url(b64):
                        return self._validation_error(
                            INVALID_BASE64, message=f"Invalid Base64 Data URL at index {i}"
                        )
            structured_error = self._validate_imagine_image_inputs(cmd.image_inputs)
            if structured_error is not None:
                return structured_error
            return None

        def _populate_inputs(job: Job) -> None:
            prompt_images = list(cmd.image_inputs.prompt_images) if cmd.image_inputs else None
            if prompt_images is None:
                prompt_images = cmd.base64_array
            job.inputs.base64_array = prompt_images
            if cmd.image_inputs and cmd.image_inputs.style_reference is not None:
                job.inputs.style_reference_images = list(cmd.image_inputs.style_reference.images)
                if cmd.image_inputs.style_reference.multipliers:
                    job.inputs.style_reference_multipliers = list(
                        cmd.image_inputs.style_reference.multipliers
                    )
            if cmd.image_inputs and cmd.image_inputs.character_reference is not None:
                job.inputs.character_reference_images = list(
                    cmd.image_inputs.character_reference.images
                )
            if cmd.image_inputs and cmd.image_inputs.omni_reference is not None:
                job.inputs.omni_reference_image = cmd.image_inputs.omni_reference.image

        def _populate_context(job: Job) -> None:
            job.context.tile_follow_up_mode = self._tile_follow_up_mode_for_prompt(cmd.prompt)

        return await self._execute_job_flow(
            action=JobAction.IMAGINE,
            state=cmd.state,
            prompt=cmd.prompt,
            pre_validation=_validate,
            populate_context=_populate_context,
            populate_inputs=_populate_inputs,
            queue_full_detail_factory=lambda inst: (
                f"Queue is full ({inst.queue.qsize()}/{inst.queue.maxsize})"
                if getattr(inst, "queue", None) is not None
                else "Queue is full"
            ),
        )

    async def submit_image_change(self, cmd: JobImageChangeCommand) -> Result[str]:
        """Submit an image-based change action."""
        resolved: _ResolvedImageContext | None = None

        def _pre_validate() -> Result[None] | None:
            nonlocal resolved
            if cmd.action not in IMAGE_CHANGE_ACTIONS:
                return error_result(INVALID_ACTION)
            ref, err = self._resolve_image_context_for_action(
                job_id=None,
                base64=cmd.base64,
                action=cmd.action,
                index_fallback=None,
            )
            if err:
                return err
            if not ref:
                return self._validation_error(MISSING_CONTEXT)
            resolved = ref
            return None

        def _post_engine_validate() -> Result[None] | None:
            return None

        def _populate_context(job: Job) -> None:
            assert resolved is not None  # for type checkers
            job.context.message_id = resolved.message_id
            job.context.message_hash = resolved.message_hash
            job.context.flags = resolved.flags
            job.context.index = resolved.index
            job.context.final_prompt = resolved.prompt_text
            job.context.tile_follow_up_mode = resolved.tile_follow_up_mode
            job.context.action_custom_ids = dict(resolved.action_custom_ids)
            job.context.implicit_tile_promotion_pending = resolved.implicit_tile_promotion_required
            job.context.implicit_tile_promotion_index = (
                resolved.index if resolved.implicit_tile_promotion_required else None
            )
            if resolved.source_job_id:
                job.context.original_job_id = resolved.source_job_id

        return await self._execute_job_flow(
            action=cmd.action,
            state=cmd.state,
            prompt=None,
            pre_validation=_pre_validate,
            post_engine_validation=_post_engine_validate,
            populate_context=_populate_context,
        )

    async def submit_change(self, cmd: JobChangeCommand) -> Result[str]:
        """Submit a change action for an existing job."""
        original_job: Job | None = None
        resolved: _ResolvedImageContext | None = None

        def _pre_validate() -> Result[None] | None:
            nonlocal original_job, resolved
            if cmd.action not in CHANGE_ACTIONS:
                return error_result(INVALID_ACTION)
            if cmd.action in INDEX_REQUIRED_ACTIONS and (cmd.index is None):
                return error_result(INDEX_REQUIRED)

            job_store = self._ctx.job_store
            original = job_store.get(cmd.job_id)
            if not original:
                return error_result(ORIGINAL_NOT_FOUND)
            if original.status != JobStatus.SUCCEEDED:
                return error_result(ORIGINAL_NOT_FINISHED)
            original_job = original
            resolved_ctx, err = self._resolve_image_context_for_action(
                job_id=cmd.job_id,
                base64=None,
                action=cmd.action,
                index_fallback=cmd.index,
            )
            if err:
                return err
            if not resolved_ctx:
                return self._validation_error(MISSING_CONTEXT)
            resolved = resolved_ctx
            return None

        def _post_engine_validate() -> Result[None] | None:
            # Job-id change actions already target recognized Midjourney context.
            # No local image backend is required unless a separate image payload is
            # part of the request, which this DTO does not carry.
            return None

        def _populate_context(job: Job) -> None:
            assert original_job is not None and resolved is not None  # for type checkers
            job.context.original_job_id = original_job.id
            job.context.message_id = resolved.message_id
            job.context.message_hash = resolved.message_hash
            job.context.flags = resolved.flags
            job.context.index = resolved.index
            job.context.final_prompt = resolved.prompt_text
            job.context.tile_follow_up_mode = resolved.tile_follow_up_mode
            job.context.action_custom_ids = dict(resolved.action_custom_ids)
            job.context.implicit_tile_promotion_pending = resolved.implicit_tile_promotion_required
            job.context.implicit_tile_promotion_index = (
                resolved.index if resolved.implicit_tile_promotion_required else None
            )

        return await self._execute_job_flow(
            action=cmd.action,
            state=cmd.state,
            prompt=original_job.prompt if original_job else None,
            pre_validation=_pre_validate,
            post_engine_validation=_post_engine_validate,
            populate_context=_populate_context,
        )

    async def submit_describe(self, cmd: JobDescribeCommand) -> Result[str]:
        """Submit a describe job."""

        def _populate_inputs(job: Job) -> None:
            job.inputs.base64 = cmd.base64

        return await self._execute_job_flow(
            action=JobAction.DESCRIBE,
            state=cmd.state,
            prompt=None,
            populate_inputs=_populate_inputs,
        )

    async def submit_animate(self, cmd: JobAnimateCommand) -> Result[str]:
        """Submit one unified animate request.

        The service prefers the existing follow-up animate route when the start frame
        is a recognized upscaled Midjourney image and no prompt-video-only controls
        were requested. Otherwise it falls back to prompt-based ``--video`` generation.
        """
        resolved: _ResolvedImageContext | None = None
        normalized_prompt = ""
        use_follow_up_route = False

        def _pre_validate() -> Result[None] | None:
            nonlocal normalized_prompt, resolved, use_follow_up_route
            if not parse_data_url(cmd.start_frame_data_url):
                return self._validation_error(
                    INVALID_BASE64, message="Invalid Base64 Data URL in start_frame_data_url"
                )
            if cmd.end_frame_data_url and not parse_data_url(cmd.end_frame_data_url):
                return self._validation_error(
                    INVALID_BASE64, message="Invalid Base64 Data URL in end_frame_data_url"
                )
            if cmd.batch_size is not None and cmd.batch_size not in {1, 2, 4}:
                return self._validation_error(INVALID_ANIMATE_BATCH_SIZE)
            normalized_prompt = normalize_animate_prompt_text(cmd.prompt)
            use_follow_up_route = (
                cmd.end_frame_data_url is None and not normalized_prompt and cmd.batch_size is None
            )
            if not use_follow_up_route:
                return None
            resolved = self._try_resolve_upscaled_image(
                base64_data_url=cmd.start_frame_data_url,
                index_fallback=1,
            )
            use_follow_up_route = resolved is not None
            return None

        def _post_engine_validate() -> Result[None] | None:
            return None

        def _populate_context(job: Job) -> None:
            if not use_follow_up_route:
                return
            assert resolved is not None
            job.context.message_id = resolved.message_id
            job.context.message_hash = resolved.message_hash
            job.context.flags = resolved.flags
            job.context.index = resolved.index
            job.context.final_prompt = resolved.prompt_text
            job.context.tile_follow_up_mode = resolved.tile_follow_up_mode
            job.context.action_custom_ids = dict(resolved.action_custom_ids)
            job.context.implicit_tile_promotion_pending = resolved.implicit_tile_promotion_required
            job.context.implicit_tile_promotion_index = (
                resolved.index if resolved.implicit_tile_promotion_required else None
            )
            if resolved.source_job_id:
                job.context.original_job_id = resolved.source_job_id

        def _populate_inputs(job: Job) -> None:
            if use_follow_up_route:
                return
            job.inputs.base64 = cmd.start_frame_data_url
            job.inputs.end_frame_base64 = cmd.end_frame_data_url
            job.inputs.prompt = normalized_prompt or None
            job.inputs.batch_size = cmd.batch_size
            job.context.tile_follow_up_mode = self._tile_follow_up_mode_for_prompt(
                normalized_prompt or None
            )

        return await self._execute_job_flow(
            action=self._animate_action_for_motion(cmd.motion),
            state=cmd.state,
            prompt=normalized_prompt or None,
            pre_validation=_pre_validate,
            post_engine_validation=_post_engine_validate,
            populate_context=_populate_context,
            populate_inputs=_populate_inputs,
        )

    async def submit_animate_extend(self, cmd: JobAnimateExtendCommand) -> Result[str]:
        """Submit one animate-extend follow-up from either a job id or video bytes."""
        resolved: _ResolvedVideoContext | None = None

        resolved_ctx, err = self._resolve_target_video(
            job_id=cmd.job_id,
            video_bytes=cmd.video_bytes,
        )
        if err:
            return cast(Result[str], err)
        if not resolved_ctx:
            return self._validation_error(MISSING_VIDEO_CONTEXT)
        resolved = resolved_ctx

        def _populate_context(job: Job) -> None:
            assert resolved is not None
            job.context.message_id = resolved.message_id
            job.context.message_hash = resolved.message_hash
            job.context.flags = resolved.flags
            job.context.index = resolved.index
            job.context.final_prompt = resolved.prompt
            job.context.action_custom_ids = dict(resolved.action_custom_ids)

        return await self._execute_job_flow(
            action=self._animate_extend_action_for_motion(cmd.motion),
            state=cmd.state,
            prompt=resolved.prompt,
            populate_context=_populate_context,
        )

    async def submit_blend(self, cmd: JobBlendCommand) -> Result[str]:
        """Submit a blend job."""

        def _pre_validate() -> Result[None] | None:
            if not (2 <= len(cmd.base64_array) <= 5):
                return error_result(INVALID_BLEND_COUNT)

            seen_hashes: set[str] = set()
            for i, b64 in enumerate(cmd.base64_array):
                data_url = parse_data_url(b64)
                if not data_url:
                    return error_result(
                        INVALID_BASE64, message=f"Invalid Base64 Data URL at index {i}"
                    )
                digest = hashlib.sha256(data_url.data).hexdigest()
                if digest in seen_hashes:
                    return error_result(DUPLICATE_IMAGES)
                seen_hashes.add(digest)

            return None

        def _populate_inputs(job: Job) -> None:
            job.inputs.base64_array = cmd.base64_array
            job.inputs.dimensions = cmd.dimensions

        return await self._execute_job_flow(
            action=JobAction.BLEND,
            state=cmd.state,
            prompt=None,
            pre_validation=_pre_validate,
            populate_inputs=_populate_inputs,
        )

    async def submit_custom_zoom(self, cmd: JobCustomZoomCommand) -> Result[str]:
        """Submit a custom zoom job."""
        resolved: _ResolvedImageContext | None = None

        def _pre_validate() -> Result[None] | None:
            nonlocal resolved
            zoom_text = (cmd.zoom_text or "").strip()
            m = re.search(r"--zoom\s+([0-9]*\.?[0-9]+)", zoom_text)
            if not m:
                return self._validation_error(INVALID_ZOOM_TEXT)

            resolved_ctx, err = self._resolve_image_context_for_action(
                job_id=cmd.job_id,
                base64=cmd.base64,
                action=JobAction.CUSTOM_ZOOM,
                index_fallback=cmd.index,
            )
            if err:
                return err
            if not resolved_ctx:
                return self._validation_error(MISSING_CONTEXT)

            resolved = resolved_ctx
            return None

        def _populate_context(job: Job) -> None:
            assert resolved is not None  # for type checkers
            job.context.message_id = resolved.message_id
            job.context.message_hash = resolved.message_hash
            job.context.flags = resolved.flags
            job.context.index = resolved.index
            job.context.zoom_text = cmd.zoom_text
            job.context.final_prompt = resolved.prompt_text
            job.context.tile_follow_up_mode = resolved.tile_follow_up_mode
            job.context.action_custom_ids = dict(resolved.action_custom_ids)
            job.context.implicit_tile_promotion_pending = resolved.implicit_tile_promotion_required
            job.context.implicit_tile_promotion_index = (
                resolved.index if resolved.implicit_tile_promotion_required else None
            )
            if resolved.source_job_id:
                job.context.original_job_id = resolved.source_job_id

        return await self._execute_job_flow(
            action=JobAction.CUSTOM_ZOOM,
            state=cmd.state,
            prompt=None,
            pre_validation=_pre_validate,
            populate_context=_populate_context,
        )

    async def submit_inpaint(self, cmd: JobInpaintCommand) -> Result[str]:
        """Submit an inpaint job."""
        resolved: _ResolvedImageContext | None = None
        webp_b64: str | None = None

        def _pre_validate() -> Result[None] | None:
            nonlocal resolved, webp_b64
            webp_b64 = encode_mask_to_webp_base64(cmd.mask)
            if not webp_b64:
                return self._validation_error(INVALID_MASK)

            resolved_ctx, err = self._resolve_image_context_for_action(
                job_id=cmd.job_id,
                base64=cmd.base64,
                action=JobAction.INPAINT,
                index_fallback=1,
            )
            if err:
                return err
            if not resolved_ctx:
                return self._validation_error(MISSING_CONTEXT)

            resolved = resolved_ctx
            return None

        def _populate_context(job: Job) -> None:
            assert resolved is not None  # for type checkers
            job.context.message_id = resolved.message_id
            job.context.message_hash = resolved.message_hash
            job.context.flags = resolved.flags
            job.context.index = resolved.index
            job.context.custom_id = cmd.custom_id
            job.context.final_prompt = resolved.prompt_text
            job.context.tile_follow_up_mode = resolved.tile_follow_up_mode
            job.context.action_custom_ids = dict(resolved.action_custom_ids)
            job.context.implicit_tile_promotion_pending = resolved.implicit_tile_promotion_required
            job.context.implicit_tile_promotion_index = (
                resolved.index if resolved.implicit_tile_promotion_required else None
            )
            if resolved.source_job_id:
                job.context.original_job_id = resolved.source_job_id

        def _populate_inputs(job: Job) -> None:
            job.inputs.mask_webp_base64 = webp_b64
            job.inputs.prompt = cmd.prompt
            job.inputs.full_prompt = cmd.full_prompt

        return await self._execute_job_flow(
            action=JobAction.INPAINT,
            state=cmd.state,
            prompt=None,
            pre_validation=_pre_validate,
            populate_context=_populate_context,
            populate_inputs=_populate_inputs,
        )

    async def submit_cancel(self, cmd: JobCancelCommand) -> Result[str]:
        """Submit a cancel command for a job."""

        job_store = self._ctx.job_store
        job = job_store.get(cmd.job_id)
        if not job:
            return error_result(CANCEL_NOT_FOUND)

        if job.status not in {JobStatus.SUBMITTED, JobStatus.IN_PROGRESS}:
            return error_result(CANCEL_NOT_RUNNING)

        cancel_ctx = _can_cancel(job)
        if not cancel_ctx.can_cancel:
            http_status = int(cancel_ctx.error_code or 400)
            if http_status == 400:
                http_status = 409
            return Result(
                code=int(cancel_ctx.error_code or 400),
                message=cancel_ctx.error_message or "Cancel not available",
                http_status=http_status,
            )

        instance = self._require_engine()
        if not instance:
            return error_result(NO_AVAILABLE_ACCOUNTS)

        nonce = str(get_current_timestamp_ms())

        set_job_context(job_id=job.id, action="cancel", status=job.status.value)
        try:
            self._logger.info("[cancel] requested -> job_id=%s", job.id)
            result = await instance.commands.cancel_job(
                message_id=cancel_ctx.message_id or "",
                job_id=cancel_ctx.job_id or "",
                message_flags=int(cancel_ctx.message_flags or 0),
                nonce=nonce,
            )

            if result != "Success":
                self._logger.warning("[cancel] failed -> job_id=%s reason=%s", job.id, result)
                if result:
                    return error_result(CANCEL_FAILED, message=result)
                return error_result(CANCEL_FAILED)

            job.context.cancelled = True
            JobStateMachine.apply(job, JobTransition.FAIL, "Cancelled by user")
            job_store.save(job)
            instance.notify_bus.publish_job(job)

            self._logger.info("[cancel] success -> job_id=%s", job.id)
            return Result(code=1, message="Cancel sent", value=job.id)
        finally:
            clear_job_context()

    @staticmethod
    def _animate_action_for_motion(motion: AnimateMotion) -> JobAction:
        """Map one public animate motion level to the submitted job action."""
        if motion is AnimateMotion.HIGH:
            return JobAction.ANIMATE_HIGH
        return JobAction.ANIMATE_LOW

    @staticmethod
    def _animate_extend_action_for_motion(motion: AnimateMotion) -> JobAction:
        """Map one public motion level to the animate-extend follow-up action."""
        if motion is AnimateMotion.HIGH:
            return JobAction.ANIMATE_EXTEND_HIGH
        return JobAction.ANIMATE_EXTEND_LOW


__all__ = ["JobSubmissionService"]
