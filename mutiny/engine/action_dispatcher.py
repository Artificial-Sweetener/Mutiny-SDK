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

"""Dispatches job actions to Midjourney/Discord provider executors.

This module owns the job-action registry and maps Mutiny domain actions to
provider calls. Behavior is frozen to match existing Midjourney interaction
contracts; changes must preserve payloads and state transitions.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict

from mutiny.discord.custom_ids import (
    CustomIdKind,
    build_inpaint_custom_id,
    find_matching_solo_upscale_custom_id,
    parse_custom_id,
)
from mutiny.engine.runtime.artifact_prep import prepare_image_input
from mutiny.interfaces.commands import GenerativeCommands
from mutiny.services.animate_prompt_builder import build_video_prompt
from mutiny.services.cache.artifact_cache import ArtifactCacheService
from mutiny.services.interaction_cache import InteractionCache
from mutiny.types import AnimateMotion, Job, JobAction

logger = logging.getLogger(__name__)


def _indexed_filename_factory(prefix: str, index: int) -> Callable[[str], str]:
    def _filename_factory(extension: str) -> str:
        return f"{prefix}_{index}{extension}"

    return _filename_factory


def _plain_filename_factory(prefix: str) -> Callable[[str], str]:
    def _filename_factory(extension: str) -> str:
        return f"{prefix}{extension}"

    return _filename_factory


@dataclass(frozen=True)
class ActionContext:
    """Bundle provider and cache dependencies used by one action executor."""

    commands: GenerativeCommands
    artifact_cache: ArtifactCacheService
    interaction_cache: InteractionCache
    channel_id: str


Executor = Callable[[ActionContext, Job, str], Awaitable[str | None]]

_REGISTRY: Dict[JobAction, Executor] = {}


def register(action: JobAction):
    def _wrap(fn: Executor) -> Executor:
        _REGISTRY[action] = fn
        return fn

    return _wrap


async def _execute_pending_tile_promotion(ctx: ActionContext, job: Job, nonce: str) -> str | None:
    """Dispatch the hidden `U#` hop required before some modern tile actions.

    The public job action remains the user-requested follow-up, but the first wire
    action for promotion-required tile flows is always the matching tile upscale.
    """

    err = _ensure_job_props(job, ["message_id", "message_hash", "implicit_tile_promotion_index"])
    if err:
        return err
    return await ctx.commands.upscale(
        job.context.message_id or "",
        int(job.context.implicit_tile_promotion_index or 0),
        job.context.message_hash or "",
        job.context.flags or 0,
        nonce,
    )


async def execute_action(ctx: ActionContext, job: Job, nonce: str) -> str | None:
    if job.context.implicit_tile_promotion_pending:
        return await _execute_pending_tile_promotion(ctx, job, nonce)
    exec_fn = _REGISTRY.get(job.action)
    if not exec_fn:
        logger.warning("No executor registered for action %s (job=%s)", job.action, job.id)
        return f"No executor registered for action {job.action}"
    return await exec_fn(ctx, job, nonce)


# --- Executors (preserve existing behavior) ---


async def _prepare_cdn_image_urls(
    ctx: ActionContext,
    job: Job,
    *,
    values: list[str],
    label_prefix: str,
    filename_prefix: str,
) -> list[str]:
    """Upload one or more data URLs and return the resolved CDN URLs."""
    resolved_urls: list[str] = []
    for index, value in enumerate(values):
        if job.fail_reason:
            break
        result = await prepare_image_input(
            ctx,
            job,
            value,
            index_label=f"{label_prefix} {index}",
            filename_factory=_indexed_filename_factory(filename_prefix, index),
            use_cache=True,
            fetch_cdn=True,
            cdn_required=True,
        )
        if result.error:
            logger.warning(
                "Imagine image preparation failed",
                extra={
                    "job_id": job.id,
                    "job_action": job.action,
                    "index": index,
                    "reason": result.error,
                    "cdn_required": True,
                    "cache_hit": result.cache_hit,
                },
            )
            break
        if result.cdn_url:
            resolved_urls.append(result.cdn_url)
    return resolved_urls


def _format_style_reference_tokens(job: Job, style_urls: list[str]) -> list[str]:
    """Format uploaded style-reference URLs with any matching multipliers."""
    multipliers = job.inputs.style_reference_multipliers or []
    tokens: list[str] = []
    for index, style_url in enumerate(style_urls):
        if index < len(multipliers):
            tokens.append(f"{style_url}::{multipliers[index]:g}")
        else:
            tokens.append(style_url)
    return tokens


def _build_imagine_prompt(
    job: Job,
    *,
    prompt_image_urls: list[str],
    style_reference_urls: list[str],
    character_reference_urls: list[str],
    omni_reference_url: str | None,
) -> str:
    """Compose the final imagine prompt in Midjourney's expected image order."""
    prompt_parts: list[str] = []

    if prompt_image_urls:
        prompt_parts.extend(prompt_image_urls)

    prompt_text = (job.prompt or "").strip()
    if prompt_text:
        prompt_parts.append(prompt_text)

    if style_reference_urls:
        prompt_parts.append(
            f"--sref {' '.join(_format_style_reference_tokens(job, style_reference_urls))}"
        )

    if character_reference_urls:
        prompt_parts.append(f"--cref {' '.join(character_reference_urls)}")

    if omni_reference_url:
        prompt_parts.append(f"--oref {omni_reference_url}")

    return " ".join(part for part in prompt_parts if part).strip()


@register(JobAction.IMAGINE)
async def _exec_imagine(ctx: ActionContext, job: Job, nonce: str) -> str | None:
    """Upload prompt images if provided and invoke provider imagine with combined prompt."""
    image_urls = await _prepare_cdn_image_urls(
        ctx,
        job,
        values=job.inputs.base64_array or [],
        label_prefix="index",
        filename_prefix=f"{job.id}_prompt",
    )
    style_reference_urls = await _prepare_cdn_image_urls(
        ctx,
        job,
        values=job.inputs.style_reference_images or [],
        label_prefix="style reference",
        filename_prefix=f"{job.id}_style",
    )
    character_reference_urls = await _prepare_cdn_image_urls(
        ctx,
        job,
        values=job.inputs.character_reference_images or [],
        label_prefix="character reference",
        filename_prefix=f"{job.id}_character",
    )
    omni_reference_urls = await _prepare_cdn_image_urls(
        ctx,
        job,
        values=[job.inputs.omni_reference_image] if job.inputs.omni_reference_image else [],
        label_prefix="omni reference",
        filename_prefix=f"{job.id}_omni",
    )

    if job.fail_reason:
        return None

    final_prompt = _build_imagine_prompt(
        job,
        prompt_image_urls=image_urls,
        style_reference_urls=style_reference_urls,
        character_reference_urls=character_reference_urls,
        omni_reference_url=omni_reference_urls[0] if omni_reference_urls else None,
    )
    job.context.final_prompt = final_prompt
    return await ctx.commands.imagine(final_prompt, nonce)


@register(JobAction.DESCRIBE)
async def _exec_describe(ctx: ActionContext, job: Job, nonce: str) -> str | None:
    """Describe an uploaded or cached image, falling back to upload when CDN fails."""
    initial = await prepare_image_input(
        ctx,
        job,
        job.inputs.base64 or "",
        index_label="",
        filename_factory=_plain_filename_factory(job.id),
        use_cache=True,
        fetch_cdn=True,
        cdn_required=False,
    )

    if initial.error:
        return None

    if initial.cache_hit and initial.cdn_url:
        desc = await ctx.commands.describe_by_url(initial.cdn_url, nonce)
        if desc == "Success":
            return desc
        fallback = await prepare_image_input(
            ctx,
            job,
            job.inputs.base64 or "",
            index_label="",
            filename_factory=_plain_filename_factory(job.id),
            use_cache=False,
            fetch_cdn=False,
            cdn_required=False,
        )
        if fallback.error:
            return None
        if not fallback.uploaded_name:
            return None
        return await ctx.commands.describe(fallback.uploaded_name, nonce)

    if initial.uploaded_name:
        return await ctx.commands.describe(initial.uploaded_name, nonce)

    # Should not occur, but guard to preserve behavior if CDN exists without upload
    if initial.cdn_url:
        desc = await ctx.commands.describe_by_url(initial.cdn_url, nonce)
        if desc == "Success":
            return desc
        fallback = await prepare_image_input(
            ctx,
            job,
            job.inputs.base64 or "",
            index_label="",
            filename_factory=_plain_filename_factory(job.id),
            use_cache=False,
            fetch_cdn=False,
            cdn_required=False,
        )
        if fallback.error or not fallback.uploaded_name:
            return None
        return await ctx.commands.describe(fallback.uploaded_name, nonce)

    return None


@register(JobAction.BLEND)
async def _exec_blend(ctx: ActionContext, job: Job, nonce: str) -> str | None:
    """Upload multiple images and invoke provider blend with supplied aspect ratio."""
    uploaded_filenames: list[str] = []
    for i, b64 in enumerate(job.inputs.base64_array or []):
        res = await prepare_image_input(
            ctx,
            job,
            b64,
            index_label=f"index {i}",
            filename_factory=_indexed_filename_factory(job.id, i),
            use_cache=False,
            fetch_cdn=False,
            cdn_required=False,
        )
        if res.error:
            break
        if res.uploaded_name:
            uploaded_filenames.append(res.uploaded_name)

    if job.fail_reason:
        return None
    return await ctx.commands.blend(uploaded_filenames, job.inputs.dimensions or "1:1", nonce)


# --- New executors (foundations) ---


def _job_attr(job: Job, key: str):
    """Return a job attribute from context/inputs/artifacts in priority order."""

    if hasattr(job.context, key):
        return getattr(job.context, key)
    if hasattr(job.inputs, key):
        return getattr(job.inputs, key)
    if hasattr(job.artifacts, key):
        return getattr(job.artifacts, key)
    return None


def _ensure_job_props(job: Job, required: list[str]) -> str | None:
    """Validate required job properties are present and non-empty."""

    missing = [k for k in required if _job_attr(job, k) in (None, "")]
    if missing:
        return f"Missing required properties: {', '.join(missing)}"
    return None


async def _poll_message_component(
    ctx: ActionContext,
    *,
    message_id: str,
    target_label: str,
    resolve_custom_id: Callable[[set[str]], str | None],
    job: Job,
    attempts: int = 20,
    delay_seconds: float = 0.5,
) -> str | None:
    """Poll cached message components for one exact component id."""

    try:
        for _ in range(attempts):
            components = ctx.interaction_cache.get_message_components(str(message_id))
            resolved = resolve_custom_id(components)
            if resolved:
                return resolved
            await asyncio.sleep(delay_seconds)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "%s component polling failed",
            target_label,
            exc_info=exc,
            extra={
                "job_id": job.id,
                "message_id": message_id,
            },
        )
    return None


def _register_button_executor(action: JobAction, method_name: str, *, requires_index: bool) -> None:
    """Register a button-style executor that forwards stored message context."""

    async def _exec_button(
        ctx: ActionContext,
        job: Job,
        nonce: str,
        _method: str = method_name,
        _requires_index: bool = requires_index,
    ) -> str | None:
        """Invoke the mapped provider button handler after validating message context fields."""
        required = ["message_id", "message_hash"]
        if _requires_index:
            required.append("index")
        err = _ensure_job_props(job, required)
        if err:
            return err
        provider_fn = getattr(ctx.commands, _method)
        if _requires_index:
            return await provider_fn(
                job.context.message_id,
                job.context.index,
                job.context.message_hash,
                job.context.flags or 0,
                nonce,
            )
        return await provider_fn(
            job.context.message_id,
            job.context.message_hash,
            job.context.flags or 0,
            nonce,
        )

    register(action)(_exec_button)


async def _exec_solo_upscale(
    ctx: ActionContext,
    job: Job,
    nonce: str,
    *,
    mode: str,
    fallback_method: str,
) -> str | None:
    """Dispatch subtle/creative solo upscale using observed components first."""

    err = _ensure_job_props(job, ["message_id", "message_hash", "index"])
    if err:
        return err

    message_id = str(job.context.message_id or "")
    message_hash = str(job.context.message_hash or "")
    index = int(job.context.index or 0)
    persisted_custom_id = (job.context.action_custom_ids or {}).get(f"upscale_{mode}")
    if persisted_custom_id:
        return await ctx.commands.send_button_interaction(
            message_id,
            persisted_custom_id,
            job.context.flags or 0,
            nonce,
        )
    target_custom_id = await _poll_message_component(
        ctx,
        message_id=message_id,
        target_label="Solo upscale",
        resolve_custom_id=lambda components: find_matching_solo_upscale_custom_id(
            components,
            mode=mode,
            index=index,
            message_hash=message_hash,
        ),
        job=job,
        attempts=6,
        delay_seconds=0.25,
    )
    if target_custom_id:
        return await ctx.commands.send_button_interaction(
            message_id,
            target_custom_id,
            job.context.flags or 0,
            nonce,
        )

    logger.info(
        "Solo upscale component cache miss; falling back to synthesized custom_id",
        extra={
            "job_id": job.id,
            "message_id": message_id,
            "message_hash": message_hash,
            "index": index,
            "mode": mode,
        },
    )
    provider_fn = getattr(ctx.commands, fallback_method)
    return await provider_fn(
        message_id,
        index,
        message_hash,
        job.context.flags or 0,
        nonce,
    )


@register(JobAction.UPSCALE_V7_2X_SUBTLE)
async def _exec_upscale_subtle(ctx: ActionContext, job: Job, nonce: str) -> str | None:
    """Dispatch subtle upscale using the exact solo-message component when present."""

    return await _exec_solo_upscale(
        ctx,
        job,
        nonce,
        mode="subtle",
        fallback_method="upscale_v7_subtle",
    )


@register(JobAction.UPSCALE_V7_2X_CREATIVE)
async def _exec_upscale_creative(ctx: ActionContext, job: Job, nonce: str) -> str | None:
    """Dispatch creative upscale using the exact solo-message component when present."""

    return await _exec_solo_upscale(
        ctx,
        job,
        nonce,
        mode="creative",
        fallback_method="upscale_v7_creative",
    )


_BUTTON_WITH_INDEX = {
    JobAction.UPSCALE: "upscale",
    JobAction.VARIATION: "variation",
    JobAction.VARY_SUBTLE: "vary_subtle",
    JobAction.VARY_STRONG: "vary_strong",
    JobAction.ZOOM_OUT_2X: "outpaint_50",
    JobAction.ZOOM_OUT_1_5X: "outpaint_75",
    JobAction.PAN_LEFT: "pan_left",
    JobAction.PAN_RIGHT: "pan_right",
    JobAction.PAN_UP: "pan_up",
    JobAction.PAN_DOWN: "pan_down",
    JobAction.ANIMATE_EXTEND_HIGH: "animate_extend_high",
    JobAction.ANIMATE_EXTEND_LOW: "animate_extend_low",
}

_BUTTON_NO_INDEX = {
    JobAction.REROLL: "reroll",
}

for _action, _method in _BUTTON_WITH_INDEX.items():
    _register_button_executor(_action, _method, requires_index=True)

for _action, _method in _BUTTON_NO_INDEX.items():
    _register_button_executor(_action, _method, requires_index=False)


def _is_prompt_video_job(job: Job) -> bool:
    """Return whether an animate job should use prompt-based ``--video`` submission."""
    return bool(job.inputs.base64)


def _animate_motion_value(action: JobAction) -> AnimateMotion:
    """Translate one animate action into the Midjourney prompt flag value."""
    if action is JobAction.ANIMATE_HIGH:
        return AnimateMotion.HIGH
    return AnimateMotion.LOW


async def _prepare_prompt_video_frame(
    ctx: ActionContext,
    job: Job,
    *,
    data_url: str,
    index_label: str,
    filename_prefix: str,
) -> str | None:
    """Upload one prompt-video frame and return the resolved CDN URL."""
    result = await prepare_image_input(
        ctx,
        job,
        data_url,
        index_label=index_label,
        filename_factory=_plain_filename_factory(filename_prefix),
        use_cache=True,
        fetch_cdn=True,
        cdn_required=True,
    )
    return None if result.error else result.cdn_url


@register(JobAction.ANIMATE_HIGH)
@register(JobAction.ANIMATE_LOW)
async def _exec_animate(ctx: ActionContext, job: Job, nonce: str) -> str | None:
    """Dispatch animate through either the follow-up button or prompt-video path."""
    if not _is_prompt_video_job(job):
        err = _ensure_job_props(job, ["message_id", "message_hash", "index"])
        if err:
            return err
        provider_fn = (
            ctx.commands.animate_high
            if job.action is JobAction.ANIMATE_HIGH
            else ctx.commands.animate_low
        )
        message_id = str(job.context.message_id)
        index_value = job.context.index
        assert index_value is not None
        index = int(index_value)
        message_hash = str(job.context.message_hash)
        return await provider_fn(
            message_id,
            index,
            message_hash,
            job.context.flags or 0,
            nonce,
        )

    start_frame_url = await _prepare_prompt_video_frame(
        ctx,
        job,
        data_url=job.inputs.base64 or "",
        index_label="start frame",
        filename_prefix=f"{job.id}_video_start",
    )
    if job.fail_reason or not start_frame_url:
        return None

    end_frame_url = None
    if job.inputs.end_frame_base64:
        end_frame_url = await _prepare_prompt_video_frame(
            ctx,
            job,
            data_url=job.inputs.end_frame_base64,
            index_label="end frame",
            filename_prefix=f"{job.id}_video_end",
        )
        if job.fail_reason or not end_frame_url:
            return None

    final_prompt = build_video_prompt(
        start_frame_url=start_frame_url,
        prompt_text=job.inputs.prompt or "",
        motion=_animate_motion_value(job.action),
        end_frame_url=end_frame_url,
        batch_size=job.inputs.batch_size,
    )
    job.context.final_prompt = final_prompt
    return await ctx.commands.imagine(final_prompt, nonce)


@register(JobAction.CUSTOM_ZOOM)
async def _exec_custom_zoom(ctx: ActionContext, job: Job, nonce: str) -> str | None:
    """Send a custom zoom interaction using prior message context and user-entered text."""
    # Requires prior job context and zoom text for modal
    err = _ensure_job_props(job, ["message_id", "message_hash", "zoom_text"])
    if err:
        return err
    message_id = str(job.context.message_id)
    message_hash = str(job.context.message_hash)
    return await ctx.commands.custom_zoom(
        message_id,
        message_hash,
        job.context.flags or 0,
        nonce,
        job.context.zoom_text or "",
    )


@register(JobAction.INPAINT)
async def _exec_inpaint(ctx: ActionContext, job: Job, nonce: str) -> str | None:
    """Perform inpaint: validate context, poll iframe token, then submit mask/prompt."""
    err = _ensure_job_props(
        job,
        [
            "message_id",
            "message_hash",
            "index",
            "mask_webp_base64",
        ],
    )
    if err:
        return err
    message_id = str(job.context.message_id)
    index_value = job.context.index
    assert index_value is not None
    index = int(index_value)
    message_hash = str(job.context.message_hash)
    target_cid = build_inpaint_custom_id(index, message_hash)
    await _poll_message_component(
        ctx,
        message_id=message_id,
        target_label="Inpaint",
        resolve_custom_id=lambda components: target_cid if target_cid in components else None,
        job=job,
    )
    res = await ctx.commands.inpaint_button(
        message_id,
        index,
        message_hash,
        job.context.flags or 0,
        nonce,
    )
    if res != "Success":
        return res
    try:
        await asyncio.sleep(0.75)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "Inpaint post-button delay interrupted", exc_info=exc, extra={"job_id": job.id}
        )
    iframe_token = job.context.custom_id
    parsed_custom_id = parse_custom_id(iframe_token or "")
    if parsed_custom_id and parsed_custom_id.kind == CustomIdKind.IFRAME:
        iframe_token = parsed_custom_id.token
    if not iframe_token:
        key = ctx.channel_id or "default"
        try:
            # poll up to ~10s for an iframe token observed on gateway
            for _ in range(20):
                tok = ctx.interaction_cache.get_inpaint_token(key)
                if tok:
                    iframe_token = tok
                    break
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Inpaint token polling failed",
                exc_info=exc,
                extra={"job_id": job.id, "channel_id": ctx.channel_id},
            )
            iframe_token = None
    if not iframe_token:
        return "Could not derive iframe token for inpaint"
    # Step 2: submit job to app endpoint
    return await ctx.commands.inpaint_submit_job(
        iframe_token=iframe_token,
        mask_webp_base64=job.inputs.mask_webp_base64 or "",
        prompt=job.inputs.prompt,
    )


__all__ = ["ActionContext", "execute_action", "register"]
