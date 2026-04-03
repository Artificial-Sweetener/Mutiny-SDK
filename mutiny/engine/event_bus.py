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

import logging
from collections import defaultdict
from typing import DefaultDict, Iterable, Protocol, Type

from mutiny.domain.time import get_current_timestamp_ms
from mutiny.engine.events import ProviderMessageReceived, SystemError

logger = logging.getLogger(__name__)


class EventReactor(Protocol):
    def handle(self, event: object) -> bool | None:
        """Handle an event and optionally indicate if it was consumed."""


class JobEventBus:
    """Event bus for engine-level events."""

    def __init__(self) -> None:
        self._subs: DefaultDict[Type[object], list[EventReactor]] = defaultdict(list)

    def subscribe(self, event_type: Type[object], reactor: EventReactor) -> None:
        self._subs[event_type].append(reactor)

    def publish(self, event: object) -> None:
        reactors = list(self._subs.get(type(event), []))
        if isinstance(event, ProviderMessageReceived):
            self._publish_message_event(event, reactors)
            return
        for reactor in reactors:
            self._safe_handle(reactor, event)

    def _publish_message_event(
        self, event: ProviderMessageReceived, reactors: Iterable[EventReactor]
    ) -> None:
        for reactor in reactors:
            try:
                handled = reactor.handle(event)
            except Exception as exc:
                self._publish_system_error(
                    source=type(reactor).__name__,
                    error=exc,
                    context={"event_type": event.event_type},
                )
                logger.exception("Reactor failed handling provider message")
                continue
            if handled:
                break

    def _safe_handle(self, reactor: EventReactor, event: object) -> None:
        try:
            reactor.handle(event)
        except Exception as exc:
            self._publish_system_error(
                source=type(reactor).__name__,
                error=exc,
                context={"event_type": type(event).__name__},
            )
            logger.exception("Reactor failed handling event")

    def _publish_system_error(self, source: str, error: Exception, context: dict) -> None:
        err_event = SystemError(
            source=source,
            error=error,
            context=context,
            occurred_at_ms=get_current_timestamp_ms(),
        )
        for reactor in list(self._subs.get(SystemError, [])):
            try:
                reactor.handle(err_event)
            except Exception:
                logger.exception("SystemError reactor failed")


__all__ = ["JobEventBus", "EventReactor"]
