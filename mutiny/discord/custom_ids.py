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

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CustomIdKind(str, Enum):
    UPSCALE = "upscale"
    VARIATION = "variation"
    VARIATION_LOW = "variation_low"
    VARIATION_HIGH = "variation_high"
    UPSCALE_SOLO = "upscale_solo"
    REROLL = "reroll"
    CANCEL = "cancel"
    OUTPAINT = "outpaint"
    PAN = "pan"
    ANIMATE = "animate"
    ANIMATE_EXTEND = "animate_extend"
    CUSTOM_ZOOM_BUTTON = "custom_zoom_button"
    CUSTOM_ZOOM_MODAL = "custom_zoom_modal"
    INPAINT = "inpaint"
    IFRAME = "iframe"


@dataclass(frozen=True)
class CustomIdParts:
    kind: CustomIdKind
    index: Optional[int] = None
    message_hash: Optional[str] = None
    job_id: Optional[str] = None
    scale: Optional[int] = None
    direction: Optional[str] = None
    level: Optional[str] = None
    mode: Optional[str] = None
    version: Optional[int] = None
    token: Optional[str] = None


_REGISTRY: dict[CustomIdKind, re.Pattern[str]] = {
    CustomIdKind.UPSCALE: re.compile(r"^MJ::JOB::upsample::(?P<index>\d+)::(?P<message_hash>.+)$"),
    CustomIdKind.VARIATION: re.compile(
        r"^MJ::JOB::variation::(?P<index>\d+)::(?P<message_hash>.+)$"
    ),
    CustomIdKind.VARIATION_LOW: re.compile(
        r"^MJ::JOB::low_variation::(?P<index>\d+)::(?P<message_hash>.+)::SOLO$"
    ),
    CustomIdKind.VARIATION_HIGH: re.compile(
        r"^MJ::JOB::high_variation::(?P<index>\d+)::(?P<message_hash>.+)::SOLO$"
    ),
    CustomIdKind.UPSCALE_SOLO: re.compile(
        r"^MJ::JOB::upsample_v(?P<version>\d+)_2x_(?P<mode>[^:]+)::"
        r"(?P<index>\d+)::(?P<message_hash>.+)::SOLO$"
    ),
    CustomIdKind.REROLL: re.compile(r"^MJ::JOB::reroll::0::(?P<message_hash>.+)::SOLO$"),
    CustomIdKind.CANCEL: re.compile(r"^MJ::CancelJob::ByJobid::(?P<job_id>.+)$"),
    CustomIdKind.OUTPAINT: re.compile(
        r"^MJ::Outpaint::(?P<scale>\d+)::(?P<index>\d+)::(?P<message_hash>.+)::SOLO$"
    ),
    CustomIdKind.PAN: re.compile(
        r"^MJ::JOB::pan_(?P<direction>left|right|up|down)::(?P<index>\d+)::(?P<message_hash>.+)::SOLO$"
    ),
    CustomIdKind.ANIMATE: re.compile(
        r"^MJ::JOB::animate_(?P<level>high|low)::(?P<index>\d+)::(?P<message_hash>.+)::SOLO$"
    ),
    CustomIdKind.ANIMATE_EXTEND: re.compile(
        r"^MJ::JOB::animate_(?P<level>high|low)_extend::(?P<index>\d+)::(?P<message_hash>.+)$"
    ),
    CustomIdKind.CUSTOM_ZOOM_BUTTON: re.compile(r"^MJ::CustomZoom::(?P<message_hash>.+)$"),
    CustomIdKind.CUSTOM_ZOOM_MODAL: re.compile(
        r"^MJ::OutpaintCustomZoomModal::(?P<message_hash>.+)$"
    ),
    CustomIdKind.INPAINT: re.compile(r"^MJ::Inpaint::(?P<index>\d+)::(?P<message_hash>.+)::SOLO$"),
    CustomIdKind.IFRAME: re.compile(r"^MJ::iframe::(?P<token>.+)$"),
}


def parse_custom_id(custom_id: str) -> Optional[CustomIdParts]:
    if not custom_id:
        return None
    for kind, pattern in _REGISTRY.items():
        match = pattern.match(custom_id)
        if not match:
            continue
        group = match.groupdict()
        return CustomIdParts(
            kind=kind,
            index=_parse_optional_int(group.get("index")),
            message_hash=group.get("message_hash"),
            job_id=group.get("job_id"),
            scale=_parse_optional_int(group.get("scale")),
            direction=group.get("direction"),
            level=group.get("level"),
            mode=group.get("mode"),
            version=_parse_optional_int(group.get("version")),
            token=group.get("token"),
        )
    return None


def validate_custom_id(custom_id: str) -> bool:
    return parse_custom_id(custom_id) is not None


def build_upscale_custom_id(index: int, message_hash: str) -> str:
    return f"MJ::JOB::upsample::{int(index)}::{message_hash}"


def build_variation_custom_id(index: int, message_hash: str) -> str:
    return f"MJ::JOB::variation::{int(index)}::{message_hash}"


def build_low_variation_custom_id(index: int, message_hash: str) -> str:
    return f"MJ::JOB::low_variation::{int(index)}::{message_hash}::SOLO"


def build_high_variation_custom_id(index: int, message_hash: str) -> str:
    return f"MJ::JOB::high_variation::{int(index)}::{message_hash}::SOLO"


def build_upscale_v7_custom_id(mode: str, index: int, message_hash: str) -> str:
    mode_norm = str(mode).strip().lower()
    if mode_norm not in {"subtle", "creative"}:
        # keep string but still construct; validation happens upstream
        mode_norm = mode_norm or "subtle"
    return f"MJ::JOB::upsample_v7_2x_{mode_norm}::{int(index)}::{message_hash}::SOLO"


def find_matching_solo_upscale_custom_id(
    custom_ids: set[str] | list[str] | tuple[str, ...],
    *,
    mode: str,
    index: int,
    message_hash: str,
) -> str | None:
    """Return the exact solo subtle/creative component id from one message surface.

    Midjourney varies the ``upsample_v*_2x_*`` family by model/version, so callers
    should prefer the observed button id on the message whenever available instead
    of synthesizing a guessed version.
    """

    mode_norm = str(mode).strip().lower()
    for custom_id in custom_ids:
        parsed = parse_custom_id(custom_id)
        if parsed is None or parsed.kind is not CustomIdKind.UPSCALE_SOLO:
            continue
        if parsed.mode != mode_norm:
            continue
        if parsed.index != int(index):
            continue
        if parsed.message_hash != message_hash:
            continue
        return custom_id
    return None


def build_reroll_custom_id(message_hash: str) -> str:
    return f"MJ::JOB::reroll::0::{message_hash}::SOLO"


def build_cancel_by_jobid(job_id: str) -> str:
    return f"MJ::CancelJob::ByJobid::{job_id}"


def build_outpaint_custom_id(scale: int, index: int, message_hash: str) -> str:
    # scale is observed as 50 (2x) or 75 (1.5x)
    return f"MJ::Outpaint::{int(scale)}::{int(index)}::{message_hash}::SOLO"


def build_pan_custom_id(direction: str, index: int, message_hash: str) -> str:
    dir_norm = str(direction).strip().lower()
    if dir_norm not in {"left", "right", "up", "down"}:
        dir_norm = "left"
    return f"MJ::JOB::pan_{dir_norm}::{int(index)}::{message_hash}::SOLO"


def build_animate_custom_id(level: str, index: int, message_hash: str) -> str:
    lvl = str(level).strip().lower()
    if lvl not in {"high", "low"}:
        lvl = "high"
    return f"MJ::JOB::animate_{lvl}::{int(index)}::{message_hash}::SOLO"


def build_animate_extend_custom_id(level: str, index: int, message_hash: str) -> str:
    lvl = str(level).strip().lower()
    if lvl not in {"high", "low"}:
        lvl = "high"
    return f"MJ::JOB::animate_{lvl}_extend::{int(index)}::{message_hash}"


def build_custom_zoom_button_custom_id(message_hash: str) -> str:
    return f"MJ::CustomZoom::{message_hash}"


def build_custom_zoom_modal_custom_id(message_hash: str) -> str:
    return f"MJ::OutpaintCustomZoomModal::{message_hash}"


def build_inpaint_custom_id(index: int, message_hash: str) -> str:
    return f"MJ::Inpaint::{int(index)}::{message_hash}::SOLO"


def _parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


__all__ = [
    "CustomIdKind",
    "CustomIdParts",
    "parse_custom_id",
    "validate_custom_id",
    "build_upscale_custom_id",
    "build_variation_custom_id",
    "build_low_variation_custom_id",
    "build_high_variation_custom_id",
    "build_upscale_v7_custom_id",
    "find_matching_solo_upscale_custom_id",
    "build_outpaint_custom_id",
    "build_pan_custom_id",
    "build_animate_custom_id",
    "build_animate_extend_custom_id",
    "build_reroll_custom_id",
    "build_cancel_by_jobid",
    "build_custom_zoom_button_custom_id",
    "build_custom_zoom_modal_custom_id",
    "build_inpaint_custom_id",
]
