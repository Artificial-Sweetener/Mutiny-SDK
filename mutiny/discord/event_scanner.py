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

"""Event scanning helpers that extract Discord gateway metadata into cache."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from ..services.interaction_cache import InteractionCache
from .custom_ids import CustomIdKind, parse_custom_id
from .identity import DiscordIdentity


@dataclass
class EventScanError:
    """Represents a recoverable scanner failure for diagnostics."""

    message: str
    event_type: str | None
    exception: Exception | None = None


@dataclass
class EventScanResult:
    """Structured outcome of a gateway event scan."""

    modal_cached: bool = False
    iframe_token_cached: bool = False
    message_components_cached: bool = False
    errors: list[EventScanError] = field(default_factory=list)


def scan_gateway_event(
    data: dict[str, Any],
    interaction_cache: InteractionCache,
    identity: DiscordIdentity,
) -> EventScanResult:
    """Inspect a Discord DISPATCH payload and opportunistically cache metadata."""

    event_type = data.get("t")
    raw_event_data = data.get("d")
    event_data: dict[str, Any] = raw_event_data if isinstance(raw_event_data, dict) else {}
    result = EventScanResult()

    try:
        modal_cached, iframe_cached = _capture_modal_and_iframe(
            event_data, interaction_cache, identity
        )
        result.modal_cached = modal_cached
        result.iframe_token_cached = iframe_cached
    except Exception as exc:  # pragma: no cover - logged upstream but we want context
        result.errors.append(
            EventScanError(
                message="Failed to cache modal or iframe metadata",
                event_type=event_type,
                exception=exc,
            )
        )

    if event_type in {"MESSAGE_CREATE", "MESSAGE_UPDATE"}:
        try:
            if _capture_message_components(event_data, interaction_cache):
                result.message_components_cached = True
        except Exception as exc:  # pragma: no cover - logged upstream but we want context
            result.errors.append(
                EventScanError(
                    message="Failed to cache message components",
                    event_type=event_type,
                    exception=exc,
                )
            )

    return result


def _capture_modal_and_iframe(
    event_data: dict[str, Any], interaction_cache: InteractionCache, identity: DiscordIdentity
) -> tuple[bool, bool]:
    """Scan nested custom_id fields for zoom modal or iframe tokens and cache them."""

    found_modal = None
    found_modal_raw = None
    found_iframe = None
    for key, value in _deep_iter(event_data):
        if key != "custom_id" or not isinstance(value, str):
            continue
        parsed = parse_custom_id(value)
        if not parsed:
            continue
        if parsed.kind == CustomIdKind.CUSTOM_ZOOM_MODAL:
            found_modal = parsed
            found_modal_raw = value
            break
        if parsed.kind == CustomIdKind.IFRAME:
            found_iframe = parsed

    modal_cached = False
    iframe_cached = False

    if found_modal:
        modal_id = event_data.get("id") or (
            event_data.get("data", {}) if isinstance(event_data.get("data"), dict) else {}
        ).get("id")
        message_hash = found_modal.message_hash
        if message_hash:
            interaction_cache.set_custom_zoom_modal(
                message_hash,
                {"id": modal_id, "custom_id": found_modal_raw},
            )
            modal_cached = True

    if found_iframe and found_iframe.token:
        channel_id = None
        try:
            channel_id = event_data.get("channel_id")
        except Exception:
            channel_id = None
        channel_key = channel_id or getattr(identity, "channel_id", None) or "default"
        interaction_cache.set_inpaint_token(channel_key, found_iframe.token)
        iframe_cached = True

    return modal_cached, iframe_cached


def _capture_message_components(
    event_data: dict[str, Any], interaction_cache: InteractionCache
) -> bool:
    """Cache component custom_ids from a message event if present."""

    message_id = event_data.get("id")
    rows = event_data.get("components") or []
    custom_ids: list[str] = []
    for row in rows:
        for component in row.get("components") or []:
            custom_id = component.get("custom_id")
            if isinstance(custom_id, str):
                custom_ids.append(custom_id)

    if message_id and custom_ids:
        interaction_cache.set_message_components(str(message_id), set(custom_ids))
        return True
    return False


def _deep_iter(obj: Any) -> Iterator[tuple[Any, Any]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key, value
            yield from _deep_iter(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _deep_iter(item)


__all__ = [
    "EventScanError",
    "EventScanResult",
    "scan_gateway_event",
]
